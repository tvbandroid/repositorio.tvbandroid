# -*- coding: utf-8 -*-
import json
import urllib.parse
import urllib.request
import urllib.error
import xbmcaddon
import xbmc
import time, hashlib

API = "https://api.themoviedb.org/3"
API_TIMEOUT = 20
IMAGE = "https://image.tmdb.org/t/p/w500"
IMAGE_FANART = "https://image.tmdb.org/t/p/w1280"
DEFAULT_KEY = "b70756b7083d9ee60f849d82d94a0d80"
ADDON = xbmcaddon.Addon()

_last_error = ""
_SEARCH_CACHE={}

def _key():
    return (ADDON.getSetting("tmdb_api_key") or DEFAULT_KEY).strip()

def _token():
    return (ADDON.getSetting("tmdb_api_token") or "").strip()

def _clean_query(q):
    return " ".join((q or "").strip().split())

def _get(path, params=None):
    global _last_error
    p = dict(params or {})
    token = _token()
    if not token:
        p["api_key"] = _key()
    p["language"] = "es-ES"
    p["include_adult"] = "false"
    url = API + path + "?" + urllib.parse.urlencode(p)
    xbmc.log("[DARKVIO][TMDB] GET %s" % path, xbmc.LOGDEBUG)
    try:
        headers = {
            "User-Agent": "Kodi/21 DARKVIO/0.4.5",
            "Accept": "application/json",
        }
        token = _token()
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as r:
            raw = r.read().decode("utf-8", "replace")
            data = json.loads(raw)
            _last_error = ""
            return data
    except urllib.error.HTTPError as e:
        body = ""
        try: body = e.read().decode("utf-8", "replace")[:500]
        except Exception: pass
        if e.code == 401:
            _last_error = "Clave API de TMDB no válida o caducada (HTTP 401)"
        elif e.code == 404:
            _last_error = "TMDB no encontró el recurso (HTTP 404)"
        else:
            _last_error = "HTTP %s: %s" % (e.code, body)
        xbmc.log("[DARKVIO][TMDB] %s %s" % (path, _last_error), xbmc.LOGERROR)
        return {}
    except Exception as e:
        _last_error = "%s: %s" % (type(e).__name__, e)
        xbmc.log("[DARKVIO][TMDB] %s %s" % (path, _last_error), xbmc.LOGERROR)
        return {}

def last_error():
    return _last_error

def _norm_text(value):
    """Normaliza texto para coincidencias parciales tolerantes."""
    import unicodedata
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())

def search_category(q, typ, page=1):
    """Busca una categoria y agrupa hasta 5 paginas de TMDB (hasta 100 resultados).

    TMDB entrega 20 resultados por pagina. DARKVIO mantiene la paginacion de
    100 resultados por pagina de interfaz para que no haya que entrar en una
    pagina nueva cada 20 titulos.
    """
    global _last_error
    q = _clean_query(q)
    if not q:
        _last_error = "Escribe un titulo para buscar"
        return [], 0
    typ = "tv" if typ == "tv" else "movie"
    try: page=max(1,int(page))
    except Exception: page=1
    UI_PAGE_SIZE=100
    TMDB_PAGES_PER_UI_PAGE=5
    try:
        page=max(1,int(page))
    except Exception:
        page=1
    cache_key=("cat100",_norm_text(q),typ,page)
    cached=_SEARCH_CACHE.get(cache_key)
    if cached and time.time()-cached[0] < 300:
        return list(cached[1]), int(cached[2])
    path="/search/tv" if typ=="tv" else "/search/movie"
    first_tmdb_page=((page-1)*TMDB_PAGES_PER_UI_PAGE)+1
    nq=_norm_text(q); matched=[]; tmdb_total_pages=0
    for tmdb_page in range(first_tmdb_page, first_tmdb_page+TMDB_PAGES_PER_UI_PAGE):
        d=_get(path,{"query":q,"page":tmdb_page,"include_adult":"false"})
        rows=d.get("results",[]) or []
        tmdb_total_pages=max(tmdb_total_pages,int(d.get("total_pages",1) or 1))
        if not rows:
            break
        for x in rows:
            x["media_type"]=typ
            titles=[_norm_text(x.get("title")),_norm_text(x.get("name")),
                    _norm_text(x.get("original_title")),_norm_text(x.get("original_name"))]
            if any(nq in t for t in titles if t): matched.append(x)
    def _search_year(item):
        date = item.get("release_date") or item.get("first_air_date") or ""
        try:
            return int(str(date)[:4])
        except Exception:
            return 0
    # En las búsquedas de DARKVIO priorizamos siempre las obras más recientes.
    # Las que no tienen año quedan al final y, a igualdad de año, usamos
    # popularidad y título como desempate estable.
    matched.sort(key=lambda x:(-_search_year(x), -float(x.get("popularity") or 0),
                               (x.get("title") or x.get("name") or "").lower()))
    total_pages=max(1,(tmdb_total_pages + TMDB_PAGES_PER_UI_PAGE - 1)//TMDB_PAGES_PER_UI_PAGE)
    total_results=len(matched)
    _SEARCH_CACHE[cache_key]=(time.time(),list(matched),total_pages)
    _last_error=""
    xbmc.log("[DARKVIO][TMDB][SEARCH] %s %r pagina=%d -> %d coincidencias (TMDB total=%d)" % (typ,q,page,len(matched),total_results),xbmc.LOGINFO)
    return matched,total_pages

def search(q, page=1):
    """Compatibilidad: devuelve peliculas y series de la pagina solicitada."""
    movies,_=search_category(q,"movie",page)
    tv,_=search_category(q,"tv",page)
    return movies+tv

def title(typ, mid):
    path = "/movie/" if typ == "movie" else "/tv/"
    return _get(path + str(mid), {"append_to_response": "external_ids"})

def category(mode, page=1):
    if mode == "movies": d = _get("/movie/popular", {"page": page})
    elif mode == "series": d = _get("/tv/popular", {"page": page})
    else: d = _get("/trending/all/week", {"page": page})
    return d.get("results", [])

def seasons(mid):
    return title("tv", mid).get("seasons", [])

def episodes(mid, season):
    return _get("/tv/%s/season/%s" % (mid, season), {}).get("episodes", [])
