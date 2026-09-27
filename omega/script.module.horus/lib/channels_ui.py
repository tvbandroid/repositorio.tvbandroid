# -*- coding: utf-8 -*-
"""Browser for the channels the engine publishes.

The catalogue and its normalisation live in catalog.py; here it is only navigated and
painted. Navigation is a stack of levels, because the list window is single level and what
is needed is for Back to go up instead of closing.

EKHorus hosts none of these links: the engine publishes them and here they are only shown.
"""
import os

import xbmc
import xbmcgui

from lib import catalog, history, ui_common
from lib.acestream.server import version_tuple
from lib.history_ui import ANADIDO, ANADIR, QUITADO, QUITAR, VER, avisar
from lib.utils import (ENGINE_ACESERVE, HEADING, Item, detect_engine, logger,
                       runtime_path, server)
from lib.list_screen import Fila, mostrar

# Painting 1800 rows at once is more than two seconds on a TV box, and the user is not
# going to go through them. It pages, and leaves a row to carry on.
POR_PAGINA = 300

PISTA = '[B]OK[/B] abre    ·    [B]Derecha[/B] lee    ·    [B]Atrás[/B] vuelve'
# Only channel rows have options, so only there is the key named.
PISTA_CANALES = '[B]OK[/B] lo ve    ·    [B]Menú[/B] opciones    ·    [B]Atrás[/B] vuelve'
ESTADO_CANALES = 'Con [B]Menú[/B] o pulsación larga puedes añadirlo a Mis favoritos'

RAIZ = 'raiz'
FACETA = 'faceta'
CANALES = 'canales'
GRUPOS = 'grupos'

_FACETAS = (('categorias', 'Por categoría'), ('paises', 'Por país'), ('idiomas', 'Por idioma'))

# The three shared the magnifier and there was no telling them apart at a glance.
_ICONO_FACETA = {'categorias': 'categorias.png', 'paises': 'paises.png',
                 'idiomas': 'idiomas.png'}

# An entry of the own list the catalogue does not recognise: no logo and unclassified.
# Immutable on purpose, because it serves as the template for building the real ones.
_SIN_FICHA = {'logo': '', 'categorias': (), 'paises': (), 'idiomas': (),
              'estado': catalog.DISPONIBLE, 'disponibilidad': 0}


# Languages whose flag leaves no room for doubt. Not all of them are here on purpose:
# Arabic, Kurdish or Catalan are not from one country and giving them one would be
# deciding for the user.
_BANDERA_IDIOMA = {
    'rus': 'ru', 'deu': 'de', 'pol': 'pl', 'eng': 'gb', 'spa': 'es', 'ita': 'it',
    'nld': 'nl', 'fra': 'fr', 'zho': 'cn', 'cmn': 'cn', 'ces': 'cz', 'ukr': 'ua',
    'ell': 'gr', 'por': 'pt', 'tur': 'tr', 'hin': 'in', 'ind': 'id', 'vie': 'vn',
    'tha': 'th', 'urd': 'pk', 'hye': 'am', 'bul': 'bg', 'fin': 'fi', 'kat': 'ge',
    'hun': 'hu', 'jpn': 'jp', 'swe': 'se', 'ron': 'ro', 'dan': 'dk', 'nor': 'no',
    'isl': 'is', 'tam': 'in',
}

# The catalogue writes Ukraine both ways, and the United Kingdom three ways.
_ALIAS_PAIS = {'ukr': 'ua', 'uk': 'gb', 'en': 'gb'}

_carpetas = dict()


def _icono(nombre):
    return os.path.join(runtime_path, 'resources', 'media', nombre)


def _hay(carpeta, nombre):
    """Whether that media folder has that png.

    The directory is read once and not once per row: there are up to seventy rows and each
    one would ask the disk on its own."""
    if carpeta not in _carpetas:
        try:
            _carpetas[carpeta] = frozenset(n[:-4] for n in os.listdir(_icono(carpeta))
                                           if n.endswith('.png'))
        except OSError as e:
            logger(f'channels_ui: no se pudo leer {carpeta}: {e}', 'error')
            _carpetas[carpeta] = frozenset()

    return nombre in _carpetas[carpeta]


