# -*- coding: utf-8 -*-
import re
from platformcode import config, logger
from core import scrapertools, httptools
from core.item import Item
from core import servertools
from core import urlparse
from bs4 import BeautifulSoup
from core import jsontools


canonical = {
             'channel': 'xhamster', 
             'host': config.get_setting("current_host", 'xhamster', default=''), 
             'host_alt': ["https://xhamster.com/"], 
             'host_black_list': [], 
             'set_tls': True, 'set_tls_min': True, 'retries_cloudflare': 1, 'cf_assistant': False, 
             'CF': False, 'CF_test': False, 'alfa_s': True
            }
host = canonical['host'] or canonical['host_alt'][0]


def mainlist(item):
    logger.info()
    itemlist = []
    itemlist.append(Item(channel=item.channel, action="lista", title="Útimos videos", url=host + "newest"))
    itemlist.append(Item(channel=item.channel, action="votados", title="Lo mejor"))
    itemlist.append(Item(channel=item.channel, action="vistos", title="Los mas vistos"))
    itemlist.append(Item(channel=item.channel, action="lista", title="Recomendados", url=host + "videos/recommended"))
    itemlist.append(Item(channel=item.channel, title="PornStar" , action="catalogo", url=host + "pornstars"))
    itemlist.append(Item(channel=item.channel, title="Canal" , action="catalogo", url=host + "channels"))
    itemlist.append(Item(channel=item.channel, action="categorias", title="Categorías", url=host))
    itemlist.append(Item(channel=item.channel, action="search", title="Buscar"))
    return itemlist


def search(item, texto):
    logger.info()
    texto = texto.replace(" ", "+")
    item.url = "%ssearch/%s?sort=newest" % (host, texto)
    item.extra = "buscar"
    try:
        return lista(item)
    # Se captura la excepción, para no interrumpir al buscador global si un canal falla
    except Exception:
        import sys
        for line in sys.exc_info():
            logger.error("%s" % line)
        return []


def categorias(item):
    logger.info()
    itemlist = []
    soup = create_soup(item.url).find('div', class_='all-categories')
    matches = soup.find_all('li')
    for elem in matches:
        url = elem.a['href']
        title = elem.text.strip()
        url += "/newest"
        itemlist.append(Item(channel=item.channel, action="lista", title=title, url=url))
    return itemlist


def catalogo(item):
    logger.info()
    itemlist = []
    soup = create_soup(item.url)
    if "pornstars" in item.url:
        matches = soup.find_all('div', class_='root-4fca8')
    else:
        matches = soup.find_all('div', class_='root-02a1b')
    for elem in matches:
        url = elem.a['href']
        title = elem.img['alt']
        if elem.find('a', class_='site-02a1b'):   
            thumbnail = elem.find('a', class_='site-02a1b')['style']
            thumbnail = scrapertools.find_single_match(thumbnail, '(http.*?.jpg)')
            cantidad = elem.find('div', class_='count-02a1b').text.strip()
        else:
            thumbnail = elem.img['src']
            cantidad = elem.find('div', class_='videos-4fca8').text.strip()
        if cantidad:
            title = "%s (%s)" % (title,cantidad)
        url = urlparse.urljoin(item.url,url)
        url += "/newest"
        thumbnail = urlparse.urljoin(item.url,thumbnail)
        plot = ""
        itemlist.append(Item(channel=item.channel, action="lista", title=title, url=url,
                             fanart=thumbnail, thumbnail=thumbnail , plot=plot) )
    next_page = soup.find('a', class_='prev-next-list-link--next')
    if next_page:
        next_page = next_page['href']
        next_page = urlparse.urljoin(item.url,next_page)
        itemlist.append(Item(channel=item.channel, action="catalogo", title="[COLOR blue]Página Siguiente >>[/COLOR]", url=next_page) )
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
    data = httptools.downloadpage(item.url, canonical=canonical).data
    json = scrapertools.find_single_match(data, '(?:trendingVideoListProps|videoListProps|searchResult)":(.*?\}\]),"')+"}"
    json = jsontools.load(json)
    for elem in json['videoThumbProps']:
        title = elem['title']
        url = elem['pageURL']
        segundos = elem['duration']
        if not elem.get('thumbURL', ''): 
            continue
        else:
            thumbnail = elem['thumbURL']
        quality = ""
        if elem.get('isUHD', ''):
            quality = "4K"
        
        horas=int(segundos/3600)
        segundos-=horas*3600
        minutos=int(segundos/60)
        segundos-=minutos*60
        if segundos < 10:
            segundos = "0%s" %segundos
        if minutos < 10:
            minutos = "0%s" %minutos
        if horas == 00:
            time = "%s:%s" % (minutos,segundos)
        else:
            time = "%s:%s:%s" % (horas,minutos,segundos)

    # matches = soup.find_all('div', class_='thumb-list__item')
    # matches = soup.find_all('div', data-video-id=re.compile(r"^\d+"))
    # matches = soup.find(attrs={"data-video-id": re.compile(r"^\d+")})
    # for elem in matches:
        # if not elem.get('data-video-id',''):
            # continue
        # if "Not available in " in elem.text: #Geolocalizacion
            # continue
        # if "Solo para el dueño" in elem.a.text: #Solo para el dueño
            # continue
        # url = elem.a['href']
        # if elem.a.get("title", ""):
            # title =  elem.a['title']
        # else:
            # title = elem.img['alt']
        # title = elem.find('a', class_='video-thumb-info__name role-pop').text.strip() 
        # thumbnail = ""
        # if elem.img and elem.img.get("src", ""):
            # thumbnail = elem.img['src']
        # time = elem.find('div', class_='thumb-image-container__duration')
        # if not time: # purga moment
            # continue
        # time = time.text.strip()
        # quality = ""
        # if elem.find('i', class_='thumb-image-container__icon--hd'):
            # quality = "HD"
        # if elem.find('i', class_='thumb-image-container__icon--uhd'):
            # quality = "4K"
        if quality:
            title = "[COLOR yellow]%s[/COLOR] [COLOR red]%s[/COLOR] %s" % (time,quality,title)
        else:
            title = "[COLOR yellow]%s[/COLOR] %s" % (time,title)
        plot = ""
        action = "play"
        if logger.info() is False:
            action = "findvideos"
        itemlist.append(Item(channel=item.channel, action=action, title=title, contentTitle=title, url=url,
                             fanart=thumbnail, thumbnail=thumbnail , plot=plot) )
    if soup.find('a', attrs={'data-page':'next'}):
        next_page = soup.find('a', attrs={'data-page':'next'})
    else:
        next_page = soup.find('a', class_='prev-next-list-link--next')
    if next_page:
        next_page = next_page['href']
        next_page = urlparse.urljoin(item.url,next_page)
        itemlist.append(Item(channel=item.channel, action="lista", title="[COLOR blue]Página Siguiente >>[/COLOR]", url=next_page) )
    return itemlist


