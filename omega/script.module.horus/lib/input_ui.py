# -*- coding: utf-8 -*-
# EKHorus - Typing a text with the remote or with the phone.
#
# Reproducir identificador and Buscar enlaces ask through here. The phone part is the addon's
# own, the same idea StreamNinja and EspaTV carry, and it says it runs on LoioLink's technology.
# LoioLink's own api cannot be loaded from here, as both addons have a top-level 'lib'.

import hashlib
import os
import threading
import time

import xbmc
import xbmcgui

from lib import qr
from lib.ui_common import clasica
from lib.utils import (HEADING, echar_pestillo, get_setting, icon_path, logger, pantalla_sola,
                       quitar_pestillo, runtime_path, translatePath)

# The values of the escribir_con setting.
PREGUNTAR = 0
MANDO = 1
MOVIL = 2

ID_CERRAR = 100
ID_USAR_MANDO = 101
ID_MANDO = 110
ID_MOVIL = 111

# Long enough to find the phone and type an identifier by hand, short enough that a forgotten
# screen does not keep a server open on the network all evening.
ESPERA_S = 300
SONDEO_S = 0.25

# A second OK on "Con el móvil" lands on the first button of the QR screen and would swap the
# phone for the keyboard at once. A click this soon after the screen opens is taken as that.
IGNORAR_CLIC_S = 0.8

_PESTILLO = 'ekhorus.escribir'

_ATRAS = (9, 10, 92)  # ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, ACTION_NAV_BACK

FIRMA = 'Con la tecnología de loiolink'

# Why the phone page could not be prepared, by the reason receiver.NoArranca gives.
_SE_ABRE_EL_TECLADO = '\n\nSe abre el teclado de la tele.'
SIN_SERVIDOR = {
    'red': ('No se ha podido preparar la página para el móvil. Este aparato no está conectado '
            'a la red.' + _SE_ABRE_EL_TECLADO),
    'puertos': ('No se ha podido preparar la página para el móvil. Otro programa está usando '
                'los puertos que necesita.' + _SE_ABRE_EL_TECLADO),
    'pagina': 'No se ha podido preparar la página para el móvil.' + _SE_ABRE_EL_TECLADO,
}


class Elector(xbmcgui.WindowXMLDialog):
    """Remote or phone. The choice goes in an attribute because doModal() returns nothing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encabezado = ''
        self.eleccion = None

    def onInit(self):
        self.setProperty('e_encabezado', self.encabezado)

    def onAction(self, action):
        # A Python WindowXMLDialog does not close by itself with Back.
        if action.getId() in _ATRAS:
            self.close()

    def onClick(self, controlId):
        if controlId == ID_MANDO:
            self.eleccion = MANDO
        elif controlId == ID_MOVIL:
            self.eleccion = MOVIL
        self.close()


class PantallaMovil(xbmcgui.WindowXMLDialog):
    """The QR and the address, open until the text comes in."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # These four are filled in by _esperar_movil() before doModal().
        self.receptor = None
        self.url = ''
        self.qr = ''
        self.explicacion = ''

        self.usar_mando = False
        self.caducada = False
        self._cerrando = False
        self._esperando = False
        self._abierta = time.monotonic()

    def onInit(self):
        self.setProperty('m_url', self.url)
        self.setProperty('m_qr', self.qr)
        self.setProperty('m_texto', self.explicacion)
        self.setProperty('m_pie', f'{FIRMA}    ·    Se cierra sola a los {ESPERA_S // 60} minutos'
                                  '    ·    [B]Atrás[/B] cancela')

        # Kodi may call here more than once (when reloading the skin); one wait is enough.
        if not self._esperando:
            self._esperando = True
            self._abierta = time.monotonic()
            threading.Thread(target=self._esperar, daemon=True, name='EKHorusTextoEspera').start()

    def _esperar(self):
        monitor = xbmc.Monitor()
        limite = time.monotonic() + ESPERA_S

        while not self._cerrando:
            if self.receptor.recibido.wait(SONDEO_S) or monitor.abortRequested():
                break
            if time.monotonic() >= limite:
                self.caducada = True
                # Nobody is at the screen, and it closing does not say otherwise.
                pantalla_sola()
                break

        if not self._cerrando:
            self.close()

    def close(self):
        self._cerrando = True
        super().close()

    def onAction(self, action):
        if action.getId() in _ATRAS:
            self.close()

    def onClick(self, controlId):
        if time.monotonic() - self._abierta < IGNORAR_CLIC_S:
            return

        if controlId == ID_USAR_MANDO:
            self.usar_mando = True
            self.close()
        elif controlId == ID_CERRAR:
            self.close()


def _qr(url):
    """PNG of the QR for the page's address.

    The address does not change from one time to the next, so the file is written once. The
    digest in the name keeps a change of network or port from serving the previous one."""
    digest = hashlib.md5(url.encode('utf-8')).hexdigest()[:10]
    destino = os.path.join(translatePath('special://temp'), f'ekhorus_qr_texto_{digest}.png')

    return qr.generar(url, destino, escala=8) or ''


