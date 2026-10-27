# -*- coding: utf-8 -*-
"""Servicio persistente de reproducción Telegram para DARKVIO.

El plugin de vídeo de Kodi puede ser terminado por CPythonInvoker unos segundos
 después de entregar la reproducción. Este proceso de servicio es independiente
y mantiene TDLib + el servidor HTTP durante toda la reproducción.
"""
import json, threading, urllib.parse, os, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import xbmc
import xbmcvfs
import xbmcaddon

CONTROL_HOST = "127.0.0.1"
CONTROL_PORTS = (38980,)


def log(msg, level=xbmc.LOGINFO):
    xbmc.log("[DARKVIO][SERVICE] " + str(msg), level)


class ControlHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, code, body, content_type="text/plain; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except Exception:
            pass

    def do_GET(self):
        parsed=urllib.parse.urlparse(self.path)
        query=urllib.parse.parse_qs(parsed.query)
        owner=getattr(self.server, "owner", None)
        if parsed.path == "/ping":
            self._send(200, "DARKVIO-TELEGRAM-SERVICE")
            return
        if not owner:
            self._send(503, "service not ready")
            return
        if parsed.path == "/start":
            try:
                def one(k, default=""):
                    return (query.get(k) or [default])[0]
                url=owner.start_stream(
                    int(one("file_id", "0")),
                    one("name", "video"),
                    int(one("size", "0") or 0),
                    one("pid", ""),
                    int(one("chat_id", "0") or 0),
                    int(one("message_id", "0") or 0),
                )
                self._send(200, json.dumps({"ok":True,"url":url}), "application/json; charset=utf-8")
            except Exception as e:
                log("Error /start: %s" % e, xbmc.LOGERROR)
                self._send(500, json.dumps({"ok":False,"error":str(e)}), "application/json; charset=utf-8")
            return
        if parsed.path == "/stop":
            try:
                owner.stop_stream()
            except Exception:
                pass
            self._send(200, "OK")
            return
        self._send(404, "not found")


class TelegramService:
    def __init__(self):
        self.monitor=xbmc.Monitor()
        self.control=None
        self.control_thread=None
        self._lock=threading.RLock()
        self._http=None
        self._telegram_playing=False

    def start_stream(self, file_id, name, size, pid, chat_id, message_id):
        from resources.lib.telegram_http import server
        with self._lock:
            # IMPORTANTE: no desmontamos TDLib/HTTP cada vez que se abre otra
            # película. En Kodi 21 esa secuencia repetida de shutdown() +
            # cierre de TDLib puede dejar la GUI esperando y terminar en la
            # rueda azul. server.url() incrementa la generación y hace que el
            # watcher anterior quede invalidado, pero reutiliza el servidor y
            # la sesión TDLib ya abiertos. La liberación completa se hace
            # únicamente cuando Kodi deja de reproducir Telegram.
            self._http=server
            url = server.url(file_id, name, size, pid, chat_id, message_id)
            log('HTTP playback listo en %s' % url)
            return url

    def stop_stream(self):
        with self._lock:
            try:
                from resources.lib.telegram_http import server
                server.stop()
            except Exception as e:
                log("stop_stream: %s" % e, xbmc.LOGWARNING)
            self._http=None
        self._telegram_playing=False

    def _cleanup_temp_fallback(self):
        """Clean Telegram playback media after playback has ended.

        TDLib can cache media under both tdlib_files/temp and tdlib_files/videos.
        This fallback runs only when the persistent service detects that the
        Telegram player is no longer active.
        """
        try:
            profile = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("profile"))
            session = os.path.join(profile, "telegram_session")
            root = os.path.join(session, "tdlib_files")
            media_dirs = [os.path.join(root, "temp"), os.path.join(root, "videos")]
        except Exception:
            return 0
        removed = 0
        import shutil
        for media_dir in media_dirs:
            try:
                os.makedirs(media_dir, exist_ok=True)
            except Exception:
                pass
            for _ in range(8):
                try:
                    names = os.listdir(media_dir)
                except Exception:
                    names = []
                if not names:
                    break
                for name in names:
                    path = os.path.join(media_dir, name)
                    try:
                        if os.path.isdir(path) and not os.path.islink(path):
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                        removed += 1
                    except Exception:
                        pass
                time.sleep(0.35)
        if removed:
            log("Limpieza independiente: %d elementos de tdlib_files/temp y tdlib_files/videos" % removed, xbmc.LOGINFO)
        return removed

    def _is_telegram_url(self, path):
        try:
            return bool(path) and ("/telegram/" in str(path) and "127.0.0.1:" in str(path))
        except Exception:
            return False

    def run(self):
        for port in CONTROL_PORTS:
            try:
                self.control=ThreadingHTTPServer((CONTROL_HOST,port),ControlHandler)
                self.control.owner=self
                break
            except OSError:
                self.control=None
        if not self.control:
            log("No se pudo abrir el control local 127.0.0.1:38980-38989", xbmc.LOGERROR)
            return
        self.control_thread=threading.Thread(target=self.control.serve_forever,name="DARKVIO-TelegramControl",daemon=True)
        self.control_thread.start()
        log("Servicio persistente iniciado en 127.0.0.1:%d" % int(self.control.server_address[1]))
        # Clean stale Telegram media once when the persistent service starts.
        self._cleanup_temp_fallback()
        player=xbmc.Player()
        while not self.monitor.abortRequested():
            try:
                playing = bool(player.isPlaying())
                path = player.getPlayingFile() if playing else ""
                is_telegram = self._is_telegram_url(path)
                if is_telegram:
                    self._telegram_playing=True
                elif self._telegram_playing and not playing:
                    self._telegram_playing=False
                    self.stop_stream()
                    self._cleanup_temp_fallback()
            except Exception as e:
                log("monitor reproduccion: %s" % e, xbmc.LOGDEBUG)
            if self.monitor.waitForAbort(1):
                break
        try:
            self.stop_stream()
        except Exception:
            pass
        try:
            self.control.shutdown()
            self.control.server_close()
        except Exception:
            pass
        log("Servicio persistente detenido")


if __name__ == "__main__":
    TelegramService().run()
