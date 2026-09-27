# -*- coding: utf-8 -*-
# EKHorus - The watch that saves in the History every AceStream link Kodi plays.
"""What the "Guardar todo" switch of the History turns on: the AceStream links Kodi plays by
itself too, from its TV section or from other addons.

Switched off, nothing of it is left running. Kodi starts it with the addon (service.py) and it
ends at once; the History starts it when it is switched on (arrancar). Switched on, it lasts
until it is switched off, a newer watch takes its place or Kodi closes.

It may last hours, and that is why it imports nothing from lib.utils: utils creates an
xbmcaddon.Addon() on import, and Kodi only refreshes the settings of the oldest one alive. Nor
does it write the history: what it finds goes to the addon in batches (see Anotador), so the
file keeps being written from one place at a time. And nothing of what plays goes to Kodi's log.
"""
import json
import os
import re
import time
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ID_ADDON = 'script.module.horus'
AJUSTE = 'anotar_fuera'

ORIGEN_TV = 'tv'
ORIGEN_FUERA = 'fuera'
# What StreamNinja plays with no name. It titles those 'AceStream' or 'AceStream Torrent' (its
# acestream_player.py), which is the same for every link. The engine that plays it gives the real
# name when the batch is written (repasar). If it does not answer, the name stays empty, so that a
# real one can still come, and the History paints one of its own meanwhile (history.SIN_NOMBRE).
ORIGEN_STREAMNINJA = 'streamninja'
ORIGEN_STREAMNINJA_TORRENT = 'streamninja_torrent'
_TITULO_ID = 'AceStream'
_TITULO_TORRENT = 'AceStream Torrent'
_SIN_NOMBRE_STREAMNINJA = {_TITULO_ID: ORIGEN_STREAMNINJA,
                           _TITULO_TORRENT: ORIGEN_STREAMNINJA_TORRENT}
# The only ones a batch may bring.
ORIGENES = (ORIGEN_TV, ORIGEN_FUERA, ORIGEN_STREAMNINJA, ORIGEN_STREAMNINJA_TORRENT)

# On the home window, the mark of the watch that runs: for the History to know whether one has to
# be started, and for an older one to know it has been replaced.
VIGIA = 'ekhorus_vigia'
# On the home window while an 'anotar' invocation writes: the time the batch was sent and its name.
# That invocation clears it when it ends, and if it dies first it stops counting after MARCA_VALE.
MARCA = 'ekhorus_anotando'
# And one per batch, with its entries, which that invocation reads and clears. The order only names
# it: Kodi writes the arguments of every call to its log in debug mode (CPythonInvoker), and a
# batch is what was watched.
LOTE = 'ekhorus_lote.'
# On the home window too: the engine address EKHorus played last (default.MyPlayer.playStream).
PROPIA = 'ekhorus_reproduciendo'
MARCA_VALE = 15
# And the links the addon has just handed to StreamNinja (default.llamada_externa), noted there
# already under their own id. The engine session StreamNinja opens for one of them is that same
# playback, and it would be a second row. It is told by its link (repasar).
REENVIOS = 'ekhorus_reenvios'
# StreamNinja buffers before it plays, up to its own timeout plus two minutes, and may then ask.
REENVIO_VALE = 5 * 60
REENVIOS_MAX = 5
# Sessions of other addons per batch that the engine is asked about, each question with a short
# wait (default.preguntar_al_motor). It answers at once for what it has just played.
SESIONES_MAX = 3
# A stream that reconnects starts again, and it is still the same watching.
REPETIDO = 30
# Entries per batch. What does not fit goes in the next one.
LOTE_MAX = 20
# Well above the biggest batch the service sends, some 50 KB with every entry at the History's
# caps. It only stops a caller from having the addon parse megabytes.
LOTE_LEIDO_MAX = 256 * 1024
# The History's own caps (history.TITULO_MAX and ICONO_MAX). Applied here too because they are
# what keeps a single entry inside a batch.
TITULO_MAX = 300
ICONO_MAX = 2000
# Read again on every channel of the TV of Kodi played outside it, so a bigger list is not read.
LISTA_MAX = 10 * 1024 * 1024
# How often what is left waiting gets another chance, and the watch makes sure it still is one.
ESPERA = 30

