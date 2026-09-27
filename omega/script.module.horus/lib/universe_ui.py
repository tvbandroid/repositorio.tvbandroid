# -*- coding: utf-8 -*-
# EKHorus - Universo EspaKodi: the links of the ecosystem.
#
# The window is built by hand
# instead of with an XML, so it places itself whatever the resolution is, and the star
# field stays behind, which would not happen with a modal WindowXMLDialog.

import os
import threading

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from lib.utils import (HEADING, apartar_musica, echar_pestillo, logger, quitar_pestillo,
                       runtime_path)
from lib.ui_common import ORO

_PESTILLO = 'ekhorus.universe_ui'
_ATRAS = (9, 10, 92)  # ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, ACTION_NAV_BACK

# Kodi alignments (XBFONT_*), which xbmcgui does not export by name
_DERECHA, _CENTRO, _MEDIO = 0x01, 0x02, 0x04

# Kodi builds the Python windows in a 1280x720 space. The measurements in _montar()
# are meant for that one, and get scaled in case some device gives another.
_BASE = 720

_TITULO = 'Universo EspaKodi'
_FIRMANTE = 'Fundado por RubénSDFA1laberot'

# Everything that moves in this window runs on one clock, and slowly on purpose: every
# time something changes, Kodi repaints the WHOLE screen. With its own animations that
# happened at the panel rate, 120 times a second on the test phone, and cost 62 points
# of CPU. Ten steps a second looks the same and dirties the screen only ten times.
_TIC_S = 0.1
_CAIDA_PX = 2  # 20 px per second, the same slow step the original animation had

_ORO_VIVO = (0xFF, 0xB7, 0x0F)
_ORO_APAGADO = (0x70, 0x50, 0x08)
_PASOS_LATIDO = 24

# What the signature easter egg, now gone, left behind in the profile. The image is over
# 200 KB and nobody else is going to look at it.
_RESTOS_DEL_HUEVO = ('ascii.jpg', 'egg_count.txt')

ENLACES = (
    ('FFFFD700', 'Contacto', 'https://t.me/rubensdfa1laberot/?direct'),
    (None, None, None),
    ('FF2AABEE', 'Canal de Telegram', 'https://t.me/espadaily'),
    ('FF2AABEE', 'Chat EspaKodi', 'https://t.me/espakodi'),
    (None, None, None),
    ('FFA0522D', 'Web de EspaKodi', 'https://espatv.github.io'),
    ('FF43A047', 'loiolo.io', 'https://loiolo.io'),
)


def _latido(vivo, apagado, pasos):
    """The tones the title goes through, there and back.

    With four tones the change looked like a jump. With these it looks like breathing,
    and costs no more; what costs is repainting the screen, not how much the colour moves."""
    ida = ['FF%02X%02X%02X' % tuple(round(v + (a - v) * n / (pasos - 1))
                                    for v, a in zip(vivo, apagado))
           for n in range(pasos)]
    return tuple(ida + ida[-2:0:-1])


_TONOS = _latido(_ORO_VIVO, _ORO_APAGADO, _PASOS_LATIDO)


def _media(nombre):
    return os.path.join(runtime_path, 'resources', 'media', nombre)


def _perfil():
    return xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))


def _abrir(url):
    try:
        apartar_musica()
        if xbmc.getCondVisibility('System.Platform.Android'):
            xbmc.executebuiltin(
                f'StartAndroidActivity("","android.intent.action.VIEW","","{url}")')
        else:
            import webbrowser  # noqa: PLC0415  (on Android there is no browser to open)
            webbrowser.open(url)
        return True
    except Exception as e:
        logger(f'universe_ui: abriendo {url}: {e}', 'error')
        return False


