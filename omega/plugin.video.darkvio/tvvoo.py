# -*- coding: utf-8 -*-
import sys
import json
import urllib.parse
import urllib.request
import os
import time
import xbmc
import xbmcvfs
import xbmcaddon
import xbmcgui
import xbmcplugin

HANDLE = int(sys.argv[1])
BASE = 'https://tvvoo.hayd.uk'
# TvVoo's bare manifest is intentionally configurable and can return no country catalogs.
# Request all supported country catalogs explicitly; the addon then filters them locally.
MANIFEST_COUNTRIES = 'it,uk,fr,de,pt,es,al,tr,nl,ar,bk,ru,ro,pl,bg'
MANIFEST_URL = BASE + '/manifest.json?include=' + MANIFEST_COUNTRIES
UA = 'Kodi/21 TvVoo/1.0'

# DARKvio global fanart: se conserva el fanart específico de TVVoO cuando existe.
try:
    GLOBAL_FANART = os.path.join(xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('path')), 'fanart.jpg')
except Exception:
    GLOBAL_FANART = ''

def apply_global_fanart(li):
    if GLOBAL_FANART:
        try:
            li.setArt({'fanart': GLOBAL_FANART})
        except Exception:
            pass


def log(msg):
    xbmc.log('[TVVOO] %s' % msg, xbmc.LOGINFO)


def get_json(url, cache_seconds=0, retries=2):
    cache_path = None
    if cache_seconds > 0:
        cache_dir = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
        try:
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
        except Exception:
            pass
        import hashlib
        cache_path = os.path.join(cache_dir, hashlib.md5(url.encode('utf-8')).hexdigest() + '.json')
        try:
            if os.path.exists(cache_path) and time.time() - os.path.getmtime(cache_path) < cache_seconds:
                log('CACHE %s' % url)
                with open(cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass

    last_error = None
    for attempt in range(retries + 1):
        try:
            log('GET %s' % url)
            req = urllib.request.Request(url, headers={
                'User-Agent': UA,
                'Accept': 'application/json,text/plain,*/*',
                'Referer': BASE + '/',
                'Connection': 'keep-alive'
            })
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode('utf-8-sig'))
            if cache_path:
                try:
                    with open(cache_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False)
                except Exception:
                    pass
            return data
        except Exception as e:
            last_error = e
            code = getattr(e, 'code', None)
            if code == 429 and attempt < retries:
                wait = 2 * (attempt + 1)
                log('HTTP 429; esperando %ss antes de reintentar' % wait)
                time.sleep(wait)
                continue
            break
    raise last_error

def notify(msg, heading='TvVoo'):
    xbmcgui.Dialog().notification(heading, msg, xbmcgui.NOTIFICATION_INFO, 4000)


def esc(s):
    return urllib.parse.quote(str(s), safe='')


def catalog_url(catalog_id, extra=None):
    # El protocolo Stremio coloca los parámetros extra en la ruta:
    # /catalog/tv/<catalog_id>/<extra>.json
    url = '%s/catalog/tv/%s' % (BASE, esc(catalog_id))
    if extra:
        parts = []
        for key, value in extra.items():
            if value is None or value == '':
                continue
            parts.append('%s=%s' % (esc(key), esc(value)))
        if parts:
            url += '/' + '&'.join(parts)
    return url + '.json'

def normalize_id(item_id):
    value = str(item_id or '')
    # Kodi puede entregar un parámetro que ya estaba percent-encoded.
    # Deshacemos codificaciones repetidas antes de volver a construir la URL Stremio.
    for _ in range(3):
        decoded = urllib.parse.unquote(value)
        if decoded == value:
            break
        value = decoded
    return value

def stream_url(item_id):
    value = normalize_id(item_id)
    return '%s/stream/tv/%s.json' % (BASE, urllib.parse.quote(value, safe=''))


def add_folder(label, action, params=None, icon='DefaultFolder.png', country_flag=False):
    params = params or {}
    params['action'] = action
    u = sys.argv[0] + '?' + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    li = xbmcgui.ListItem(label=label, path=u)
    apply_global_fanart(li)
    
    # --- NUEVA CORRECCIÓN VISUAL: Añadir metadatos para la barra lateral ---
    # Limpiamos las etiquetas de colores [COLOR] del nombre para que la descripción quede limpia
    texto_limpio = label.replace('[COLOR deepskyblue]', '').replace('[/COLOR]', '')
    
    # Enviamos el texto limpio tanto a la sinopsis (plot) como al título de información
    info_dict = {'title': texto_limpio, 'plot': ' '}
    li.setInfo('video', info_dict)
    # ----------------------------------------------------------------------
    
    if icon and icon != 'DefaultFolder.png':
        icon_path = icon
        li.setArt({
            'icon': icon_path,
            'thumb': icon_path,
            'poster': icon_path,
            'fanart': icon_path
        })
        li.setProperty('country_flag', 'true' if country_flag else 'false')
    else:
        li.setArt({'icon': icon, 'thumb': icon})
    xbmcplugin.addDirectoryItem(HANDLE, u, li, True)



