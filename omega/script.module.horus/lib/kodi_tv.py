# -*- coding: utf-8 -*-
# EKHorus - Takes channels to Kodi's TV section, through the IPTV Simple addon.
"""The "Llevar los canales a la sección TV" row of Experimental.

The channels go into an m3u of the addon's own, which IPTV Simple reads through an instance of
its own, next to whatever instances the user already has; none of those is ever written to.
Each channel is a plugin:// address of EKHorus, so pressing it in the TV plays it through the
same door as everything else in the addon.
"""
import contextlib
import json
import os
import re
import time
from datetime import datetime
from threading import get_ident

import xbmc
import xbmcgui
import xbmcvfs

from lib import history, ui_common
from lib.utils import (ENGINE_ACESERVE, HEADING, Item, active_engine, data_path, dump_json_file,
                       echar_pestillo, get_setting, kodi_major_version, load_json_file, logger,
                       quitar_pestillo, refrescar_pestillo, server, system_platform)

IPTVSIMPLE = 'pvr.iptvsimple'
PESTILLO = 'ekhorus.tv'

CARPETA_PVR = 'special://profile/addon_data/pvr.iptvsimple/'
# What IPTV Simple is told. It works the path out by itself, so it stays right wherever the
# profile lives.
RUTA_M3U = 'special://profile/addon_data/script.module.horus/tv/ekhorus.m3u'
NOMBRE_INSTANCIA = 'EKHorus'
# An instance with no name, the only kind IPTV Simple moves the one list of Kodi 19 into
# (SettingsMigration::MigrateSettings).
INSTANCIA_VACIA = '<settings version="2">\n</settings>\n'

FAVORITOS = 'favoritos'
CANALES = 'canales'
ACESERVE = 'aceserve'
FUENTES = (FAVORITOS, CANALES, ACESERVE)
# As the menu names them. The channel list is part of the addon, and what serves it underneath
# is only named when something fails (see PROHIBIDAS in test_resources).
NOMBRES = {FAVORITOS: 'Mis favoritos', CANALES: 'Canales', ACESERVE: 'Lista de AceServe'}
# Why Channels brought nothing, from channels_ui._descargar(). Here the engine is named: something
# failed, and it is the one to look at.
MOTIVOS = {'sin_motor': 'no contesta el motor', 'sin_catalogo': 'este motor no la da',
           'busqueda_falla': 'el motor no la consigue'}
GRUPO_FAVORITOS = 'Mis favoritos'

# Measured on the benches: IPTV Simple stops in under a second and loads again in 7 to 9.
PARADA_MAX = 15
CARGA_MAX = 60
# With some of our channels hidden in Kodi they never all show, and a count that holds still
# this long is taken as the end.
QUIETO = 3

# Estuary and EspaKodi's skin both call the section TV in the main menu, and so do the texts.
TITULO = 'Llevar los canales a la sección TV'
CORTA = ('Hay un canal de la sección TV en marcha, y cargar los canales lo corta.\n\n'
         '¿Sigo?')

_RE_INSTANCIA = re.compile(r'instance-settings-(\d+)\.xml\Z')


def _ruta_estado():
    return os.path.join(data_path, 'tv', 'exportacion.json')


def leer_estado():
    """What the last export took ({'fuentes', 'canales', 'fecha', ...}), or None if there is none."""
    ruta = _ruta_estado()
    if not os.path.isfile(ruta):
        return None

    try:
        estado = load_json_file(ruta)
    except OSError as e:
        logger(f'kodi_tv: no se pudo leer el estado: {e}', 'error')
        return None

    # A damaged file comes back as an empty dict.
    if not isinstance(estado, dict) or not isinstance(estado.get('fuentes'), list):
        return None

    return estado


def _guardar_estado(estado):
    try:
        dump_json_file(estado, _ruta_estado())
    except (OSError, ValueError) as e:
        logger(f'kodi_tv: no se pudo guardar el estado: {e}', 'error')


def resumen():
    """What the menu row adds about the export there is, or ''."""
    estado = leer_estado()
    if estado is None:
        return ''

    try:
        cuando = datetime.fromtimestamp(estado.get('fecha') or 0).strftime(' el %d/%m/%Y')
    except (OverflowError, OSError, TypeError, ValueError):
        cuando = ''

    n = estado.get('canales') or 0
    return f'Ahora hay {_canales(n)} en la sección TV, llevado{"" if n == 1 else "s"}{cuando}.'