def _bandera(campo, clave):
    """Flag of a country or language row, or the globe icon if there is none.

    The flags are files of the addon itself, not images from the internet: a list with
    seventy remote icons is slow to repaint, and this way opening the menu asks nothing of
    anybody. Only the ones that can be drawn faithfully are there; the rest keep the
    globe, which tells the truth, whereas a lookalike flag would lie."""
    if campo == 'paises':
        codigo = _ALIAS_PAIS.get(clave, clave)
    elif campo == 'idiomas':
        codigo = _BANDERA_IDIOMA.get(clave, '')
    else:
        return ''

    if _hay('banderas', codigo):
        return os.path.join(_icono('banderas'), codigo + '.png')

    return _icono('mundo.png')


def _icono_categoria(clave):
    """Own icon of a category or a group, or the television set if it has none.

    The same folder serves both screens, because the groups of the list carry the same
    labels as the categories. Before, the fifteen rows shared the television set and there
    was no way of telling them apart at a glance."""
    c = catalog.clave_grupo(clave)

    if _hay('categorias', c):
        return os.path.join(_icono('categorias'), c + '.png')

    return _icono('directo.png')


# Sample names that fit in the right-hand box without having to scroll it.
EJEMPLOS = 8

# A name longer than this breaks the line and the sample turns into a wall. The catalogue
# carries channels whose name is a whole web address, with up to two links.
LARGO_NOMBRE = 44


def _plot_grupo(canales, cabeza):
    """Text of the right-hand box for a row that leads to a list of channels.

    With only the number of channels, the box looked like the place where they were going
    to appear and there was no guessing that something had to be pressed. With a few names
    in front it reads as a sample with the list behind it.

    The list arrives already sorted the way it will be painted on entering, not however it
    comes: that way the names in the box really are the first ones the user will see."""
    muestra = canales[:EJEMPLOS]

    lineas = [cabeza, '']
    for canal in muestra:
        nombre = canal['nombre']
        if len(nombre) > LARGO_NOMBRE:
            nombre = nombre[:LARGO_NOMBRE - 1].rstrip() + '…'
        lineas.append(f'·  {nombre}')

    restantes = len(canales) - len(muestra)
    if restantes > 0:
        lineas.append(f'·  y {restantes} más')

    lineas += ['', '[B]Pulsa OK[/B] para abrir la lista.']

    return '\n'.join(lineas)


def _pista_canal(canal):
    partes = [catalog.etiqueta('categorias', c) for c in canal.get('categorias') or []]
    partes += [catalog.etiqueta('paises', p) for p in canal.get('paises') or []]

    return '  ·  '.join(partes[:3])


def _plot_canal(canal):
    lineas = [canal['nombre'], '']

    for campo, titulo in (('categorias', 'Categorías'), ('paises', 'País'), ('idiomas', 'Idioma')):
        valores = [catalog.etiqueta(campo, v) for v in canal.get(campo) or []]
        if valores:
            lineas.append(f'[B]{titulo}[/B]  {", ".join(valores)}')

    if canal.get('estado') != catalog.DISPONIBLE:
        lineas.append('')
        lineas.append('[B]Enlace dudoso.[/B] Puede que no arranque o que se corte.')

    lineas.append('')
    lineas.append(f'[COLOR FF808080]{canal["infohash"]}[/COLOR]')

    return '\n'.join(lineas)


def _fila_canal(canal):
    # With no logo it takes the 48 px, half a kilobyte television set, not the addon icon:
    # that one is 240x240 and 32 KB, and in a list where two out of three channels carry
    # no logo it was the heaviest image on the whole screen.
    return Fila(clave=canal['infohash'],
                titulo=canal['nombre'],
                pista=_pista_canal(canal),
                icono=canal.get('logo') or _icono('directo.png'),
                pastilla=None if canal.get('estado') == catalog.DISPONIBLE else ('Dudoso', 'gris'),
                plot=_plot_canal(canal))


def reproducir(infohash, nombre, logo=''):
    """Sends the channel to the addon itself.

    default.py cannot be imported from here, so the plugin is called the same way the
    control panel does to shut the engine down. The motor=1 mark tells playback to resolve
    the content_id, which is what keeps the external player setting applying to these
    channels."""
    item = Item(action='play', infohash=infohash, label=nombre, icon=logo, motor=1,
                origen='canales')
    xbmc.executebuiltin(f'RunPlugin(plugin://script.module.horus/?{item.tourl()})')


