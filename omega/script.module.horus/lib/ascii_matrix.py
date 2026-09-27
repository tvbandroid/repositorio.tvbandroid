# -*- coding: utf-8 -*-
# EKHorus - Background star field.
#
# The XML is generated on the fly because it is 26 rows of random stars, and writing them
# by hand would be a thousand-line file that would always look the same. It is written in
# the addon profile folder, not the addon one, so as not to depend on that being writable.
#
# The stars fall, but NOT with a Kodi animation. The original carried a looping slide, and
# any animation that never ends forces Kodi to repaint the whole screen on every frame.
# Measured on a 120 Hz phone, the window went from 9% CPU to 62% and the handset heated up
# with nobody touching anything. Here the rows are moved by Python a few times per second
# (see the clock in universe_ui.py), so the screen is dirtied that handful of times instead of
# a hundred and twenty, and the fall looks just as slow.

import os
import random

import xbmcaddon
import xbmcgui
import xbmcvfs

from lib.utils import logger

_ADDON = xbmcaddon.Addon()
_MEDIA_URI = f"special://home/addons/{_ADDON.getAddonInfo('id')}/resources/media/"
_PERFIL = xbmcvfs.translatePath(_ADDON.getAddonInfo('profile'))
_SKIN = os.path.join(_PERFIL, 'resources', 'skins', 'Default', '1080i')

# The name carries a version: when the XML changes, the one already written in the
# profile must stop being reused, as it has no identifiers to move.
XML_NAME = 'ekhorus_estrellas3.xml'
XML_PATH = os.path.join(_SKIN, XML_NAME)
_ANTERIORES = ('ekhorus_estrellas.xml', 'ekhorus_estrellas2.xml')

_ALTO_FILA = 42
# Two rows more than fit on the screen: one peeking in at the top and another leaving
# through the bottom. With just the exact number, a strip with no stars was left at the
# top edge while the bottom one finished leaving.
FILAS = 27
_CICLO_PX = FILAS * _ALTO_FILA
_ID_BASE = 3000


def _posicion(n, altura=0):
    """Where row n goes with the field lowered 'altura' pixels.

    The same arithmetic is used by the generated XML and by the fall, so the starting
    place and the place after each step cannot disagree."""
    return (n * _ALTO_FILA + altura) % _CICLO_PX - _ALTO_FILA

_ATRAS = (9, 10, 92, 216)

_FILAS = [
    " .       *             +          .   x          .          *    .         +       ",
    "       +        .            .              *           +            x             ",
    "  x              +      .       .             +               .        x   *       ",
    "      .      *               +          x            *         .            +      ",
    "  .               +                   .          *             +       .           ",
    "       x       .           *               .         .           +        *        ",
    " .                   +               x           .          *           +          ",
    "         +                 .                .          +              *       .    ",
]


def _xml():
    rng = random.Random()
    etiquetas = list()

    for n in range(FILAS):
        fila = '    '.join(rng.choice(_FILAS) for _ in range(5))
        fila = fila.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        etiquetas.append(
            f'        <control type="label" id="{_ID_BASE + n}">\n'
            f'            <left>0</left><top>{_posicion(n)}</top>\n'
            f'            <width>3000</width><height>{_ALTO_FILA}</height>\n'
            '            <font>font12</font>\n'
            '            <textcolor>AABBFFFF</textcolor>\n'
            f'            <label>{fila}</label>\n'
            '        </control>')

    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<window>\n'
            '    <defaultcontrol>2</defaultcontrol>\n'
            '    <controls>\n'
            '        <control type="image">\n'
            '            <left>0</left><top>0</top><width>1920</width><height>1080</height>\n'
            f'            <texture>{_MEDIA_URI}white.png</texture>\n'
            '            <colordiffuse>F2030610</colordiffuse>\n'
            '        </control>\n'
            # Loose and not inside a group: the rows have to be moved one by one from
            # Python, and inside a group their coordinates would be the group's.
            + '\n'.join(etiquetas) + '\n'
            # Kodi demands a defaultcontrol that can take the focus. It goes off screen rather
            # than hidden: a hidden one cannot be focused and Kodi leaves an error in the log
            # every time the window is opened.
            '        <control type="button" id="2">\n'
            '            <left>0</left><top>1200</top><width>1</width><height>1</height>\n'
            '            <label></label>\n'
            '        </control>\n'
            '    </controls>\n'
            '</window>\n')


class Estrellas(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filas = list()
        self.altura = 0

    def onInit(self):
        # The XML controls do not exist until Kodi builds the window
        self.filas = list()
        for n in range(FILAS):
            try:
                self.filas.append(self.getControl(_ID_BASE + n))
            except RuntimeError as e:
                logger('campo de estrellas: falta la fila %d (%s)' % (n, e))
                self.filas = list()
                return

    def caer(self, pixeles):
        """Lowers the field and sends back to the top the row that leaves at the bottom.

        The rows are spread every 42 px along a cycle longer than the screen, so moving
        them all as a block and wrapping them around with the remainder always leaves the
        same spread. The fall has neither a seam nor jumps."""
        if not self.filas:
            return

        self.altura = (self.altura + pixeles) % _CICLO_PX
        for n, fila in enumerate(self.filas):
            fila.setPosition(0, _posicion(n, self.altura))

    def onAction(self, action):
        if action.getId() in _ATRAS:
            self.close()


def _tirar_los_viejos():
    """Deletes from the profile the star fields of earlier versions.

    Outside the generated one and with its own try, for two reasons: whoever already has
    the current one written would never go through the generation again and would be left
    with the old one stuck for ever, and failing to delete a decorative file is no reason
    to open the window with no background."""
    for viejo in _ANTERIORES:
        ruta = os.path.join(_SKIN, viejo)
        try:
            if os.path.exists(ruta):
                os.remove(ruta)
        except OSError as e:
            logger('no se ha podido borrar el campo de estrellas viejo %s: %s' % (viejo, e))


def fondo():
    """Returns the background dialog, or None if it could not be prepared."""
    try:
        if not os.path.exists(XML_PATH):
            os.makedirs(_SKIN, exist_ok=True)
            # Written aside and moved in one go: a cut halfway would leave a truncated XML that
            # already exists, so it would never be generated again.
            temporal = XML_PATH + '.parcial'
            with open(temporal, 'w', encoding='utf-8') as f:
                f.write(_xml())
            os.replace(temporal, XML_PATH)

        _tirar_los_viejos()
        return Estrellas(XML_NAME, _PERFIL, 'Default', '1080i')
    except Exception:
        # The background is decoration: if it cannot be done, the links window still opens
        return None