_NOMBRE_LOTE = re.compile(re.escape(LOTE) + r'[0-9a-f]{16}\Z')
_HASH = re.compile(r'[0-9a-f]{40}\Z', re.I)
_ACESTREAM = re.compile(r'acestream://([0-9a-f]{40})(?![0-9a-f])', re.I)
# HTTPAceProxy, which the HaP app serves on port 8888: /content_id/<hash>/<name>.ts and so on.
_PROXY = {'content_id': 'id', 'pid': 'id', 'infohash': 'infohash'}
# The address an engine plays a session from, with the content's infohash: /ace/r/<hash>/...,
# /ace/m/<hash>/... (HLS) and AceServe's /hls/r/<hash>/.... EKHorus and StreamNinja play these.
_SESION = re.compile(r'(https?://[^/]+)/(ace|hls)/[rm]/([0-9a-f]{40})/', re.I)
# The engine a batch may name: a scheme, a host and a port, and nothing else.
_MOTOR = re.compile(r'https?://[\w.-]+(?::\d{1,5})?\Z', re.A | re.I)
_BTIH = re.compile(r'btih:([0-9a-f]{40})(?![0-9a-z])', re.I)
# <instance>@pvr.iptvsimple_<channel>.pvr from Kodi 20 on, pvr.iptvsimple_<channel>.pvr in
# Kodi 19 (CPVRChannelsPath). The channel is IPTV Simple's own id for it.
_CANAL_PVR = re.compile(r'(?:(\d+)@)?pvr\.iptvsimple_(\d+)\.pvr\Z')
_CARPETA_PVR = 'special://profile/addon_data/pvr.iptvsimple/'
# What Kodi's StringUtils::Trim takes away, which is less than str.strip() does.
_BLANCOS = ' \t\n\v\f\r'


def _log_fallo(texto):
    xbmc.log(f'[{ID_ADDON}] servicio: {texto}', xbmc.LOGERROR)


def _habilitado():
    return bool(xbmc.getCondVisibility(f'System.AddonIsEnabled({ID_ADDON})'))


def activado():
    """Whether the setting is on, read from disk now.

    With an Addon() that is let go at once: one kept alive would be the oldest of the session,
    the only one Kodi refreshes, and every other invocation would stop seeing setting changes."""
    return xbmcaddon.Addon(ID_ADDON).getSetting(AJUSTE) == 'true'


def poner_activado(encendido):
    """Switches it on or off from the History. On, the watch starts now; off, the one running
    hears it (onSettingsChanged) and ends.

    With a new Addon() too: setSetting() saves every setting of its copy, and an old copy would
    undo whatever the user has changed since."""
    xbmcaddon.Addon(ID_ADDON).setSetting(AJUSTE, 'true' if encendido else 'false')
    if encendido:
        arrancar()
    else:
        # Also when no watch runs, one that died say.
        _borrar_rastro()


def _borrar_rastro():
    """Takes off the home window what the switch left there for the watch: switched off, nothing
    of it stays, not even which links were played."""
    ventana = xbmcgui.Window(10000)
    ventana.clearProperty(PROPIA)
    ventana.clearProperty(REENVIOS)


def arrancar():
    """Starts the watch, in an invocation of the addon that lasts while it stays on (see the top
    of default.py). One that was running gives way to it."""
    xbmc.executebuiltin(f'RunPlugin(plugin://{ID_ADDON}/?action=vigilar)')


def arrancar_si_falta():
    """Starts the watch if it is on and none runs. Switched on from Kodi's settings dialog, where no
    code of ours runs, it would otherwise wait for Kodi to start again."""
    if activado() and not xbmcgui.Window(10000).getProperty(VIGIA):
        arrancar()


def _leer_reenvios(ventana):
    """The forwards still waiting for their session, oldest first. Anything else in the property is
    dropped, since any addon can write it."""
    try:
        crudos = json.loads(ventana.getProperty(REENVIOS) or '[]')
    except ValueError:
        return list()

    if not isinstance(crudos, list):
        return list()

    ahora = time.time()
    return [dict(r, id=_hash(r.get('id')), h=_hash(r.get('h'))) for r in crudos
            if isinstance(r, dict) and isinstance(r.get('t'), (int, float))
            and 0 <= ahora - r['t'] < REENVIO_VALE
            and isinstance(r.get('titulo'), str)][-REENVIOS_MAX:]


def _hash(valor):
    """valor as a hash of forty hex digits in lowercase, or '' if it is none."""
    return valor.lower() if isinstance(valor, str) and _HASH.match(valor) else ''


