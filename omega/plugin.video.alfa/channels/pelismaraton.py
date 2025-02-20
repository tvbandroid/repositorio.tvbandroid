# -*- coding: utf-8 -*-
# -*- Channel PelisMaraton -*-
# -*- Created for Alfa-addon -*-
# -*- By the Alfa Develop Group -*-

import sys
PY3 = False
if sys.version_info[0] >= 3: PY3 = True; unicode = str; unichr = chr; long = int

import re

from core import tmdb
from core import httptools
from core.item import Item
from core import scrapertools
from core import servertools
from bs4 import BeautifulSoup
from core import jsontools as json
from channelselector import get_thumb
from platformcode import config, logger
from modules import filtertools
from modules import autoplay

IDIOMAS = {'lat': 'LAT', 'spain': 'CAST', 'sub': 'VOSE'}
list_language = list(IDIOMAS.values())

list_quality = []

list_servers = [
    'fembed',
    'streampe',
    'evoload',
    'uqload',
    'upstream'
    ]


##    YA TODO es   https://embed69.org/ y falta DEsencriptar

canonical = {
             'channel': 'pelismaraton', 
             'host': config.get_setting("current_host", 'pelismaraton', default=''), 
             'host_alt': ["https://pelismaraton.nu/"], 
             'host_black_list': ["https://pelismaraton.in/", "https://pelismaraton.me/", "https://pelismaraton.com/"], 
             'set_tls': True, 'set_tls_min': True, 'retries_cloudflare': 1, 
             'CF': False, 'CF_test': False, 'alfa_s': True
            }
host = canonical['host'] or canonical['host_alt'][0]
host_save = host


def mainlist(item):
    logger.info()
    itemlist = list()
    
    autoplay.init(item.channel, list_servers, list_quality)
    
    itemlist.append(Item(channel=item.channel, title='Peliculas', url=host + 'movies', action='list_all',
                         thumbnail=get_thumb('movies', auto=True)))
    itemlist.append(Item(channel=item.channel, title='Series', url=host + 'series/', action='list_all',
                         thumbnail=get_thumb('tvshows', auto=True)))
    # itemlist.append(Item(channel=item.channel, title='Animacion', url=host + 'animacion/', action='list_all',
                         # thumbnail=get_thumb('anime', auto=True)))
    # itemlist.append(Item(channel=item.channel, title='Dorama', url=host + 'dorama/', action='list_all',
                         # thumbnail=get_thumb('tvshows', auto=True)))
    itemlist.append(Item(channel=item.channel, title='Generos', url=host, action='section',
                         thumbnail=get_thumb('genres', auto=True)))
    itemlist.append(Item(channel=item.channel, title='Por Año', url=host, action='section',
                         thumbnail=get_thumb('year', auto=True)))
    itemlist.append(Item(channel=item.channel, title="Buscar...", action="search", url=host + '?s=',
                         thumbnail=get_thumb("search", auto=True)))
    
    autoplay.show_option(item.channel, itemlist)
    
    return itemlist


# def menu_movies(item):
    # logger.info()

    # itemlist = list()

    # itemlist.append(Item(channel=item.channel, title='Utimas', url=host + 'movies', action='list_all',
                         # thumbnail=get_thumb('last', auto=True)))

    # itemlist.append(Item(channel=item.channel, title='Generos', action='section',
                         # thumbnail=get_thumb('genres', auto=True)))

    # itemlist.append(Item(channel=item.channel, title='Por Año', action='section',
                         # thumbnail=get_thumb('year', auto=True)))

    # return itemlist


def create_soup(url, referer=None, unescape=False):
    logger.info()

    if referer:
        data = httptools.downloadpage(url, headers={'Referer':referer}, canonical=canonical).data
    else:
        data = httptools.downloadpage(url, canonical=canonical).data

    if unescape:
        data = scrapertools.unescape(data)

    soup = BeautifulSoup(data, "html5lib", from_encoding="utf-8")

    return soup