class Explorador(object):
    """Navigation state. It lives inside a single opening of the window."""

    def __init__(self, canales, playlist_disponible=False):
        self.canales = canales
        self.playlist_disponible = playlist_disponible
        self.playlist = list()
        self._por_infohash = None
        self.pila = [(RAIZ, '', '', 0)]
        # They pile up here and are fired on closing: RunPlugin does not wait, and firing
        # it with the window open would leave the dialog on top of the video.
        self.al_salir = list()

    # --- navigation --------------------------------------------------------------------

    @property
    def nivel(self):
        return self.pila[-1]

    def entrar(self, modo, campo='', clave='', pagina=0):
        self.pila.append((modo, campo, clave, pagina))

    def volver(self):
        """True if a level was gone up; False if we were already at the root."""
        if len(self.pila) <= 1:
            return False

        self.pila.pop()
        return True

    def pasar_pagina(self):
        modo, campo, clave, pagina = self.pila[-1]
        self.pila[-1] = (modo, campo, clave, pagina + 1)

    # --- data --------------------------------------------------------------------------

    def visibles(self):
        return catalog.visibles(self.canales)

    def lista_actual(self):
        """The channels of the level we are on, already sorted."""
        _modo, campo, clave, _pagina = self.nivel

        if not campo:
            return catalog.ordenar(self.visibles())

        return catalog.ordenar(catalog.indexar(self.visibles(), campo).get(clave, list()))

    def playlist_canales(self):
        """The engine's own list, in the same shape as the catalogue's channels.

        The pl.m3u carries no logo and no category, checked, but its infohashes are the
        catalogue's own: crossing them gives two out of three entries their logo, their
        country and their language without asking the engine for anything else. The name
        kept is the list's, which is the one the user sees in AceServe.

        The index is cached and not the result: the list is assigned after the browser is
        built, and saving the result here would leave it empty forever."""
        if self._por_infohash is None:
            self._por_infohash = {c['infohash']: c for c in self.canales}

        return [dict(self._por_infohash.get(e['infohash']) or _SIN_FICHA,
                     nombre=e['nombre'], infohash=e['infohash'], grupo=e['grupo'])
                for e in catalog.playlist_visible(self.playlist)]

    # --- rows --------------------------------------------------------------------------

    def filas(self):
        modo = self.nivel[0]

        if modo == RAIZ:
            return self._filas_raiz()
        if modo == FACETA:
            return self._filas_faceta()
        if modo == GRUPOS:
            return self._filas_grupos()

        return self._filas_canales()

    def _filas_raiz(self):
        visibles = self.visibles()
        total = len(visibles)
        filas = [Fila(clave='todos', titulo='Todos los canales', valor=str(total),
                      icono=_icono('directo.png'),
                      plot=_plot_grupo(catalog.ordenar(visibles),
                                       f'Los {total} canales, ordenados por fiabilidad '
                                       'del enlace.'))]

        for campo, titulo in _FACETAS:
            cuantas = len(catalog.indexar(visibles, campo))
            filas.append(Fila(clave=campo, titulo=titulo, valor=str(cuantas),
                              icono=_icono(_ICONO_FACETA[campo]),
                              plot=f'Agrupa los {total} canales por este criterio.\n\n'
                                   f'[B]Pulsa OK[/B] para ver los {cuantas} grupos.'))

        # It goes with the other three and without a separator even though it is not
        # always there: that way the user who does not have it does not miss a gap, and
        # the one who does sees one more way of grouping and not a section from elsewhere.
        if self.playlist_disponible:
            # Counting over the raw entries and not over playlist_canales(): for a number
            # there is no need to build two thousand two hundred enriched dictionaries.
            grupos = len({e['grupo'] for e in catalog.playlist_visible(self.playlist)})
            filas.append(Fila(clave='playlist', titulo='Por grupos', valor=str(grupos),
                              icono=_icono('grupos.png'),
                              plot='Agrupa los canales como vienen agrupados de origen, '
                                   'con algunos que no salen en las otras listas.\n\n'
                                   f'[B]Pulsa OK[/B] para ver los {grupos} grupos.'))

        filas.append(Fila(clave='', titulo='', sep=True))
        filas.append(Fila(clave='actualizar', titulo='Actualizar la lista',
                          icono=_icono('actualizar.png'),
                          plot='Vuelve a bajar la lista completa. Tarda unos segundos.'))

        return filas

    def _filas_faceta(self):
        campo = self.nivel[1]
        indice = catalog.indexar(self.visibles(), campo)

        # The language is asked once and not once per row: there are up to 71 rows and
        # every ordenar() would ask Kodi for it on its own.
        idioma = catalog.idioma_preferido()

        # Yours first. In languages it is Kodi's, and in countries the country of that
        # language, which comes from the same table as the flags. Not applicable in
        # categories.
        preferido = idioma if campo == 'idiomas' else _BANDERA_IDIOMA.get(idioma, '')
        if campo == 'categorias':
            preferido = ''

        # In categories, a drawn icon and not the logo of one of the channels inside. It
        # was tried and it comes out badly for two measured reasons: at this size a
        # channel logo is a smudge while a line icon reads, and they are fourteen remote
        # images that delay the list's repaint on pressing, which is just when it shows.
        return [Fila(clave=clave, titulo=nombre, valor=str(len(canales)),
                     icono=_bandera(campo, clave) or _icono_categoria(clave),
                     plot=_plot_grupo(catalog.ordenar(canales, idioma),
                                      f'{len(canales)} canales en {nombre}.'))
                for clave, nombre, canales in catalog.facetas(indice, campo, preferido)]

    def _filas_grupos(self):
        grupos = dict()
        for canal in self.playlist_canales():
            grupos.setdefault(canal['grupo'], list()).append(canal)

        filas = list()
        for grupo in sorted(grupos, key=lambda g: (-len(grupos[g]),
                                                   catalog.sin_tildes(catalog.nombre_grupo(g)))):
            # The key is still the group exactly as the engine serves it, which is what
            # the filtering goes by; what is translated is only what is read.
            nombre = catalog.nombre_grupo(grupo)

            # The channels are not sorted, unlike the facets: this level is painted in the
            # order it arrives, and the sample has to match it.
            filas.append(Fila(clave=grupo, titulo=nombre, valor=str(len(grupos[grupo])),
                              icono=_icono_categoria(grupo),
                              plot=_plot_grupo(grupos[grupo],
                                               f'{len(grupos[grupo])} canales en {nombre}.')))

        return filas

    def _filas_canales(self):
        modo, campo, clave, pagina = self.nivel

        if campo == 'playlist':
            # Exact match and not 'no key means all': this level is only reached from a
            # group row, and that rule would turn a tampered url with no key into a dump
            # of the whole list.
            lista = [c for c in self.playlist_canales() if c['grupo'] == clave]
        else:
            lista = self.lista_actual()

        hasta = (pagina + 1) * POR_PAGINA
        filas = [_fila_canal(c) for c in lista[:hasta]]

        if len(lista) > hasta:
            filas.append(Fila(clave='mas', titulo=f'Ver más  ({hasta} de {len(lista)})',
                              icono=_icono('descargas.png'),
                              plot='Añade otros canales a la lista.'))

        if not filas:
            filas.append(Fila(clave='', titulo='No hay canales aquí', sep=True))

        return filas

    # --- header ------------------------------------------------------------------------

    def cabecera(self):
        modo, campo, clave, _pagina = self.nivel

        if modo == RAIZ:
            # Short because the subtitle gap is 376 px: the long phrase came out clipped.
            return 'Canales', f'{len(self.visibles())} en directo'
        if modo == GRUPOS:
            return 'Por grupos', 'Elige uno para ver sus canales'
        if modo == FACETA:
            return dict(_FACETAS)[campo], 'Elige uno para ver sus canales'

        if campo == 'playlist':
            return catalog.nombre_grupo(clave) if clave else 'Por grupos', 'Canales de este grupo'

        if not campo:
            return 'Todos los canales', 'Ordenados por fiabilidad'

        return catalog.etiqueta(campo, clave), dict(_FACETAS)[campo]


