# -*- coding: utf-8 -*-
import xbmc, xbmcgui
from .telegram_bridge import bridge, BridgeError

def _close_tdlib():
    """Libera explícitamente el cliente TDLib de este proceso de Kodi.

    Cada ejecución de default.py puede vivir en un proceso Python distinto;
    TDLib no permite que dos clientes usen simultáneamente el mismo td.binlog.
    """
    try:
        c=getattr(bridge.m, "client", None)
        if c is not None:
            c.close()
    except Exception:
        pass

def configure(show_errors=True):
    try:
        # Si quedó un servicio de reproducción activo, libéralo antes de
        # tocar el mismo td.binlog desde la pantalla de autenticación.
        try:
            from . import telegram_service
            telegram_service.stop_playback()
        except Exception:
            pass

        # La biblioteca nativa se instala únicamente al pulsar Conectar
        # Telegram. Entrar al addon nunca debe descargar ni cargar TDLib.
        if not bridge.ensure_native():
            msg=bridge.error() or "No se pudo instalar/cargar TDLib para este dispositivo."
            if show_errors:
                xbmcgui.Dialog().ok("DARKVIO · Telegram", msg)
            return False

        state=bridge.auth_state()
        # Después de desconectar TDLib puede quedar en Closed. Un cliente
        # cerrado no debe reutilizarse: se crea uno nuevo antes de mostrar
        # el diálogo de teléfono. Esto corrige el botón Conectar que a veces
        # quedaba aparentemente inoperativo después de Desconectar.
        if state in ("closed", "closing", "logging_out"):
            xbmc.log("[DARKVIO][TELEGRAM] Cliente TDLib cerrado; creando uno nuevo", xbmc.LOGINFO)
            bridge.reset()
            state=bridge.auth_state()
    except Exception as e:
        if show_errors:
            xbmcgui.Dialog().ok("DARKVIO · Telegram", str(e))
        _close_tdlib()
        return False

    # Si el usuario pulsa Conectar teniendo una sesión válida, no tocarla.
    if state == "ready":
        xbmcgui.Dialog().notification("DARKVIO · Telegram", "Ya estás conectado", xbmcgui.NOTIFICATION_INFO, 3000)
        _close_tdlib()
        return True

    ok=False
    try:
        while state not in ("ready", "error"):
            if state in ("wait_phone", "phone"):
                v=xbmcgui.Dialog().input("Telegram · número de teléfono", "+34 ", xbmcgui.INPUT_ALPHANUM)
                if not v:
                    return False
                phone=v.strip().replace(" ", "").replace("-", "")
                if phone.startswith("0034"):
                    phone="+"+phone[2:]
                elif phone.startswith("34") and not phone.startswith("+34") and len(phone)==11:
                    phone="+"+phone
                elif phone.isdigit() and len(phone)==9:
                    phone="+34"+phone
                elif phone.startswith("+34"):
                    pass
                elif not phone.startswith("+"):
                    phone="+34"+phone
                xbmc.log("[DARKVIO][TELEGRAM] Enviando número: +34/oculto", xbmc.LOGINFO)
                try:
                    bridge.submit_phone(phone)
                except Exception as e:
                    xbmcgui.Dialog().ok("Telegram", str(e))

            elif state in ("wait_code", "code"):
                v=xbmcgui.Dialog().input("Telegram · código recibido", type=xbmcgui.INPUT_NUMERIC)
                if not v:
                    return False
                try:
                    bridge.submit_code(v.strip())
                except Exception as e:
                    xbmcgui.Dialog().ok("Telegram", str(e))

            elif state in ("wait_password", "password"):
                v=xbmcgui.Dialog().input("Telegram · Verificación en dos pasos", type=xbmcgui.INPUT_ALPHANUM, option=xbmcgui.ALPHANUM_HIDE_INPUT)
                if not v:
                    return False
                try:
                    bridge.submit_password(v)
                except Exception as e:
                    xbmcgui.Dialog().ok("Telegram", str(e))

            elif state in ("initializing", "wait_qr", "wait_encryption_key"):
                xbmc.sleep(400)
            elif state in ("closed", "closing", "logging_out"):
                bridge.reset()
                state=bridge.auth_state()
                continue
            else:
                xbmc.sleep(250)

            try:
                state=bridge.auth_state()
            except Exception as e:
                if show_errors:
                    xbmcgui.Dialog().ok("DARKVIO · Telegram", str(e))
                return False

        if state == "ready":
            ok=True
            try:
                from . import sources
                sources.clear_cache()
            except Exception:
                pass
            xbmcgui.Dialog().notification("DARKVIO · Telegram", "Cuenta conectada", xbmcgui.NOTIFICATION_INFO, 3000)
            return True
        return False
    finally:
        # Fundamental: el proceso de Kodi que acaba de autenticar no puede
        # quedarse con td.binlog bloqueado cuando termina la acción Settings.
        _close_tdlib()

def ensure_login():
    try:
        if bridge.auth_state()=="ready": return True
    except Exception:
        pass
    return configure()

def has_session():
    try: return bridge.auth_state()=="ready"
    except Exception: return False

def change_account():
    try:
        if not bridge.available():
            xbmcgui.Dialog().ok('DARKVIO · Telegram','No se encontró el motor Telegram de DARKVIO.')
            return False
        if not xbmcgui.Dialog().yesno('DARKVIO · Telegram','¿Desconectar la cuenta actual y cambiar de usuario?','La sesión guardada de DARKVIO se eliminará de este dispositivo.'):
            return False
        bridge.logout()
        xbmcgui.Dialog().notification('DARKVIO · Telegram','Cuenta desconectada',xbmcgui.NOTIFICATION_INFO,2500)
        return configure()
    except Exception as e:
        xbmcgui.Dialog().ok('DARKVIO · Telegram',str(e))
        return False

def disconnect():
    try:
        try:
            from . import telegram_service
            telegram_service.stop_playback()
        except Exception:
            pass
        if not bridge.available(): return False
        # Confirmación simple: Sí desconecta, No cancela y sale sin tocar la sesión.
        if not xbmcgui.Dialog().yesno('DARKVIO · Telegram','¿Quieres desconectar la cuenta de Telegram?'):
            return False
        try:
            from . import sources
            sources.clear_cache()
        except Exception: pass
        bridge.logout()
        try:
            from . import sources
            sources.clear_cache()
        except Exception: pass
        xbmcgui.Dialog().notification('DARKVIO · Telegram','Cuenta desconectada',xbmcgui.NOTIFICATION_INFO,2500)
        return True
    except Exception as e:
        xbmcgui.Dialog().ok('DARKVIO · Telegram',str(e))
        return False
