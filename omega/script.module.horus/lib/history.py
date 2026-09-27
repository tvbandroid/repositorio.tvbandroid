# -*- coding: utf-8 -*-
# EKHorus - History and My favourites: what has been opened and what the user keeps.
"""The two lists of links that belong to the user.

The history fills itself: every link asked to play goes to the top, whatever door it came
through. My favourites holds only what the user adds. They are separate files on purpose,
so that clearing the history, or pushing it past its cap, never takes a favourite with it.
"""
import collections
import os
import re
import threading
import time
import urllib.parse as urllib_parse

from lib.utils import Item, data_path, dump_json_file, load_json_file, logger

HISTORIAL_MAX = 300

# Another addon can send a name, a description or a logo of any size, and the history is read
# and written on every playback.
TITULO_MAX = 300
PLOT_MAX = 1000
ICONO_MAX = 2000
# Longer than the request line Apache and nginx take by default, so no server would answer it.
ENLACE_MAX = 8192

FICHERO_HISTORIAL = 'historial.json'
FICHERO_FAVORITOS = 'favoritos.json'

# The door each link came through, as the rows name it. Short, because a row gives it
# 400 px shared with the date.
ORIGENES = {
    'canales': 'Canales',
    'buscar': 'Buscar enlaces',
    'manual': 'Identificador',
    'externa': 'Otro addon',
    'web': 'Ver en el móvil',
    'favoritos': 'Mis favoritos',
    # 'tv' comes from a channel of Kodi's TV section, whether it played through the addon or
    # the service noted it; 'fuera' is what the service notes from anywhere else, and the two
    # 'streamninja' are what it notes of StreamNinja with no name (SIN_NOMBRE).
    'tv': 'Sección TV',
    'fuera': 'Fuera de EKHorus',
    'streamninja': 'Fuera de EKHorus',
    'streamninja_torrent': 'Fuera de EKHorus',
}

# The name painted for what StreamNinja played with none, where it only said 'AceStream'. It is
# never saved, so that a real one can still come, from the engine when the row is opened here.
SIN_NOMBRE = {
    'streamninja': 'Canal de StreamNinja',
    'streamninja_torrent': 'Torrent de StreamNinja',
}

# In the order acestreams() gives them precedence, so that an addon sending more than one
# gets recorded under the one that really plays.
TIPOS = ('infohash', 'url', 'id')

_RE_HASH = re.compile(r'[0-9a-f]{40}\Z')
_RE_BTIH = re.compile(r'btih:([0-9a-z]+)', re.I)
_RE_XT = re.compile(r'[?&]xt=(urn:btih:[0-9a-z]+)', re.I)
_RE_DN = re.compile(r'[?&]dn=([^&]*)', re.I)


def _magnet_corto(magnet):
    """The magnet with its hash and its name and nothing else.

    Playback hands the engine the bare hash, so the trackers are never used. A magnet can carry
    dozens of them, which are kilobytes read and written on every playback and a wall of text in
    the panel. And the same hash is one row, whatever trackers it came with."""
    xt = _RE_XT.search(magnet)
    if xt is None:
        return magnet

    dn = _RE_DN.search(magnet)
    return f'magnet:?xt={xt.group(1)}' + (f'&dn={dn.group(1)}' if dn else '')


def normalizar(crudo):
    """The entry in its current shape, or None if it carries no link that can play.

    Before 1.9.0 the history saved 'title' and 'icon' next to an infohash. Those files are
    read as they are, because updating must not cost anybody their list."""
    if not isinstance(crudo, dict):
        return None

    entrada = None
    for tipo in TIPOS:
        valor = str(crudo.get(tipo) or '').strip()
        # The engine only takes forty hex digits. Anything else would be a row that never
        # plays, so it is not kept.
        if tipo != 'url':
            valor = valor.lower()
            if not _RE_HASH.match(valor):
                continue
        else:
            if valor.lower().startswith('magnet:'):
                valor = _magnet_corto(valor)
            if len(valor) > ENLACE_MAX:
                continue
        if valor:
            entrada = {tipo: valor}
            break

    if entrada is None:
        return None

    try:
        fecha = max(0, int(crudo.get('fecha') or 0))
    except (TypeError, ValueError, OverflowError):
        fecha = 0

    nombre = str(crudo.get('titulo') or crudo.get('title') or '').strip()
    icono = str(crudo.get('icono') or crudo.get('icon') or '')

    entrada.update(titulo=nombre[:TITULO_MAX],
                   # An address that long is no address, and cutting it would not make one.
                   icono=icono if len(icono) <= ICONO_MAX else '',
                   plot=str(crudo.get('plot') or '')[:PLOT_MAX],
                   origen=str(crudo.get('origen') or ''),
                   motor=bool(crudo.get('motor')),
                   fecha=fecha)

    original = str(crudo.get('original') or '').strip()[:TITULO_MAX]
    if original:
        entrada['original'] = original

    return entrada