def _canales(n):
    return '1 canal' if n == 1 else f'{n} canales'


def _de_favoritos():
    salida = list()

    for entrada in history.favoritos():
        tipo, valor = history.enlace(entrada)
        # The name it has, empty if none: the readable one the History makes up is the list's
        # business (m3u), and never a real name.
        salida.append({'tipo': tipo, 'valor': valor, 'nombre': entrada['titulo'],
                       'origen': entrada['origen'], 'logo': entrada['icono'],
                       'grupos': [GRUPO_FAVORITOS], 'motor': entrada['motor']})

    return salida


def _de_canales(catalogo):
    """The engine's channels in the order Channels paints them, each in its categories."""
    from lib import catalog

    visibles = catalog.ordenar(catalog.visibles(catalogo))

    # The categories Channels shows, with the leftovers of four channels gathered in 'Otras'.
    grupos = dict()
    for _clave, nombre, canales in catalog.facetas(catalog.indexar(visibles, 'categorias'),
                                                   'categorias'):
        for canal in canales:
            grupos.setdefault(canal['infohash'], list()).append(nombre)

    # motor=1, as when Channels plays them: that is what resolves the content_id, and with it
    # what keeps the external player applying to them on Android.
    return [{'tipo': 'infohash', 'valor': c['infohash'], 'nombre': c['nombre'],
             'logo': c.get('logo') or '', 'grupos': grupos.get(c['infohash']) or [],
             'motor': True}
            for c in visibles]


def _de_aceserve(catalogo):
    """AceServe's own list, with the logos it gets from crossing it with the catalogue."""
    from lib import catalog
    from lib.channels_ui import Explorador

    explorador = Explorador(catalogo)
    explorador.playlist = (catalog.leer_playlist(server)
                           or catalog.leer(server.base, catalog.FICHERO_PLAYLIST, ttl_horas=0)
                           or list())

    return [{'tipo': 'infohash', 'valor': c['infohash'], 'nombre': c['nombre'],
             'logo': c.get('logo') or '', 'grupos': [catalog.nombre_grupo(c['grupo'])],
             'motor': True}
            for c in explorador.playlist_canales()]


def unir(listas):
    """One channel per link, in the order they come, with the name of the first list that brings
    one (a favourite renamed by the user, say) and the groups of all of them."""
    porclave = dict()

    for lista in listas:
        for entrada in lista:
            k = history.clave({entrada['tipo']: entrada['valor']})
            if not k:
                continue

            ya = porclave.get(k)
            if ya is None:
                porclave[k] = dict(entrada, grupos=list(entrada['grupos']))
                continue

            ya['grupos'] += [g for g in entrada['grupos'] if g not in ya['grupos']]
            ya['nombre'] = ya['nombre'] or entrada['nombre']
            ya['logo'] = ya['logo'] or entrada['logo']
            ya['motor'] = ya['motor'] or entrada['motor']

    return list(porclave.values())


def entradas(fuentes):
    """(channels, names of the sources that brought none), or None if the user cancelled the
    catalogue download."""
    from lib import catalog, channels_ui

    catalogo, motivo = list(), ''
    if CANALES in fuentes:
        catalogo, motivo = channels_ui.catalogo()
        if motivo == 'cancelado':
            return None
        # With no engine right now, the list kept last time still serves for the TV.
        catalogo = catalogo or catalog.leer(server.base, ttl_horas=0) or list()
    elif ACESERVE in fuentes:
        # Only for the logos, so nothing is downloaded for it.
        catalogo = catalog.leer(server.base, ttl_horas=0) or list()

    # After the download, which brings its own progress dialog.
    with ui_common.ocupado():
        de = {FAVORITOS: _de_favoritos, CANALES: lambda: _de_canales(catalogo),
              ACESERVE: lambda: _de_aceserve(catalogo)}
        listas = [(fuente, de[fuente]()) for fuente in FUENTES if fuente in fuentes]

    def nombre(fuente):
        porque = MOTIVOS.get(motivo) if fuente == CANALES else None
        return f'{NOMBRES[fuente]} ({porque})' if porque else NOMBRES[fuente]

    return (unir(lista for _fuente, lista in listas),
            [nombre(fuente) for fuente, lista in listas if not lista])


def _limpio(texto):
    """Text fit for an #EXTINF line: a single line, and no double quote, which would cut the name
    where IPTV Simple looks for it."""
    return ' '.join(str(texto or '').replace('"', "'").split())