def _al_pulsar(exp, fila):
    modo = exp.nivel[0]

    if fila.clave == 'mas':
        exp.pasar_pagina()
        return None

    if modo == RAIZ:
        if fila.clave == 'todos':
            exp.entrar(CANALES)
        elif fila.clave == 'actualizar':
            return 'actualizar'
        elif fila.clave == 'playlist':
            exp.entrar(GRUPOS)
        else:
            exp.entrar(FACETA, campo=fila.clave)
        return 'inicio'

    if modo == FACETA:
        exp.entrar(CANALES, campo=exp.nivel[1], clave=fila.clave)
        return 'inicio'

    if modo == GRUPOS:
        exp.entrar(CANALES, campo='playlist', clave=fila.clave)
        return 'inicio'

    if fila.clave:
        exp.al_salir.append((fila.clave, fila.titulo, fila.icono))
        return 'cerrar'

    return None


def _al_menu(exp, fila):
    """Options of a channel row, from the Menu key or a long press.

    Only channel rows have them: every other row opens a list, and a favourite has to be
    something that plays."""
    if exp.nivel[0] != CANALES or fila.clave in ('mas', ''):
        return None

    entrada = {'infohash': fila.clave, 'titulo': fila.titulo, 'origen': 'canales',
               'motor': True,
               # The filler television set does not travel, just as when playing.
               'icono': fila.icono if fila.icono.startswith('http') else ''}
    k = history.clave(entrada)
    favorita = history.es_favorito(k)

    elegida = xbmcgui.Dialog().contextmenu([VER, QUITAR if favorita else ANADIR])

    if elegida == 0:
        return _al_pulsar(exp, fila)
    # A channel row does not show whether it is kept, so the notice is all the user sees.
    if elegida == 1 and favorita:
        if history.quitar_favorito(k):
            avisar(QUITADO)
    elif elegida == 1 and history.anadir_favorito(entrada):
        avisar(ANADIDO)

    return None