def add_playable(label, action, params=None, thumb='', info=None):
    params = params or {}
    params['action'] = action
    u = sys.argv[0] + '?' + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    li = xbmcgui.ListItem(label=label)
    apply_global_fanart(li)
    li.setProperty('IsPlayable', 'true')
    if thumb:
        li.setArt({'thumb': thumb, 'icon': thumb, 'poster': thumb})
    if info:
        li.setInfo('video', info)
    xbmcplugin.addDirectoryItem(HANDLE, u, li, False)


def finish(content='TV'):
    xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.endOfDirectory(HANDLE)


def manifest():
    return {}


COUNTRIES = [
    ('country_spain','vavoo_tv_es','[COLOR deepskyblue]España[/COLOR]','spain.png'),
    ('country_portugal','vavoo_tv_pt','[COLOR deepskyblue]Portugal[/COLOR]','portugal.png'),
    ('country_france','vavoo_tv_fr','[COLOR deepskyblue]Francia[/COLOR]','france.png'),
    ('country_italy','vavoo_tv_it','[COLOR deepskyblue]Italia[/COLOR]','italy.png'),
    ('country_germany','vavoo_tv_de','[COLOR deepskyblue]Alemania[/COLOR]','germany.png'),
    ('country_uk','vavoo_tv_uk','[COLOR deepskyblue]Reino Unido[/COLOR]','uk.png'),
    ('country_netherlands','vavoo_tv_nl','[COLOR deepskyblue]Países Bajos[/COLOR]','netherlands.png'),
    ('country_turkey','vavoo_tv_tr','[COLOR deepskyblue]Turquía[/COLOR]','turkey.png'),
    ('country_romania','vavoo_tv_ro','[COLOR deepskyblue]Rumanía[/COLOR]','romania.png'),
    ('country_poland','vavoo_tv_pl','[COLOR deepskyblue]Polonia[/COLOR]','poland.png'),
    ('country_bulgaria','vavoo_tv_bg','[COLOR deepskyblue]Bulgaria[/COLOR]','bulgaria.png'),
    ('country_russia','vavoo_tv_ru','[COLOR deepskyblue]Rusia[/COLOR]','russia.png'),
    ('country_balkans','vavoo_tv_bk','[COLOR deepskyblue]Balcanes[/COLOR]','balkans.png'),
    ('country_arabia','vavoo_tv_ar','[COLOR deepskyblue]Arabia[/COLOR]','arabia.png'),
    ('country_albania','vavoo_tv_al','[COLOR deepskyblue]Albania[/COLOR]','albania.png'),
]

COUNTRY_SETTINGS = {
    'country_spain': ['españa', 'spain', 'espana', 'spagna'],
    'country_portugal': ['portugal'],
    'country_france': ['francia', 'france'],
    'country_italy': ['italia', 'italy', 'italie'],
    'country_germany': ['alemania', 'germany', 'deutschland'],
    'country_uk': ['reino unido', 'united kingdom', 'uk', 'great britain', 'inglaterra', 'england'],
    'country_netherlands': ['países bajos', 'paises bajos', 'netherlands', 'holland', 'nederland'],
    'country_turkey': ['turquía', 'turquia', 'turkey', 'türkiye'],
    'country_romania': ['rumanía', 'rumania', 'romania'],
    'country_poland': ['polonia', 'poland'],
    'country_bulgaria': ['bulgaria'],
    'country_russia': ['rusia', 'russia'],
    'country_balkans': ['balcanes', 'balkans', 'balkan'],
    'country_arabia': ['arabia', 'saudi', 'arab'],
    'country_albania': ['albania'],
}


COUNTRY_FLAGS = {
    'country_spain': 'spain.png',
    'country_portugal': 'portugal.png',
    'country_france': 'france.png',
    'country_italy': 'italy.png',
    'country_germany': 'germany.png',
    'country_uk': 'uk.png',
    'country_netherlands': 'netherlands.png',
    'country_turkey': 'turkey.png',
    'country_romania': 'romania.png',
    'country_poland': 'poland.png',
    'country_bulgaria': 'bulgaria.png',
    'country_russia': 'russia.png',
    'country_balkans': 'balkans.png',
    'country_arabia': 'arabia.png',
    'country_albania': 'albania.png',
}

