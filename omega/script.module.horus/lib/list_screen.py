# -*- coding: utf-8 -*-
# EKHorus - List and panel window, shared by every list screen of the addon.
#
# The caller passes a function that returns the rows and another that says what to do
# when they are pressed; the text swiping and the remote navigation live here, and the
# right-hand panel follows the focused row from the skin itself, with no Python behind it.

import collections

import xbmcgui

from lib.utils import echar_pestillo, logger, quitar_pestillo, runtime_path
from lib.ui_common import Deslizador

ID_LISTA = 200
ID_CERRAR = 100
ID_BOTON1 = 103
ID_BOTON2 = 104
ID_BARRA = 300
ID_TEXTO = 301

_PESTILLO = 'ekhorus.lista'

_ATRAS = (9, 10, 92)  # ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, ACTION_NAV_BACK
# ACTION_CONTEXT_MENU: the Menu key, C and a long OK. Kodi also turns a right click or a long
# press on the list into this one for a Python window, checked in its WindowXML.cpp.
_MENU = 117

# pill: (text, 'on' | 'off' | 'gris'), or None if the row carries a loose value
Fila = collections.namedtuple(
    'Fila', 'clave titulo pista icono valor pastilla plot sep',
    defaults=('', '', '', None, '', False))

ORO = 'FFFFB70F'