def _descargar(servidor, forzar=False):
    """(channels, reason) from the catalogue. The reason is '' if it went well.

    Cancelling is told apart from having no engine because the right message is a
    different one: telling somebody who has just pressed Cancel that no engine answers is
    lying to them."""
    if not forzar:
        guardados = catalog.leer(servidor.base)
        if guardados:
            return guardados, ''

    dialogo = xbmcgui.DialogProgress()
    dialogo.create(HEADING, 'Bajando la lista de canales…')

    try:
        canales = catalog.asegurar(servidor, progreso=dialogo, forzar=forzar)
        cancelado = dialogo.iscanceled()
    finally:
        dialogo.close()

    if canales:
        return canales, ''

    if cancelado:
        return list(), 'cancelado'

    # The version is cached as soon as it comes back positive, and 'Actualizar' runs in the
    # same process that downloaded the catalogue a moment ago. Without this, an engine that
    # dies while the window is open (the phone going to sleep, the app killed) is reported
    # as too old, which sends the user off to change an address that was right.
    servidor.invalidate()

    # An engine that answers but carries no catalogue is not the same as having no engine,
    # and the case is real: the 3.1.32 engine EKHorus installs on Windows answers
    # everything else but has no /search. Telling that user there is no engine would be
    # lying to them and sending them off to fix something that works.
    version = servidor.version
    if not version:
        return list(), 'sin_motor'

    # /search only exists from 3.2, and it is the version and not the answer that tells the
    # two apart: a 3.2 engine whose search fails answers 200 with an error inside, and an
    # unknown route comes back 500 rather than 404. Measured on a Fire TV and a phone on
    # 17-09-2026, both with the search of their own engine failing while everything else
    # worked, and both were being told their engine was too old. On that network the cause
    # was the ISP: with a VPN the same engine answered 1856 channels in a tenth of a second.
    return list(), 'sin_catalogo' if version_tuple(version) < (3, 2) else 'busqueda_falla'


def catalogo():
    """(channels, reason) as this screen gets them, for whoever needs them elsewhere: the saved
    list while it is good, and the download with its progress when it is not."""
    return _descargar(server)


