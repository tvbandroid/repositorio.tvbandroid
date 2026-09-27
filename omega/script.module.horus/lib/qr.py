# -*- coding: utf-8 -*-
# EKHorus - QR codes as PNG files.
#
# Written by hand and not with pyqrcode's own png(), which always writes a depth of ONE bit
# per pixel. Kodi on Android does not paint those: measured on the phone, the square comes
# out blank and there is not a line in the log about it, while the very same code at eight
# bits shows up. That platform is most of this addon's audience, so the QR was useless
# exactly where it matters. The writer used here is the one pyqrcode itself carries, so
# this adds no dependency.

import os
from threading import get_ident

import xbmcvfs

from lib.utils import logger

# Modules of white margin around the code. Four is what the standard asks for and what
# pyqrcode uses; with fewer, a phone camera struggles to find the code.
MARGEN = 4

FIRMA_PNG = b'\x89PNG\r\n\x1a\n'
# Byte of the IHDR that carries the depth: signature (8) + length (4) + 'IHDR' (4)
# + width (4) + height (4).
POSICION_PROFUNDIDAD = 24


def _sirve(ruta):
    """True if what is already there is a PNG of the depth that gets painted.

    It is checked by content and not by the file merely existing, because whoever updates
    the addon has the previous ones cached, written at one bit, and going by the name they
    would go on being served blank for as long as they lasted. A file cut short by a
    process that died halfway does not pass this either."""
    try:
        with open(ruta, 'rb') as fichero:
            cabecera = fichero.read(POSICION_PROFUNDIDAD + 1)
    except OSError:
        return False

    return (len(cabecera) > POSICION_PROFUNDIDAD and cabecera[:8] == FIRMA_PNG
            and cabecera[POSICION_PROFUNDIDAD] == 8)


def _filas(codigo, escala):
    """The QR as rows of bytes, each module blown up to 'escala' pixels.

    text() gives a '1' per dark module. In greyscale 0 is black, so the two are swapped."""
    filas = list()

    for linea in codigo.text(quiet_zone=MARGEN).splitlines():
        if not linea:
            continue

        fila = bytearray()
        for modulo in linea:
            fila.extend([0 if modulo == '1' else 255] * escala)

        filas.extend([bytes(fila)] * escala)

    return filas


def generar(texto, destino, escala=6):
    """Path of the PNG with that text's QR, written only once. None if it could not.

    It is written aside and renamed: if Kodi kills the process halfway through writing, a
    truncated PNG would stay cached as good for ever."""
    # Kodi has to see it as well, and its answer is not the disk's: one written before this
    # fix, or by anybody else behind its back, is there and still does not exist for the skin.
    # Then it is written again, which is what puts it back on the map.
    if _sirve(destino) and xbmcvfs.exists(destino):
        return destino

    try:
        import pyqrcode
        from pyqrcode import png as pypng

        filas = _filas(pyqrcode.create(texto), escala)
        # The thread goes in the name: every invocation of the addon is a thread of the one
        # Kodi process, and two of them painting the same list shared the temporary file.
        parcial = f'{destino}.{os.getpid()}.{get_ident()}.tmp'

        with open(parcial, 'wb') as fichero:
            pypng.Writer(len(filas[0]), len(filas),
                         greyscale=True, bitdepth=8).write(fichero, filas)

        # Kodi's rename and not os.replace: CFile::Exists answers out of the directory cache,
        # so a file that turned up behind the VFS's back does not exist for the skin. Measured
        # on the Fire TV and on the phone: the square stayed blank, with not a line in the log,
        # until Kodi was restarted. Rename does tell the cache about it.
        #
        # Deleting first because on Windows Kodi renames with MoveFileEx and no
        # MOVEFILE_REPLACE_EXISTING, so it refuses to write over the cached one.
        xbmcvfs.delete(destino)

        if not xbmcvfs.rename(parcial, destino):
            logger(f'qr: no se pudo publicar {destino}', 'error')
            return None

        return destino
    except Exception as e:
        logger(f'qr: no se pudo generar {destino}: {e}', 'error')
        return None
