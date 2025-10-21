# -*- coding: utf-8 -*-
# -*- Channel SeriesKao -*-
# -*- Created for Alfa-addon -*-
# -*- By the Alfa Develop Group -*-
import sys
import base64

from core import tmdb
from core import httptools
from core.item import Item
from core import servertools
from core import scrapertools
from core import urlparse
from channelselector import get_thumb
from platformcode import config, logger
from modules import filtertools
from modules import autoplay
from bs4 import BeautifulSoup


IDIOMAS = {'2': 'VOSE', "0": "LAT", "1": "CAST", "JAP": "JA"}

list_language = list(IDIOMAS.values())

list_quality = []

list_servers = [
    'gvideo',
    'fembed',
    'directo'
    ]

canonical = {
             'channel': 'serieskao', 
             'host': config.get_setting("current_host", 'serieskao', default=''), 
             'host_alt': ["https://serieskao.top/"], 
             'host_black_list': ["https://serieskao.org/", "https://serieskao.net/"], 
             'pattern': ['<link\s*rel="shortcut\s*icon"\s*href="(\w+\:\/\/[^\/]+\/)'], 
             'set_tls': True, 'set_tls_min': True, 'retries_cloudflare': 1,
             'CF': False, 'CF_test': False, 'alfa_s': True
            }
host = canonical['host'] or canonical['host_alt'][0]


def mainlist(item):
    logger.info()
    itemlist = list()
    
    autoplay.init(item.channel, list_servers, list_quality)
    
    # itemlist.append(Item(channel=item.channel, title='embed69', action='findvideos', url="https://serieskao.top/pelicula/la-promesa-de-irene-bxKhP7"))
    # itemlist.append(Item(channel=item.channel, title='xupalace', action='findvideos', url="https://serieskao.top/pelicula/no-way-out-2023"))
    
    itemlist.append(Item(channel=item.channel, title='Todas', action='list_all', url=host + "peliculas",
                         thumbnail=get_thumb('movies', auto=True), type="peliculas"))
    itemlist.append(Item(channel=item.channel, title='Por Género', action='genres', url=host,
                         thumbnail=get_thumb('movies', auto=True), type="peliculas"))
    itemlist.append(Item(channel=item.channel, title='Año', action='genres', url=host,
                         thumbnail=get_thumb('movies', auto=True), type="peliculas"))
    itemlist.append(Item(channel=item.channel, title='Series', url=host + 'series', action='list_all',
                         thumbnail=get_thumb('tvshows', auto=True), type="series"))
    itemlist.append(Item(channel=item.channel, title='Por Género', action='genres', url=host,
                         thumbnail=get_thumb('tvshows', auto=True), type="series"))
    itemlist.append(Item(channel=item.channel, title='Año', action='genres', url=host,
                         thumbnail=get_thumb('tvshows', auto=True), type="series"))
    itemlist.append(Item(channel=item.channel, title='Anime', url=host + 'animes', action='list_all',
                         thumbnail=get_thumb('anime', auto=True), type="animes"))
    itemlist.append(Item(channel=item.channel, title='Por Género', action='genres', url=host,
                         thumbnail=get_thumb('anime', auto=True), type="animes"))
    itemlist.append(Item(channel=item.channel, title='Año', action='genres', url=host,
                         thumbnail=get_thumb('anime', auto=True), type="animes"))
    itemlist.append(Item(channel=item.channel, title='Dorama', url=host + 'generos/dorama', action='list_all',
                         thumbnail=get_thumb('anime', auto=True), type="animes"))
    itemlist.append(Item(channel=item.channel, title="Buscar...", action="search",
                         thumbnail=get_thumb("search", auto=True)))
    
    itemlist = filtertools.show_option(itemlist, item.channel, list_language, list_quality)
    
    autoplay.show_option(item.channel, itemlist)
    
    return itemlist


def genres(item):
    logger.info()
    itemlist = list()
    existe = []
    data = httptools.downloadpage(item.url).data
    if 'Por Género' in item.title:
        matches = scrapertools.find_multiple_matches(data, '(?is)href="/(genero[^"]+)">([^<]+)')
    else:
        matches = scrapertools.find_multiple_matches(data, '(?is)href="/(year[^"]+)">(\d+)<')
    for url, title in matches:
        url += "/%s" %item.type
        if title in existe:
            continue
        existe.append(title)
        itemlist.append(Item(channel=item.channel, title=title, url=host + url,
                 action="list_all"))
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


def list_all(item):
    logger.info()
    itemlist = list()
    year = ""
    soup = create_soup(item.url)
    matches = soup.find_all("a", class_="poster-card")
    for elem in matches:
        url = elem['href']
        # title = elem['title']
        title = elem.h3.text
        thumbnail = elem.img['src']
        year = scrapertools.find_single_match(title, ' \((\d+)\)')
        title = scrapertools.find_single_match(title, '(.*?) \(\d+\)')
        if year == '':
            year = '-'
        new_item = Item(channel=item.channel, title=title, url=url, thumbnail=thumbnail, infoLabels={"year": year})
        if "/serie/" in url or "/anime/" in url:
            new_item.contentSerieName = title
            new_item.action = "seasons"
            new_item.context = filtertools.context(item, list_language, list_quality)
        else:
            new_item.contentTitle = title
            new_item.action = "findvideos"
        itemlist.append(new_item)
    
    tmdb.set_infoLabels_itemlist(itemlist, True)
    
    next_page = soup.find('a', rel='next')
    if next_page:
        next_page = next_page['href']
        next_page = urlparse.urljoin(item.url,next_page)
        itemlist.append(item.clone(action="list_all", title="[COLOR blue]Página Siguiente >>[/COLOR]", url=next_page) )
    return itemlist


