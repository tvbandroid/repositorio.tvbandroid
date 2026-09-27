# -*- coding: utf-8 -*-
# EKHorus - What the page asks the addon for.
#
# Every function here runs in a server thread, never in Kodi's interface thread, so
# nothing in this file may open a dialog. Talking to Kodi goes through executebuiltin,
# which is exactly how the addon's own windows already ask for playback.

import json
import re
import time

import xbmc

from lib import catalog
from lib.utils import (ADDON_VERSION, HOSTS_LOCALES, Item, detect_engine, engine_name,
                       engine_port, get_setting, logger, system_platform)
from acestream.server import DEFAULT_TIMEOUT, Server

from . import bootstrap

JSON = 'application/json; charset=utf-8'
TEXTO = 'text/plain; charset=utf-8'

# The page asks for the status every few seconds, and with a dead engine the default ten
# seconds would leave it spinning for ever. Only that poll takes it; see _motor().
TIMEOUT_ESTADO = 4

# Seconds the engine's answer is reused for. See _ficha_motor(). A dead engine is asked
# again sooner, because whoever has just switched it on is watching the dot.
VISTO_TTL = 20
VISTO_TTL_MUERTO = 10
_VISTO = dict()

# Longest wait for a download that another invocation of the addon is already doing.
# Ten pages against a slow engine are around ten seconds; this leaves margin.
ESPERA_DESCARGA_S = 25

# An infohash is forty hex digits and nothing else. This is checked because the page is
# open to the whole local network: whatever arrives here goes into an engine url that the
# browser is handed back, and into the plugin url that plays on the television.
_RE_INFOHASH = re.compile(r'[0-9a-f]{40}\Z')


def _motor(timeout=DEFAULT_TIMEOUT):
    """A fresh client against the configured engine.

    It is built per request and not taken from lib.utils: that one is a singleton frozen
    at import time with the address of that moment, and the settings can be changed while
    the server is up.

    It waits what the rest of the addon waits. Shortening it is for the status poll alone:
    downloading the catalogue against a slow engine takes longer than that, and with four
    seconds the page said there was no engine while the television was playing through it."""
    return Server(host=get_setting('ip_addr', '127.0.0.1'), port=engine_port(),
                  timeout=timeout)


def _base_publica(servidor, anfitrion=''):
    """The engine's address as seen from the device reading the page.

    With the engine on this machine the setting says 127.0.0.1, and that address on the
    phone is the phone, so it has to be swapped for one that device can reach.

    The one preferred is the address the request itself came addressed to: whoever is
    reading the page got here through it, so if the engine shares this machine they can
    reach it there too. That is right on any network, and it does not depend on
    xbmc.getIPAddress(), which answers in Kodi's own thread and not necessarily in
    this one. An engine on another machine is left exactly as configured."""
    host = servidor.host

    if host in HOSTS_LOCALES:
        host = anfitrion or bootstrap.ip_anotada() or bootstrap.ip_lan() or host

    return f'http://{host}:{servidor.port}'


def enlaces(servidor, infohash, anfitrion=''):
    """The three ways of watching one channel, as absolute addresses.

    HLS is the one a browser plays: measured against the engine, it answers the manifest
    as application/vnd.apple.mpegurl and rewrites the urls inside it from the Host header,
    so it works from another device with nothing installed. The raw one comes out as
    application/octet-stream, which a browser downloads instead of playing, and it is the
    one for VLC."""
    base = _base_publica(servidor, anfitrion)

    return {
        'hls': f'{base}/ace/manifest.m3u8?infohash={infohash}',
        'directo': f'{base}/ace/getstream?infohash={infohash}',
        'acestream': f'acestream://{infohash}',
    }


def _nombre_motor(servidor):
    """AceStream or AceServe, or an empty string when it cannot be told."""
    try:
        detectado = detect_engine(servidor)
    except Exception as e:
        logger(f'webapp: detect_engine: {e}', 'error')
        return ''

    return engine_name(detectado) if detectado else ''


# --- endpoints ------------------------------------------------------------------------

def _ping():
    return 200, TEXTO, f'ekhorus {ADDON_VERSION}'


def _ficha_motor(servidor):
    """Engine and catalogue, remembered for a few seconds.

    The page asks for the status every few seconds because of the bar that says what the
    television is playing, and that part is free. This one is not: it costs a request to
    the engine, measured at over six seconds against a remote one, plus rereading a
    catalogue of 1700 channels off disk. None of it changes from one poll to the next."""
    ahora = time.time()
    guardado = _VISTO.get(servidor.base)

    if guardado:
        ttl = VISTO_TTL if guardado[1]['motor']['vivo'] else VISTO_TTL_MUERTO
        if ahora - guardado[0] < ttl:
            return guardado[1]

    version = servidor.version
    guardados = catalog.leer(servidor.base, ttl_horas=0) or list()

    ficha = {
        'motor': {
            'vivo': bool(version),
            'version': version or '',
            'nombre': _nombre_motor(servidor) if version else '',
            'direccion': f'{servidor.host}:{servidor.port}',
        },
        'catalogo': {'total': len(catalog.visibles(guardados))},
    }
    _VISTO[servidor.base] = (ahora, ficha)

    return ficha


