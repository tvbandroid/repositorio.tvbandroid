# -*- coding: utf-8 -*-
# EKHorus - The other links of the channels that carry more than one.
"""What playback tries when the link of a channel does not start.

They go in a small file of their own, next to the channel list, because playback looks them
up every time a channel is opened and the list is 400 KB of json. Reading it took 20 ms on a
desktop, several times that on a TV box, and it came before the progress dialog could even
appear, for every channel, when nearly all of them carry a single link.
"""
import os
import re

from lib.utils import data_path, dump_json_file, load_json_file, logger

FICHERO = 'alternativos.json'

_RE_HASH = re.compile(r'[0-9a-f]{40}\Z')


def grupos(canales):
    """The links of every channel that carries more than one, the chosen one first."""
    salida = list()

    for canal in canales or []:
        if not isinstance(canal, dict) or not isinstance(canal.get('alternativos'), list):
            continue

        grupo = list()
        for enlace in [canal.get('infohash')] + canal['alternativos']:
            enlace = str(enlace or '').lower()
            if _RE_HASH.match(enlace) and enlace not in grupo:
                grupo.append(enlace)

        if len(grupo) > 1:
            salida.append(grupo)

    return salida


def guardar(base, canales):
    """Writes the groups of a channel list that has just been saved."""
    ruta = os.path.join(data_path, FICHERO)

    try:
        dump_json_file({'base': base, 'grupos': grupos(canales)}, ruta, compacto=True)
    except (OSError, ValueError) as e:
        logger(f'alternatives: no se pudo guardar {FICHERO}: {e}', 'error')
        # An older file would pair up the links of a list that has been replaced.
        try:
            os.remove(ruta)
        except OSError:
            pass


def otros(base, infohash):
    """The other links of the channel an infohash belongs to, healthiest first.

    The infohash can be the chosen one or any of the rest, because a favourite or a history row
    keeps the link that was pressed and a later download may have picked another as the best.
    Empty for a channel with a single link, one that is not in the list, and a file that is
    missing, damaged or from another engine."""
    ruta = os.path.join(data_path, FICHERO)
    if not os.path.isfile(ruta):
        return list()

    try:
        sobre = load_json_file(ruta)
    except OSError as e:
        logger(f'alternatives: no se pudo leer {FICHERO}: {e}', 'error')
        return list()

    if not isinstance(sobre, dict) or sobre.get('base') != base:
        return list()

    guardados = sobre.get('grupos')
    if not isinstance(guardados, list):
        return list()

    buscado = str(infohash or '').lower()

    for grupo in guardados:
        if isinstance(grupo, list) and buscado in grupo:
            return [e for e in grupo if isinstance(e, str) and _RE_HASH.match(e) and e != buscado]

    return list()
