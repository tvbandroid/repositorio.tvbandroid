# -*- coding: utf-8 -*-
# EKHorus - The web server: static files and the json api.
#
# It answers on the whole local network with no password, which is what the rest of the
# EspaKodi addons do too and what makes it usable: typing an address is the point. The one
# door that is bolted is the browser one, see _host_valido().

import os
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from lib.utils import logger, runtime_path

from . import api

ESTATICOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
MEDIOS = os.path.join(runtime_path, 'resources', 'media')

# The only bodies this serves are a handful of fields. Anything larger is refused without
# reading it, and its connection closed.
CUERPO_MAXIMO = 65536

_TIPOS = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.json': 'application/json; charset=utf-8',
}


def _anfitrion(cabecera):
    """Address part of the Host header, with no port.

    An IPv6 address comes in brackets, with the port outside them."""
    cabecera = (cabecera or '').strip()

    if cabecera.startswith('['):
        return cabecera[1:].split(']', 1)[0]

    return cabecera.split(':')[0]


def _host_valido(cabecera):
    """True if the request arrives addressed to a bare address and not to a name.

    This is the only real defence the server needs. A page the user is browsing cannot
    read our answers (the api sends no permissive CORS), but it CAN fire requests at
    192.168.x.x blindly, and with a name that resolves to the local network it could even
    read them back. Demanding the Host be an ip closes that second door, and no legitimate
    use loses anything: nobody reaches this by a domain name."""
    host = _anfitrion(cabecera)

    if host in ('localhost', '::1'):
        return True

    partes = host.split('.')

    return len(partes) == 4 and all(p.isdigit() and len(p) <= 3 for p in partes)


def _peticion_propia(cabeceras):
    """True unless the browser says the request was fired by another site.

    A page from elsewhere cannot read our answers, but it can fire blind requests at the
    television: play a channel, stop it, shut this server down. Browsers mark those with
    Sec-Fetch-Site, and every cross-origin POST carries an Origin that is not ours. The
    addon's own calls (urllib) and the page talking to its own origin send neither, or ours.
    Only the host of the Origin is compared: an old browser that writes the port its own way
    must not be turned away, and an attacker on this very address is not the threat."""
    sitio = (cabeceras.get('Sec-Fetch-Site') or '').lower()
    if sitio in ('cross-site', 'same-site'):
        return False

    origen = cabeceras.get('Origin')
    if not origen:
        return True

    return _anfitrion(urllib.parse.urlsplit(origen).netloc) == _anfitrion(cabeceras.get('Host'))


