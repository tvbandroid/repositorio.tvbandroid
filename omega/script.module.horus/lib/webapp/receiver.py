# -*- coding: utf-8 -*-
# EKHorus - A short-lived server that takes one text typed on the phone.
#
# Reproducir identificador and Buscar enlaces raise it only while the screen with its QR is
# open. It is not the phone page's server: that one stays up until Kodi closes, on purpose, and
# whoever only wanted to paste an identifier would be left with a server open on the network.

import html
import json
import os
import re
import threading
import unicodedata

from lib.utils import logger

from .bootstrap import ip_lan
from .server import CUERPO_MAXIMO, ESTATICOS, MEDIOS, Manejador, Servidor

# Clear of the phone page's range (8099 and the seven above it) and of LoioLink's (8090-8100),
# either of which may be running at the same time.
PUERTO = 8120
PUERTOS = 8

PAGINA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'escribir.html')

_HUECO = re.compile(r'\{\{(\w+)\}\}')

# Cc: control characters. Cf: invisible formatting, such as the BOM, the zero-width space or the
# direction marks some apps copy along. Cs: a lone surrogate, which Kodi cannot turn into UTF-8.
_INVISIBLES = ('Cc', 'Cf', 'Cs')

_JSON = 'application/json; charset=utf-8'


class NoArranca(Exception):
    """The server could not start. 'motivo' says why: 'red', 'puertos' or 'pagina'."""

    def __init__(self, motivo):
        super().__init__(motivo)
        self.motivo = motivo


def limpiar(texto):
    """The text on one line, with single spaces and nothing invisible.

    A paste brings what no keyboard types: line breaks, Unicode spaces and invisible characters.
    A single one of those ahead of 'magnet:' is enough for the link not to be recognised."""
    visible = ''.join(c for c in texto
                      if c.isspace() or unicodedata.category(c) not in _INVISIBLES)
    return ' '.join(visible.split())


class ManejadorTexto(Manejador):
    """The Host and cross-site checks come from Manejador; only the doors are different."""

    def _encaminar(self, metodo, ruta, parametros, cuerpo_peticion):
        if metodo == 'POST' and ruta == '/texto':
            self._recibir(cuerpo_peticion)

        elif metodo == 'GET' and ruta == '/':
            # The heading depends on the row that opened the screen, so no copy is kept.
            self._responder(200, 'text/html; charset=utf-8', self.server.pagina, cache='no-store')

        elif ruta == '/estilo.css':
            self._fichero(ESTATICOS, 'estilo.css', cache='no-cache')

        elif ruta.startswith('/media/'):
            self._fichero(MEDIOS, ruta[len('/media/'):], cache='public, max-age=86400')

        else:
            # /api/ping too, since answering it would make bootstrap take this for the phone page.
            self._responder(404, 'text/plain; charset=utf-8', 'No esta')

    def _recibir(self, cuerpo_peticion):
        # A body over the cap arrives empty, since _cuerpo_peticion() does not read it, and
        # answering "write something" to whoever pasted a whole page would be wrong.
        try:
            largo = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            largo = 0
        if largo > CUERPO_MAXIMO:
            self._responder(413, _JSON, '{"error":"largo"}')
            return

        try:
            texto = json.loads(cuerpo_peticion.decode('utf-8')).get('texto')
        except (ValueError, AttributeError, RecursionError):
            # RecursionError is a body of nothing but nested brackets.
            texto = None

        texto = limpiar(texto) if isinstance(texto, str) else ''
        if not texto:
            self._responder(400, _JSON, '{"error":"vacio"}')
            return

        # Each connection has its own thread, so two sends can arrive at once, and one can
        # arrive while the television is closing. The television takes this same lock to read
        # the text once it has stopped the server, so a send is either in that text or refused
        # here, and the phone is never told "sent" for a text nobody is going to read.
        with self.server.cerrojo:
            if self.server.cerrando.is_set():
                codigo, cuerpo = 410, '{"error":"cerrado"}'
            elif self.server.texto is not None:
                codigo, cuerpo = 409, '{"error":"ya"}'
            else:
                self.server.texto = texto
                codigo, cuerpo = 200, '{"ok":true}'

        if codigo != 200:
            self._responder(codigo, _JSON, cuerpo)
            return

        try:
            self._responder(codigo, _JSON, cuerpo)
        except OSError as e:
            logger(f'receiver: el movil colgo antes de la respuesta, el texto vale igual: {e}')
        finally:
            # Set only once answered, because the television stops the server as soon as it sees
            # this and stopping first could cut the answer off. And set whatever happened to the
            # answer, or the screen would stay open with the text already taken.
            self.server.recibido.set()


class Receptor(Servidor):

    def __init__(self, direccion, pagina):
        super().__init__(direccion, ManejadorTexto)
        self.pagina = pagina
        self.texto = None
        self.recibido = threading.Event()
        self.cerrojo = threading.Lock()


def arrancar(encabezado, pista):
    """Starts the server and returns (server, address). Raises NoArranca if it cannot.

    The serving thread is already started when this returns. apagar() waits for serve_forever
    to finish, so on a server whose thread never started that wait would never end and the
    port would never be let go."""
    ip = ip_lan()
    if not ip:
        logger('receiver: este aparato no tiene direccion en la red local', 'error')
        raise NoArranca('red')

    try:
        with open(PAGINA, encoding='utf-8') as fichero:
            plantilla = fichero.read()
    except OSError as e:
        logger(f'receiver: no se puede leer {PAGINA}: {e}', 'error')
        raise NoArranca('pagina') from e

    valores = {'ENCABEZADO': encabezado, 'PISTA': pista}
    pagina = _HUECO.sub(lambda m: html.escape(valores[m.group(1)]), plantilla).encode('utf-8')

    for puerto in range(PUERTO, PUERTO + PUERTOS):
        try:
            receptor = Receptor(('0.0.0.0', puerto), pagina)
        except OSError:
            continue

        threading.Thread(target=receptor.serve_forever, daemon=True, name='EKHorusTexto').start()
        url = f'http://{ip}:{puerto}/'
        logger(f'receiver: esperando texto en {url}')
        return receptor, url

    logger(f'receiver: ningun puerto libre entre {PUERTO} y {PUERTO + PUERTOS - 1}', 'error')
    raise NoArranca('puertos')