def _guardar_reenvios(ventana, reenvios):
    if reenvios:
        ventana.setProperty(REENVIOS, json.dumps(reenvios[-REENVIOS_MAX:]))
    else:
        ventana.clearProperty(REENVIOS)


def como_vuelve(enlace):
    """The link as StreamNinja hands it back when it cannot play it (url_player.play_acestream):
    lowercase, and an acestream:// one as its bare id. Its circuit breaker goes by it too
    (default.llamada_externa)."""
    enlace = enlace.strip().lower()
    return enlace[len('acestream://'):] if enlace.startswith('acestream://') else enlace


def apuntar_reenvio(enlace):
    """Notes that the addon has just handed enlace to StreamNinja (what goes to it: 'id',
    'infohash' or 'url', and 'title' if there is one), under the title StreamNinja will show.

    The addon and the watch run apart, and each writes the list whole. If they ever meet, the worst
    it does is one row more, or one less of the same link."""
    k = enlace.get('id') or enlace.get('infohash') or enlace.get('url') or ''
    # As StreamNinja takes it (url_player.play_acestream): an id, or an acestream:// address,
    # plays as an id and anything else as a torrent, with the title it is given if there is one.
    como_id = bool(enlace.get('id')) or k.lower().startswith('acestream://')
    titulo = enlace.get('title') or (_TITULO_ID if como_id else _TITULO_TORRENT)
    vuelve = como_vuelve(k)
    # What its session will be told by (_era_reenvio): the id, which the engine gives for the
    # session's infohash, or the infohash itself, also the one inside a magnet.
    btih = _BTIH.search(vuelve)
    contenido = _hash(vuelve) if como_id else ''
    infohash = '' if como_id else _hash(btih.group(1) if btih else vuelve)

    ventana = xbmcgui.Window(10000)
    reenvios = _leer_reenvios(ventana)
    reenvios.append({'t': time.time(), 'k': vuelve, 'id': contenido, 'h': infohash,
                     'titulo': titulo.strip()[:TITULO_MAX]})
    _guardar_reenvios(ventana, reenvios)


def olvidar_reenvio(k):
    """StreamNinja handed link k back to the addon, which plays it itself, so no session of
    StreamNinja is coming for it."""
    ventana = xbmcgui.Window(10000)
    reenvios = _leer_reenvios(ventana)
    k = como_vuelve(k)
    quedan = [r for r in reenvios if r.get('k') != k]
    if len(quedan) != len(reenvios):
        _guardar_reenvios(ventana, quedan)


def _era_reenvio(infohash, mostrado, id_del_motor):
    """Whether the engine session of infohash, shown as mostrado, is a link the addon handed to
    StreamNinja. Each forward accounts for one session, the oldest first.

    Told by the link whenever it can be, so that a forward whose buffering was cancelled can take
    no other channel's session. An infohash is the session's own, and an id is the one the engine
    gives for it (id_del_motor(), asked only if an id is waiting). The title StreamNinja shows is
    only for a .torrent, or for an engine that does not answer."""
    ventana = xbmcgui.Window(10000)
    reenvios = _leer_reenvios(ventana)
    contenido = None

    for n, reenvio in enumerate(reenvios):
        if reenvio['h']:
            suyo = reenvio['h'] == infohash
        else:
            if reenvio['id'] and contenido is None:
                contenido = _hash(id_del_motor())
            if reenvio['id'] and contenido:
                suyo = reenvio['id'] == contenido
            else:
                suyo = reenvio['titulo'] == mostrado

        if suyo:
            del reenvios[n]
            _guardar_reenvios(ventana, reenvios)
            return True

    return False


def _nombre_del_motor(datos):
    """The name the engine gives a content: that of its first file (get_media_files), or ''."""
    ficheros = datos.get('files') if isinstance(datos, dict) else None
    fichero = ficheros[0] if isinstance(ficheros, list) and ficheros else None
    nombre = fichero.get('filename') if isinstance(fichero, dict) else None
    return nombre.strip() if isinstance(nombre, str) else ''