def setting_enabled(setting_id):
    try:
        return xbmcaddon.Addon().getSettingBool(setting_id)
    except Exception:
        try:
            return xbmcaddon.Addon().getSetting(setting_id).lower() == 'true'
        except Exception:
            return True


def country_enabled(catalog):
    name = str(catalog.get('name', '')).lower()
    cid = str(catalog.get('id', '')).lower()
    haystack = name + ' ' + cid
    for setting_id, aliases in COUNTRY_SETTINGS.items():
        if any(alias in haystack for alias in aliases):
            return setting_enabled(setting_id)
    return True


def home():
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    added = 0
    for setting_id, catalog_id, name, flag in COUNTRIES:
        if not setting_enabled(setting_id):
            continue
        icon = os.path.join(addon_path, 'resources', 'media', 'flags', flag)
        add_folder(name, 'genres_menu', {'catalog': catalog_id}, icon, country_flag=True)
        added += 1
    if not added:
        notify('No hay países seleccionados en Ajustes')
    add_folder('Buscar canal', 'search_country', {}, 'special://home/addons/plugin.video.tvvoo/resources/media/search.png')
    finish()


def genres_menu(catalog):
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    
    # 1. Buscamos de forma automática qué bandera le corresponde a este país
    nombre_bandera = 'spain.png'  # Bandera por defecto si algo falla
    for setting_id, catalog_id, name, flag in COUNTRIES:
        if catalog_id == catalog:
            nombre_bandera = flag
            break
            
    # Construimos la ruta directa hacia la bandera de este país
    ruta_bandera_pais = os.path.join(addon_path, 'resources', 'media', 'flags', nombre_bandera)

    categorias = [
        ('Todos los canales', ''),
        ('Deportes', 'Sport'),
        ('Cine y Series', 'Movies'),
        ('General', 'General'),
        ('Documentales', 'Documentary'),
        ('Infantil', 'Kids'),
        ('Noticias', 'News'),
        ('Música', 'Music')
    ]
    for nombre, genero_id in categorias:
        add_folder(nombre, 'catalog', {'catalog': catalog, 'skip': 0, 'genre': genero_id}, ruta_bandera_pais)
    finish()


def search_country():
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    for setting_id, catalog_id, name, flag in COUNTRIES:
        if setting_enabled(setting_id):
            icon = os.path.join(addon_path, 'resources', 'media', 'flags', flag)
            add_folder(name, 'search', {'catalog': catalog_id}, icon, country_flag=True)
    finish()


def do_search(catalog):
    keyboard = xbmc.Keyboard('', 'Buscar canal')
    keyboard.doModal()
    if not keyboard.isConfirmed():
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    q = keyboard.getText().strip()
    if not q:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    show_catalog(catalog, 0, q)


def show_catalog(catalog, skip=0, search=None, genre=None):
    extra = {'skip': skip}
    if search:
        extra['search'] = search
    if genre and genre != 'Tutti':
        extra['genre'] = genre
    try:
        data = get_json(catalog_url(catalog, extra), cache_seconds=300)
    except Exception as e:
        log('Catalog error: %s' % e)
        notify('No se pudo cargar la lista de canales')
        return

    metas = data.get('metas') or data.get('items') or []
    for item in metas:
        iid = item.get('id')
        if not iid:
            continue
        title = item.get('name') or item.get('title') or iid
        thumb = item.get('poster') or item.get('logo') or item.get('background') or ''
        info = {'title': title}
        if item.get('description'):
            info['plot'] = item['description']
        if item.get('genre'):
            info['genre'] = ', '.join(item['genre']) if isinstance(item['genre'], list) else str(item['genre'])
        if item.get('releaseInfo'):
            info['year'] = str(item['releaseInfo'])[:4]
        add_playable(title, 'play_tvvoo', {'id': iid, 'title': title, 'thumb': thumb}, thumb or 'DefaultTVShows.png', info)

    if len(metas) >= 100:
        params = {'catalog': catalog, 'skip': skip + len(metas), 'search': search or '', 'genre': genre or ''}
        params['action'] = 'catalog'
        u = sys.argv[0] + '?' + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        li = xbmcgui.ListItem(label='Siguiente página')
        apply_global_fanart(li)
        
	# 1. Buscamos de forma automática qué bandera le toca al país actual
        addon_path = xbmcaddon.Addon().getAddonInfo('path')
        nombre_bandera = 'spain.png' # Por defecto si falla
        for setting_id, catalog_id, name, flag in COUNTRIES:
            if catalog_id == catalog:
                nombre_bandera = flag
                break
        ruta_bandera = os.path.join(addon_path, 'resources', 'media', 'flags', nombre_bandera)
	
        # 2. Le asignamos la bandera al botón Siguiente Página
        li.setArt({
            'icon': ruta_bandera,
            'thumb': ruta_bandera,
            'poster': ruta_bandera,
            'fanart': ruta_bandera
        })
        xbmcplugin.addDirectoryItem(HANDLE, u, li, True)
        
    xbmcplugin.setContent(HANDLE, 'tv')
    xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=True)


