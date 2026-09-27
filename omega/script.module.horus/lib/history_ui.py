# -*- coding: utf-8 -*-
# EKHorus - The History and My favourites screens.
"""The links the user has opened and the ones kept, in the addon's list window.

What the classic route says too comes from strings.po, so that both always say the same. What
only this window paints lives here, as in the channels browser.
"""
import os
from datetime import date, datetime

import xbmc
import xbmcgui

from lib import elementum, history, playback_watch
from lib.list_screen import Fila, mostrar
from lib.ui_common import GRIS, VERDE, color
from lib.utils import HEADING, Item, icon_path, runtime_path, translate

ANADIR = translate(30135)
QUITAR = translate(30136)
RENOMBRAR = translate(30137)
ANADIDO = translate(30138)
QUITADO = translate(30145)
BORRAR = translate(30048)
ABRIR_ELEMENTUM = translate(30149)
MOVER = {'subir': translate(30172), 'bajar': translate(30173), 'principio': translate(30174)}

VER = 'Verlo ahora'
SIN_HISTORIAL = 'Todavía no has abierto ningún enlace'
SIN_FAVORITOS = 'Todavía no tienes favoritos'

# With the list empty the panel says what the screen is for, since there is no row to explain.
PLOT_SIN_HISTORIAL = (
    'Aquí se apuntan solos los últimos 300 enlaces que abras, vengan de donde vengan: Canales, '
    'Buscar enlaces, Reproducir identificador, Ver en el móvil o las llamadas de otros addons.\n\n'
    'Lo último que abres sube arriba. Con la tecla [B]Menú[/B], o manteniendo pulsado, podrás '
    'borrar una fila o guardarla en Mis favoritos.\n\n'
    'Con el botón [B]Guardar todo[/B] de arriba, se guardan todos los enlaces de AceStream que se '
    'reproducen en Kodi, también los que no abres desde EKHorus.')

# The "Guardar todo" switch (lib/playback_watch.py). The question only comes when switching on.
GUARDAR_TODO = 'Guardar todo'
# The skin's yes/no dialog shows four lines (855 px of NotoSans 30) and scrolls anything longer,
# which hid the first sentence. This one takes three.
ANOTAR_PREGUNTA = ('Guarda todos los enlaces de AceStream que Kodi reproduce, como los de listas de '
                   'la sección TV.\n¿Lo enciendo?')
PLOT_ANOTAR = (
    'Encendido, el historial guarda todos los enlaces de AceStream que se reproducen en Kodi, '
    'también los que no abres desde EKHorus.\n\n'
    'Lo que abres desde EKHorus se guarda siempre.')
ANOTANDO = 'Se guardarán todos los enlaces de AceStream que se vean en Kodi'
SIN_ANOTAR = 'Solo se guardará lo que abras desde EKHorus'
PLOT_SIN_FAVORITOS = (
    'Aquí tendrás a mano los enlaces que guardes, con el nombre que tú les pongas.\n\n'
    'Se guardan desde [B]Canales[/B] y desde el [B]Historial[/B]. Ponte sobre uno, pulsa la tecla '
    '[B]Menú[/B] del mando, o mantén pulsado, y elige [B]Añadir a Mis favoritos[/B].\n\n'
    'Aquí mismo, con esas opciones, podrás renombrarlos, cambiarlos de orden y quitarlos.')

# Measured with the skin's font against the 1130 px of their bar: the History one comes to 1111.
# Saying "manteniendo pulsado", as the other texts do, it came to 1213.
ESTADO_HISTORIAL = 'Con [B]Menú[/B] o pulsación larga puedes añadirlo a Mis favoritos o borrarlo'
ESTADO_FAVORITOS = 'Con [B]Menú[/B] o pulsación larga puedes renombrarlo, moverlo o quitarlo'

# "OK lo abre" left 2 px free of the 574 the legend gets.
PISTA = '[B]OK[/B] lo ve    ·    [B]Menú[/B] opciones    ·    [B]Atrás[/B] cierra'
PISTA_VACIA = '[B]Atrás[/B] cierra'