def repasar(entradas, preguntar):
    """The entries of a batch as they go to the History (default.escribir_lote). Of each engine
    session of another addon, the engine that played it says what it was: a link the addon handed
    to StreamNinja, which the History has already, or the name of one that came with none.

    preguntar(motor, metodo, infohash) is the answer ('result') of that engine to the method, or
    None. It is asked about SESIONES_MAX sessions of a batch at most, and any more are told apart
    by what needs no engine."""
    salida = list()
    preguntadas = 0

    for entrada in entradas:
        motor = entrada.pop('sesion', '')
        mostrado = entrada.pop('mostrado', '')

        if not (motor and _hash(entrada.get('infohash'))):
            salida.append(entrada)
            continue

        if isinstance(motor, str) and _MOTOR.match(motor) and preguntadas < SESIONES_MAX:
            preguntadas += 1
        else:
            motor = ''

        entrada = _sesion(entrada, motor, mostrado if isinstance(mostrado, str) else '', preguntar)
        if entrada is not None:
            salida.append(entrada)

    return salida


def _sesion(entrada, motor, mostrado, preguntar):
    """The entry of an engine session as it goes to the History, or None if it is a forward (see
    repasar). With no engine to ask (motor ''), it is told apart by what needs none."""
    infohash = _hash(entrada['infohash'])

    def pregunta(metodo):
        return preguntar(motor, metodo, infohash) if motor else None

    def id_del_motor():
        datos = pregunta('get_content_id')
        return datos.get('content_id') if isinstance(datos, dict) else ''

    if _era_reenvio(infohash, mostrado, id_del_motor):
        return None

    if not entrada.get('titulo'):
        entrada['titulo'] = _nombre_del_motor(pregunta('get_media_files'))

    return entrada


def enlace_ace(url):
    """('id' | 'infohash', hash) of an AceStream link, or None for anything else.

    Only the forms that name the content, which are also what a list can carry. The addresses
    the engine plays a session from are looked at in lo_que_suena()."""
    # Behind a '|' go the options Kodi opens it with (User-Agent=...), which a list may add.
    url = (url or '').split('|', 1)[0].strip()

    encontrado = _ACESTREAM.match(url)
    if encontrado:
        return 'id', encontrado.group(1).lower()

    try:
        partes = urllib.parse.urlsplit(url)
    except ValueError:
        return None

    if partes.scheme.lower() not in ('http', 'https'):
        return None

    trozos = [t for t in partes.path.split('/') if t]

    if trozos in (['ace', 'getstream'], ['ace', 'manifest.m3u8']):
        consulta = urllib.parse.parse_qs(partes.query)
        for tipo in ('id', 'infohash'):
            valor = (consulta.get(tipo) or [''])[0]
            if _HASH.match(valor):
                return tipo, valor.lower()
        return None

    if len(trozos) >= 2 and trozos[0] in _PROXY and _HASH.match(trozos[1]):
        return _PROXY[trozos[0]], trozos[1].lower()

    return None


def icono_real(icono):
    """The address of a logo Kodi hands over wrapped (image://...), or '' if it is none.

    Only an http(s) one. With no logo the TV section wraps the channel's name instead, which must
    not pass for a logo."""
    icono = (icono or '').strip()

    if icono.startswith('image://'):
        dentro = icono[len('image://'):].rstrip('/')
        if dentro.startswith('pvrchannel_'):
            dentro = dentro.partition('@')[2]
        icono = urllib.parse.unquote(dentro)

    return icono if icono.lower().startswith(('http://', 'https://')) else ''


def _abs32(n):
    return abs(n - (1 << 32) if n >= 1 << 31 else n)


def ids_canal(nombre, url):
    """The ids IPTV Simple may give a channel (Channels::GenerateChannelId): a djb2 hash of its
    name and its address, worked out both ways because C's char is signed on x86 and not on ARM."""
    con_signo = sin_signo = 0

    for b in (nombre + url).encode('utf-8'):
        sin_signo = (sin_signo * 33 + b) & 0xFFFFFFFF
        con_signo = (con_signo * 33 + (b - 256 if b > 127 else b)) & 0xFFFFFFFF

    return {_abs32(con_signo), _abs32(sin_signo)}


def _nombre_extinf(linea):
    """The channel name of an #EXTINF line, cut where IPTV Simple cuts it
    (PlaylistLoader::ParseIntoChannel): after the comma that follows the last quote, so that a
    comma in the name counts, or else after the last comma."""
    coma = linea.rfind(',')
    comilla = linea.rfind('"')

    if comilla != -1:
        resto = linea[comilla + 1:]
        if resto.strip(_BLANCOS).startswith(','):
            coma = comilla + 1 + resto.find(',')

    dos_puntos = linea.find(':')
    if dos_puntos == -1 or coma <= dos_puntos:
        return ''

    return linea[coma + 1:].strip(_BLANCOS)