def _logo(logo):
    logo = str(logo or '').strip()

    if '"' in logo or '\n' in logo or '\r' in logo:
        return ''

    return logo if logo.lower().startswith(('http://', 'https://')) or os.path.isabs(logo) else ''


def _item(entrada, nombre):
    """What the channel plays: the same road as a History row, marked as coming from the TV.

    The logo stays out of it. IPTV Simple tells channels apart by name and address, and with a
    logo inside, a new logo in the catalogue would make the channel a new one on the next export,
    losing whatever the user did with it in Kodi (hiding it, moving it to a group)."""
    campos = {entrada['tipo']: entrada['valor'], 'action': 'play', 'label': nombre, 'origen': 'tv'}
    if entrada['motor']:
        campos['motor'] = 1

    return Item(**campos)


def m3u(canales):
    lineas = ['#EXTM3U']

    for entrada in canales:
        nombre = _limpio(entrada['nombre'])
        # A link with no name shows the History's readable one in the TV, and goes with none: played,
        # the History waits for the engine's instead of keeping a made-up one as real.
        visible = nombre or _limpio(history.titulo({entrada['tipo']: entrada['valor'],
                                                    'origen': entrada.get('origen', '')}))
        grupos = ';'.join(g for g in (_limpio(g).replace(';', ',') for g in entrada['grupos']) if g)

        # group-title always goes, empty or not: with no quote on the line IPTV Simple would cut
        # the name at its last comma.
        logo = _logo(entrada['logo'])
        atributos = (f' tvg-logo="{logo}"' if logo else '') + f' group-title="{grupos}"'

        lineas.append(f'#EXTINF:-1{atributos},{visible}')
        lineas.append(f'plugin://script.module.horus/?{_item(entrada, nombre).tourl()}')

    return '\n'.join(lineas) + '\n'


def instancia_xml():
    # No default="true" on any setting: Kodi would take the value for untouched and ignore it.
    return ('<settings version="2">\n'
            f'    <setting id="kodi_addon_instance_name">{NOMBRE_INSTANCIA}</setting>\n'
            '    <setting id="kodi_addon_instance_enabled">true</setting>\n'
            '    <setting id="m3uPathType">0</setting>\n'
            f'    <setting id="m3uPath">{RUTA_M3U}</setting>\n'
            '</settings>\n')


def _carpeta_pvr():
    return xbmcvfs.translatePath(CARPETA_PVR)


def _ajustes_de(ruta):
    """{id: value} of a Kodi settings file, or None if it cannot be read."""
    # Here and not above, as in _reactivar(): it is tens of milliseconds, and Experimental
    # imports this module only to paint its row.
    import xml.etree.ElementTree as ET

    try:
        raiz = ET.parse(ruta).getroot()
    except (OSError, ET.ParseError) as e:
        logger(f'kodi_tv: no se pudo leer {ruta}: {e}')
        return None

    return {s.get('id'): (s.text or '').strip() for s in raiz.iter('setting')}


def _instancias():
    """{number: path} of IPTV Simple's instance files, readable or not."""
    try:
        nombres = os.listdir(_carpeta_pvr())
    except OSError:
        return dict()

    return {int(m.group(1)): os.path.join(_carpeta_pvr(), m.group(0))
            for m in map(_RE_INSTANCIA.match, nombres) if m}


def _nuestra(instancias):
    """The number of the instance that reads our list, or None."""
    for numero, ruta in sorted(instancias.items()):
        ajustes = _ajustes_de(ruta)
        if ajustes is not None and ajustes.get('m3uPath') == RUTA_M3U:
            return numero

    return None


def numero_instancia():
    """(number, new, with an empty 1): where our instance goes.

    One that is already there is used again. Otherwise the number after the highest, counting
    the files that cannot be read, which are never opened to write. With none at all it is the
    1, so that IPTV Simple does not make an empty one of its own that would complain on every
    start. Unless the one list of Kodi 19 is still waiting to be moved: that only goes into an
    instance with no name, so an empty 1 is left for it and ours is the 2."""
    instancias = _instancias()

    propia = _nuestra(instancias)
    if propia is not None:
        return propia, False, False

    if instancias:
        return max(instancias) + 1, True, False

    viejo = os.path.join(_carpeta_pvr(), 'settings.xml')
    ajustes = _ajustes_de(viejo) if os.path.isfile(viejo) else None
    if ajustes and (ajustes.get('m3uPath') or ajustes.get('m3uUrl')):
        return 2, True, True

    return 1, True, False