# Gold on the grey pill: the green and red ones say whether something works, and this one
# says nothing of the sort.
_FAVORITO = ('[COLOR FFFFB70F]Favorito[/COLOR]', 'gris')


def _icono(nombre):
    return os.path.join(runtime_path, 'resources', 'media', nombre)


def avisar(texto):
    xbmcgui.Dialog().notification(HEADING, texto, icon_path, 3000)


def _cuando(fecha):
    """'hoy a las 21:34', 'ayer a las 09:05' or the bare date, in local time."""
    if not fecha:
        return ''

    try:
        momento = datetime.fromtimestamp(fecha)
    except (OverflowError, OSError, ValueError):
        # A date no clock could have written. Each platform refuses it with a different error.
        return ''

    dias = (date.today() - momento.date()).days

    if dias == 0:
        return momento.strftime('hoy a las %H:%M')
    if dias == 1:
        return momento.strftime('ayer a las %H:%M')

    return momento.strftime('%d/%m/%Y')


def _enlace_legible(entrada):
    tipo, valor = history.enlace(entrada)

    # The kind goes on a line of its own. Beside it, the forty characters reached the edge of the
    # panel, and Kodi, which rounds every letter to whole pixels, sent the last one down alone.
    if tipo == 'id':
        return f'acestream://\n{valor}'
    if tipo == 'infohash':
        return f'infohash\n{valor}'

    return valor


def _pista(entrada):
    partes = (history.ORIGENES.get(entrada['origen'], ''), _cuando(entrada['fecha']))
    return '  ·  '.join(p for p in partes if p)


def _plot(entrada, fecha_se_llama, favorita=False):
    lineas = [history.titulo(entrada), '']

    origen = history.ORIGENES.get(entrada['origen'])
    if origen:
        lineas.append(f'[B]Viene de[/B]  {origen}')
    if entrada['fecha']:
        lineas.append(f'[B]{fecha_se_llama}[/B]  {_cuando(entrada["fecha"])}')

    original = entrada.get('original')
    if original and original != entrada['titulo']:
        lineas.append(f'[B]Nombre original[/B]  {original}')

    if favorita:
        lineas.append('[B]Está en Mis favoritos[/B]')

    lineas += ['', f'[COLOR FF808080]{_enlace_legible(entrada)}[/COLOR]']

    return '\n'.join(lineas)


def _fila(entrada, pista, plot, favorita=False):
    return Fila(clave=history.clave(entrada),
                titulo=history.titulo(entrada),
                pista=pista,
                # With no logo, the 48 px television set and not the addon icon, as in Channels.
                icono=entrada['icono'] or _icono('directo.png'),
                pastilla=_FAVORITO if favorita else None,
                plot=plot)


def _cabecera(estado):
    # The first paint happens before the window is handed over, so the count waits for it. With
    # no rows, the bar at the bottom stops talking about them.
    if estado['ventana'] is not None:
        estado['ventana'].set_cabecera(subtitulo=estado['sub'],
                                       estado='' if estado['vacio'] else estado['pie'],
                                       pista=PISTA_VACIA if estado['vacio'] else PISTA)


def _ver(entrada, origen='', con_elementum=False):
    """Sends the entry to the addon itself, to play it or to hand it to Elementum.

    It is called once the window has closed: RunPlugin does not wait, and firing it with the
    window open would leave the progress dialog on top of the video."""
    item = history.item_para_ver(entrada, origen)
    if con_elementum:
        item.action = 'elementum'
    xbmc.executebuiltin(f'RunPlugin(plugin://script.module.horus/?{item.tourl()})')


def _abre_elementum(entrada):
    """True if the entry's menu offers Elementum, which takes a magnet or a .torrent and has to
    be installed."""
    tipo, valor = history.enlace(entrada)
    return tipo == 'url' and elementum.puede_abrir(valor) and elementum.instalado()


def _si_no(encendido):
    return color('Sí', VERDE) if encendido else color('No', GRIS)


def alternar_anotar_fuera():
    """Switches "Guardar todo" the other way. Returns whether it is on afterwards."""
    encendido = not playback_watch.activado()

    if encendido and not xbmcgui.Dialog().yesno(HEADING, ANOTAR_PREGUNTA):
        return False

    playback_watch.poner_activado(encendido)
    avisar(ANOTANDO if encendido else SIN_ANOTAR)
    return encendido