def section(item):
    logger.info()

    itemlist = list()
    base_url = "%s%s" % (host, "pelicula")
    soup = create_soup(base_url)

    is_genre = False
    if item.title == "Generos":
        matches = soup.find("section", class_="widget_categories")
        is_genre = True
    else:
        matches = soup.find("section", class_="Torofilm_movies_annee")

    for elem in matches.find_all("li"):
        url = elem.a["href"]
        title = elem.a.text
        if is_genre:
            cant = elem.a.find("span").text
            title = re.sub(cant, "", elem.a.text)
        else:
            url = '%spelicula-año/%s/' % (host, url)

        itemlist.append(Item(channel=item.channel, title=title, action="list_all", url=url, first=0))

    if not is_genre:
        return itemlist[::-1]
    return itemlist


def list_all(item):
    logger.info()
    itemlist = list()
    
    soup = create_soup(item.url)
    matches = soup.find("ul", class_="MovieList").find_all("li")
    
    for elem in matches:
        url = elem.a["href"]
        title = elem.h2.text
        try:
            year = int(elem.find("span", class_="Date").text)
        except:
            year = "-"
        if elem.img.has_attr("data-src"):
            thumb = elem.img["data-src"]
        elif elem.img.has_attr("src"):
            thumb = elem.img["src"]
        else:
            thumb = ""
        
        new_item = Item(channel=item.channel, title=title, url=url, thumbnail=thumb, infoLabels={"year": year})
        
        if "series/" in url:
            new_item.contentSerieName = title
            new_item.action = "seasons"
            new_item.contentType = 'tvshow'
        else:
            new_item.contentTitle = title
            new_item.action = "findvideos"
            new_item.contentType = 'movie'
        
        itemlist.append(new_item)
    
    tmdb.set_infoLabels_itemlist(itemlist, True)
    
    try:
        url_next_page = soup.find("nav", class_="wp-pagenavi").find_all("a")[-1]["href"]
    except:
        return itemlist
    
    if url_next_page and len(matches) > 16:
        itemlist.append(Item(channel=item.channel, title="Siguiente >>", url=url_next_page, action='list_all'))
    
    return itemlist


def seasons(item):
    logger.info()
    itemlist = list()
    
    infoLabels = item.infoLabels
    
    soup = create_soup(item.url)
    matches = soup.find_all("section", class_="SeasonBx")
    for elem in matches:
        try:
            season = int(scrapertools.find_single_match(elem.text, "Temporada (\d+)"))
        except:
            season = 1
        title = "Temporada %s" % season
        infoLabels["season"] = season
        url = elem.a['href']
        
        itemlist.append(Item(channel=item.channel, title=title, url=url, action='episodesxseasons',
                             context=filtertools.context(item, list_language, list_quality), infoLabels=infoLabels, 
                             contentType='season'))
    
    tmdb.set_infoLabels_itemlist(itemlist, True)
    
    if config.get_videolibrary_support() and len(itemlist) > 0:
        itemlist.append(
            Item(channel=item.channel, title='[COLOR yellow]Añadir esta serie a la videoteca[/COLOR]', url=item.url,
                 action="add_serie_to_library", extra="episodios", contentSerieName=item.contentSerieName))
    
    return itemlist


def episodios(item):
    logger.info()
    
    itemlist = []
    templist = seasons(item)
    
    for tempitem in templist:
        itemlist += episodesxseasons(tempitem)

    return itemlist


def episodesxseasons(item):
    logger.info()
    itemlist = list()
    
    infoLabels = item.infoLabels
    season = infoLabels["season"]
    
    soup = create_soup(item.url)
    matches = soup.find_all('tr', class_='Viewed')
    for elem in matches:
        epi_num = elem.find('span', class_='Num').text.strip()
        url = elem.a['href']
        infoLabels["episode"] = epi_num
        title = "%sx%s" % (season, epi_num)
        
        itemlist.append(Item(channel=item.channel, title=title, url=url, action='findvideos',
                             infoLabels=infoLabels, contentType='episode'))
    
    tmdb.set_infoLabels_itemlist(itemlist, True)
    
    return itemlist


