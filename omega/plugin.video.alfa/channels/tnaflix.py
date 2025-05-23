# -*- coding: utf-8 -*-
#------------------------------------------------------------
import re

from platformcode import config, logger
from core import scrapertools
from core.item import Item
from core import servertools
from core import httptools
from core import urlparse

canonical = {
             'channel': 'tnaflix', 
             'host': config.get_setting("current_host", 'tnaflix', default=''), 
             'host_alt': ["https://www.tnaflix.com/"], 
             'host_black_list': [], 
             'set_tls': True, 'set_tls_min': True, 'retries_cloudflare': 1, 'cf_assistant': False, 
             'CF': False, 'CF_test': False, 'alfa_s': True
            }
host = canonical['host'] or canonical['host_alt'][0]


def mainlist(item):
    logger.info()
    itemlist = []
    itemlist.append(item.clone(title="Nuevas" , action="lista", url=host + "new/?d=all&period=all"))
    itemlist.append(item.clone(title="Popular" , action="lista", url=host + "popular/?d=all&period=all"))
    itemlist.append(item.clone(title="Mejor valorado" , action="lista", url=host + "toprated/?d=all&period=month"))
    itemlist.append(item.clone(title="Canal" , action="catalogo", url=host + "channels?page=1"))
    itemlist.append(item.clone(title="PornStars" , action="categorias", url=host + "pornstars?page=1"))
    itemlist.append(item.clone(title="Categorias" , action="categorias", url=host + "categories/"))
    itemlist.append(item.clone(title="Buscar", action="search"))
    return itemlist


def search(item, texto):
    logger.info()
    texto = texto.replace(" ", "+")
    item.url = "%ssearch.php?what=%s&&sb=date" % (host, texto)
    try:
        return lista(item)
    except Exception:
        import sys
        for line in sys.exc_info():
            logger.error("%s" % line)
        return []


def catalogo(item):
    logger.info()
    itemlist = []
    data = httptools.downloadpage(item.url, canonical=canonical).data
    patron = '<a class="thumb.*?' 
    patron += 'href="([^"]+)">.*?'
    patron  += 'thumb-title">([^>]+)<.*?'
    patron += 'src="([^"]+)".*?'
    patron  += '</i>([^<]+)'
    matches = re.compile(patron,re.DOTALL).findall(data)
    for scrapedurl,scrapedtitle,scrapedthumbnail,cantidad in matches:
        scrapedurl = urlparse.urljoin(item.url,scrapedurl)
        title = "%s (%s)" % (scrapedtitle,cantidad)
        scrapedplot = ""
        itemlist.append(item.clone(action="lista", title=title, url=scrapedurl,
                              fanart=scrapedthumbnail, thumbnail=scrapedthumbnail, plot=scrapedplot) )
    next_page_url = scrapertools.find_single_match(data,'pagination-next">.*?href="([^"]+)">')
    if next_page_url!="":
        next_page_url = urlparse.urljoin(item.url,next_page_url)
        itemlist.append(item.clone(action="catalogo" , title="[COLOR blue]Página Siguiente >>[/COLOR]",  url=next_page_url , folder=True) )
    return itemlist


def categorias(item):
    logger.info()
    itemlist = []
    data = httptools.downloadpage(item.url, canonical=canonical).data
    data = re.sub(r"\n|\r|\t|&nbsp;|<br>", "", data)
    patron = '<a class="thumb.*?' 
    patron += 'href="([^"]+)">.*?'
    patron += 'src="([^"]+)".*?'
    patron  += 'thumb-title">([^>]+)<.*?'
    patron  += '</i>([^<]+)'
    matches = re.compile(patron,re.DOTALL).findall(data)
    for scrapedurl,scrapedthumbnail,scrapedtitle,cantidad in matches:
        scrapedplot = ""
        if not scrapedthumbnail.startswith("https"):
            scrapedthumbnail = "https:%s" % scrapedthumbnail
        scrapedurl = urlparse.urljoin(item.url,scrapedurl)
        if not scrapedurl.startswith("https"):
            scrapedurl = "https:%s" % scrapedurl
        if "profile" not in scrapedurl:
            scrapedurl += "/most-recent/?hd=0&d=all"
        scrapedtitle = "%s (%s)" % (scrapedtitle,cantidad)
        itemlist.append(item.clone(action="lista", title=scrapedtitle , url=scrapedurl ,
                              fanart=scrapedthumbnail, thumbnail=scrapedthumbnail , plot=scrapedplot) )
    next_page_url = scrapertools.find_single_match(data,'pagination-next">.*?href="([^"]+)">')
    if next_page_url!="":
        next_page_url = urlparse.urljoin(item.url,next_page_url)
        itemlist.append(item.clone(action="categorias", title="[COLOR blue]Página Siguiente >>[/COLOR]", url=next_page_url , folder=True) )
    return itemlist


def lista(item):
    logger.info()
    itemlist = []
    data = httptools.downloadpage(item.url, canonical=canonical).data
    data = re.sub(r"\n|\r|\t|&nbsp;|<br>", "", data)
    patron = '<a class="thumb.*?' 
    patron += 'href=".*?/video(\d+).*?'
    patron += 'data-src="([^"]+)" alt="([^"]+)".*?'
    patron += 'video-duration">([^<]+)</div>.*?'
    patron += 'max-quality">([^<]+)<'
    matches = re.compile(patron,re.DOTALL).findall(data)
    for scrapedurl,scrapedthumbnail,scrapedtitle,duracion,quality in matches:
        url = "https://player.tnaflix.com/video/%s" %scrapedurl
        title = "[COLOR yellow]%s[/COLOR] %s" % (duracion, scrapedtitle)
        if quality:
            quality= scrapertools.find_single_match(quality, '>(\d+p)<')
            title = "[COLOR yellow]%s[/COLOR] [COLOR red]%s[/COLOR] %s" % (duracion, quality, scrapedtitle)
        contentTitle = title
        thumbnail = scrapedthumbnail
        plot = ""
        action = "play"
        if logger.info() is False:
            action = "findvideos"
        itemlist.append(item.clone(action=action, title=title , url=url, thumbnail=thumbnail,
                             fanart=thumbnail, plot=plot, contentTitle = contentTitle))
    next_page_url = scrapertools.find_single_match(data,'pagination-next">.*?href="([^"]+)">')
    if next_page_url!="":
        next_page_url = urlparse.urljoin(item.url,next_page_url)
        itemlist.append(item.clone(action="lista", title="[COLOR blue]Página Siguiente >>[/COLOR]", url=next_page_url) )
    return itemlist


def findvideos(item):
    logger.info()
    itemlist = []
    itemlist.append(item.clone(action="play", title= "%s", contentTitle = item.title, url=item.url))
    itemlist = servertools.get_servers_itemlist(itemlist, lambda i: i.title % i.server.capitalize())
    return itemlist


def play(item):
    logger.info()
    itemlist = []
    itemlist.append(item.clone(action="play", title= "%s", contentTitle = item.title, url=item.url))
    itemlist = servertools.get_servers_itemlist(itemlist, lambda i: i.title % i.server.capitalize())
    return itemlist