def canales_m3u(texto):
    """(name, address) of each entry of a list, read line by line as IPTV Simple reads it."""
    nombre = ''

    # Split on '\n' alone, as std::getline does. splitlines() also breaks on characters a
    # name may carry.
    for linea in texto.split('\n'):
        linea = linea.rstrip(' \t\r\n').lstrip(' \t')

        if linea.startswith('#EXTINF'):
            nombre = _nombre_extinf(linea)
        elif linea and not linea.startswith('#'):
            yield nombre, linea[1:] if linea.startswith('@') else linea
            nombre = ''


def _texto(datos):
    try:
        return datos.decode('utf-8-sig')
    except UnicodeDecodeError:
        return datos.decode('latin-1')


def _leer_lista(ruta):
    """The text of a list on this device, or None.

    A path of another machine (smb://, nfs://) is not followed: translatePath() leaves it as
    it is, and it fails as a missing file instead of making the service wait on the network."""
    ruta = xbmcvfs.translatePath(ruta)

    try:
        if os.path.getsize(ruta) > LISTA_MAX:
            return None
        with open(ruta, 'rb') as f:
            return _texto(f.read())
    except OSError:
        return None


def _lista_de_instancia(instancia):
    """The text of the list an IPTV Simple instance loaded, if it is on this device, or None."""
    # Here and not above: it is tens of milliseconds, and the History imports this module too.
    import xml.etree.ElementTree as ET

    if instancia is None:
        ajustes, copia = 'settings.xml', 'iptv.m3u.cache'
    else:
        ajustes, copia = f'instance-settings-{instancia}.xml', f'iptv.m3u.cache-{instancia}'

    try:
        raiz = ET.parse(xbmcvfs.translatePath(_CARPETA_PVR + ajustes)).getroot()
    except (OSError, ET.ParseError):
        return None

    valores = {s.get('id'): (s.text or '').strip() for s in raiz.iter('setting')}

    # With no value it is remote, which is IPTV Simple's own default.
    if valores.get('m3uPathType', '1') == '0':
        return _leer_lista(valores.get('m3uPath', ''))

    # IPTV Simple keeps a copy of a remote list, and reads from it, only with its periodic
    # refresh off (PlaylistLoader::LoadPlayList). HaP sets every instance of its own with it on,
    # and there the copy is missing or old. Nor is the list fetched again from its address, which
    # would be EKHorus asking another project's server for it.
    copia = _CARPETA_PVR + copia
    if valores.get('m3uRefreshMode', '0') == '0' and os.path.isfile(xbmcvfs.translatePath(copia)):
        return _leer_lista(copia)

    return None


def canal_de_la_tv(fichero, nombre=''):
    """(name, address) of the IPTV Simple channel Kodi names fichero, or None.

    The id in the file name is worked out again for each AceStream entry of the list until one
    gives it. 'nombre' is the channel's name in Kodi, which is the list's unless it has been
    renamed there, and trying those entries first saves hashing the rest."""
    encontrado = _CANAL_PVR.match(fichero or '')
    if encontrado is None:
        return None

    instancia = int(encontrado.group(1)) if encontrado.group(1) else None
    uid = int(encontrado.group(2))

    texto = _lista_de_instancia(instancia)
    if texto is None:
        return None

    candidatos = [(n, u) for n, u in canales_m3u(texto) if enlace_ace(u)]
    candidatos.sort(key=lambda c: c[0] != nombre)

    for n, u in candidatos:
        if uid in ids_canal(n, u):
            return n, u

    return None


def _titulo_fuera(url, titulo, fichero):
    """The title another addon gave the video, or '' when Kodi made it up from the address."""
    titulo = titulo.strip()

    try:
        ultimo = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rstrip('/').rsplit('/', 1)[-1])
    except ValueError:
        ultimo = ''

    if titulo in ('', url, ultimo, fichero) or '://' in titulo:
        return ''

    return titulo


