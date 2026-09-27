# -*- coding: utf-8 -*-
# EKHorus - The screen that hands the web interface over to the phone.
#
# It is the whole discoverability of the feature: until it existed, the engine already
# served video to any browser on the network and nothing in the addon said so.

import hashlib
import os

import xbmcgui

from lib import qr
from lib.ui_common import clasica
from lib.utils import (HEADING, echar_pestillo, logger, quitar_pestillo, runtime_path,
                       translatePath)
from lib.webapp import bootstrap

ID_CERRAR = 100
ID_ABRIR = 101
ID_APAGAR = 102

_PESTILLO = 'ekhorus.web'

_ATRAS = (9, 10, 92)  # ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, ACTION_NAV_BACK

TEXTO = (
    'Abre esa dirección en el móvil, en la tablet o en otro ordenador de casa y verás '
    'la lista entera de canales, con su buscador, sus categorías y sus países.\n\n'
    '[COLOR FFFFB70F]Ver aquí[/COLOR] reproduce el canal en el propio móvil, dentro del '
    'navegador y sin instalar nada.\n'
    '[COLOR FFFFB70F]Ver en la tele[/COLOR] lo pone en este Kodi, así que el móvil hace '
    'de mando a distancia.\n\n'
    'No hace falta cuenta ni contraseña, solo estar en la misma red.'
)

PIE = ('El servidor sigue encendido mientras Kodi esté abierto'
       '    ·    [B]Atrás[/B] cierra esta pantalla')

SIN_SERVIDOR = (
    'No se ha podido encender el servidor web.\n\n'
    'Suele ser que este aparato no tiene dirección en la red local, o que el puerto '
    'y los siete siguientes están ocupados. Puedes cambiarlo en Ajustes > Interfaz.'
)

POCA_MEMORIA = (
    'Este aparato tiene poca memoria. A veces va bien, pero con el navegador delante '
    'Android puede cerrar Kodi, y con él la página, o cortarse el vídeo.\n'
    'Mejor ábrela desde el móvil, en la misma wifi.'
)


def _qr(url):
    """PNG of the QR for that address, generated once.

    The name carries a digest of the url so that changing port or network does not keep
    serving the previous image, and it keeps the ekhorus_qr_ prefix so the cleanup that
    already runs from the menu sweeps it too."""
    digest = hashlib.md5(url.encode('utf-8')).hexdigest()[:10]
    destino = os.path.join(translatePath('special://temp'), f'ekhorus_qr_web_{digest}.png')

    # Bigger than the one on a channel row, because this one is read from the sofa.
    return qr.generar(url, destino, escala=8) or ''


class Pantalla(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url = ''
        self.qr = ''

    def onInit(self):
        self.setProperty('w_url', self.url)
        self.setProperty('w_qr', self.qr)
        self.setProperty('w_texto', TEXTO)
        self.setProperty('w_pie', PIE)

    def onAction(self, action):
        # A Python WindowXMLDialog does not close by itself with Back.
        if action.getId() in _ATRAS:
            self.close()

    def onClick(self, controlId):
        if controlId == ID_CERRAR:
            self.close()

        elif controlId == ID_ABRIR:
            if bootstrap.poca_memoria() and not xbmcgui.Dialog().yesno(
                    HEADING, POCA_MEMORIA, yeslabel='Abrir aquí', nolabel='Cancelar'):
                return

            if not bootstrap.abrir_en_navegador(self.url):
                xbmcgui.Dialog().ok(HEADING, f'No se pudo abrir el navegador.\n\n{self.url}')

        elif controlId == ID_APAGAR:
            # Asked before, because whoever is watching on the phone loses the page.
            if xbmcgui.Dialog().yesno(HEADING, 'Se apagará el servidor y la dirección '
                                               'dejará de funcionar.\n\n¿Seguro?'):
                bootstrap.parar()
                self.close()


def _sin_ventana(url):
    """The address with Kodi's usual dialogs, for the classic interface or a window that
    would not open."""
    xbmcgui.Dialog().ok(HEADING, f'[B]{url}[/B]\n\nAbre esa dirección en el navegador del '
                                 f'móvil, estando en la misma red, y tendrás la lista de '
                                 f'canales.')


def mostrar():
    """Starts the web server and shows how to get to it."""
    if not echar_pestillo(_PESTILLO):
        logger('web_ui: ya hay una ventana abierta, no se abre otra')
        return

    try:
        url = bootstrap.asegurar()

        if not url:
            xbmcgui.Dialog().ok(HEADING, SIN_SERVIDOR)
            return

        if clasica():
            _sin_ventana(url)
            return

        ventana = None
        fallo = False
        try:
            ventana = Pantalla('ekhorus_web.xml', runtime_path, 'Default', '1080i')
            ventana.url = url
            ventana.qr = _qr(url)
            ventana.doModal()
        except Exception as e:
            logger(f'web_ui: {e}', 'error')
            fallo = True
        finally:
            # doModal does not free the controls, and in Kodi those are textures in memory
            del ventana

        if fallo:
            _sin_ventana(url)
    finally:
        quitar_pestillo(_PESTILLO)
