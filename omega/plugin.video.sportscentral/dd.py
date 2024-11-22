import sys
import re
import json
from urllib.parse import quote_plus, urljoin
import xbmc
import xbmcaddon
import xbmcplugin
import xbmcgui
import requests
from bs4 import BeautifulSoup
from resources.lib.modules.utils import create_listitem, play_video
from resources.lib.modules.models import Item


BASE_URL = 'https://dlhd.so'
SCHEDULE = urljoin(BASE_URL, '/schedule/schedule-generated.json')
EXTRA = urljoin(BASE_URL, '/schedule/schedule-extra-generated.json')
CHANNELS = f'{BASE_URL}/24-7-channels.php'
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
HEADERS = {
    'User-Agent': USER_AGENT,
    'Referer': f'{BASE_URL}/'
}
SOURCE = re.compile("source: '(.+?)',")
KODI_VER = float(xbmc.getInfoLabel("System.BuildVersion")[:4])
ADDON = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_ICON = ADDON.getAddonInfo('icon')
ADDON_FANART = ADDON.getAddonInfo('fanart')


def main():
    xbmcplugin.setPluginCategory(int(sys.argv[1]), 'Live Sports')
    schedule = requests.get(SCHEDULE, headers=HEADERS, timeout=10).json()
    extra = requests.get(EXTRA, headers=HEADERS, timeout=10).json()
    #schedule.update(extra)
    for key in schedule.keys():
        create_listitem(
            Item(
                'Channels',
                type='dir',
                mode='ddlive_channels',
                thumbnail=ADDON_ICON,
                fanart=ADDON_FANART
            )
        )
        create_listitem(
            Item(
                key.split(' -')[0],
                type='dir',
                link=json.dumps(schedule[key]),
                mode='ddlive_categories',
                thumbnail=ADDON_ICON,
                fanart=ADDON_FANART
            )
        )

def live_categories(url: str):
    categories = json.loads(url)
    for cat in categories.keys():
        create_listitem(
            Item(
                cat,
                type='dir',
                link=json.dumps(categories[cat]),
                mode='ddlive_submenu',
                thumbnail=ADDON_ICON,
                fanart=ADDON_FANART
            )
        )

def submenu(name: str, url: str):
    xbmcplugin.setPluginCategory(int(sys.argv[1]), name)
    events = json.loads(url)
    for event in events:
        create_listitem(
            Item(
                event.get('event', ''),
                link=json.dumps([[channel.get('channel_name'), f"{BASE_URL}/stream/stream-{channel.get('channel_id')}.php"] for channel in event.get('channels')]),
                mode='ddlive_links',
                thumbnail=ADDON_ICON,
                fanart=ADDON_FANART
                )
            )

def get_channels():
    xbmcplugin.setPluginCategory(int(sys.argv[1]), 'Live Channels')
    response = requests.get(CHANNELS, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    password = ADDON.getSetting('adult_pw')
    channels = []
    for a in soup.find_all('a')[8:]:
        title = a.text
        link = f"{BASE_URL}{a['href']}"
        if '18+' in title and password != 'xxXXxx':
            continue
        if not link in channels:
            channels.append(link)
            create_listitem(
                Item(
                    title,
                    link=link,
                    mode='ddlive_links',
                    thumbnail=ADDON_ICON,
                    fanart=ADDON_FANART
                )
            )

def get_links(name, url: str):
    if url.startswith('['):
        url = json.loads(url)
        if len(url) > 1:
            labels = [_url[0] for _url in url]
            links = [_url[1] for _url in url]
            ret = xbmcgui.Dialog().select('Select a Link', labels)
            if ret > -1:
                url = links[ret]
            else:
                sys.exit()
        else:
            url = url[0][1]
    response = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    iframe = soup.find('iframe', attrs={'id': 'thatframe'})
    if not iframe:
        sys.exit()
    url2 = iframe.get('src')
    if not url2:
        sys.exit()
    HEADERS['Referer'] = url
    response2 = requests.get(url2, headers=HEADERS, timeout=10)
    link = re.findall(SOURCE, response2.text)
    if not link:
        sys.exit()
    link = link[0]
    splitted = url2.split('/')
    referer = f"{quote_plus('/'.join(splitted[:3]))}"
    user_agent = quote_plus(USER_AGENT)
    headers_ = f'Referer={referer}/&Origin={referer}&Connection=keep-alive&User-Agent={user_agent}'
    link = f'{link}|{headers_}'
    play_video(name, link, ADDON_ICON, name, is_ffmpeg=True)

def runner(p: dict):
    name = p.get('title', '')
    url = p.get('link', '')
    mode = p.get('mode')
    
    if mode == 'ddlive_main':
        main()
    
    elif mode == 'ddlive_categories':
        live_categories(url)
    
    elif mode == 'ddlive_submenu':
        submenu(name, url)
    
    elif mode == 'ddlive_channels_main':
        get_channels()
    
    elif mode == 'ddlive_channels':
        get_channels()
    
    elif mode == 'ddlive_links':
        get_links(name, url)
    
   