def votados(item):
    logger.info()
    itemlist = []

    itemlist.append(Item(channel=item.channel, action="lista", title="Día", url=urlparse.urljoin(host, "/best/daily"),
                         viewmode="movie"))
    itemlist.append(Item(channel=item.channel, action="lista", title="Semana", url=urlparse.urljoin(host, "/best/weekly"),
             viewmode="movie"))
    itemlist.append(Item(channel=item.channel, action="lista", title="Mes", url=urlparse.urljoin(host, "/best/monthly"),
             viewmode="movie"))
    itemlist.append(Item(channel=item.channel, action="lista", title="De siempre", url=urlparse.urljoin(host, "/best/"),
             viewmode="movie"))
    return itemlist


def vistos(item):
    logger.info()
    itemlist = []
    itemlist.append(Item(channel=item.channel, action="lista", title="Día", url=urlparse.urljoin(host, "/most-viewed/daily"),
             viewmode="movie"))
    itemlist.append(Item(channel=item.channel, action="lista", title="Semana", url=urlparse.urljoin(host, "/most-viewed/weekly"),
             viewmode="movie"))
    itemlist.append(Item(channel=item.channel, action="lista", title="Mes", url=urlparse.urljoin(host, "/most-viewed/monthly"),
             viewmode="movie"))
    itemlist.append(Item(channel=item.channel, action="lista", title="De siempre", url=urlparse.urljoin(host, "/most-viewed/"),
             viewmode="movie"))
    return itemlist


def findvideos(item):
    logger.info()
    itemlist = []
    data = httptools.downloadpage(item.url).data
    url = scrapertools.find_single_match(data, '"embedUrl":"([^"]+)"')
    url = url.replace("\\", "")
    itemlist.append(Item(channel=item.channel, action="play", title= "%s", contentTitle = item.title, url=url))
    itemlist = servertools.get_servers_itemlist(itemlist, lambda i: i.title % i.server.capitalize())
    return itemlist


def play(item):
    logger.info()
    itemlist = []
    data = httptools.downloadpage(item.url).data
    
    soup = BeautifulSoup(data, "html5lib", from_encoding="utf-8")
    pornstars = soup.find('nav', id='video-tags-list-container').find_all('a', href=re.compile("/pornstars/[A-z0-9-]+(?:/|)"))
    for x , value in enumerate(pornstars):
        pornstars[x] = value.text.strip()
    pornstar = ' & '.join(pornstars)
    pornstar = "[COLOR cyan]%s[/COLOR]" % pornstar
    lista = item.title.split()
    if "HD" in item.title or "4K" in item.title:
        lista.insert (4, pornstar)
    else:
        lista.insert (2, pornstar)
    item.contentTitle = ' '.join(lista)
    
    url = scrapertools.find_single_match(data, '"embedUrl":"([^"]+)"')
    url = url.replace("\\", "")
    itemlist.append(Item(channel=item.channel, action="play", title= "%s", contentTitle = item.contentTitle, url=url))
    itemlist = servertools.get_servers_itemlist(itemlist, lambda i: i.title % i.server.capitalize())
    return itemlist
