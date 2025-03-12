import re
import sys
import json
import time
from urllib.parse import quote
from os.path import join
import requests
import xbmc
import xbmcaddon
import xbmcvfs
import xbmcgui
from resources.lib.modules.utils import create_listitem, play_video, log
from resources.lib.modules.models import Item


ADDON = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
M3U_PATH = join(ADDON_DATA, 'tvapp.m3u')
JSON_PATH = join(ADDON_DATA, 'tvapp.json')
M3U_URL = 'https://thetvapp-m3u.data-search.workers.dev/playlist'
TIMESTAMP = join(ADDON_DATA, 'timestamp.txt')
BASE_URL = 'https://thetvapp.to/'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0'

def fetch_m3u():
    response = requests.get(M3U_URL, timeout=10)
    if 'Rate Limit Reached' not in response.text and response.status_code == 200:
        write_file(M3U_PATH, response.text)
        return True
    dialog = xbmcgui.Dialog()
    dialog.ok(ADDON_NAME, 'The list could not be downloaded.\nThe site only allows the list to be downloaded\n5 times every 2 hours per IP Address.\nCheck your internet connection or try again in 2 hours.')
    return False

def write_file(file_path, string):
    with open(file_path, 'w', encoding='utf-8', errors='ignore') as f:
        f.write(string)

def open_file(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def parse_m3u(string:str) -> dict:
    items = {}
    pattern = (
        r'#EXTINF:-1\s+'
        r'tvg-id="(?P<tvg_id>[^"]+)"\s+'
        r'tvg-name="(?P<title>[^"]+)"\s+'
        r'tvg-logo="(?P<thumbnail>[^"]+)"\s+'
        r'group-title="(?P<category>[^"]+)",'
        r'(?P<summary>[^#\n]+)\n'
        r'(?P<link>https?://[^\s]+)'
    )
    
    matches = re.finditer(pattern, string, re.MULTILINE)
    
    for match in matches:
        title = match.group('title')
        thumbnail = match.group('thumbnail')
        category = match.group('category')
        summary = match.group('summary').strip()
        link = match.group('link')
        if category not in items:
            items[category] = []
        items[category].append(
            {
                'type': 'item',
                'title': title,
                'link': f'{link}|Referer={BASE_URL}&Origin={BASE_URL}&Connection=keep-alive&User-Agent={quote(USER_AGENT)}',
                'thumbnail': thumbnail,
                'summary': summary
            }
        )
    return items

def create_json():
    m3u = open_file(M3U_PATH)
    items = parse_m3u(m3u)
    write_file(JSON_PATH, json.dumps(items, indent=2))

def create_timestamp():
    timestamp = time.time() + 7200
    write_file(TIMESTAMP, str(timestamp))

def refresh():
    timestamp = open_file(TIMESTAMP)
    if float(timestamp) < time.time():
        if fetch_m3u() is True:
            create_json()
        create_timestamp()
        xbmc.executebuiltin("Container.Refresh")

def main():
    items = json.loads(open_file(JSON_PATH))
    for item in iter(items):
        create_listitem(
            Item(
                item,
                type='dir',
                mode='tvapp_submenu'
        )
    )
    create_listitem(
        Item(
            '[B][COLOR yellow]Refresh List[/COLOR][/B]',
            mode='tvapp_refresh'
        )
    )

def submenu(name: str):
    items = json.loads(open_file(JSON_PATH))
    for item in items.get(name, []):
        item['mode'] = 'tvapp_play_video'
        create_listitem(item)

def play(name, url, icon, description):
    play_video(name, url, icon, description, is_ffmpeg=True)

def runner(params):
    if not xbmcvfs.exists(ADDON_DATA):
        xbmcvfs.mkdirs(ADDON_DATA)
    if not xbmcvfs.exists(M3U_PATH):
        if fetch_m3u() is True:
            create_json()
        create_timestamp()
    refresh()
    
    mode = params.get('mode')
    name = params.get('title')
    url = params.get('link')
    icon = params.get('thumbnail')
    description = params.get('summary')
    
    if mode == 'tvapp_main':
        main()
    
    elif mode == 'tvapp_submenu':
        submenu(name)
    
    elif mode == 'tvapp_refresh':
        dialog = xbmcgui.Dialog()
        yes = dialog.yesno(ADDON_NAME, 'Warning! The site only allows 5 refreshes\nevery 2 hours per IP Address.\nOnly use this option if links are not resolving.\nDo you wish to proceed?')
        if yes:
            if fetch_m3u() is True:
                create_json()
            create_timestamp()
            xbmc.executebuiltin("Container.Refresh")
    
    elif mode == 'tvapp_play_video':
        play(name, url, icon, description)
        