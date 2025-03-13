import sys
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import xbmcgui
import xbmcaddon
from resources.lib.modules.utils import create_listitem, log, play_video
from resources.lib.modules.models import Item


ADDON = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo('name')
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0'
HEADERS = {"User-Agent": USER_AGENT}

def replays_main():
    sites = [
        ['Hockey', 'https://nhlfullgame.com'],
        ['Football', 'https://www.fullreplays.com'],
        ['American Footall', 'https://nfl-video.com'],
        ['Basketball', 'https://basketball-video.com'],
        ['Baseball', 'https://mlblive.net'],
        ['Rugby', 'https://rugby24.net'],
        ['MMA', 'https://fullfightreplays.com'],
        ['Motor Sports', 'https://fullraces.com']
    ]
    create_listitem(
        Item(
            title='[B][COLOR deepskyblue]*** Replays Central ***[/COLOR][/B]'
        )
    )
    for title, link in sites:
        create_listitem(
            Item(
                title,
                type='dir',
                mode='replays_submenu',
                link=link
            )
        )
    
def replays_submenu(name, url):
    base_url = f'https://{urlparse(url).netloc}'
    HEADERS['Referer'] = base_url
    response = requests.get(url, headers=HEADERS, timeout=10).text
    soup = BeautifulSoup(response, 'html.parser')
    
    if name == 'Hockey':
        matches = soup.find_all(class_='portfolio-thumb ph-link')
        for match in matches:
            title = match.img['title'].rstrip(' NHL Full Game Replay')
            link = f"{base_url}{match.a['href']}"
            thumbnail = f"{base_url}{match.img['src']}"
            create_listitem(
                Item(
                    title,
                    mode='replays_links',
                    link=link,
                    thumbnail=thumbnail,
                    title2=name
                )
            )
        next_page = soup.find(class_='swchItem swchItem-next')
        if next_page:
            create_listitem(
                Item(
                    'Next Page',
                    type='dir',
                    mode='replays_submenu',
                    link=f"{base_url}{next_page['href']}",
                    title2=name
                )
            )
    
    elif name == 'Football':
        matches = soup.find_all(class_='row')
        for match in matches:
            articles = match.find_all('article')
            for article in articles:
                if article is None:
                    continue
                title = article.h2.text
                link = article.a['href']
                thumbnail = article.a.img['src']
                create_listitem(
                    Item(
                        title,
                        mode='replays_links',
                        link=link,
                        thumbnail=thumbnail,
                        title2=name
                    )
                )
        next_page = soup.find(class_='next page-numbers')
        if next_page:
            create_listitem(
                Item(
                    'Next Page',
                    type='dir',
                    mode='replays_submenu',
                    link=next_page['href'],
                    title2=name
                )
            )
    
    else:
        matches = soup.find_all(class_='short_item')
        for match in matches:
            title = match.h3.a.text
            link = f"{base_url}{match.a['href']}"
            thumbnail = f"{base_url}{match.a.img['src']}"
            create_listitem(
                Item(
                    title,
                    mode='replays_links',
                    link=link,
                    thumbnail=thumbnail,
                    title2=name
                )
            )
        next_page = soup.find(class_='swchItem swchItem-next')
        if next_page:
            create_listitem(
                Item(
                    'Next Page',
                    type='dir',
                    mode='replays_submenu',
                    link=f"{base_url}{next_page['href']}",
                    title2=name
                )
            )

def replays_links(name, url, icon, name2):
    links = []
    labels = []
    base_url = f"https://{urlparse(url).netloc}"
    HEADERS['Referer'] = base_url
    response = requests.get(url, headers=HEADERS, timeout=10).text
    soup = BeautifulSoup(response, 'html.parser')
    
    if name2 == 'Football':
        sources = soup.find_all(class_='frc-sources-wrap')
        for source in sources:
            host = source.find(class_='frc-vid-label').text.lower()
            for button in source.find_all(class_='vlog-button'):
                title = f'{button.text.strip()} - {host.capitalize()}'
                link = button.get('data-sc')
                if button is None:
                    continue
                labels.append(title)
                links.append(link)
    
    else:
        for button in soup.find_all(class_='su-button'):
            link = button['href']
            if 'nfl-replays' in link:
                response = requests.get(link, headers=HEADERS, timeout=10).text
                _soup = BeautifulSoup(response, 'html.parser')
                iframe = _soup.find('iframe')
                if not iframe:
                    continue
                link = iframe['src']
            if link.startswith('//'):
                link = f'https:{link}'
            title = link.split('/')[2]
            labels.append(title)
            links.append(link)
        for iframe in soup.find_all('iframe'):
            link = iframe['src']
            if link.startswith('//'):
                link = f'https:{link}'
            title = link.split('/')[2]
            labels.append(title)
            links.append(link)
    
    if not links:
        xbmcgui.Dialog().notification(ADDON_NAME, 'No links were found.')
        sys.exit()
    if name2 == 'Hockey':
        labels.reverse()
        links.reverse()
    ret = xbmcgui.Dialog().select('Select a Link', labels)
    if ret > -1:
        title = labels[ret]
        link = links[ret]
    else:
        sys.exit()
    play_video(name, link, icon)

def runner(params: dict):
    mode = params.get('mode')
    name = params.get('title')
    url = params.get('link')
    icon = params.get('thumbnail')
    name2 = params.get('title2')
    
    if mode == 'replays_main':
        replays_main()
    
    elif mode == 'replays_submenu':
        name = name2 if name == 'Next Page' else name
        replays_submenu(name, url)
    
    elif mode == 'replays_links':
        replays_links(name, url, icon, name2)