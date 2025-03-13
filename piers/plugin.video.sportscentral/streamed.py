import sys
import json
import base64
from urllib.parse import parse_qsl, urlparse, quote
import re
import requests
from bs4 import BeautifulSoup
import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
from resources.lib.modules.utils import create_listitem, log, play_video
from resources.lib.modules.models import Item

HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_ICON = ADDON.getAddonInfo('icon')

BASE_URL = 'https://streamed.su'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0'
HEADERS = {"User-Agent": USER_AGENT, "Referer": BASE_URL}
REFERER = 'https://embedme.top/'
KODI_VER = float(xbmc.getInfoLabel("System.BuildVersion")[:4])

# Matches
MATCHES = f'{BASE_URL}/api/matches'
ALL_MATCHES = f'{MATCHES}/all'
ALL_POPULAR = f'{ALL_MATCHES}/popular'
ALL_TODAY = f'{MATCHES}/all-today'
ALL_TODAY_POPULAR = f'{MATCHES}/all-today/popular'
LIVE = f'{MATCHES}/live'
LIVE_POPULAR = f'{MATCHES}/live/popular'
SPORTS = f'{BASE_URL}/api/sports'

# Stream
def stream_url(source: str, _id: str) -> str:
    return f'{BASE_URL}/api/stream/{source}/{_id}'

def sport_matches(sport: str) -> str:
    return f'{MATCHES}/{sport}'

def popular_sport_matches(sport: str) -> str:
    return f'{sport_matches(sport)}/popular'

def images_id(_id: str) -> str:
    return f'{BASE_URL}/api/images/badge/{_id}.webp'

def images_badge(badge:str) -> str:
    return f'{BASE_URL}/api/images/poster/[{badge}/{badge}.webp'

def images_poster(poster: str) -> str:
    return f'/api/images/proxy/{poster}.webp'
    

def main_menu():
    xbmcplugin.setPluginCategory(HANDLE, 'Main Menu')
    
    create_listitem(
        Item(
            title='[B][COLOR deepskyblue]*** Sports Central ***[/COLOR][/B]'
        )
    )
    create_listitem(
        Item(
            title='Replays',
            type='dir',
            mode='replays_main'
        )
    )
    for item in get_categories():
        create_listitem(item)
    

def get_categories():
    items = []
    for title, link in (['Live', LIVE], ['Live Popular', LIVE_POPULAR], ['All Today', ALL_TODAY], ['All Today Popular', ALL_TODAY_POPULAR]):
        items.append(Item(title, type='dir', mode='get_list', link=link))
    
    cats = get_json(SPORTS)
    for cat in cats:
        _id = cat.get('id', '')
        title = cat.get('name', '')
        link = sport_matches(_id)
        items.append(Item(title, type='dir', mode='get_list', link=link))
    
    for cat in cats:
        _id = cat.get('id', '')
        title = cat.get('name', '')
        title = f'{title} [B][COLOR green](Popular)[/COLOR][/B]'
        link = popular_sport_matches(_id)
        items.append(Item(title, type='dir', mode='get_list', link=link))
        
    return items

def get_json(url: str):
    return requests.get(url, headers=HEADERS, timeout=10).json()

def get_page(url: str):
    return requests.get(url, headers=HEADERS, timeout=10).text

def get_list(url: str):
    response = get_json(url)
    for index, item in enumerate(response):
        if url in (LIVE, LIVE_POPULAR):
            response[index]['live'] = True
        else:
            response[index]['live'] = False
    for item in process_items(response):
        create_listitem(item)
    
def process_items(response: str):
    items = []
    for item in response:
        _item = parse_item(item)
        if _item.to_dict().get('link'):
            items.append(_item)
    return items
    #return [parse_item(item) for item in response]
        
def parse_item(item: dict):
    title = item.get('title', '')
    live = item.get('live', False)
    category = item.get('category', '')
    if category:
        title = f'[B][COLOR deepskyblue]{str(category).capitalize()}[/COLOR][/B] - {title}'
    sources = item.get('sources', [])
    sources = [source for source in sources if source['source'] in ('alpha', 'bravo')]
    if live is True and not sources:
        link = []
    else:
        link = json.dumps(sources).encode()
        link = base64.b64encode(link).decode()
    thumbnail = item.get('poster', ADDON_ICON)
    thumbnail = f'{BASE_URL}{thumbnail}' if thumbnail != ADDON_ICON else thumbnail
    return Item(
        title=title,
        mode='get_links',
        link=link,
        thumbnail=thumbnail
    )

def get_links(name: str, url: str, icon):
    url = base64.b64decode(url).decode()
    sources = json.loads(url)
    #_links = [[str(source['source']).capitalize(), stream_url(source['source'], source['id'])] for source in sources if source['source'] in ('alpha', 'bravo')]
    _links = [stream_url(source['source'], source['id']) for source in sources if source['source'] in ('alpha', 'bravo')]
    if not _links:
        xbmcgui.Dialog().notification(ADDON_NAME, 'No links were found. The event may not have started or has finished.', icon=ADDON_ICON)
        sys.exit()
    """labels = [link[0] for link in links]
    ret = xbmcgui.Dialog().select('Select a Link', labels)
    if ret > -1:
        title = labels[ret]
        link = links[ret][1]
    else:
        sys.exit()"""
    labels = []
    links = []
    for link in _links:
        response = get_json(link)
        
        for stream in response:
            stream_source = stream.get('source')
            stream_num = stream.get('streamNo')
            title = f'{stream_source} {stream_num}'
            title += ' HD' if stream.get('hd') is True else ''
            link = stream.get('embedUrl')
            labels.append(title)
            links.append(link)
        if not links:
            xbmcgui.Dialog().notification(ADDON_NAME, 'No links were found. The event may not have started or has finished.', icon=ADDON_ICON)
            sys.exit()
    ret = xbmcgui.Dialog().select('Select a Link', labels)
    if ret > -1:
        title = labels[ret]
        link = links[ret]
    else:
        sys.exit()
        
    response = get_page(link)
    match = re.findall(r'k="(.+?)",i="(.+?)",s="(.+?)",l=\["(.+?)"\],h="(.+?)"', response)
    if not match:
        sys.exit()
    match = match[0]
    link = f"https://{match[3]}.{match[4]}/{match[0]}/js/{match[1]}/{match[2]}/playlist.m3u8|Referer={REFERER}&Origin={REFERER}&Connection=Keep-Alive&User-Agent={USER_AGENT}"
    data = {'path': f'/{match[0]}/js/{match[1]}/{match[2]}/playlist.m3u8'}
    HEADERS['Referer'] = REFERER
    log(f"post= {requests.post('https://secure.bigcoolersonline.top/init-session', data=data, headers=HEADERS).text}")
    #link = f'https://info-fetch.vercel.app/api/stream?url=https%3A%2F%2Frr.vipstreams.in%2Falpha%2Fjs%2Funion-vs-atletico-tucuman%2F1%2Fplaylist.m3u8|Referer=https%3A%2F%2Fembedme.top'
    play_video(name, link, icon, is_ffmpeg=True)


def runner(params):
    mode = params.get('mode')
    name = params.get('title')
    url = params.get('link')
    icon = params.get('thumbnail')
    
    if mode == 'streamed_main':
        main_menu()
    
    elif mode == 'streamed_get_list':
        get_list(url)
        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    
    elif mode == 'streamed_get_links':
        get_links(name, url, icon)
    