def _publicar(destino, texto):
    """Writes texto to destino through Kodi's VFS. False if it could not.

    Written apart and renamed with xbmcvfs, as qr.generar() does, which is the way Kodi's
    directory cache learns about a file. If Kodi closes halfway, what was there stays whole."""
    carpeta = os.path.dirname(destino)
    parcial = os.path.join(carpeta, f'.ekhorus.{os.getpid()}.{get_ident()}.tmp')

    try:
        os.makedirs(carpeta, exist_ok=True)
        with open(parcial, 'w', encoding='utf-8', newline='\n') as f:
            f.write(texto)

        # On Windows Kodi renames with MoveFileEx and no MOVEFILE_REPLACE_EXISTING.
        xbmcvfs.delete(destino)
        if xbmcvfs.rename(parcial, destino):
            return True

        logger(f'kodi_tv: no se pudo publicar {destino}', 'error')
    except OSError as e:
        logger(f'kodi_tv: no se pudo escribir {destino}: {e}', 'error')

    try:
        os.remove(parcial)
    except OSError:
        pass

    return False


def _reactivar(ruta):
    """Switches our instance back on if it was switched off in Kodi, since exporting is asking for
    it. Anything else the user changed in it (a guide, say) is kept."""
    import xml.etree.ElementTree as ET

    try:
        arbol = ET.parse(ruta)
    except (OSError, ET.ParseError) as e:
        logger(f'kodi_tv: no se pudo leer {ruta}: {e}', 'error')
        return False

    ajuste = next((s for s in arbol.getroot().iter('setting')
                   if s.get('id') == 'kodi_addon_instance_enabled'), None)
    if ajuste is None or (ajuste.text or '').strip() != 'false':
        return True

    ajuste.text = 'true'
    ajuste.attrib.pop('default', None)

    return _publicar(ruta, ET.tostring(arbol.getroot(), encoding='unicode') + '\n')


def _escribir(canales, numero, nueva, con_vacia):
    """Our list, and our instance if it is new. The list first, so that IPTV Simple never finds
    the instance without it. False if something could not be written."""
    if not _publicar(xbmcvfs.translatePath(RUTA_M3U), m3u(canales)):
        return False

    ruta = os.path.join(_carpeta_pvr(), f'instance-settings-{numero}.xml')

    if not nueva:
        return _reactivar(ruta)

    if con_vacia and not _publicar(os.path.join(_carpeta_pvr(), 'instance-settings-1.xml'),
                                   INSTANCIA_VACIA):
        return False

    return _publicar(ruta, instancia_xml())


def _borrar(numero=None, vacia=False):
    """Takes away what the addon wrote: the list, the state and the instances named."""
    rutas = [xbmcvfs.translatePath(RUTA_M3U), _ruta_estado()]
    if numero is not None:
        rutas.append(os.path.join(_carpeta_pvr(), f'instance-settings-{numero}.xml'))
    if vacia:
        rutas.append(os.path.join(_carpeta_pvr(), 'instance-settings-1.xml'))

    for ruta in rutas:
        if os.path.exists(ruta) and not xbmcvfs.delete(ruta):
            logger(f'kodi_tv: no se pudo borrar {ruta}', 'error')


def _jsonrpc(metodo, **params):
    peticion = {'jsonrpc': '2.0', 'id': 1, 'method': metodo, 'params': params}

    try:
        respuesta = json.loads(xbmc.executeJSONRPC(json.dumps(peticion)))
    except ValueError as e:
        logger(f'kodi_tv: {metodo}: {e}', 'error')
        return dict()

    return respuesta if isinstance(respuesta, dict) else dict()


def _clientes():
    """[(addon, instance, client)] of the TV addons Kodi has running. An error counts as none."""
    clientes = _jsonrpc('PVR.GetClients').get('result', dict()).get('clients') or list()
    return [(c.get('addonid'), c.get('instanceid'), c.get('clientid')) for c in clientes]


def _habilitar(encendido):
    _jsonrpc('Addons.SetAddonEnabled', addonid=IPTVSIMPLE, enabled=encendido)