class Universo(xbmcgui.WindowDialog):
    """Centred panel with the links of the ecosystem, over the star field."""

    def __init__(self, fondo=None):
        super().__init__()
        self.fondo = fondo
        self.urls = dict()
        self.botones = list()
        self.id_cerrar = -1
        self.id_titulo = -1
        self.titulo = None
        self._cerrando = False
        self._montar()
        threading.Thread(target=self._latir, daemon=True).start()

    def close(self):
        self._cerrando = True
        super().close()

    def _latir(self):
        """A single clock for the title tone and for the falling stars.

        Together and not each on its own: both dirty the screen, and done at the same
        instant Kodi repaints once instead of twice."""
        monitor = xbmc.Monitor()
        n = 0

        while not self._cerrando:
            if monitor.waitForAbort(_TIC_S):
                break
            n += 1
            try:
                self.titulo.setLabel(
                    f'[B][COLOR {_TONOS[n % len(_TONOS)]}]{_TITULO}[/COLOR][/B]')
                if self.fondo is not None:
                    self.fondo.caer(_CAIDA_PX)
            except Exception as e:
                # The window may have been closed between the check and the painting
                logger(f'universe_ui: latido: {e}')
                break

    # --- assembly ----------------------------------------------------------------------

    def _montar(self):
        ancho = self.getWidth() or _BASE * 16 // 9
        alto = self.getHeight() or _BASE
        k = alto / _BASE

        def u(v):
            return int(v * k)

        pw = int(ancho * 0.47)
        ph = u(30 + 34 + 18 + 1 + 16
               + sum(28 if e[1] else 16 for e in ENLACES)
               + 16 + 1 + 18 + 32 + 28)
        px, py = (ancho - pw) // 2, (alto - ph) // 2
        margen = u(34)
        blanco, transparente = _media('white.png'), _media('transparent.png')
        foco_fila, foco_centro = _media('focus.png'), _media('focus_centro.png')

        nuevos = list()

        def imagen(x, y, w, h, tinta, ruta=None):
            c = xbmcgui.ControlImage(x, y, w, h, ruta or blanco, colorDiffuse=tinta)
            nuevos.append(c)
            return c

        def etiqueta(x, y, w, h, texto, tinta, alineado=0):
            c = xbmcgui.ControlLabel(x, y, w, h, texto, font='font13', textColor=tinta,
                                     alignment=alineado | _MEDIO)
            nuevos.append(c)
            return c

        def boton(x, y, w, h, texto, tinta, alineado, textura, hueco=0):
            c = xbmcgui.ControlButton(x, y, w, h, texto, font='font13', textColor=tinta,
                                      focusedColor='FFFFFFFF', alignment=alineado | _MEDIO,
                                      noFocusTexture=transparente, focusTexture=textura,
                                      textOffsetX=hueco)
            nuevos.append(c)
            self.botones.append(c)
            return c

        # Panel background and gold edge at the top
        imagen(px, py, pw, ph, 'F00B0F14')
        imagen(px, py, pw, u(3), ORO)
        for x, y, w, h in ((px, py + ph - 1, pw, 1), (px, py, 1, ph),
                           (px + pw - 1, py, 1, ph)):
            imagen(x, y, w, h, '30FFB70F')

        # The title pulses so that it shows it can be pressed, and pressing it tells whose
        # this is. It is the first thing to take the focus.
        y = py + u(30)
        titulo = self.titulo = boton(px + margen, y, pw - margen * 2, u(34),
                                     f'[B][COLOR {_TONOS[0]}]{_TITULO}[/COLOR][/B]',
                                     ORO, _CENTRO, foco_centro)
        y += u(34 + 18)
        imagen(px + margen, y, pw - margen * 2, 1, '22FFFFFF')
        y += u(16)

        enlaces = list()
        for tinta, nombre, url in ENLACES:
            if nombre is None:
                y += u(7)
                imagen(px + margen, y, pw - margen * 2, 1, '22FFFFFF')
                y += u(9)
                continue

            punto = u(8)
            imagen(px + u(24), y + (u(28) - punto) // 2, punto, punto, tinta,
                   _media('punto.png'))
            etiqueta(px + u(44), y, pw - u(88), u(28), f'[B]{nombre}[/B]', tinta)
            enlaces.append((boton(px + u(14), y, pw - u(28), u(28),
                                  url.replace('https://', ''), 'FFB9C2CC', _DERECHA,
                                  foco_fila, hueco=u(16)), url))
            y += u(28)

        y += u(16)
        imagen(px + margen, y, pw - margen * 2, 1, '22FFFFFF')
        y += u(18)

        # The outline goes under the button, so the focus wash is painted inside it
        ancho_cerrar = u(180)
        imagen(px + (pw - ancho_cerrar) // 2, y, ancho_cerrar, u(32), 'FFFFFFFF',
               _media('boton_borde.png'))
        cerrar = boton(px + (pw - ancho_cerrar) // 2, y, ancho_cerrar, u(32),
                       '[B]Cerrar[/B]', 'FFB9C2CC', _CENTRO, foco_centro)

        # addControls in a single call: one by one, Kodi repaints with every control
        self.addControls(nuevos)

        # The ids only exist after addControls
        self.id_titulo = titulo.getId()
        self.id_cerrar = cerrar.getId()
        for b, url in enlaces:
            self.urls[b.getId()] = url

        for n, b in enumerate(self.botones):
            b.controlUp(self.botones[n - 1])
            b.controlDown(self.botones[(n + 1) % len(self.botones)])
        self.setFocus(self.botones[0])

    # --- actions -----------------------------------------------------------------------

    def onControl(self, control):
        # Kodi reports through here, not through onClick: onClick belongs to XML windows.
        # And as the report comes from the control itself, a press outside it fires nothing.
        controlId = control.getId()

        if controlId == self.id_cerrar:
            self.close()
        elif controlId == self.id_titulo:
            xbmcgui.Dialog().notification(HEADING, _FIRMANTE,
                                          xbmcgui.NOTIFICATION_INFO, 4000)
        elif controlId in self.urls:
            if _abrir(self.urls[controlId]):
                xbmcgui.Dialog().notification(HEADING, 'Abriendo enlace…',
                                              xbmcgui.NOTIFICATION_INFO, 2000)
            else:
                xbmcgui.Dialog().notification(HEADING, 'No se ha podido abrir el enlace',
                                              xbmcgui.NOTIFICATION_WARNING, 4000)

    def onAction(self, action):
        if action.getId() in _ATRAS:
            self.close()


def _tirar_el_huevo():
    """Deletes from the profile what the signature easter egg left behind."""
    for nombre in _RESTOS_DEL_HUEVO:
        ruta = os.path.join(_perfil(), nombre)
        try:
            if os.path.exists(ruta):
                os.remove(ruta)
        except OSError as e:
            logger(f'universe_ui: no se ha podido borrar {nombre}: {e}')


def mostrar():
    if not echar_pestillo(_PESTILLO):
        logger('universe_ui: ya hay una ventana abierta, no se abre otra')
        return

    fondo = ventana = None
    try:
        _tirar_el_huevo()

        from lib import ascii_matrix  # noqa: PLC0415  (only loaded if this is opened)
        fondo = ascii_matrix.fondo()
        if fondo:
            fondo.show()

        ventana = Universo(fondo)
        ventana.doModal()

    except Exception as e:
        logger(f'universe_ui: {e}', 'error')

    finally:
        if ventana is not None:
            # Stops the clock even if the window was closed some other way
            ventana._cerrando = True
        if fondo is not None:
            try:
                fondo.close()
            except Exception as e:
                logger(f'universe_ui: cerrando el fondo: {e}')
        # doModal does not free the controls, and in Kodi those are textures in memory
        del fondo
        del ventana
        quitar_pestillo(_PESTILLO)
