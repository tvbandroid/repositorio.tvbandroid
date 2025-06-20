# -*- coding: utf-8 -*-
import re

from core import httptools
from core import scrapertools
from core.item import Item
from core import servertools
from core import urlparse
from platformcode import config, logger
from bs4 import BeautifulSoup

canonical = {
             'channel': 'cumlouder', 
             'host': config.get_setting("current_host", 'cumlouder', default=''), 
             'host_alt': ["https://www.cumlouder.com/"], 
             'host_black_list': [], 
             'set_tls': True, 'set_tls_min': True, 'retries_cloudflare': 1, 'cf_assistant': False, 
             'CF': False, 'CF_test': False, 'alfa_s': True
            }
host = canonical['host'] or canonical['host_alt'][0]


def mainlist(item):
    logger.info()
    itemlist = []
    config.set_setting("url_error", False, "cumlouder")
    itemlist.append(item.clone(title="Clips", action="lista", url= host + "porn/"))
    itemlist.append(item.clone(title="Últimos videos", action="lista", url= host + "2/?s=last"))
    itemlist.append(item.clone(title="Pornstars", action="submenu", url=host + "girls/"))
    itemlist.append(item.clone(title="Listas", action="categorias", url= host + "series/"))
    itemlist.append(item.clone(title="Canal", action="submenu", url=host + "channels/"))
    itemlist.append(item.clone(title="Categorias", action="categorias", url= host + "categories/"))
    itemlist.append(item.clone(title="Buscar Clips", action="search"))
    itemlist.append(item.clone(title="Buscar", action="search"))
    return itemlist


def search(item, texto):
    logger.info()
    # texto = texto.replace(" ", "+")
    if "Clips" in item.title:
        item.url = "%ssearch?q=%s" % (host,texto.replace(" ", "+"))
    else:
        item.url = "%sporn-videos/%s" % (host,texto.replace(" ", "-"))  #?show=cumlouder or all
    try:
        return lista(item)
    except Exception:
        import sys
        for line in sys.exc_info():
            logger.error("%s" % line)
        return []


def submenu(item):
    logger.info()
    itemlist = []
    if "/channels/" in item.url:
        itemlist.append(item.clone(title="Mas Populares", action="categorias", url=host + "channels/1/"))
    else:
        itemlist.append(item.clone(title="Mas Populares", action="categorias", url=host + "girls/1/"))
    for letra in "abcdefghijklmnopqrstuvwxyz":
        itemlist.append(item.clone(title=letra.upper(), url=urlparse.urljoin(item.url, letra), action="categorias"))
    return itemlist


def categorias(item):
    logger.info()
    itemlist = []
    soup = create_soup(item.url)
    matches = soup.find('div', class_='listado-escenas').find_all('a', class_='muestra-escena')
    for elem in matches:
        url = elem['href']
        thumbnail = elem.img['data-src']
        if elem.find('span', class_='cantidad'):
            title = elem.find('span', class_='categoria').text.strip()
            cantidad = elem.find('span', class_='cantidad').text.strip()
        else:
            title = elem.h2.text.strip()
            if elem.find('span', class_='videos'):
                cantidad = elem.find('span', class_='videos').text.strip()
            else:
                cantidad = elem.p.text.strip()
            cantidad =  cantidad.replace(" Videos", "")
        title="%s (%s)" % (title, cantidad)
        url = urlparse.urljoin(item.url, url)
        if not thumbnail.startswith("https"):
            thumbnail = "https:%s" % thumbnail
        itemlist.append(item.clone(action="lista", title=title, url=url, fanart=thumbnail, thumbnail=thumbnail))
    if not "/girls/" in item.url:
        itemlist.sort(key=lambda x: x.title)
    next_page = soup.find("a", string=re.compile(r"^Next"))
    if next_page:
        next_page = next_page['href']
        next_page = urlparse.urljoin(item.url,next_page)
        itemlist.append(item.clone(action="categorias", title="[COLOR blue]Página Siguiente >>[/COLOR]", url=next_page) )
    return itemlist


def create_soup(url, referer=None, unescape=False):
    logger.info()
    if referer:
        data = httptools.downloadpage(url, headers={'Referer': referer}, canonical=canonical).data
    else:
        data = httptools.downloadpage(url, canonical=canonical).data
    if unescape:
        data = scrapertools.unescape(data)
    soup = BeautifulSoup(data, "html5lib", from_encoding="utf-8")
    return soup


def lista(item):
    logger.info()
    itemlist = []
    soup = create_soup(item.url)
    matches = soup.find('div', class_='listado-escenas').find_all('a', class_='muestra-escena')
    for elem in matches:
        logger.debug()
        # id = scrapertools.find_single_match(elem['onclick'], '(\d+)')    ### 
        # embed = "%sembed/%s/" %(host, id)
        url = elem['href']
        title = elem.h2.text.strip()
        thumbnail = elem.img['data-src']
        time = elem.find('span', class_='minutos').text.strip().replace("min", "m")
        quality = elem.find('span', class_='hd')
        if quality:
            title = "[COLOR yellow]%s[/COLOR] [COLOR red]HD[/COLOR] %s" % (time,title)
        else:
            title = "[COLOR yellow]%s[/COLOR] %s" % (time,title)
        url = urlparse.urljoin(host, url)
        if not thumbnail.startswith("https"):
            thumbnail = "https:%s" % thumbnail
        plot = ""
        action = "play"
        if logger.info() is False:
            action = "findvideos"
        itemlist.append(Item(channel = item.channel, action=action, title=title, url=url, thumbnail=thumbnail,
                             fanart=thumbnail, contentTitle=title,  plot=plot))
    next_page = soup.find("a", string=re.compile(r"^Next"))
    if next_page:
        next_page = next_page['href']
        next_page = urlparse.urljoin(item.url,next_page)
        itemlist.append(item.clone(action="lista", title="[COLOR blue]Página Siguiente >>[/COLOR]", url=next_page) )
    return itemlist


def findvideos(item):
    logger.info()
    itemlist = []
    itemlist.append(Item(channel=item.channel, action="play", title= "%s" , contentTitle=item.contentTitle, url=item.url)) 
    itemlist = servertools.get_servers_itemlist(itemlist, lambda i: i.title % i.server.capitalize()) 
    return itemlist


def play(item):
    logger.info()
    itemlist = []
    soup = create_soup(item.url)
    if soup.find_all('a', href=re.compile(r"/(?:girl|chica)/[a-z0-9-]+")):
        pornstars = soup.find_all('a', href=re.compile(r"/(?:girl|chica)/[a-z0-9-]+"))
        for x, value in enumerate(pornstars):
            pornstars[x] = value.get_text(strip=True)
        pornstar = ' & '.join(pornstars)
        pornstar = " [COLOR cyan]%s" % pornstar
        lista = item.contentTitle.split('[/COLOR]')
        lista.insert (2, pornstar)
        item.contentTitle = '[/COLOR]'.join(lista)
    itemlist.append(Item(channel=item.channel, action="play", title= "%s" , contentTitle=item.contentTitle, url=item.url)) 
    itemlist = servertools.get_servers_itemlist(itemlist, lambda i: i.title % i.server.capitalize()) 
    return itemlist