def _instalado():
    """Whether IPTV Simple is there, switched on or not. System.AddonIsEnabled says only the
    ones that are on, and System.HasAddon says nothing about being on."""
    return 'addon' in _jsonrpc('Addons.GetAddonDetails', addonid=IPTVSIMPLE,
                               properties=['enabled']).get('result', dict())


def _esperar(condicion, plazo, paso=0.25):
    """True once condicion() holds; False if plazo seconds go by first or Kodi is closing."""
    monitor = xbmc.Monitor()
    limite = time.time() + plazo

    while not condicion():
        if time.time() > limite or monitor.waitForAbort(paso):
            return False
        refrescar_pestillo(PESTILLO)

    return True


def _parado():
    """IPTV Simple has stopped for good: switched off, with no client left, and the TV of Kodi
    idle, unless another TV addon keeps it going."""
    if xbmc.getCondVisibility(f'System.AddonIsEnabled({IPTVSIMPLE})'):
        return False

    clientes = _clientes()
    if any(addon == IPTVSIMPLE for addon, _i, _c in clientes):
        return False

    return xbmc.getInfoLabel('PVR.BackendHost') == '' or bool(clientes)


def _recargar():
    """Switches IPTV Simple off and on, so that it reads its instances and its lists again.

    Measured on both benches: off and on in a row left instances unloaded. It has to be stopped
    for good first, and PVR.GetClients alone does not say so: it stops listing it within 0.06 s
    and the TV of Kodi takes another second."""
    _habilitar(False)
    _esperar(_parado, PARADA_MAX)
    xbmc.sleep(500)
    _habilitar(True)


def _canales_nuestros(numero):
    """How many channels of our instance Kodi has, or None while the instance is not running."""
    cliente = next((c for addon, i, c in _clientes() if addon == IPTVSIMPLE and i == numero), None)
    if cliente is None:
        return None

    canales = _jsonrpc('PVR.GetChannels', channelgroupid='alltv',
                       properties=['clientid']).get('result', dict()).get('channels') or list()
    return sum(1 for c in canales if c.get('clientid') == cliente)


def _esperar_canales(numero, cuantos):
    """True once the TV of Kodi has our channels: all of them, or as many as stop growing."""
    visto = {'n': None, 'desde': time.time()}

    def listos():
        n = _canales_nuestros(numero)
        if n is not None and n >= cuantos:
            return True
        if n != visto['n']:
            visto.update(n=n, desde=time.time())
            return False
        return bool(n) and time.time() - visto['desde'] >= QUIETO

    # Once a second: every look is the whole channel list of the TV of Kodi.
    return _esperar(listos, CARGA_MAX, paso=1)


@contextlib.contextmanager
def _avance(texto):
    barra = xbmcgui.DialogProgressBG()
    barra.create(HEADING, texto)
    try:
        yield
    finally:
        barra.close()


def _opciones():
    """(source, text) of each source that can be chosen, with its channels when that is known
    without asking the engine."""
    from lib import catalog

    def con(nombre, n):
        return nombre if n is None else f'{nombre}  ({n})'

    guardados = catalog.leer(server.base, ttl_horas=0)
    opciones = [(FAVORITOS, con(NOMBRES[FAVORITOS], len(history.favoritos()))),
                (CANALES, con(NOMBRES[CANALES],
                              len(catalog.visibles(guardados)) if guardados else None))]

    # Only whoever has AceServe, or had it when the list was saved.
    lista = catalog.leer(server.base, catalog.FICHERO_PLAYLIST, ttl_horas=0)
    if lista or active_engine() == ENGINE_ACESERVE:
        opciones.append((ACESERVE, con(NOMBRES[ACESERVE],
                                       len(catalog.playlist_visible(lista)) if lista else None)))

    return opciones


def _elegir_fuentes(previas):
    with ui_common.ocupado():
        opciones = _opciones()

    elegidas = xbmcgui.Dialog().multiselect(
        '¿Qué canales llevo a la sección TV?', [texto for _fuente, texto in opciones],
        preselect=[n for n, (fuente, _texto) in enumerate(opciones) if fuente in previas])

    # None is cancelling, and [] accepting with nothing marked: neither takes anything.
    return [opciones[n][0] for n in elegidas] if elegidas else None