def _estado():
    ficha = dict(_ficha_motor(_motor(TIMEOUT_ESTADO)))
    ficha['kodi'] = {
        'reproduciendo': xbmc.getCondVisibility('Player.HasVideo'),
        'titulo': xbmc.getInfoLabel('Player.Title') or '',
        # On Android the channel goes out to the engine's own application, so Kodi never
        # reports a picture and the page must not sit waiting for one that will not come.
        # Gated by platform exactly like the branch in default.py that uses it: the setting
        # defaults to true and on a desktop it means nothing.
        'externo': (system_platform == 'android'
                    and bool(get_setting('reproductor_externo'))),
    }

    return 200, JSON, json.dumps(ficha)


def _canales(servidor, forzar):
    """The catalogue, waiting for somebody else's download if one is under way.

    Two devices opening the page at the same moment would otherwise leave one of them with
    an empty list and a message that is not true, because the catalogue IS on its way, just
    fetched by the other one. The latch lets only one download happen; this is the wait for
    it. If it is us who came back empty the latch is already ours to release, so the loop
    does not even start and a dead engine is still reported at once."""
    canales = catalog.asegurar(servidor, forzar=forzar)

    if canales:
        return canales

    limite = time.time() + ESPERA_DESCARGA_S

    while catalog.descargando() and time.time() < limite:
        time.sleep(1)
        canales = catalog.leer(servidor.base)
        if canales:
            return canales

    return list()


def _catalogo(parametros, anfitrion):
    servidor = _motor()
    forzar = parametros.get('forzar') == '1'

    if forzar:
        # Whoever asked for it wants to see the new count now, not in twenty seconds.
        _VISTO.clear()

    canales = catalog.ordenar(catalog.visibles(_canales(servidor, forzar)))

    return 200, JSON, json.dumps({
        'total': len(canales),
        'canales': canales,
        'etiquetas': catalog.tablas(),
        'sin_dato': catalog.SIN_DATO,
        'motor': _base_publica(servidor, anfitrion),
    }, ensure_ascii=False, separators=(',', ':'))


def _enlaces(parametros, anfitrion):
    infohash = (parametros.get('infohash') or '').strip().lower()

    if not _RE_INFOHASH.match(infohash):
        return 400, JSON, '{"error":"falta infohash"}'

    return 200, JSON, json.dumps(enlaces(_motor(), infohash, anfitrion))


def _tele(cuerpo):
    """Sends the channel to the Kodi that is serving this page.

    It goes through the plugin and not straight to the player so that the channel takes
    the same route as one pressed on the television: the external player setting, the
    content_id resolution, the history and the OSD."""
    datos = _leer_json(cuerpo)
    infohash = str(datos.get('infohash') or '').strip().lower()

    if not _RE_INFOHASH.match(infohash):
        return 400, JSON, '{"error":"falta infohash"}'

    item = Item(action='play', infohash=infohash, motor=1, origen='web',
                label=str(datos.get('nombre') or 'EKHorus'),
                icon=str(datos.get('logo') or ''))
    xbmc.executebuiltin(f'RunPlugin(plugin://script.module.horus/?{item.tourl()})')

    return 200, JSON, '{"ok":true}'


def _parar():
    xbmc.executebuiltin('PlayerControl(Stop)')
    return 200, JSON, '{"ok":true}'


def _lista_m3u(anfitrion):
    """The whole catalogue as an m3u pointing at the engine.

    This is what turns the feature into more than a page. The same list opens in VLC, in a
    television's own player or in Kodi's IPTV Simple, on any device of the house."""
    servidor = _motor()
    base = _base_publica(servidor, anfitrion)
    lineas = ['#EXTM3U']

    for canal in catalog.ordenar(catalog.visibles(catalog.asegurar(servidor))):
        categorias = canal.get('categorias') or []
        grupo = catalog.etiqueta('categorias', categorias[0]) if categorias else 'EKHorus'
        lineas.append(f'#EXTINF:-1 tvg-logo="{canal.get("logo") or ""}" '
                      f'group-title="{grupo}",{canal.get("nombre") or ""}')
        lineas.append(f'{base}/ace/manifest.m3u8?infohash={canal["infohash"]}')

    return 200, 'audio/x-mpegurl; charset=utf-8', '\n'.join(lineas) + '\n'


def _leer_json(cuerpo):
    try:
        datos = json.loads(cuerpo.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return dict()

    return datos if isinstance(datos, dict) else dict()


def atender(metodo, ruta, parametros, cuerpo, anfitrion=''):
    """(code, content type, body) for an /api/ route.

    'anfitrion' is the address this request came addressed to, which is what the engine
    urls are built on. See _base_publica()."""
    if ruta == '/api/ping':
        return _ping()

    if ruta == '/api/estado':
        return _estado()

    if ruta == '/api/catalogo':
        return _catalogo(parametros, anfitrion)

    if ruta == '/api/enlaces':
        return _enlaces(parametros, anfitrion)

    if ruta == '/api/lista.m3u':
        return _lista_m3u(anfitrion)

    if metodo == 'POST' and ruta == '/api/tele':
        return _tele(cuerpo)

    if metodo == 'POST' and ruta == '/api/parar':
        return _parar()

    return 404, JSON, '{"error":"no existe"}'
