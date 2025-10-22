import sys
import json
from pathlib import Path
from typing import Union
import xbmc
import xbmcplugin
import xbmcaddon
import xbmcgui
import xbmcvfs
from .models import Item

# Define global variables
URL = sys.argv[0]
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else 0
ADDON = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo('name')
ICON = ADDON.getAddonInfo('icon')
FANART = ADDON.getAddonInfo('fanart')
PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
FILES_PATH = Path(PATH) / 'files'
KODI_VER = float(xbmc.getInfoLabel("System.BuildVersion")[:4])

try:
    KODI_VER = float(xbmc.getInfoLabel("System.BuildVersion")[:4])
except (ValueError, IndexError):
    KODI_VER = 0

def log(string: str):
    xbmc.log(string, xbmc.LOGINFO)

def dump(item):
    return json.dumps(item, indent=4)

def write_file(file_path, string):
    with open(file_path, 'w', encoding='utf-8', errors='ignore') as f:
        f.write(string)

def read_file(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def ok_dialog(text: str):
    xbmcgui.Dialog().ok(ADDON_NAME, text)

def from_keyboard(default_text='', header='Search'):
    kb = xbmc.Keyboard(default_text, header, False)
    kb.doModal()
    if kb.isConfirmed():
        return kb.getText()
    return None

def get_multilink(items: list):
    if not items:
        return None
    
    labels = []
    links = []
    counter = 1
    
    for item in items:
        if isinstance(item, list) and len(item) == 2:
            # Handle case where there is only one item in the list
            if len(items) == 1:
                return item[1]
            labels.append(item[0])
            links.append(item[1])
        elif isinstance(item, str):
            # Handle case where there is only one string item
            if len(items) == 1:
                return item.strip()
            if item.strip().endswith(')') and '(' in item:
                label = item.split('(')[-1].replace(')', '')
                link = item.rsplit('(', 1)[0].strip()
                labels.append(label)
                links.append(link)
            else:
                labels.append(f'Link {counter}')
                links.append(item.strip())
        else:
            return None
        counter += 1
    
    if not labels or not links:
        return None
    
    # Display a dialog to the user to choose a link
    ret = xbmcgui.Dialog().select('Choose a Link', labels)
    
    if ret == -1:
        return None
    return links[ret]

def set_info(liz: xbmcgui.ListItem, infolabels: dict, cast: list=None):
    cast = cast or []
    if KODI_VER < 21:
        liz.setInfo("video", infolabels)
        liz.setCast(cast)
    else:
        i = liz.getVideoInfoTag()
        i.setMediaType(infolabels.get("mediatype", "video"))
        i.setTitle(infolabels.get("title", "Unknown"))
        i.setPlot(infolabels.get("plot", infolabels.get("title", "")))
        i.setTagLine(infolabels.get("tagline", ""))
        i.setPremiered(infolabels.get("premiered", ""))
        i.setGenres(infolabels.get("genre", []))
        i.setMpaa(infolabels.get("mpaa", ""))
        i.setDirectors(infolabels.get("director", []))
        i.setWriters(infolabels.get("writer", []))
        i.setRating(infolabels.get("rating", 0))
        i.setVotes(infolabels.get("votes", 0))
        i.setStudios(infolabels.get("studio", []))
        i.setCountries(infolabels.get("country", []))
        i.setSet(infolabels.get("set", ""))
        i.setTvShowStatus(infolabels.get("status", ""))
        i.setDuration(infolabels.get("duration", 0))
        i.setTrailer(infolabels.get("trailer", ""))

        cast_list = []
        for actor in cast:
            cast_list.append(xbmc.Actor(
                name=actor.get("name", ""),
                role=actor.get("role", ""),
                thumbnail=actor.get("thumbnail", "")
            ))
        i.setCast(cast_list)

def play_video(name: str, url: str, icon: str, description='', set_resolved: bool=False, is_ffmpeg: bool=False):
    if url.startswith('['):
        url = json.loads(url)
        url = get_multilink(url)
        if not url:
            sys.exit()

    if not description:
        description = name
    
    try:
        import resolveurl
        hmf = resolveurl.HostedMediaFile(url)
        if hmf.valid_url():
            url = hmf.resolve()
    except Exception as e:
        log(f'Error Resolving Url: {e}')

    liz = xbmcgui.ListItem(name, path=url)
    set_info(liz, {'title': name, 'plot': description})
    liz.setArt({'thumb': icon, 'icon': icon, 'poster': icon})
    if is_ffmpeg is True:
        ffmpeg(liz)
    if set_resolved is True:
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, liz)
    else:
        xbmc.Player().play(url, liz)

def ffmpeg(liz: xbmcgui.ListItem) -> None:
    liz.setProperty('inputstream', 'inputstream.ffmpegdirect')
    liz.setProperty('inputstream.ffmpegdirect.is_realtime_stream', 'true')
    liz.setProperty('inputstream.ffmpegdirect.stream_mode', 'timeshift')
    if KODI_VER < 21:
        liz.setProperty('inputstream.adaptive.manifest_type', 'hls') # Deprecated on Kodi 21
    liz.setMimeType('application/x-mpegURL')
    log('ffmpeg applied')

def create_listitem(item: Union[Item, dict]):
    if isinstance(item, dict):
        item = Item(**item)
    is_folder = item.type == 'dir'
    title = item.title
    icon = item.thumbnail
    fanart = item.fanart
    description = item.summary or title
    duration = item.duration or 0
    is_playable = 'true' if item.is_playable is True else 'false'
    list_item = xbmcgui.ListItem(label=title)
    list_item.setArt({'thumb': icon, 'icon': icon, 'poster': icon, 'fanart': fanart})
    list_item.setProperty('isPlayable', is_playable)
    
    infolabels = item.infolabels or {
        'mediatype': 'video',
        'title': title,
        'plot': description,
        'duration': duration
    }
    cast = item.cast
    set_info(list_item, infolabels, cast=cast)

    plugin_url = f'{URL}?{item.url_encode()}'
    xbmcplugin.addDirectoryItem(HANDLE, plugin_url, list_item, is_folder)