def exportar():
    """The Experimental row: takes channels to the TV of Kodi, updates them or takes them away."""
    # Two presses in a row would write the same files and switch IPTV Simple off and on at once.
    if not echar_pestillo(PESTILLO):
        logger('kodi_tv: ya hay una exportación en marcha')
        return

    try:
        _exportar()
    except Exception as e:
        # It goes through files, dialogs and another addon: whatever breaks is said, not lost.
        logger(f'kodi_tv: no se pudo exportar: {e!r}', 'error')
        xbmcgui.Dialog().ok(HEADING, f'No se ha podido terminar: {e}')
    finally:
        quitar_pestillo(PESTILLO)


def _exportar():
    estado = leer_estado()
    fuentes = None

    if estado is not None:
        eleccion = xbmcgui.Dialog().select(TITULO, ['Actualizar los canales',
                                                    'Cambiar qué se lleva',
                                                    'Quitarlos de la sección TV'])
        if eleccion < 0:
            return
        if eleccion == 2:
            quitar()
            return
        if eleccion == 0:
            fuentes = [f for f in estado['fuentes'] if f in FUENTES]

    if not fuentes:
        fuentes = _elegir_fuentes(estado['fuentes'] if estado else [FAVORITOS])
        if not fuentes:
            return

    refrescar_pestillo(PESTILLO)
    resultado = entradas(fuentes)
    if resultado is None:
        return

    canales, fallidas = resultado
    refrescar_pestillo(PESTILLO)

    if not canales:
        xbmcgui.Dialog().ok(HEADING, 'No hay ningún canal que llevar a la sección TV.\n\n'
                                     f'Sin canales: {", ".join(fallidas)}.')
        return

    if kodi_major_version() < 20:
        _en_kodi19(canales, fuentes, fallidas)
        return

    encendido = bool(xbmc.getCondVisibility(f'System.AddonIsEnabled({IPTVSIMPLE})'))
    presente = encendido or _instalado()

    if encendido and xbmc.getCondVisibility('PVR.IsPlayingTV') \
            and not xbmcgui.Dialog().yesno(HEADING, CORTA):
        return

    numero, nueva, con_vacia = numero_instancia()
    if not _escribir(canales, numero, nueva, con_vacia):
        xbmcgui.Dialog().ok(HEADING, 'No se han podido escribir los ficheros de la lista. '
                                     'Mira si queda espacio en el aparato.')
        return

    if not presente:
        xbmcgui.Dialog().ok(HEADING, 'Para ver los canales en la sección TV hace falta IPTV Simple, '
                                     'un addon del repositorio oficial de Kodi.\n\n'
                                     'Ahora Kodi te preguntará si quieres instalarlo.')
        from lib import espakodi_installer

        if not espakodi_installer.instalar_oficial(IPTVSIMPLE):
            _borrar(numero, con_vacia)
            _sin_iptvsimple()
            return

    refrescar_pestillo(PESTILLO)
    # Freshly installed it is already on, and finds our instance as it loads for the first time.
    with _avance('Cargando los canales en la sección TV…'):
        if encendido:
            _recargar()
        elif presente:
            _habilitar(True)

        cargados = _esperar_canales(numero, len(canales))

        # The list of Kodi 19 moves into the empty instance on the first load, and only loads on
        # the next one (measured).
        if con_vacia:
            _recargar()
            cargados = _esperar_canales(numero, len(canales))

    nuevo = {'fuentes': fuentes, 'canales': len(canales), 'fecha': int(time.time()),
             'instancia': numero, 'tv_mostrada': bool(estado and estado.get('tv_mostrada'))}
    _guardar_estado(nuevo)
    _terminar(nuevo, fallidas, cargados, presente and not encendido)


def _sin_iptvsimple():
    texto = ('IPTV Simple no se ha instalado, así que los canales no se han llevado a la sección '
             'TV.\n\nSi la descarga ha fallado, vuelve a intentarlo: a veces falla un servidor '
             'de Kodi y a la siguiente sale.')
    if system_platform == 'linux':
        texto += ' En Linux puede que venga del gestor de paquetes (kodi-pvr-iptvsimple).'

    xbmcgui.Dialog().ok(HEADING, texto)


def _entrada_tv(oculta):
    """Whether the TV entry of the home menu is hidden (or shown), only in the skins whose setting
    is known: Estuary and EspaKodi's, which comes from it."""
    return (xbmc.getSkinDir() in ('skin.estuary', 'skin.espatuary')
            and bool(xbmc.getCondVisibility('Skin.HasSetting(HomeMenuNoTVButton)')) == oculta)