def _sin_catalogo(motivo):
    """Explains why there is no catalogue and offers each platform's way out.

    The texts go in here, as in the control panel, and not in strings.po. That is not only
    for consistency: translate() returns an empty string when the string is not loaded,
    and a dialog with no line of text and an OK button tells nobody anything. Written
    here, that cannot happen."""
    from lib.utils import es_host_local, system_platform

    donde = f'{server.host}:{server.port}'

    if motivo == 'sin_catalogo':
        xbmcgui.Dialog().ok(HEADING,
            f'El motor de {donde} es demasiado antiguo.\n\n'
            'Hace falta uno de la serie 3.2: el de un móvil o un Docker. Se apunta en el '
            'Cuadro de mandos.')
        return

    if motivo == 'busqueda_falla':
        xbmcgui.Dialog().ok(HEADING,
            'No se puede obtener la lista, aunque sí se pudo conectar con el motor.\n'
            'Suele ser cosa de la operadora; prueba con una VPN.')
        return

    # It is said in few words because the Kodi dialog box only shows four lines: whatever
    # does not fit scrolls by itself and the user has to wait for it to go past to read the
    # whole thing.
    if not es_host_local(server.host):
        # Nothing on this device can start it.
        xbmcgui.Dialog().ok(HEADING,
            f'Sin motor en {donde} no hay canales.\n\n'
            'Arráncalo en ese aparato o revisa la dirección en el Cuadro de mandos.')
        return

    if system_platform == 'android':
        # The APK menu is named because from here there is no way of knowing whether the
        # engine application is installed, and not having it is exactly the case of
        # somebody who has just put EKHorus on and does not know a piece is missing.
        pregunta = (f'Sin motor en {donde} no hay canales.\n\n'
                    'Necesitas AceServe o AceStream arrancado. Si no los tienes, están en '
                    '[B]Descargar APKs[/B].')
        abrir = 'Abrir el motor'
    else:
        # Until this existed, the desktop text said "start it" and nothing in the addon
        # could: the engine only came up by playing something.
        pregunta = (f'Sin motor en {donde} no hay canales.\n\n'
                    'EKHorus lo arranca en este equipo. Si es la primera vez, antes lo descarga.')
        abrir = 'Arrancar'

    if xbmcgui.Dialog().yesno(HEADING, pregunta, yeslabel=abrir, nolabel='Ahora no'):
        # The road playback takes to get an engine up, and Channels again once it answers.
        # Through the plugin, as when playing: this window is on its way out.
        item = Item(action='arrancar_motor', luego='catalogo')
        xbmc.executebuiltin(f'RunPlugin(plugin://script.module.horus/?{item.tourl()})')


def mostrar_explorador(forzar=False):
    """Opens the browser. False if the window could not be built."""
    # A loop and not recursion: 'Actualizar' reopens the window, and with recursion every
    # press would add a frame to the stack forever.
    while True:
        # Everything up to here is silent: reading a list of 1700 channels off disk,
        # asking the engine which one it is and fetching its own playlist are a couple of
        # seconds with the menu frozen and nothing to look at. The spinner goes on before
        # any of it and comes off before the window, which is the one thing it must not
        # share the screen with.
        with ui_common.ocupado():
            canales, motivo = _descargar(server, forzar=forzar)

            exp = None
            if canales:
                exp = Explorador(canales,
                                 playlist_disponible=detect_engine() == ENGINE_ACESERVE)
                if exp.playlist_disponible:
                    exp.playlist = catalog.leer_playlist(server)
                    exp.playlist_disponible = bool(exp.playlist)

        if exp is None:
            if motivo != 'cancelado':
                _sin_catalogo(motivo)
            return True

        abierta, recargar = _abrir_ventana(exp)

        for infohash, nombre, logo in exp.al_salir:
            # The filler icon does not travel: if the channel had no logo, let the history
            # and the player go without one rather than with a generic television set.
            reproducir(infohash, nombre, logo if logo.startswith('http') else '')

        if not recargar:
            return abierta

        forzar = True


def _abrir_ventana(exp):
    """(it_opened, needs_reload) after the window closes."""
    estado = {'recargar': False, 'ventana': None}

    def al_pulsar(fila):
        resultado = _al_pulsar(exp, fila)

        if resultado == 'actualizar':
            estado['recargar'] = True
            return 'cerrar'

        return resultado

    def al_abrir(ventana):
        estado['ventana'] = ventana
        _cabecera(exp, ventana)

    def filas():
        # Repainting and changing level always go together, so the header is refreshed
        # here and not in every place that navigates. On the first paint the window is not
        # set yet, and al_abrir takes care of that.
        _cabecera(exp, estado['ventana'])
        return exp.filas()

    abierta = mostrar(
        titulo='Canales',
        subtitulo='',
        hacer_filas=filas,
        al_pulsar=al_pulsar,
        al_menu=lambda fila: _al_menu(exp, fila),
        al_volver=exp.volver,
        al_abrir=al_abrir,
        pista=PISTA)

    return abierta, estado['recargar']