def lo_que_suena(reproductor):
    """The History entry for what has just started, or None if it is no AceStream link."""
    # All Kodi says of it is read at once, first, because its external player is done with the
    # item 80 ms in (measured on the phone) and finding the link in a list takes a while.
    dicho = {e: xbmc.getInfoLabel(e) for e in ('Player.Filenameandpath', 'Player.Filename',
                                               'Player.Title', 'Player.Icon',
                                               'VideoPlayer.ChannelName')}
    en_la_tv = bool(xbmc.getCondVisibility('PVR.IsPlayingTV'))
    ruta = dicho['Player.Filenameandpath']

    try:
        url = reproductor.getPlayingFile()
    except RuntimeError:
        # Already stopped. With the external player, only the path of what it opened is left.
        url = ''

    # Callbacks reach Python a moment late: with another item opening meanwhile, what was read
    # above could be half of each. That one brings its own start.
    if xbmc.getInfoLabel('Player.Filenameandpath') not in ('', ruta):
        return None

    # With nothing left, the player let the item go before it could be read.
    url = url or ruta
    if not url:
        return None

    enlace = enlace_ace(url)
    nombre_lista = ''

    # Another addon playing through the engine (StreamNinja does). EKHorus plays these addresses
    # too, and what it plays it has noted already.
    sesion = _SESION.match(url) if enlace is None else None
    if sesion and url != xbmcgui.Window(10000).getProperty(PROPIA):
        enlace = 'infohash', sesion.group(3).lower()

    # A channel of the TV of Kodi that went to the external player: only its file name is left.
    if enlace is None and url.startswith('pvr://'):
        canal = canal_de_la_tv(url.rsplit('/', 1)[-1], dicho['VideoPlayer.ChannelName'])
        if canal is not None:
            nombre_lista, enlace = canal[0], enlace_ace(canal[1])

    if enlace is None:
        return None

    # From the external player PVR.IsPlayingTV is already false, and the path still says it.
    sesion_de = dict()
    if ruta.startswith('pvr://channels/') or en_la_tv:
        origen = ORIGEN_TV
        nombre = dicho['VideoPlayer.ChannelName'].strip() or nombre_lista
        icono = icono_real(dicho['Player.Icon'])
    else:
        origen = ORIGEN_FUERA
        nombre = _titulo_fuera(url, dicho['Player.Title'], dicho['Player.Filename'])
        icono = ''
        if sesion is not None:
            titulo = dicho['Player.Title'].strip()
            if titulo in _SIN_NOMBRE_STREAMNINJA:
                nombre = ''
                # Said to be StreamNinja's only when it can be: another addon may title its own
                # sessions the same way.
                if xbmc.getCondVisibility('System.HasAddon(plugin.video.streamninja)'):
                    origen = _SIN_NOMBRE_STREAMNINJA[titulo]
            # For the addon, which asks that engine what it was when it writes (repasar).
            sesion_de = {'sesion': sesion.group(1), 'mostrado': titulo[:TITULO_MAX]}

    tipo, valor = enlace
    return {tipo: valor,
            'titulo': nombre[:TITULO_MAX],
            'icono': icono if len(icono) <= ICONO_MAX else '',
            'origen': origen,
            **sesion_de}


def recoger(nombre):
    """The entries of the batch left on the home window under nombre, which comes off it.
    ValueError if there is no batch there.

    Anybody can call the addon with action=anotar, so nothing of it is trusted beyond its
    shape: every entry still goes through history.normalizar(). Nor is any property read or
    cleared but a batch's, whatever name comes."""
    if not _NOMBRE_LOTE.match(nombre):
        raise ValueError('no es el nombre de un lote')

    ventana = xbmcgui.Window(10000)
    texto = ventana.getProperty(nombre)
    ventana.clearProperty(nombre)

    if len(texto) > LOTE_LEIDO_MAX:
        raise ValueError(f'lote de {len(texto)} caracteres')

    entradas = json.loads(texto)

    if not isinstance(entradas, list) or not all(isinstance(e, dict) for e in entradas):
        raise ValueError('no es una lista de entradas')

    return entradas[:LOTE_MAX]


def _escribiendo(marca):
    """Whether the mark ('<time> <batch>') says a batch is being written right now."""
    try:
        return 0 <= time.time() - float(marca.partition(' ')[0]) < MARCA_VALE
    except ValueError:
        return False


def soltar_marca(lote):
    """Clears the mark once batch lote is written. Only its own: one that took longer than
    MARCA_VALE may end after the next batch was sent, and any addon may call action=anotar."""
    ventana = xbmcgui.Window(10000)
    if ventana.getProperty(MARCA).partition(' ')[2] == lote:
        ventana.clearProperty(MARCA)