def _terminar(estado, fallidas, cargados, activado):
    lineas = [f'{_canales(estado["canales"])} en la sección TV.']

    if fallidas:
        lineas.append(f'Sin canales: {", ".join(fallidas)}.')
    if not cargados:
        lineas.append('Todavía están cargando: saldrán en unos segundos.')
    if activado:
        lineas.append('IPTV Simple estaba desactivado y se ha activado.')
    if system_platform == 'android' and get_setting('reproductor_externo'):
        lineas.append('Al pulsar uno se abre en la app del motor, como en el resto de EKHorus.')

    texto = '\n'.join(lineas)

    if _entrada_tv(oculta=True):
        if xbmcgui.Dialog().yesno(HEADING, f'{texto}\n\nLa entrada TV del menú principal está '
                                           'oculta. ¿La enseño?',
                                  yeslabel='Enseñarla', nolabel='Dejarla así'):
            xbmc.executebuiltin('Skin.Reset(HomeMenuNoTVButton)')
            # So that taking the channels away offers to hide it again.
            _guardar_estado(dict(estado, tv_mostrada=True))
        texto = ''

    pregunta = '¿Abro ahora la sección TV?'
    if texto:
        pregunta = f'{texto}\n\n{pregunta}'
    if xbmcgui.Dialog().yesno(HEADING, pregunta, yeslabel='Abrirla', nolabel='Ahora no'):
        xbmc.executebuiltin('ActivateWindow(TVChannels)')


def _en_kodi19(canales, fuentes, fallidas):
    """In Kodi 19 IPTV Simple takes a single list, which may be the user's, so the list is left
    ready and the user is told where it is."""
    ruta = xbmcvfs.translatePath(RUTA_M3U)
    if not _publicar(ruta, m3u(canales)):
        xbmcgui.Dialog().ok(HEADING, 'No se ha podido escribir la lista. Mira si queda espacio '
                                     'en el aparato.')
        return

    _guardar_estado({'fuentes': fuentes, 'canales': len(canales), 'fecha': int(time.time())})

    aviso = f'\n\nSin canales: {", ".join(fallidas)}.' if fallidas else ''
    xbmcgui.Dialog().ok(HEADING, f'Hecha la lista, con {_canales(len(canales))}.{aviso}\n\n'
                                 'En Kodi 19 IPTV Simple solo admite una lista, y EKHorus no toca '
                                 'la que tengas. Para usar esta, ponla en los ajustes de IPTV '
                                 f'Simple como lista local:\n{ruta}')


def quitar():
    """Takes our channels out of the TV of Kodi and leaves everything else as it was."""
    if not xbmcgui.Dialog().yesno(HEADING, 'Se quitan de la sección TV los canales que llevó '
                                           'EKHorus. Las demás listas no se tocan.\n\n'
                                           '¿Los quito?'):
        return

    estado = leer_estado() or dict()
    encendido = kodi_major_version() >= 20 and bool(
        xbmc.getCondVisibility(f'System.AddonIsEnabled({IPTVSIMPLE})'))

    if encendido and xbmc.getCondVisibility('PVR.IsPlayingTV') \
            and not xbmcgui.Dialog().yesno(HEADING, CORTA):
        return

    instancias = _instancias() if kodi_major_version() >= 20 else dict()
    numero = _nuestra(instancias)
    _borrar(numero)

    if encendido:
        quedan = [n for n in instancias if n != numero]
        if not quedan and xbmcgui.Dialog().yesno(
                HEADING, 'IPTV Simple se ha quedado sin listas. ¿Lo desactivo?\n\n'
                         'Si lo dejas activado, en cada arranque buscará una lista que no tiene.',
                yeslabel='Desactivarlo', nolabel='Dejarlo'):
            _habilitar(False)
        else:
            with _avance('Quitando los canales de la sección TV…'):
                _recargar()

    if estado.get('tv_mostrada') and _entrada_tv(oculta=False) and xbmcgui.Dialog().yesno(
            HEADING, 'EKHorus enseñó la entrada TV del menú principal al llevar los canales. '
                     '¿La oculto otra vez?', yeslabel='Ocultarla', nolabel='Dejarla'):
        xbmc.executebuiltin('Skin.SetBool(HomeMenuNoTVButton)')

    xbmcgui.Dialog().notification(HEADING, 'Canales quitados de la sección TV',
                                  xbmcgui.NOTIFICATION_INFO, 3000)