def enlace(entrada):
    """(kind, value) of the link an entry carries, or ('', '') if it carries none."""
    for tipo in TIPOS:
        if entrada.get(tipo):
            return tipo, entrada[tipo]

    return '', ''


def clave(entrada):
    """What tells two entries apart: the kind of link and the link itself."""
    tipo, valor = enlace(entrada)

    if not tipo:
        return ''

    return f'{tipo}:{valor if tipo == "url" else valor.lower()}'


def titulo(entrada):
    """The name to paint, or something recognisable for a link that came with none.

    A pasted identifier brings no name, and a list where every such row read the same would
    be no use. What StreamNinja played with none says where it came from instead, until the
    engine names it the first time it is opened here (poner_nombre)."""
    if entrada.get('titulo'):
        return entrada['titulo']

    if entrada.get('origen') in SIN_NOMBRE:
        return SIN_NOMBRE[entrada['origen']]

    tipo, valor = enlace(entrada)

    if tipo == 'id':
        return f'acestream://{valor[:12]}…'
    if tipo == 'infohash':
        return f'Torrent {valor[:12]}…'

    if valor.lower().startswith('magnet:'):
        nombre = urllib_parse.parse_qs(urllib_parse.urlsplit(valor).query).get('dn')
        if nombre:
            return nombre[0]
        btih = _RE_BTIH.search(valor)
        return f'Magnet {btih.group(1)[:12]}…' if btih else valor

    # A .torrent or an .acelive: the file name says more than the whole address.
    return urllib_parse.unquote(valor.split('?', 1)[0].rstrip('/').rsplit('/', 1)[-1]) or valor


def _ruta(fichero):
    return os.path.join(data_path, fichero)


def _leer(fichero):
    """The file's entries, [] if it is missing or damaged, or None if it cannot be read.

    Not being able to read is not being empty. Whoever writes next has to tell one from the
    other, or a file that happens to be busy would be written over with a list of one."""
    ruta = _ruta(fichero)

    if not os.path.isfile(ruta):
        return list()

    try:
        crudo = load_json_file(ruta)
    except OSError as e:
        logger(f'history: no se pudo leer {fichero}: {e}', 'error')
        return None

    # A damaged file comes back from load_json() as a dict, and a bad entry inside a good
    # list is dropped alone: one broken row must not empty the whole list.
    if not isinstance(crudo, list):
        return list()

    entradas = list()
    vistas = set()

    for entrada in map(normalizar, crudo):
        if entrada is not None and clave(entrada) not in vistas:
            vistas.add(clave(entrada))
            entradas.append(entrada)

    return entradas


def _guardar(fichero, entradas):
    """True if it was written. A full disk is logged and playback carries on."""
    try:
        dump_json_file(entradas, _ruta(fichero), compacto=True)
    except (OSError, ValueError) as e:
        logger(f'history: no se pudo guardar {fichero}: {e}', 'error')
        return False

    return True


def historial():
    return _leer(FICHERO_HISTORIAL) or list()


def anotar(id='', url='', infohash='', titulo='', icono='', plot='', origen='', motor=False):
    """Puts the link at the top of the history. Returns the entry, or None if nothing was written.

    It is written when the link is asked for, not after minutes of video. That is what gets
    everything in: a channel that goes out to VLC on Android never plays inside Kodi, and
    one that does not start is still worth finding again.

    A link that was already there moves up and keeps whatever the new call does not bring:
    going back to it from the history carries no origin, and some addons send no name."""
    nueva = normalizar({'id': id, 'url': url, 'infohash': infohash, 'titulo': titulo,
                        'icono': icono, 'plot': plot, 'origen': origen, 'motor': motor})

    if nueva is None:
        # What it was stays out of the log, as every link does.
        logger('history: no es un enlace, no se anota')
        return None

    entradas = _leer(FICHERO_HISTORIAL)
    if entradas is None:
        return None

    entradas = _poner_arriba(entradas, nueva)

    return nueva if _guardar(FICHERO_HISTORIAL, entradas[:HISTORIAL_MAX]) else None