class Anotador:
    """What the watch finds, on its way to the addon, which is the one that writes it."""

    def __init__(self):
        self.pendientes = list()
        self.vistos = dict()

    def poner(self, entrada):
        """Queues entrada. False if the same link was queued less than REPETIDO seconds ago."""
        ahora = time.time()
        self.vistos = {k: t for k, t in self.vistos.items() if 0 <= ahora - t < REPETIDO}

        k = next(f'{t}:{entrada[t]}' for t in ('id', 'infohash') if t in entrada)
        if k in self.vistos:
            return False

        self.vistos[k] = ahora
        self.pendientes.append(entrada)
        return True

    def enviar(self):
        """Sends what is waiting to the addon, unless it is still writing the last batch."""
        if not self.pendientes:
            return False

        ventana = xbmcgui.Window(10000)
        # Disabled, Kodi would not run the call, and the batch would stay on the window. The watch
        # notices within ESPERA and ends.
        if _escribiendo(ventana.getProperty(MARCA)) or not _habilitado():
            return False

        lote = self.pendientes[:LOTE_MAX]
        del self.pendientes[:LOTE_MAX]
        nombre = LOTE + os.urandom(8).hex()
        ventana.setProperty(nombre, json.dumps(lote, ensure_ascii=False))
        ventana.setProperty(MARCA, f'{time.time()} {nombre}')
        xbmc.executebuiltin(f'RunPlugin(plugin://{ID_ADDON}/?action=anotar&lote={nombre})')
        return True

    def vaciar(self):
        del self.pendientes[:]


class Vigia(xbmc.Player):
    """The player Kodi tells of what starts, while the watch runs switched on."""

    def __init__(self, anotador):
        super().__init__()
        self.anotador = anotador

    def onAVStarted(self):
        # onAVStarted and not onPlayBackStarted: that one comes before the stream is open, and
        # by the time a link that fails fast reaches Python the player has already stopped.
        try:
            entrada = lo_que_suena(self)
            if entrada is not None and self.anotador.poner(entrada):
                self.anotador.enviar()
        except Exception as e:
            # Raised, it would reach Kodi's log with its message, which may carry what plays.
            _log_fallo(f'no se pudo mirar lo que suena ({type(e).__name__})')


class Guardia(xbmc.Monitor):
    """Keeps the watch as the setting says, from the moment it is saved.

    Kodi tells every Monitor of the addon when its settings are saved, from the settings dialog
    or from setSetting() in another invocation, which is what the History's button does."""

    def __init__(self):
        super().__init__()
        self.anotador = Anotador()
        self.vigia = None
        # What it leaves on the home window (VIGIA), different for each watch.
        self.ficha = os.urandom(8).hex()

    def onSettingsChanged(self):
        try:
            self.actualizar()
        except Exception as e:
            _log_fallo(f'no se pudo leer el ajuste ({type(e).__name__})')

    def actualizar(self):
        encendido = activado()

        if encendido and self.vigia is None:
            self.vigia = Vigia(self.anotador)
        elif not encendido and self.vigia is not None:
            # Dropped, it is no longer told of any playback, and vigilar() ends.
            self.vigia = None
            self.anotador.vaciar()
            # Switched off from Kodi's settings dialog nothing else hears it.
            _borrar_rastro()

    def sigue(self):
        """Whether it is still the watch. A newer one takes its place. And Kodi only stops the
        service it started itself, so one the History started would go on with the addon
        disabled or uninstalled."""
        return xbmcgui.Window(10000).getProperty(VIGIA) == self.ficha and _habilitado()


def vigilar():
    """The watch, for as long as the setting stays on.

    Switched off it returns at once, and Kodi frees its interpreter. Switched on it returns when
    it is switched off, when a newer watch takes its place or when Kodi closes."""
    if not activado():
        return

    ventana = xbmcgui.Window(10000)
    guardia = Guardia()
    # The newest is the watch. Two only meet for a moment, as when it is switched off and on
    # again before the first has ended, or when Kodi starts it with the addon right as the
    # History does.
    ventana.setProperty(VIGIA, guardia.ficha)
    try:
        guardia.actualizar()
        mirado = time.monotonic()
        # A second at a time, so that switched off it is gone at once.
        while guardia.vigia is not None and not guardia.waitForAbort(1):
            if time.monotonic() - mirado >= ESPERA:
                mirado = time.monotonic()
                if not guardia.sigue():
                    break
                guardia.anotador.enviar()
    finally:
        if ventana.getProperty(VIGIA) == guardia.ficha:
            ventana.clearProperty(VIGIA)
