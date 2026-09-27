# -*- coding: utf-8 -*-
# EKHorus - Opening a magnet or a .torrent with Elementum.
"""Elementum plays torrents, which is not what the AceStream engine is for.

EKHorus installs nothing and configures nothing here. When Elementum is installed, the links it
can open offer it, and they go to its own play route.
"""
import re
import urllib.parse as urllib_parse

import xbmc

ADDON_ID = 'plugin.video.elementum'

_RE_BTIH = re.compile(r'[?&]xt=urn:btih:', re.I)


def instalado():
    """Installed and enabled. Asked every time, since it can be installed with EKHorus open.

    AddonIsEnabled and not HasAddon, which says nothing about a switched-off addon: offering to
    open a link with one would end in a PlayMedia that plays nothing."""
    return xbmc.getCondVisibility(f'System.AddonIsEnabled({ADDON_ID})')


def puede_abrir(enlace):
    """True for a BitTorrent magnet or the address of a .torrent."""
    enlace = str(enlace or '').strip()

    if enlace.lower().startswith('magnet:'):
        return bool(_RE_BTIH.search(enlace))

    return urllib_parse.urlsplit(enlace).path.lower().endswith('.torrent')


def abrir(enlace):
    """Plays the link through Elementum.

    PlayMedia and not RunPlugin, because Elementum answers its play route with setResolvedUrl,
    which needs the handle Kodi only gives a playable item. The link goes encoded whole, so that
    no comma or bracket inside it can split the arguments of the builtin."""
    uri = urllib_parse.quote(enlace, safe='')
    xbmc.executebuiltin(f'PlayMedia(plugin://{ADDON_ID}/play?uri={uri})')
