# -*- coding: utf-8 -*-
# EKHorus - The guide inside Kodi.
#
# Two windows: the one that asks whether to open it in the browser or read it here, and
# the reader, with the index of sections on the left and the text on the right.
#
# The text is NOT written here: it comes from resources/guia.json, which build_guia.py
# generates out of index.html. That way the guide inside and the one on the web say the
# same thing, word for word. If index.html is touched, the generator must be run again.

import json
import os
import threading

import xbmc
import xbmcgui

from lib.utils import (HEADING, echar_pestillo, logger, quitar_pestillo, runtime_path)
from lib.ui_common import Deslizador, clasica

ID_LISTA = 200
ID_CERRAR = 100
ID_WEB = 103
ID_BARRA = 300
ID_TEXTO = 301
ID_ELEGIR_WEB = 110
ID_ELEGIR_AQUI = 111

_PESTILLO = 'ekhorus.guia'
SONDEO_MS = 200

_ATRAS = (9, 10, 92)  # ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, ACTION_NAV_BACK


def _media(nombre):
    return os.path.join(runtime_path, 'resources', 'media', nombre)


def _cargar():
    with open(os.path.join(runtime_path, 'resources', 'guia.json'), encoding='utf-8') as f:
        guia = json.load(f)

    # An empty guide would leave the list with no rows and the focus with nowhere to go.
    # Better to fall over here and send the user to the web than to open a dead window.
    if not guia or not all(s.get('titulo') for s in guia):
        raise ValueError('guia.json no trae apartados')

    return guia


def _cuenta(n):
    """How many texts hang from the section. Only the number: written out in full it does
    not fit, and next to the title of an index it is already understood."""
    return str(n) if n else ''