def mostrar_historial():
    """Opens the History. False if the window could not be built."""
    estado = {'ventana': None, 'ver': None, 'elementum': False, 'sub': '', 'vacio': False,
              'pie': ESTADO_HISTORIAL}
    porclave = dict()

    def filas():
        entradas = history.historial()
        favoritas = history.claves_favoritas()
        porclave.clear()

        salida = list()
        for entrada in entradas:
            k = history.clave(entrada)
            porclave[k] = entrada
            salida.append(_fila(entrada, _pista(entrada),
                                _plot(entrada, 'Última vez', k in favoritas), k in favoritas))

        estado['sub'] = f'{len(entradas)} de {history.HISTORIAL_MAX}'
        estado['vacio'] = not entradas
        _cabecera(estado)

        return salida or [Fila(clave='', titulo=SIN_HISTORIAL, sep=True, plot=PLOT_SIN_HISTORIAL)]

    def al_abrir(ventana):
        estado['ventana'] = ventana
        _cabecera(estado)

    def al_pulsar(fila):
        estado['ver'] = porclave[fila.clave]
        return 'cerrar'

    def al_menu(fila):
        entrada = porclave[fila.clave]
        favorita = history.es_favorito(fila.clave)

        # By what each option does and not by its text, which is empty for all of them when
        # strings.po is not loaded.
        opciones = [(VER, 'ver')]
        if _abre_elementum(entrada):
            opciones.append((ABRIR_ELEMENTUM, 'elementum'))
        opciones += [(QUITAR, 'quitar') if favorita else (ANADIR, 'anadir'), (BORRAR, 'borrar')]

        elegida = xbmcgui.Dialog().contextmenu([texto for texto, _ in opciones])
        if elegida < 0:
            return None

        accion = opciones[elegida][1]
        if accion == 'ver':
            return al_pulsar(fila)
        if accion == 'elementum':
            estado['ver'], estado['elementum'] = entrada, True
            return 'cerrar'
        if accion == 'quitar':
            if history.quitar_favorito(fila.clave):
                avisar(QUITADO)
        elif accion == 'anadir':
            if history.anadir_favorito(entrada):
                avisar(ANADIDO)
        else:
            history.borrar(fila.clave)

        # The row has gained or lost its pill, or is gone.
        return 'refrescar'

    def borrar_todo():
        if not porclave:
            avisar('El historial ya está vacío')
            return None

        if not xbmcgui.Dialog().yesno(HEADING, translate(30051)):
            return None

        history.vaciar()
        return 'refrescar'

    def anotar_fuera():
        # Only the button's text changes: the rows are the same.
        encendido = alternar_anotar_fuera()
        if estado['ventana'] is not None:
            estado['ventana'].set_boton(1, f'{GUARDAR_TODO}: {_si_no(encendido)}')

    abierta = mostrar(
        titulo=translate(30037),
        subtitulo='',
        hacer_filas=filas,
        al_pulsar=al_pulsar,
        al_menu=al_menu,
        al_abrir=al_abrir,
        botones=(('Borrar todo', borrar_todo),
                 (f'{GUARDAR_TODO}: {_si_no(playback_watch.activado())}', anotar_fuera)),
        estado=ESTADO_HISTORIAL,
        pista=PISTA)

    if estado['ver'] is not None:
        _ver(estado['ver'], con_elementum=estado['elementum'])

    return abierta