def _cabecera(exp, ventana):
    if ventana is None:
        return

    titulo, sub = exp.cabecera()
    en_canales = exp.nivel[0] == CANALES
    ventana.set_cabecera(titulo=titulo, subtitulo=sub,
                         pista=PISTA_CANALES if en_canales else PISTA,
                         estado=ESTADO_CANALES if en_canales else '')


def actualizar():
    """Downloads the catalogue again. True if it brought anything."""
    canales, motivo = _descargar(server, forzar=True)

    if not canales:
        if motivo != 'cancelado':
            _sin_catalogo(motivo)
        return False

    # Only AceServe serves /pl.m3u; asking the other one for it is a wasted request.
    if detect_engine() == ENGINE_ACESERVE:
        catalog.leer_playlist(server, forzar=True)

    return True


def filas_clasicas(item):
    """Directory items for the route with no window of its own.

    Every press relaunches the addon, so the level travels in the item itself."""
    canales, motivo = _descargar(server)

    if not canales:
        if motivo != 'cancelado':
            _sin_catalogo(motivo)
        return list()

    modo = item.modo or RAIZ

    # Knowing whether there is an own list costs a request to the engine, and on the
    # classic route every level relaunches the whole addon. It only matters at the root,
    # which is where that row is painted; inside the list it is already known to exist
    # because that is where it was entered from.
    exp = Explorador(canales)

    if modo == RAIZ:
        exp.playlist_disponible = detect_engine() == ENGINE_ACESERVE
        if exp.playlist_disponible:
            exp.playlist = catalog.leer_playlist(server)
            exp.playlist_disponible = bool(exp.playlist)
    elif modo == GRUPOS or item.campo == 'playlist':
        exp.playlist = catalog.leer_playlist(server)

    # The level travels through the url, so even though the addon writes it, it is best
    # not to trust it: a tampered item must not bring the whole menu down.
    try:
        pagina = max(0, int(item.pagina or 0))
    except (TypeError, ValueError):
        pagina = 0

    exp.pila = [(modo, item.campo or '', item.clave or '', pagina)]

    itemlist = list()

    for fila in exp.filas():
        if fila.sep:
            continue

        if modo == CANALES and fila.clave not in ('mas', ''):
            # What plays travels as the window sends it, with no filler icon and no panel text,
            # which would end up in the history, in My favourites and as the video's plot. The
            # row still paints both, from the two fields the listing reads first.
            logo = fila.icono if fila.icono.startswith('http') else ''
            itemlist.append(Item(label=fila.titulo, action='play', infohash=fila.clave, icon=logo,
                                 motor=1, origen='canales', icono_fila=fila.icono,
                                 plot_fila=fila.plot))
            continue

        siguiente = _siguiente_nivel(exp, modo, fila, pagina)
        if siguiente is not None:
            itemlist.append(siguiente)

    return itemlist


def _siguiente_nivel(exp, modo, fila, pagina):
    """The directory Item a row leads to on the classic route."""
    etiqueta = fila.titulo if not fila.valor else f'{fila.titulo}  ({fila.valor})'

    if fila.clave == 'mas':
        return Item(label=fila.titulo, action='catalogo', modo=modo, campo=exp.nivel[1],
                    clave=exp.nivel[2], pagina=pagina + 1, icon=fila.icono, plot=fila.plot)

    if modo == RAIZ:
        if fila.clave == 'todos':
            return Item(label=etiqueta, action='catalogo', modo=CANALES,
                        icon=fila.icono, plot=fila.plot)
        if fila.clave == 'playlist':
            return Item(label=etiqueta, action='catalogo', modo=GRUPOS,
                        icon=fila.icono, plot=fila.plot)
        if fila.clave == 'actualizar':
            return Item(label=etiqueta, action='catalogo_refresh', icon=fila.icono,
                        plot=fila.plot, isFolder=False)
        return Item(label=etiqueta, action='catalogo', modo=FACETA, campo=fila.clave,
                    icon=fila.icono, plot=fila.plot)

    if modo == FACETA:
        return Item(label=etiqueta, action='catalogo', modo=CANALES, campo=exp.nivel[1],
                    clave=fila.clave, icon=fila.icono, plot=fila.plot)

    if modo == GRUPOS:
        return Item(label=etiqueta, action='catalogo', modo=CANALES, campo='playlist',
                    clave=fila.clave, icon=fila.icono, plot=fila.plot)

    logger(f'channels_ui: fila sin destino en {modo}: {fila.clave}')
    return None