def findvideos(item):
    logger.info()
    itemlist = list()
    
    url = create_soup(item.url).find('div', class_='Video').iframe['src']
    url = create_soup(url).find('div', class_='Video').iframe['src']
    data = httptools.downloadpage(url).data
    
                ##############################################
                #       LAS PELICULAS SON embed69.org        #
                #    FALTA DESENCRIPTAR url = vid['link']    #
                ##############################################
    
    # https://pelismaraton.nu/?trembed=0&trid=116671&trtype=1  >>>  https://embed69.org/f/tt32313870/
    if "dataLink" in data:
        data = scrapertools.find_single_match(data, "const dataLink = (.*?);")
        JSONData = json.load(data)
        for elem in JSONData:
            lang = elem['video_language']
            matches = elem['sortedEmbeds']
            for vid in matches:
                server = vid['servername']
                if "filemoon" in server: server = "Tiwikiwi"
                url = vid['link']
                # IDIOMAS.get(lang.lower(), lang)
                itemlist.append(Item(channel=item.channel, action='play', url=url, server=server,
                                     language=lang, infoLabels=item.infoLabels))
    # https://pelismaraton.nu/?trembed=0&trid=116357&trtype=2  >>>  https://xupalace.org/video/tt0115378-1x01/  
    else:
        IDIOMAS = {'0': 'LAT', '1': 'CAST', '2': 'VOSE'}
        SERVER = {'dood': 'Doodstream', 'vidhide': 'Vidhidepro', 'vox': 'Voe', 'stape': 'Streamtape',
                  'filemoon': 'Tiwikiwi', 'filemooon': 'Tiwikiwi', '1fichier': 'onefichier'}
        soup = BeautifulSoup(data, "html5lib", from_encoding="utf-8")
        matches = soup.find('div', class_='OptionsLangDisp').find_all('li')
        for elem in matches:
            url = elem['onclick']
            url = scrapertools.find_single_match(url, "\('([^']+)'")
            lang = elem['data-lang']
            srv = elem.span.text.strip()
            server=SERVER.get(srv, srv)
            itemlist.append(Item(channel=item.channel, action='play', url=url, server=server,
                                 language=IDIOMAS.get(lang.lower(), lang), infoLabels=item.infoLabels))
    # Requerido para FilterTools
    itemlist = filtertools.get_links(itemlist, item, list_language)
    
    # Requerido para AutoPlay
    autoplay.start(itemlist, item)
    
    if config.get_videolibrary_support() and len(itemlist) > 0 and item.extra != 'findvideos':
        itemlist.append(Item(channel=item.channel, title='[COLOR yellow]Añadir esta pelicula a la videoteca[/COLOR]',
                             url=item.url, action="add_pelicula_to_library", extra="findvideos",
                             contentTitle=item.contentTitle))
    return itemlist


# def play(item):
    # logger.info()

    # data = httptools.downloadpage(item.url).url
    # url = httptools.downloadpage(item.url, follow_redirects=False, canonical=canonical).headers.get("location", "")
    #url = scrapertools.find_single_match(data, 'location.href = "([^"]+)')
   
    # if not url.startswith("http"):
        # url = "https:" + url
    # itemlist = servertools.get_servers_itemlist([item.clone(url=url, server="")])
    
    # return itemlist


def search(item, texto):
    logger.info()
    
    try:
        texto = texto.replace(" ", "+")
        item.url = item.url + texto

        if texto != '':
            return list_all(item)
        else:
            return []
    # Se captura la excepción, para no interrumpir al buscador global si un canal falla
    except:
        for line in sys.exc_info():
            logger.error("%s" % line)
        return []

def newest(categoria):
    logger.info()

    item = Item()
    try:
        if categoria in ['peliculas']:
            item.url = host + 'pelicula'
        elif categoria == 'infantiles':
            item.url = host + 'peliculas/animacion/'
        elif categoria == 'terror':
            item.url = host + 'peliculas/terror/'
        itemlist = list_all(item)
        if itemlist[-1].title == 'Siguiente >>':
            itemlist.pop()
    except:
        import sys
        for line in sys.exc_info():
            logger.error("{0}".format(line))
        return []

    return itemlist