def anotar_lote(entradas):
    """Notes several links with one read and one write, as the service sends them, oldest first.

    What they bring only fills what an entry already there lacks: a name the service had to
    guess must not replace one the user has seen. Returns how many were written."""
    nuevas = [e for e in map(normalizar, entradas) if e is not None]
    if not nuevas:
        return 0

    actuales = _leer(FICHERO_HISTORIAL)
    if actuales is None:
        return 0

    for nueva in nuevas:
        actuales = _poner_arriba(actuales, nueva, rellenar=True)

    return len(nuevas) if _guardar(FICHERO_HISTORIAL, actuales[:HISTORIAL_MAX]) else 0


def _poner_arriba(entradas, nueva, rellenar=False):
    """The list with nueva on top, taking from the entry it replaces whatever it does not bring.

    With rellenar, the name, the logo and the description the entry already had are kept."""
    k = clave(nueva)
    previa = next((e for e in entradas if clave(e) == k), None)

    if previa is not None:
        for campo in ('titulo', 'icono', 'plot'):
            if rellenar:
                nueva[campo] = previa[campo] or nueva[campo]
            else:
                nueva[campo] = nueva[campo] or previa[campo]
        nueva['origen'] = nueva['origen'] or previa['origen']
        nueva['motor'] = nueva['motor'] or previa['motor']

    nueva['fecha'] = int(time.time())

    return [nueva] + [e for e in entradas if clave(e) != k]


# What this invocation left for the history's own thread, in the order it was asked. Every
# invocation of the addon is an interpreter of its own, so neither the queue nor the thread is
# ever another invocation's.
_cola = collections.deque()
_cerrojo = threading.Lock()
_hilo = None


def _en_segundo_plano(funcion, **datos):
    """Queues funcion(**datos) behind whatever this invocation queued before."""
    global _hilo

    with _cerrojo:
        _cola.append((funcion, datos))
        if _hilo is not None:
            return

        _hilo = threading.Thread(target=_vaciar_cola)
        try:
            _hilo.start()
            return
        except RuntimeError as e:
            # With no thread to spare, the history is written the slow way rather than not at all.
            logger(f'history: sin hilo para escribir, se escribe aquí: {e}', 'error')
            _hilo = None

    _vaciar_cola()


def _vaciar_cola():
    global _hilo

    while True:
        with _cerrojo:
            if not _cola:
                _hilo = None
                return
            funcion, datos = _cola.popleft()

        try:
            funcion(**datos)
        except Exception as e:
            # Raised on a thread, it would reach nobody.
            logger(f'history: {funcion.__name__} ha fallado en segundo plano: {e}', 'error')


def anotar_de_fondo(**datos):
    """anotar() on the history's thread. Gives the entry's key back at once, or '' for no link.

    Playback calls it before anything else, and writing there made the progress dialog wait
    for a read, a write and an fsync, which on the flash storage of a TV box take long enough
    to notice. Whoever calls it has to call esperar() before the invocation ends."""
    nueva = normalizar(datos)

    if nueva is None:
        logger('history: no es un enlace, no se anota')
        return ''

    _en_segundo_plano(anotar, **datos)
    return clave(nueva)


def poner_nombre_de_fondo(k, nombre):
    """poner_nombre() on the history's thread, once the entry it names has been written."""
    _en_segundo_plano(poner_nombre, k=k, nombre=nombre)


def esperar():
    """Waits until what this invocation left for the history's thread is on disk."""
    esperado = None

    while True:
        with _cerrojo:
            hilo = _hilo

        # From that thread itself, waiting for it would be waiting forever. And a thread already
        # waited for that is still marked did not end on its own. Kodi raises SystemExit in every
        # thread of a script that does not stop in time, and nothing more is coming from that one.
        if hilo is None or hilo is esperado or hilo is threading.current_thread():
            return

        hilo.join()
        esperado = hilo


