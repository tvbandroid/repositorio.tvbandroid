# -*- coding: utf-8 -*-
"""First-run wizard.

With Kodi dialogs and no window of its own, on purpose. It is the first thing someone who
has just installed the addon sees, on a device we know nothing about, and a window of our
own that failed to open would be the worst possible first impression. Dialogs always come
up.

The only thing EKHorus needs to know is where the engine listens. Everything else follows.
"""
import threading

import xbmc
import xbmcgui

from lib import netscan
from lib.utils import (ENGINE_ACESERVE, ENGINE_ACESTREAM, HEADING, android_engine_launch,
                       apartar_musica, buscar_motor_en_otro_puerto, echar_pestillo, engine_name,
                       engine_port, forget_engine, get_setting, logger, quitar_pestillo,
                       set_setting, system_platform)
from acestream.server import Server

PESTILLO = 'ekhorus.setup_wizard'
MARCA = 'asistente_hecho'

COMPROBAR_TIMEOUT = 4


def _marcar():
    """Called as soon as the user answers the first question, even if they cancel later.

    Were it left to the end, whoever cancels would meet it again on every opening of the
    menu, which is the fastest way to get somebody to uninstall an addon."""
    set_setting(MARCA, True)


def _hay_motor(host, puerto):
    """(version, engine) of whatever answers at that address, or (None, None)."""
    servidor = Server(host=host, port=puerto, timeout=COMPROBAR_TIMEOUT)

    if not servidor.ping(timeout=2):
        return None, None

    version = servidor.version
    if not version:
        return None, None

    sirve = servidor.playlist_status()
    if sirve is None:
        return version, None

    return version, (ENGINE_ACESERVE if sirve else ENGINE_ACESTREAM)


def _elegir_motor_android():
    """Asks which app acts as the engine and saves it. False if the user cancels."""
    opciones = ['Ace Stream (la app oficial)', 'AceServe (servidor sin publicidad)']
    elegido = xbmcgui.Dialog().select('¿Qué motor tienes instalado?', opciones)

    if elegido < 0:
        return False

    set_setting('ace_engine', ENGINE_ACESTREAM if elegido == 0 else ENGINE_ACESERVE)
    forget_engine()

    return True


def _buscar_en_la_red():
    """Sweeps the subnet and sets the IP the user picks. False if none or cancelled."""
    dialogo = xbmcgui.DialogProgress()
    dialogo.create(HEADING, 'Buscando motores en la red…')
    cancelar = threading.Event()

    def avanzar(hechas, total):
        if dialogo.iscanceled():
            cancelar.set()
            return
        dialogo.update(int(hechas * 100 / total) if total else 0,
                       f'Mirando {total} direcciones de tu red…')

    try:
        encontrados = netscan.barrer(al_avanzar=avanzar, cancelar=cancelar)
    finally:
        dialogo.close()

    # Whoever cancels wants out, not to be told that nothing was found. The same flag is set
    # when Kodi is closing.
    if cancelar.is_set():
        return False

    if encontrados is None:
        xbmcgui.Dialog().ok(HEADING, 'Este aparato no está en una red doméstica.\n\n'
                                     'Escribe la dirección del motor a mano en los '
                                     'ajustes.')
        return False

    if not encontrados:
        xbmcgui.Dialog().ok(HEADING, 'No se ha encontrado ningún motor.\n\n'
                                     'Comprueba que está arrancado y que el puerto 6878 '
                                     'está abierto. Hay wifis que aíslan los aparatos.')
        return False

    etiquetas = [f'{ip}   v{version}' + (f'   {motor}' if motor else '')
                 for ip, version, motor in encontrados]
    elegido = xbmcgui.Dialog().select('Elige el motor que vas a usar', etiquetas)

    if elegido < 0:
        return False

    ip = encontrados[elegido][0]
    set_setting('ip_addr', ip)
    # The module's Server was built with the previous IP and is no longer good for
    # anything that comes after this within the same invocation.
    forget_engine()
    logger(f'setup_wizard: motor elegido en {ip}')

    return True


def _comprobar_y_rematar():
    """Looks for an engine where it should be and, if not, offers each platform's exit."""
    host = get_setting('ip_addr', '127.0.0.1')
    # The port of the engine just chosen: AceServe may keep one of its own.
    puerto = engine_port()
    version, motor = _hay_motor(host, puerto)

    # Nobody on the configured port: the official app may be answering on another one (see
    # buscar_motor_en_otro_puerto), and then that is the port to report and to keep.
    if not version and buscar_motor_en_otro_puerto():
        puerto = engine_port()
        version, motor = _hay_motor(host, puerto)

    if version:
        nombre = engine_name(motor) if motor else 'Un motor'
        xbmcgui.Dialog().ok(HEADING,
                            f'{nombre} v{version} responde en {host}:{puerto}.\n\n'
                            'Ya puedes reproducir. La lista está en [B]Canales[/B].')
        return

    if system_platform == 'android':
        if xbmcgui.Dialog().yesno(HEADING,
                                  f'No responde nadie en {host}:{puerto}.\n\n'
                                  'En Android el motor es una aplicación aparte y tiene '
                                  'que estar arrancada.',
                                  yeslabel='Abrir el motor', nolabel='Ahora no'):
            apartar_musica()
            xbmc.executebuiltin(android_engine_launch())
        return

    xbmcgui.Dialog().ok(HEADING,
                        f'No responde nadie en {host}:{puerto}.\n\n'
                        'EKHorus lo arranca al reproducir algo o con '
                        '[B]Arrancar motor Acestream[/B].')


def mostrar(forzado=False):
    """Runs the wizard. Returns nothing; it leaves the settings in place and goes."""
    if not echar_pestillo(PESTILLO):
        return

    try:
        donde = xbmcgui.Dialog().yesno(
            HEADING,
            # Short on purpose: the Kodi dialog only shows four lines of about fifty
            # characters, and whatever is left over scrolls by itself. This is the first
            # thing someone who just installed the addon sees; it cannot arrive half read.
            'EKHorus necesita un motor AceStream para reproducir.\n\n¿Dónde lo tienes?',
            yeslabel='En este aparato', nolabel='En otro de la red')

        # Marked now, not at the end: whoever cancels halfway must not meet it again on
        # every opening of the menu.
        if not forzado:
            _marcar()

        if donde:
            set_setting('ip_addr', '127.0.0.1')
            forget_engine()
        elif not _buscar_en_la_red():
            return

        if system_platform == 'android' and not _elegir_motor_android():
            return

        _comprobar_y_rematar()

    except Exception as e:
        # A wizard that blows up must not leave the menu unopened.
        logger(f'setup_wizard: {e}', 'error')

    finally:
        quitar_pestillo(PESTILLO)