class Pantalla(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.titulo = ''
        self.subtitulo = ''
        self.estado = ''
        self.pista = ''          # remote legend, different on each screen
        self.botones = ()        # ((label, function), ...), up to two
        self.hacer_filas = None  # callable -> [Fila]
        self.al_pulsar = None    # callable(Fila) -> 'cerrar' closes, 'inicio' repaints at top
        # callable(Fila), from Menu or a long press; None repaints nothing, and ('refrescar', n)
        # repaints with the cursor on row n, where an option that moves the row has put it
        self.al_menu = None
        self.al_volver = None    # callable() -> True if Back has gone up a level
        self.al_abrir = None     # callable(window) once painted
        self._filas = list()
        self._dedo = None

    # --- life cycle --------------------------------------------------------------------

    def onInit(self):
        # Kodi may call here more than once (when reloading the skin); without this guard
        # the rows would be duplicated.
        if self._filas:
            return

        self._dedo = Deslizador(self, ID_BARRA, ID_TEXTO)
        self.setProperty('pl_titulo', self.titulo)
        self.setProperty('pl_sub', self.subtitulo)
        self.setProperty('pl_estado', self.estado)
        self.setProperty('pl_pista', self.pista)
        for n, (etiqueta, _) in enumerate(self.botones[:2]):
            self.setProperty('pl_b1' if n == 0 else 'pl_b2', etiqueta)

        self._pintar(0, enfocar=True)

        if self.al_abrir is not None:
            self.al_abrir(self)

    def set_cabecera(self, titulo=None, subtitulo=None, estado=None, pista=None):
        """Changes the texts at the top without touching the list.

        A multi-level window needs it, where the title says where you are."""
        for propiedad, valor in (('pl_titulo', titulo), ('pl_sub', subtitulo),
                                 ('pl_estado', estado), ('pl_pista', pista)):
            if valor is not None:
                self.setProperty(propiedad, valor)

    def set_boton(self, n, texto):
        """Changes the text of header button n (0 or 1), for a button that switches something."""
        self.setProperty('pl_b1' if n == 0 else 'pl_b2', texto)

    def repintar(self, seleccion=0):
        self._pintar(seleccion, enfocar=True)

    # --- painting ----------------------------------------------------------------------

    def _pintar(self, seleccion=None, enfocar=False):
        control = self.getControl(ID_LISTA)
        if seleccion is None:
            seleccion = control.getSelectedPosition()

        self._filas = list(self.hacer_filas())
        items = list()

        for fila in self._filas:
            item = xbmcgui.ListItem(label=fila.titulo)
            # The panel reads this straight from the focused item, in the XML. Until 20-09-2026
            # a thread polled the focus and wrote window properties instead, and its xbmcgui
            # calls froze every Python of Kodi while Kodi installed an addon modally: a
            # repository served from Python (Elementum's) could not answer Kodi and the install
            # failed. The skin needs no thread, and follows the finger and the wheel as well.
            item.setProperty('f_plot', fila.plot)
            if fila.sep:
                item.setProperty('f_tipo', 'sep')
            else:
                item.setProperty('f_icono', fila.icono)
                item.setProperty('f_pista', fila.pista)
                if fila.pastilla:
                    item.setProperty('f_pastilla', fila.pastilla[0])
                    item.setProperty('f_estado', fila.pastilla[1])
                elif fila.valor:
                    item.setLabel2(fila.valor)
            items.append(item)

        control.reset()
        control.addItems(items)

        # When the last row has just been deleted the position is past the end, and the cursor
        # goes to the new last row instead of back to the top, where Kodi would send it.
        if items:
            control.selectItem(min(max(seleccion, 0), len(items) - 1))

        if enfocar:
            self.setFocusId(ID_LISTA)

    # --- actions -----------------------------------------------------------------------

    def onAction(self, action):
        if self._dedo is not None and self._dedo.accion(action):
            return

        if action.getId() == _MENU:
            self._menu()
            return

        # A Python WindowXMLDialog does not close by itself with Back.
        if action.getId() in _ATRAS:
            # With al_volver the window has several levels: Back goes up one, and only
            # closes when there is nowhere left to go up to. Without it, it behaves as
            # it always did.
            if self.al_volver is not None and self.al_volver():
                self.repintar()
                return

            self.close()

    def onClick(self, controlId):
        if controlId == ID_CERRAR:
            self.close()
            return

        if controlId in (ID_BOTON1, ID_BOTON2):
            n = 0 if controlId == ID_BOTON1 else 1
            if n < len(self.botones) and self.botones[n][1]() == 'refrescar':
                self.repintar()
            return

        if controlId != ID_LISTA:
            return

        pos, fila = self._fila_elegida()
        if fila is None:
            return

        self._responder(self.al_pulsar(fila), pos)

    def _menu(self):
        """The options of the row under the cursor, if the screen has any.

        Only with the focus on the list: from the X or a header button no row is being
        pointed at, and acting on the one left selected behind would be a surprise."""
        if self.al_menu is None or self.getFocusId() != ID_LISTA:
            return

        pos, fila = self._fila_elegida()
        if fila is None:
            return

        resultado = self.al_menu(fila)
        if isinstance(resultado, tuple):
            resultado, pos = resultado

        # Most options change nothing on screen, such as cancelling or keeping a channel, and
        # painting a page of 300 channels again for them is a blink and a wait on a TV box.
        if resultado in ('cerrar', 'inicio', 'refrescar'):
            self._responder(resultado, pos)
        else:
            self.setFocusId(ID_LISTA)

    def _fila_elegida(self):
        """(position, row) under the cursor, or (-1, None) if there is none to act on."""
        if not self._filas:
            return -1, None

        pos = self.getControl(ID_LISTA).getSelectedPosition()
        if not 0 <= pos < len(self._filas) or self._filas[pos].sep:
            return -1, None

        return pos, self._filas[pos]

    def _responder(self, resultado, pos):
        if resultado == 'cerrar':
            self.close()
            return

        # The focus is set here on purpose: on returning from a dialog it belongs to
        # the dialog just closed, and has to go back to the row it was left from. With
        # 'inicio' it is the other way round: the level has changed and the list is
        # another one, so keeping the position would leave the selection in the middle
        # of a new list.
        self.repintar(0 if resultado == 'inicio' else pos)


def mostrar(titulo, subtitulo, hacer_filas, al_pulsar, botones=(), estado='',
            pista='[B]OK[/B] abre    ·    [B]Derecha[/B] lee    ·    [B]Atrás[/B] cierra',
            al_volver=None, al_abrir=None, al_menu=None):
    """Opens the window. Returns False if it could not, to fall back to the classic list."""
    if not echar_pestillo(_PESTILLO):
        logger('list_screen: ya hay una ventana abierta, no se abre otra')
        return True

    ventana = None
    try:
        # Inside the try: if it blew up while being built, the latch cannot stay closed
        ventana = Pantalla('ekhorus_lista.xml', runtime_path, 'Default', '1080i')
        ventana.titulo = titulo
        ventana.subtitulo = subtitulo
        ventana.estado = estado
        ventana.pista = pista
        ventana.botones = tuple(botones)[:2]
        ventana.hacer_filas = hacer_filas
        ventana.al_pulsar = al_pulsar
        ventana.al_volver = al_volver
        ventana.al_abrir = al_abrir
        ventana.al_menu = al_menu
        ventana.doModal()
        return True

    except Exception as e:
        logger(f'list_screen: {e}', 'error')
        return False

    finally:
        # doModal does not free the controls, and in Kodi those are textures in memory
        del ventana
        quitar_pestillo(_PESTILLO)