def mostrar_favoritos():
    """Opens My favourites. False if the window could not be built."""
    estado = {'ventana': None, 'ver': None, 'elementum': False, 'sub': '', 'vacio': False,
              'pie': ESTADO_FAVORITOS}
    porclave = dict()

    def filas():
        entradas = history.favoritos()
        porclave.clear()

        salida = list()
        for entrada in entradas:
            porclave[history.clave(entrada)] = entrada
            salida.append(_fila(entrada, history.ORIGENES.get(entrada['origen'], ''),
                                _plot(entrada, 'Guardado')))

        estado['sub'] = (f'{len(entradas)} guardado' if len(entradas) == 1
                         else f'{len(entradas)} guardados')
        estado['vacio'] = not entradas
        _cabecera(estado)

        # One row and not two. The second said where they are kept from, which was too long for the
        # panel title and now goes in the text.
        return salida or [Fila(clave='', titulo=SIN_FAVORITOS, sep=True, plot=PLOT_SIN_FAVORITOS)]

    def al_abrir(ventana):
        estado['ventana'] = ventana
        _cabecera(estado)

    def al_pulsar(fila):
        estado['ver'] = porclave[fila.clave]
        return 'cerrar'

    def al_menu(fila):
        entrada = porclave[fila.clave]

        opciones = [(VER, 'ver')]
        if _abre_elementum(entrada):
            opciones.append((ABRIR_ELEMENTUM, 'elementum'))
        opciones.append((RENOMBRAR, 'renombrar'))
        # porclave keeps the order the rows are painted in.
        opciones += [(MOVER[m], m) for m in history.movimientos(list(porclave), fila.clave)]
        opciones.append((QUITAR, 'quitar'))

        elegida = xbmcgui.Dialog().contextmenu([texto for texto, _ in opciones])
        if elegida < 0:
            return None

        accion = opciones[elegida][1]
        if accion == 'ver':
            return al_pulsar(fila)
        if accion == 'elementum':
            estado['ver'], estado['elementum'] = entrada, True
            return 'cerrar'
        if accion == 'renombrar':
            nombre = xbmcgui.Dialog().input(translate(30139), entrada['titulo'])
            return 'refrescar' if history.renombrar_favorito(fila.clave, nombre) else None
        if accion in MOVER:
            puesto = history.mover_favorito(fila.clave, accion)
            # The cursor goes with the row, so that up can be pressed again. If it could not
            # move, the file changed under the list, which is painted again as it is now.
            return 'refrescar' if puesto is None else ('refrescar', puesto)
        if history.quitar_favorito(fila.clave):
            return 'refrescar'

        return None

    abierta = mostrar(
        titulo=translate(30133),
        subtitulo='',
        hacer_filas=filas,
        al_pulsar=al_pulsar,
        al_menu=al_menu,
        al_abrir=al_abrir,
        estado=ESTADO_FAVORITOS,
        pista=PISTA)

    if estado['ver'] is not None:
        _ver(estado['ver'], origen='favoritos', con_elementum=estado['elementum'])

    return abierta


def items_historial():
    """History rows for the classic route, which is a plain Kodi listing.

    The "Guardar todo" switch goes first even with nothing saved, which is just when somebody
    would want to switch it on. It says what it does in full, as in the settings."""
    entradas = history.historial()
    items = [Item(label=f'{translate(30171)}: {_si_no(playback_watch.activado())}',
                  action='anotar_fuera', plot=PLOT_ANOTAR, isFolder=False)]

    if not entradas:
        return items + [Item(label=SIN_HISTORIAL, action='')]

    items.append(Item(label=f'[B]{translate(30049)}[/B]', action='del_historial', isFolder=False))

    for entrada in entradas:
        items.append(_item_clasico(entrada, _pista(entrada), hist=history.clave(entrada),
                                   origen_fila=entrada['origen']))

    return items


def items_favoritos():
    """My favourites rows for the classic route."""
    entradas = history.favoritos()

    if not entradas:
        return [Item(label=SIN_FAVORITOS, action='')]

    return [_item_clasico(e, history.ORIGENES.get(e['origen'], ''), origen='favoritos',
                          fav=history.clave(e))
            for e in entradas]


def _item_clasico(entrada, pista, origen='', **marca):
    """A row that plays the entry, with the marks its context menu goes by.

    The label is the readable one, which for a link with no name is made up. The name itself
    travels apart in 'nombre', so that a made-up label never becomes the video title."""
    item = history.item_para_ver(entrada, origen)
    item.nombre = entrada['titulo']
    item.label = history.titulo(entrada)

    if pista:
        item.label += f'  [COLOR FF8A97A5]{pista}[/COLOR]'

    for campo, valor in marca.items():
        setattr(item, campo, valor)

    return item