def seasons(item):
    logger.info()
    itemlist = list()
    soup = create_soup(item.url)
    matches = soup.find('ul', id='season-tabs').find_all('li')
    infoLabels = item.infoLabels
    for elem in matches:
        season = scrapertools.find_single_match(elem.text, '\d+')
        infoLabels["season"] = season
        
        itemlist.append(Item(channel=item.channel, title="Temporada %s" %season, url=item.url, action='episodesxseasons',
                             infoLabels=infoLabels))
    
    tmdb.set_infoLabels_itemlist(itemlist, True)
    
    if config.get_videolibrary_support() and len(itemlist) > 0 and not item.add_videolibrary:
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
    season = item.infoLabels["season"]
    
    id = "season-%s" %season
    
    soup = create_soup(item.url)
    matches = soup.find('div', id=id).find_all('a')
    for elem in matches:
        url = elem['href']
        epi_num = scrapertools.find_single_match(url, "/capitulo/(\d+)")
        infoLabels["episode"] = epi_num
        title = "%sx%s" % (season, epi_num)
        itemlist.append(Item(channel=item.channel, title=title, url=url, action='findvideos',
                             infoLabels=infoLabels))
    
    tmdb.set_infoLabels_itemlist(itemlist, True)
    
    return itemlist


def findvideos(item):
    logger.info()
    itemlist = list()
    
    data = httptools.downloadpage(item.url).data
    url = scrapertools.find_single_match(data, "videoSources\s*=\s*\[\s*'([^']+)")
    
    data = httptools.downloadpage(url).data
    soup = BeautifulSoup(data, "html5lib", from_encoding="utf-8")
    
    if "embed69" in url and "No folders found" not in data:
        import ast
        
        clave = scrapertools.find_single_match(data, r"decryptLink\(server.link, '(.+?)'\),")
        dataLinkString = scrapertools.find_single_match(data, r"dataLink\s*=\s*([^;]+)")
        
        dataLinkString = dataLinkString.replace(r"\/", "/")
        dataLink = ast.literal_eval(dataLinkString)
        
        for langSection in dataLink:
            language = langSection.get('video_language', 'LAT')
            language = IDIOMAS.get(language, language)
            for elem in langSection['sortedEmbeds']:
                if elem['servername'] != "download":
                    vid = elem['link']
                    if clave:
                        from lib.crylink import crylink
                        vid = crylink(vid, clave)
                    else:
                        vid = scrapertools.find_single_match(vid, '\.(eyJs.*?)\.')
                        vid += "="
                        vid = base64.b64decode(vid).decode()
                        vid = scrapertools.find_single_match(vid, '"link":"([^"]+)"')
                    itemlist.append(Item(channel=item.channel, title='%s', action='play', url=vid,
                                           language=language, infoLabels=item.infoLabels))
    
    else:
        matches = soup.find('div', class_='OptionsLangDisp').find_all('li')
        for elem in matches:
            vid = elem['onclick']
            lang = elem['data-lang']
            server = elem.span.text.strip()
            vid = scrapertools.find_single_match(vid, "go_to_player(?:Vast|)\('([^']+)")
            if vid.startswith("http"):
                vid = vid
            elif vid:
                try:
                    vid = base64.b64decode(vid).decode()
                except (ValueError, TypeError):
                    vid = url
            else:
                continue
            
            if "1fichier=" in vid or "1fichier" in server:
                vid = scrapertools.find_single_match(vid, '=\?([A-z0-9]+)')
                vid = "https://1fichier.com/?%s" %url
            
            language = IDIOMAS.get(lang, lang)
            if "plusvip" not in vid:
                itemlist.append(Item(channel=item.channel, title='%s', action='play', url=vid,
                                           language=language, infoLabels=item.infoLabels))
    
    itemlist.sort(key=lambda x: x.language)
    
    itemlist = servertools.get_servers_itemlist(itemlist, lambda x: x.title % x.server.capitalize())
    
    # Requerido para FilterTools
    itemlist = filtertools.get_links(itemlist, item, list_language)
    # Requerido para AutoPlay
    autoplay.start(itemlist, item)

    if config.get_videolibrary_support() and len(itemlist) > 0 and item.extra != 'findvideos':
        itemlist.append(Item(channel=item.channel, title='[COLOR yellow]Añadir esta pelicula a la videoteca[/COLOR]',
                             url=item.url, action="add_pelicula_to_library", extra="findvideos",
                             contentTitle=item.contentTitle))

    return itemlist


def search(item, texto):
    logger.info()
    try:
        texto = texto.replace(" ", "+")
        item.url = "%ssearch?s=%s" % (host, texto)

        # item.url = item.url + texto
        item.extra = "buscar"

        if texto != '':
            return list_all(item)
        else:
            return []
    # Se captura la excepción, para no interrumpir al buscador global si un canal falla
    except Exception:
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
            item.url = host + 'pelicula/filtro/?genre=animacion-2'
        elif categoria == 'terror':
            item.url = host + 'pelicula/filtro/?genre=terror-2/'
        item.first = 0
        itemlist = list_all(item)
        if itemlist[-1].title == 'Siguiente >>':
            itemlist.pop()
    except Exception:
        import sys
        for line in sys.exc_info():
            logger.error("{0}".format(line))
        return []

    return itemlist
