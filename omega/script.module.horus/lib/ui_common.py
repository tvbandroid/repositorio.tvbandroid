# -*- coding: utf-8 -*-
# EKHorus - Pieces shared by the addon's own windows.

import contextlib

import xbmc
import xbmcgui

from lib.utils import get_setting

# Kodi's own spinner. 'nocancel' because what it covers cannot be interrupted halfway:
# offering a Cancel that does nothing is worse than offering none.
_ESPERA = 'busydialognocancel'

ORO = 'FFFFB70F'
GRIS = 'FF8A97A5'
VERDE = 'FF6BD16B'
ROJO = 'FFE06C5A'
# Text inside the pills: it sits on saturated fill, so the text is dark
TINTA_VERDE = 'FF08130C'
TINTA_ROJA = 'FF1A0805'
TINTA_ORO = 'FF0F1216'


def color(texto, tinta):
    return f'[COLOR {tinta}]{texto}[/COLOR]'


@contextlib.contextmanager
def ocupado():
    """Kodi's spinner while a screen takes a moment to be built.

    executebuiltin() returns straight away and the dialog is painted by Kodi's own thread,
    so this adds nothing to the wait; what it buys is that the seconds spent reading the
    list off disk or asking the engine stop looking like a freeze.

    It MUST be closed before opening a window of ours. Two modal windows fighting over the
    focus is the reason the directory is already closed before any of these screens opens."""
    xbmc.executebuiltin(f'ActivateWindow({_ESPERA})')
    try:
        yield
    finally:
        xbmc.executebuiltin(f'Dialog.Close({_ESPERA})')


def clasica():
    """The user has asked to go back to the classic lists.

    It is the emergency exit in case the addon's own windows fail on some device.
    With this none of them opens and everything is a Kodi listing again."""
    return bool(get_setting('interfaz_clasica'))


# Checked on the phone: Kodi hands these gestures to onAction() with the finger
# position when no control takes them. A container (the list) DOES take them and
# scrolls on its own, so only what happens outside the list arrives here.
GESTO_INICIO = 501
GESTO_ARRASTRE = 504
GESTO_CORTE = 505
GESTO_FIN = 599

# A Kodi <textbox> honours neither gestures nor mouse. It only moves through its
# page control, and a scrollbar can only be told page up or page down. Hence a
# swipe turns pages instead of dragging the text.
_PASO = 0.61      # text box height relative to the screen
_MINIMO = 0.10    # shortest swipe that counts as a page turn


class Deslizador:
    """Turns finger dragging into page changes of a text box."""

    def __init__(self, ventana, barra, texto):
        self.ventana = ventana
        self.barra = barra
        self.texto = texto
        self._activo = False
        self._ultimo = 0.0
        self._suma = 0.0

        # Gestures arrive in pixels of the Kodi surface, which on a phone does not match
        # the 1080 of the skin; the threshold is measured in screens, not in points.
        alto = xbmcgui.getScreenHeight() or 1080
        self._paso = alto * _PASO
        self._minimo = alto * _MINIMO

    def accion(self, action):
        """True if the gesture was meant for the text and has been handled."""
        gesto = action.getId()

        if gesto == GESTO_INICIO:
            self._activo = True
            self._ultimo = action.getAmount2()
            self._suma = 0.0
            return True

        if not self._activo:
            return False

        if gesto == GESTO_ARRASTRE:
            y = action.getAmount2()
            self._suma += self._ultimo - y
            self._ultimo = y
            while self._suma >= self._paso:
                self._suma -= self._paso
                self._pagina(1)
            while self._suma <= -self._paso:
                self._suma += self._paso
                self._pagina(-1)
            return True

        if gesto in (GESTO_FIN, GESTO_CORTE):
            self._activo = False
            if gesto == GESTO_FIN and abs(self._suma) >= self._minimo:
                self._pagina(1 if self._suma > 0 else -1)
            self._suma = 0.0
            # Kodi leaves the focus on the default control after a gesture. Without this,
            # whoever swipes and then picks up the remote finds the focus somewhere else.
            self.ventana.setFocusId(self.texto)
            return True

        return False

    def _pagina(self, sentido):
        orden = 'PageDown' if sentido > 0 else 'PageUp'
        xbmc.executebuiltin(f'{orden}({self.barra})')