def poner_nombre(k, nombre):
    """Names an entry that came with none, once the engine has said what it is: in the history,
    and in My favourites if it was kept there with none either."""
    nombre = (nombre or '').strip()[:TITULO_MAX]

    if not k or not nombre:
        return

    # Otherwise it could read the history before its own entry got there.
    esperar()

    for fichero in (FICHERO_HISTORIAL, FICHERO_FAVORITOS):
        entradas = _leer(fichero) or list()
        entrada = next((e for e in entradas if clave(e) == k), None)

        if entrada is not None and not entrada['titulo']:
            entrada['titulo'] = nombre
            _guardar(fichero, entradas)


def borrar(k):
    entradas = _leer(FICHERO_HISTORIAL) or list()
    restantes = [e for e in entradas if clave(e) != k]

    if len(restantes) != len(entradas):
        _guardar(FICHERO_HISTORIAL, restantes)


def vaciar():
    _guardar(FICHERO_HISTORIAL, list())


def favoritos():
    return _leer(FICHERO_FAVORITOS) or list()


def claves_favoritas():
    """The keys of every favourite, read once to mark a whole list."""
    return {clave(e) for e in favoritos()}


def es_favorito(k):
    return k in claves_favoritas()


def anadir_favorito(datos):
    """Keeps the link at the end of My favourites. False if it was already there or is no link.

    At the end and not at the top, as Kodi's own favourites do: whoever keeps a handful of
    channels finds each one where they left it."""
    nueva = normalizar(datos)

    if nueva is None:
        return False

    entradas = _leer(FICHERO_FAVORITOS)

    if entradas is None or any(clave(e) == clave(nueva) for e in entradas):
        return False

    nueva['fecha'] = int(time.time())
    return _guardar(FICHERO_FAVORITOS, entradas + [nueva])


def quitar_favorito(k):
    entradas = _leer(FICHERO_FAVORITOS) or list()
    restantes = [e for e in entradas if clave(e) != k]

    return len(restantes) != len(entradas) and _guardar(FICHERO_FAVORITOS, restantes)


def renombrar_favorito(k, nombre):
    """Gives the favourite a name of the user's own. The one it came with is kept apart."""
    nombre = (nombre or '').strip()[:TITULO_MAX]
    entradas = _leer(FICHERO_FAVORITOS) or list()
    entrada = next((e for e in entradas if clave(e) == k), None)

    if entrada is None or not nombre or nombre == entrada['titulo']:
        return False

    if entrada['titulo'] and 'original' not in entrada:
        entrada['original'] = entrada['titulo']

    entrada['titulo'] = nombre
    return _guardar(FICHERO_FAVORITOS, entradas)


def movimientos(claves, k):
    """The moves that make sense for favourite k, given the keys of all of them in order, in the
    order its menu offers them.

    To the top only from the third place on: from the second it would be the same as up."""
    if k not in claves:
        return list()

    puesto = claves.index(k)
    return [m for m, vale in (('subir', puesto > 0), ('bajar', puesto < len(claves) - 1),
                              ('principio', puesto > 1)) if vale]


def mover_favorito(k, hacia):
    """Moves the favourite one place up ('subir') or down ('bajar'), or to the top ('principio').
    Returns its new place, or None if it is not there or cannot go that way.

    Worked out on the file as it is now, and not on the list the menu was painted from, which
    may be older."""
    entradas = _leer(FICHERO_FAVORITOS) or list()
    puesto = next((n for n, e in enumerate(entradas) if clave(e) == k), None)
    if puesto is None:
        return None

    destino = {'subir': puesto - 1, 'bajar': puesto + 1, 'principio': 0}.get(hacia)
    if destino is None or destino == puesto or not 0 <= destino < len(entradas):
        return None

    entradas.insert(destino, entradas.pop(puesto))
    return destino if _guardar(FICHERO_FAVORITOS, entradas) else None


def item_para_ver(entrada, origen=''):
    """The Item that plays the entry through the addon, the same road any other link takes.

    The plugin and not the player straight away: on that road a link gets the external
    player setting, the content_id resolution, the history and the OSD."""
    tipo, valor = enlace(entrada)
    campos = {tipo: valor, 'action': 'play', 'label': entrada['titulo'], 'origen': origen}

    if entrada['icono']:
        campos['icon'] = entrada['icono']
    if entrada['plot']:
        campos['plot'] = entrada['plot']
    # motor=1 is what makes playback resolve a channel's content_id, and with it what keeps
    # the external player applying to it on Android.
    if entrada['motor']:
        campos['motor'] = 1

    return Item(**campos)