class Elector(xbmcgui.WindowXMLDialog):
    """Web or here. Returns the choice in an attribute because doModal() returns nothing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.eleccion = None

    def onAction(self, action):
        if action.getId() in _ATRAS:
            self.close()

    def onClick(self, controlId):
        if controlId == ID_ELEGIR_WEB:
            self.eleccion = 'web'
        elif controlId == ID_ELEGIR_AQUI:
            self.eleccion = 'aqui'
        self.close()


class Lector(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guia = list()        # filled in by mostrar() before doModal()
        self._abiertas = set()    # expanded sections
        self._filas = list()
        self._cerrando = False
        self._pintado = None
        self._dedo = None

    # --- life cycle --------------------------------------------------------------------

    def onInit(self):
        # Kodi may call here more than once (when reloading the skin); without this guard
        # the rows would be duplicated and a second thread would start.
        if self._filas:
            return

        self._dedo = Deslizador(self, ID_BARRA, ID_TEXTO)
        self._pintar(0, enfocar=True)
        self._refrescar_panel(forzar=True)
        threading.Thread(target=self._bucle_foco, daemon=True).start()

    def close(self):
        self._cerrando = True
        super().close()

    # --- painting ----------------------------------------------------------------------

    def _construir_filas(self):
        filas = list()
        for s, seccion in enumerate(self.guia):
            filas.append(('seccion', s, -1))
            if s in self._abiertas:
                filas.extend(('entrada', s, e) for e in range(len(seccion['entradas'])))

        return filas

    def _pintar(self, seleccion=None, enfocar=False):
        control = self.getControl(ID_LISTA)
        if seleccion is None:
            seleccion = control.getSelectedPosition()

        self._filas = self._construir_filas()
        items = list()

        for tipo, s, e in self._filas:
            seccion = self.guia[s]
            if tipo == 'seccion':
                item = xbmcgui.ListItem(label=f"{seccion['num']}  {seccion['titulo']}")
                item.setProperty('g_tipo', 'seccion')
                item.setProperty('g_icono', _media(seccion['icono']))
                item.setProperty('g_pista', '' if s in self._abiertas
                                 else _cuenta(len(seccion['entradas'])))
            else:
                item = xbmcgui.ListItem(label=seccion['entradas'][e]['titulo'])
                item.setProperty('g_tipo', 'entrada')
            items.append(item)

        control.reset()
        control.addItems(items)

        if 0 <= seleccion < len(items):
            control.selectItem(seleccion)

        if enfocar:
            self.setFocusId(ID_LISTA)

    def _refrescar_panel(self, forzar=False):
        if self.getFocusId() != ID_LISTA or not self._filas:
            return

        # The thread may read just while the main thread rebuilds the list, so the position
        # is checked against the rows before indexing.
        pos = self.getControl(ID_LISTA).getSelectedPosition()
        if not 0 <= pos < len(self._filas) or (pos == self._pintado and not forzar):
            return

        self._pintado = pos
        tipo, s, e = self._filas[pos]
        seccion = self.guia[s]

        if tipo == 'seccion':
            titulo = f"{seccion['num']}  {seccion['titulo']}"
            # Almost every section brings its own text; the ones that do not list what they
            # are made of, so that focusing them says something
            cuerpo = seccion['cuerpo'] or '\n'.join(f"·  {x['titulo']}"
                                                    for x in seccion['entradas'])
        else:
            titulo = seccion['entradas'][e]['titulo']
            cuerpo = seccion['entradas'][e]['cuerpo']

        self.setProperty('g_titulo', titulo)
        self.setProperty('g_cuerpo', cuerpo)

    def _bucle_foco(self):
        monitor = xbmc.Monitor()

        while not self._cerrando and not monitor.abortRequested():
            try:
                self._refrescar_panel()
            except Exception as e:
                # The window may have been closed between the read and the painting
                logger(f'guide_ui: bucle de foco: {e}')
            if monitor.waitForAbort(SONDEO_MS / 1000):
                break

    # --- actions -----------------------------------------------------------------------

    def onAction(self, action):
        # Swiping over the text turns pages. The list keeps its own gestures, so what gets
        # this far is what happened outside it.
        if self._dedo is not None and self._dedo.accion(action):
            return

        # A Python WindowXMLDialog does not close by itself with Back.
        if action.getId() in _ATRAS:
            self.close()

    def onClick(self, controlId):
        if controlId == ID_CERRAR:
            self.close()
            return

        if controlId == ID_WEB:
            from lib import espakodi_installer
            espakodi_installer.open_guia()
            return

        if controlId != ID_LISTA or not self._filas:
            return

        pos = self.getControl(ID_LISTA).getSelectedPosition()
        if not 0 <= pos < len(self._filas):
            return

        tipo, s, _e = self._filas[pos]
        if tipo != 'seccion' or not self.guia[s]['entradas']:
            # A tap moves the selection and presses at the same time, so the panel
            # thread does not see the new row before the focus goes; it is painted here.
            self._refrescar_panel(forzar=True)
            # There is nothing to expand: the focus moves to the text, the only thing left
            self.setFocusId(ID_TEXTO)
            return

        self._abiertas.symmetric_difference_update({s})
        # The row of the section does not move when expanding: what grows goes underneath
        self._pintar(pos, enfocar=True)
        self._refrescar_panel(forzar=True)


def _elegir():
    ventana = None
    try:
        ventana = Elector('ekhorus_elige.xml', runtime_path, 'Default', '1080i')
        ventana.doModal()
        return ventana.eleccion
    except Exception as e:
        logger(f'guide_ui: elector: {e}', 'error')
        return None
    finally:
        # doModal does not free the controls, and in Kodi those are textures in memory
        del ventana


def _abrir_web():
    from lib import espakodi_installer
    espakodi_installer.open_guia()


def _leer():
    try:
        guia = _cargar()
    except (OSError, ValueError) as e:
        logger(f'guide_ui: no se puede leer guia.json: {e}', 'error')
        xbmcgui.Dialog().ok(HEADING, 'No se ha podido abrir la guía guardada en el addon.\n\n'
                                     'Se abrirá la de la web.')
        _abrir_web()
        return

    ventana = None
    fallo = False
    try:
        ventana = Lector('ekhorus_guia.xml', runtime_path, 'Default', '1080i')
        ventana.guia = guia
        ventana.doModal()
    except Exception as e:
        logger(f'guide_ui: lector: {e}', 'error')
        fallo = True
    finally:
        if ventana is not None:
            ventana._cerrando = True
        del ventana

    # If the addon's own window could not open, the guide is still read with the usual
    # dialogs; being left blank would be worse than seeing it ugly.
    if fallo:
        _leer_clasico()


def _leer_clasico():
    """The guide with Kodi's usual dialogs, for when the classic interface is asked for
    or the addon's own window could not open."""
    try:
        guia = _cargar()
    except (OSError, ValueError) as e:
        logger(f'guide_ui: no se puede leer guia.json: {e}', 'error')
        _abrir_web()
        return

    while True:
        titulos = [f"{s['num']}  {s['titulo']}" for s in guia]
        elegido = xbmcgui.Dialog().select('Guía de EKHorus', titulos)
        if elegido < 0:
            return

        seccion = guia[elegido]
        partes = [seccion['cuerpo']] if seccion['cuerpo'] else list()
        partes.extend(f"[B]{e['titulo']}[/B]\n{e['cuerpo']}" for e in seccion['entradas'])
        xbmcgui.Dialog().textviewer(titulos[elegido], '\n\n'.join(partes))


def mostrar():
    """Asks how to read the guide and opens it."""
    if not echar_pestillo(_PESTILLO):
        logger('guide_ui: ya hay una ventana abierta, no se abre otra')
        return

    try:
        if clasica():
            _leer_clasico()
            return

        eleccion = _elegir()
        if eleccion == 'web':
            _abrir_web()
        elif eleccion == 'aqui':
            _leer()
    finally:
        quitar_pestillo(_PESTILLO)