class Manejador(BaseHTTPRequestHandler):

    # The default one answers 1.0, and with it every response needs to close the
    # connection. The page asks for a handful of things at once when it opens.
    protocol_version = 'HTTP/1.1'

    # A phone that locks its screen leaves its kept-alive connection open for ever. Idle this
    # long, the connection is dropped; the page polls every five seconds, so a live one never
    # is. It also bounds every read and write inside a request.
    timeout = 30

    # How often a connection waiting for its next request looks up to see whether the server
    # is stopping, see _llega_peticion().
    VISTAZO_S = 0.5

    def log_message(self, formato, *args):
        # The base class writes to stderr, and in Kodi that is the log: a page with
        # thirty logos would put thirty lines in it per opening.
        pass

    def do_GET(self):
        self._atender('GET')

    def do_POST(self):
        self._atender('POST')

    # --- plumbing -------------------------------------------------------------------

    def handle(self):
        # The base class waits for each request blocked in readline(). The wait happens in
        # _llega_peticion() instead, where stopping the server can end it.
        self.close_connection = True
        while self._llega_peticion():
            self.handle_one_request()
            if self.close_connection:
                return

    def _llega_peticion(self):
        """True once a request starts arriving on this connection, False to hang up.

        Blocked in readline(), a connection the browser keeps alive held its thread until the
        client spoke again or the timeout ran out, also after the server had stopped, and Kodi
        waits for every thread of a script on exit. With the phone page open that was up to
        thirty seconds and "script didn't stop in 5 seconds", measured on Android. Browsers
        also open connections they never use. So the wait looks up every VISTAZO_S seconds to
        see whether the server is stopping. Cutting the sockets instead is not enough: on
        Windows shutdown() does not wake a thread blocked reading."""
        limite = time.monotonic() + self.timeout

        while not self.server.cerrando.is_set():
            espera = min(self.VISTAZO_S, limite - time.monotonic())
            if espera <= 0:
                return False

            try:
                # Two requests sent in one go leave the second in the reader's buffer, where
                # the socket does not show it. It is looked at without blocking, because a
                # timeout inside the reader leaves it unusable for good.
                self.connection.setblocking(False)
                if self.rfile.peek(1):
                    return True

                self.connection.settimeout(espera)
                # An empty answer is the client hanging up.
                return bool(self.connection.recv(1, socket.MSG_PEEK))
            except socket.timeout:
                pass
            except OSError:
                return False
            finally:
                self.connection.settimeout(self.timeout)

        return False

    def _responder(self, codigo, tipo, cuerpo, cache=None):
        if isinstance(cuerpo, str):
            cuerpo = cuerpo.encode('utf-8')

        try:
            self.send_response(codigo)
            self.send_header('Content-Type', tipo)
            self.send_header('Content-Length', str(len(cuerpo)))
            if cache:
                self.send_header('Cache-Control', cache)
            self.end_headers()
            self.wfile.write(cuerpo)
        except OSError:
            # The phone locking its screen mid-answer is not a fault worth logging. The
            # headers are in here too because end_headers() is the first thing that reaches
            # the socket: a hang-up by then went up to handle_error(), which writes the
            # traceback to Kodi's log, and left /api/apagar without shutting the server down.
            self.close_connection = True

    def _cuerpo_peticion(self):
        """The body of the request, read WHOLE whatever we then do with it.

        Leaving it in the socket is what desynchronises a kept-alive connection: the next
        request would start reading in the middle of this body. Hence it is read here, at
        the top, and not inside the branch that happens to want it."""
        try:
            largo = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return b''

        if largo <= 0:
            return b''

        # A body is only ever a handful of fields. Something bigger is not ours, and
        # draining it to keep the connection tidy would be doing the sender a favour.
        if largo > CUERPO_MAXIMO:
            self.close_connection = True
            return b''

        return self.rfile.read(largo)

    def _atender(self, metodo):
        cuerpo_peticion = self._cuerpo_peticion() if metodo == 'POST' else b''

        if not _host_valido(self.headers.get('Host')):
            self._responder(403, 'text/plain; charset=utf-8', 'Host no permitido')
            return

        ruta, _, consulta = self.path.partition('?')
        parametros = dict(urllib.parse.parse_qsl(consulta))

        # Everything that changes something is a POST, and no other site may fire one. Asking
        # for the catalogue again is the exception: it is a GET, because the page asks for it
        # as it loads, and it empties the cache and downloads ten pages from the engine, so an
        # <img> on any page could keep the engine busy. It goes through the same door.
        forzado = ruta == '/api/catalogo' and parametros.get('forzar') == '1'
        if (metodo == 'POST' or forzado) and not _peticion_propia(self.headers):
            self._responder(403, 'text/plain; charset=utf-8', 'Peticion de otro sitio')
            return

        self._encaminar(metodo, ruta, parametros, cuerpo_peticion)

    def _encaminar(self, metodo, ruta, parametros, cuerpo_peticion):
        """Answers a request that has already passed the checks in _atender().

        Kept apart so that a server with other doors, the one the phone types into
        (receiver.py), inherits those checks instead of carrying a copy of them."""
        if ruta == '/api/apagar':
            # Only a POST: an <img> on any page could otherwise switch the server off.
            if metodo != 'POST':
                self.send_response(405)
                self.send_header('Allow', 'POST')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return

            # It cannot be answered from api.py: shutting down needs the server object, and
            # it happens on a thread of its own because shutdown() waits for serve_forever,
            # which is what is running this very request. Hence the answer first.
            self._responder(200, 'application/json; charset=utf-8', '{"ok":true}')
            self.server.apagar()
            return

        if ruta.startswith('/api/'):
            try:
                codigo, tipo, cuerpo = api.atender(metodo, ruta, parametros,
                                                   cuerpo_peticion,
                                                   _anfitrion(self.headers.get('Host')))
            except Exception as e:
                logger(f'webapp: {ruta}: {e}', 'error')
                codigo, tipo, cuerpo = 500, 'application/json; charset=utf-8', '{"error":1}'

            self._responder(codigo, tipo, cuerpo, cache='no-store')
            return

        if ruta.startswith('/media/'):
            # The flags and the category icons the addon already ships. Serving them saves
            # drawing them again for the web and keeps both interfaces looking alike.
            self._fichero(MEDIOS, ruta[len('/media/'):], cache='public, max-age=86400')
            return

        # Whatever is not a file is the page itself: the interface navigates on its own
        # and reloading it on any address has to come back with the app, not with a 404.
        self._fichero(ESTATICOS, ruta.lstrip('/') or 'index.html',
                      respaldo='index.html', cache='no-cache')

    def _fichero(self, raiz, relativa, respaldo=None, cache=None):
        completa = os.path.join(raiz, relativa.replace('/', os.sep))

        if not os.path.realpath(completa).startswith(os.path.realpath(raiz) + os.sep) \
                or not os.path.isfile(completa):
            if not respaldo:
                self._responder(404, 'text/plain; charset=utf-8', 'No esta')
                return
            completa = os.path.join(raiz, respaldo)

        try:
            with open(completa, 'rb') as f:
                datos = f.read()
        except OSError as e:
            logger(f'webapp: no se pudo leer {completa}: {e}', 'error')
            self._responder(404, 'text/plain; charset=utf-8', 'No esta')
            return

        extension = os.path.splitext(completa)[1].lower()
        self._responder(200, _TIPOS.get(extension, 'application/octet-stream'), datos,
                        cache=cache)


class Servidor(ThreadingHTTPServer):
    # Without this a phone that walks off with a connection open keeps Kodi from
    # closing the server.
    daemon_threads = True

    # On Windows SO_REUSEADDR lets a second socket bind a port somebody is already
    # listening on, and which of the two gets the connections is anyone's guess. Everywhere
    # else it only forgives TIME_WAIT, which is what lets the server come back after a
    # hard stop, so it is worth keeping there.
    allow_reuse_address = os.name != 'nt'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set once the server is down, for whoever waits on it: parar() and the abort watch.
        self.parado = threading.Event()
        # Set as soon as it is told to stop, for the connections waiting for a request.
        self.cerrando = threading.Event()

    def apagar(self):
        """shutdown() and then server_close(), on a thread of their own. Returns the thread.

        shutdown() waits for serve_forever, so it can never run on the thread serving a
        request; and the socket is closed only once nobody polls it, which is what frees
        the port at once instead of when the interpreter dies. The connections still open
        go by themselves as soon as they see 'cerrando'."""
        self.cerrando.set()

        def cerrar():
            self.shutdown()
            self.server_close()
            self.parado.set()

        hilo = threading.Thread(target=cerrar, daemon=True, name='EKHorusWebCierre')
        hilo.start()
        return hilo


def crear_servidor(host, puerto):
    return Servidor((host, puerto), Manejador)