def _elegir_clasico():
    opciones = [xbmcgui.ListItem('Con el mando de la tele'),
                xbmcgui.ListItem('Con el móvil', FIRMA)]
    elegido = xbmcgui.Dialog().select('Escribir con', opciones, useDetails=True)

    return (MANDO, MOVIL)[elegido] if elegido in (0, 1) else None


def _elegir(encabezado):
    """MANDO, MOVIL, or None if the user backs out."""
    if clasica():
        return _elegir_clasico()

    ventana = None
    try:
        ventana = Elector('ekhorus_escribir.xml', runtime_path, 'Default', '1080i')
        ventana.encabezado = encabezado
        ventana.doModal()
        return ventana.eleccion
    except Exception as e:
        # Kodi's own list is better than dropping what the user was about to type.
        logger(f'input_ui: elector: {e}', 'error')
        return _elegir_clasico()
    finally:
        # doModal does not free the controls, and in Kodi those are textures in memory
        del ventana


def _esperar_clasico(receptor, url):
    """The wait in Kodi's progress dialog, with no QR. True if the time ran out."""
    dialogo = xbmcgui.DialogProgress()
    # A single message, which is all Kodi 19 takes now that the three separate lines are gone.
    dialogo.create(HEADING, f'En el navegador del móvil, abre esta dirección:\n[B]{url}[/B]\n\n{FIRMA}')
    monitor = xbmc.Monitor()
    limite = time.monotonic() + ESPERA_S

    try:
        while not receptor.recibido.wait(SONDEO_S):
            if dialogo.iscanceled() or monitor.abortRequested():
                return False

            quedan = limite - time.monotonic()
            if quedan <= 0:
                return True

            # Without a message the address already on screen stays.
            dialogo.update(int(100 * (ESPERA_S - quedan) / ESPERA_S))

        return False
    finally:
        dialogo.close()


def _esperar_movil(receptor, url, encabezado, pista):
    """Waits for the phone. Returns (usar_mando, caducada)."""
    if not clasica():
        ventana = None
        try:
            ventana = PantallaMovil('ekhorus_escribir_movil.xml', runtime_path, 'Default', '1080i')
            ventana.receptor = receptor
            ventana.url = url
            ventana.qr = _qr(url)
            ventana.explicacion = (
                f'[B]{encabezado}[/B]\n{pista}\n\n'
                'Escríbelo en la página que se abre en el móvil y pulsa '
                '[COLOR FFFFB70F]Enviar a la tele[/COLOR]. Esta pantalla se cierra sola en '
                'cuanto llega.\n\nEl móvil tiene que estar en la misma red que este Kodi.')
            ventana.doModal()
            return ventana.usar_mando, ventana.caducada
        except Exception as e:
            # The server is already up, so the wait goes on in Kodi's own dialog.
            logger(f'input_ui: pantalla del movil: {e}', 'error')
        finally:
            if ventana is not None:
                ventana._cerrando = True
            del ventana

    return False, _esperar_clasico(receptor, url)


def _con_movil(encabezado, pista, por_defecto):
    # Imported here because server.py brings in the api, and with it the catalogue and the
    # engine client, none of which the keyboard needs.
    from lib.webapp import bootstrap, receiver

    try:
        receptor, url = receiver.arrancar(encabezado, pista)
    except receiver.NoArranca as e:
        xbmcgui.Dialog().ok(HEADING, SIN_SERVIDOR[e.motivo])
        return xbmcgui.Dialog().input(encabezado, por_defecto)

    # Kodi does not hold the screensaver back for a dialog, and it comes on after three minutes
    # by default, so the QR would go dark while the phone is still being found.
    xbmc.executebuiltin('InhibitScreensaver(true)')
    try:
        usar_mando, caducada = _esperar_movil(receptor, url, encabezado, pista)
    finally:
        xbmc.executebuiltin('InhibitScreensaver(false)')
        # Down before anything else opens, so nobody types with the remote while it is up.
        receptor.apagar().join(bootstrap.CIERRE_S)

    # Read under the lock the server decides with. A send that got in before apagar() has
    # written its text by now and a later one has been refused, so what the phone was told and
    # what the television does always agree. A text that came in just as Back or the remote
    # button was pressed wins for that same reason.
    with receptor.cerrojo:
        texto = receptor.texto

    if texto:
        return texto

    if usar_mando:
        return xbmcgui.Dialog().input(encabezado, por_defecto)

    if caducada:
        xbmcgui.Dialog().notification(HEADING, 'No ha llegado nada del móvil', icon_path, 5000)

    return ''


def pedir_texto(encabezado, pista, por_defecto=''):
    """What the user types, with the remote or with the phone, or '' if they give up.

    '' and never None, the same as Dialog().input(), because Reproducir identificador runs
    regular expressions straight over the answer."""
    if not echar_pestillo(_PESTILLO):
        logger('input_ui: ya hay una ventana abierta, no se abre otra')
        return ''

    try:
        modo = get_setting('escribir_con', PREGUNTAR)
        if modo not in (MANDO, MOVIL):
            modo = _elegir(encabezado)

        if modo == MANDO:
            return xbmcgui.Dialog().input(encabezado, por_defecto)
        if modo == MOVIL:
            return _con_movil(encabezado, pista, por_defecto)
        return ''
    finally:
        quitar_pestillo(_PESTILLO)