def play(item_id, title='', thumb=''):
    try:
        item_id = normalize_id(item_id)
        data = get_json(stream_url(item_id), cache_seconds=0, retries=1)
    except Exception as e:
        log('Stream error: %s' % e)
        notify('No se pudo resolver el canal')
        return
    streams = data.get('streams') or []
    log('Stream response: %d streams' % len(streams))
    if not streams:
        notify('TvVoo no devolvió ningún stream')
        return
    if len(streams) == 1:
        start_stream(streams[0], title, thumb)
        return
    preferred = None
    for stream in streams:
        name = str(stream.get('name') or stream.get('title') or '').lower()
        if 'nofreeze' in name or 'no freeze' in name:
            preferred = stream
            break
    if preferred is not None:
        log('Seleccionando automáticamente variante NoFreeze')
        start_stream(preferred, title, thumb)
        return
    start_stream(streams[0], title, thumb)


def start_stream(s, title, thumb):
    url = s.get('url') or s.get('externalUrl')
    if not url:
        notify('Stream sin URL reproducible')
        return

    name = str(s.get('name') or s.get('title') or '').lower()
    headers = {}
    for source in (
        s.get('headers'),
        s.get('behaviorHints', {}).get('proxyHeaders'),
        s.get('behaviorHints', {}).get('headers')
    ):
        if isinstance(source, dict):
            headers.update(source)

    if 'vavoo' in name or 'clean' in name:
        headers.setdefault('User-Agent', 'okhttp/4.11.0')
        headers.setdefault('Referer', 'https://vavoo.to/')
        headers.setdefault('Origin', 'https://vavoo.to')
    elif 'nofreeze' in name or 'freeze' in name:
        headers.setdefault('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/116.0.0.0 Safari/537.36')

    if headers:
        parts = []
        for k, v in headers.items():
            if v is not None:
                parts.append('%s=%s' % (k, urllib.parse.quote(str(v), safe='')))
        if parts:
            url += '|' + '&'.join(parts)

    li = xbmcgui.ListItem(path=url)
    apply_global_fanart(li)
    li.setProperty('IsPlayable', 'true')
    li.setArt({'thumb': thumb, 'icon': thumb})
    li.setInfo('video', {'title': title})
    li.setMimeType('application/vnd.apple.mpegurl')
    li.setContentLookup(False)
    try:
        li.setProperty('inputstream', 'inputstream.adaptive')
        li.setProperty('inputstream.adaptive.live_delay', '60')
        li.setProperty('inputstream.adaptive.stream_selection_type', 'adaptive')
        li.setProperty('inputstream.adaptive.chooser_bandwidth_max', '5000000')
        li.setProperty('inputstream.adaptive.manifest_type', 'hls')
        log('BUFFER ESTABLE: live_delay=60s chooser_bandwidth_max=5Mbps adaptive=true')
    except Exception as e:
        log('InputStream Adaptive properties: %s' % e)
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def main():
    qs = urllib.parse.parse_qs(sys.argv[2].lstrip('?')) if len(sys.argv) > 2 else {}
    action = qs.get('action', ['home'])[0]
    if action == 'home':
        home()
    elif action == 'genres_menu':
        genres_menu(qs.get('catalog', [''])[0])
    elif action == 'catalog':
        show_catalog(qs.get('catalog', [''])[0], int(qs.get('skip', ['0'])[0]), qs.get('search', [''])[0] or None, qs.get('genre', [''])[0] or None)
    elif action == 'search_country':
        search_country()
    elif action == 'search_tvvoo':
        do_search(qs.get('catalog', [''])[0])
    elif action == 'play_tvvoo':
        play(qs.get('id', [''])[0], qs.get('title', [''])[0], qs.get('thumb', [''])[0])
    else:
        home()


if __name__ == '__main__':
    main()
