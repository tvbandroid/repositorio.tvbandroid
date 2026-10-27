# -*- coding: utf-8 -*-
"""Stremio source connector adapted to the Darktook source model."""
import json, re, urllib.parse, urllib.request, time, hashlib, threading
import xbmc

UA = "Kodi/21 DARKVIO/3.2.6"
_CACHE = {}
_LOCK = threading.Lock()
_TTL = 300
_TIMEOUT = 15

def _get(url, timeout=None):
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    now = time.time()
    with _LOCK:
        c = _CACHE.get(key)
        if c and now - c[0] < _TTL:
            xbmc.log("[DARKVIO][STREMIO][CACHE] %s" % url, xbmc.LOGDEBUG)
            return c[1]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=(timeout or _TIMEOUT)) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        with _LOCK:
            _CACHE[key] = (time.time(), data)
        return data
    except Exception as e:
        xbmc.log("[DARKVIO][STREMIO] %s -> %s" % (url, e), xbmc.LOGWARNING)
        return {}

def _base_url(value):
    return (value or "").strip().rstrip("/")

def _imdb(info):
    ext = (info or {}).get("external_ids") or {}
    return ext.get("imdb_id") or ""

def _streams(base, imdb_id, media_type, season=None, episode=None):
    if not base or not imdb_id:
        return []
    if media_type == "tv":
        if season is None or episode is None:
            return []
        path = "/stream/series/%s:%s:%s.json" % (imdb_id, season, episode)
    else:
        path = "/stream/movie/%s.json" % imdb_id
    data = _get(base + path)
    return data.get("streams", []) or []

def _parse_size(text):
    m = re.search(r"(?:💾|Size)\s*([0-9.]+)\s*(GB|MB)", text or "", re.I)
    if not m:
        return 0
    n = float(m.group(1))
    return int(n * (1024**3 if m.group(2).upper() == "GB" else 1024**2))

def _seeders(s):
    # Darktook prioritises the explicit `seed` field and falls back to the
    # standard description format used by Stremio addons.
    val = s.get("seed")
    if val is None:
        val = s.get("seeders")
    try:
        if val is not None:
            return int(val)
    except Exception:
        pass
    text = (s.get("description") or "") + "\n" + (s.get("title") or "")
    m = re.search(r"👤\s*(\d+)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(?:seeders?|seeds?)\s*[:=]?\s*(\d+)", text, re.I)
    return int(m.group(1)) if m else 0

def _parse(s, label):
    title = (s.get("title") or "Resultado").splitlines()[0]
    url = s.get("url") or ""
    ih = s.get("infoHash") or ""
    if not url and ih:
        url = "magnet:?xt=urn:btih:" + ih + "&dn=" + urllib.parse.quote(title[:120])
    seeders = _seeders(s)
    description = s.get("description") or ""
    return {
        "label": label + " — " + title,
        "url": url,
        "playable": bool(url),
        "type": "stremio",
        "infoHash": ih,
        "size": s.get("sizebytes") or _parse_size(description or title),
        "seeders": seeders,
        "provider": label,
    }

def query_one(label, base, info, season=None, episode=None):
    imdb = _imdb(info)
    if not imdb or not base:
        return [], label + ": falta IMDb o URL"
    typ = "tv" if info.get("name") is not None or info.get("first_air_date") else "movie"
    try:
        streams = _streams(_base_url(base), imdb, typ, season, episode)
        if streams:
            return [_parse(x, label) for x in streams], ""

        # Torrentio puede cambiar de configuración o responder con un
        # endpoint temporal. Si falla una configuración personalizada,
        # probamos el endpoint público estándar una sola vez.
        if label == "Torrentio":
            fallback = "https://torrentio.strem.fun/providers=mejortorrent,wolfmax4k|language=spanish"
            if _base_url(base) != fallback:
                xbmc.log("[DARKVIO][STREMIO] Torrentio sin resultados; probando configuración pública", xbmc.LOGINFO)
                streams = _streams(fallback, imdb, typ, season, episode)
                if streams:
                    return [_parse(x, "Torrentio") for x in streams], ""
        return [], ""
    except Exception as e:
        # No propagamos un fallo de un proveedor al otro. query_sources
        # recoge el error por separado y continúa con las demás fuentes.
        return [], label + ": " + str(e)

def query_sources(info, season=None, episode=None, peerflix_url="", torrentio_url=""):
    """Consulta únicamente Peerflix y Torrentio."""

    default_torrentio = "https://torrentio.strem.fun/providers=mejortorrent,wolfmax4k|language=spanish"
    default_peerflix = "https://addon.peerflix.mov/language=es|qualityfilter=threed,vhs,screener,unknown|sort=seed-desc"

    peerflix_url = _base_url(peerflix_url) or default_peerflix
    torrentio_url = _base_url(torrentio_url) or default_torrentio
    configs = [("Peerflix", peerflix_url), ("Torrentio", torrentio_url)]

    out, errors = [], []
    xbmc.log("[DARKVIO][STREMIO] Peerflix configurado=%s" % peerflix_url, xbmc.LOGINFO)
    xbmc.log("[DARKVIO][STREMIO] Torrentio configurado=%s" % torrentio_url, xbmc.LOGINFO)
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=len(configs) or 1) as ex:
            jobs = {ex.submit(query_one, label, base, info, season, episode): label for label, base in configs}
            for fut in as_completed(jobs):
                label = jobs[fut]
                try:
                    items, err = fut.result()
                    out.extend(items)
                    xbmc.log("[DARKVIO][STREMIO] %s fuentes=%d" % (label, len(items)), xbmc.LOGINFO)
                    if err:
                        errors.append(err)
                except Exception as e:
                    errors.append(label + ": " + str(e))
                    xbmc.log("[DARKVIO][STREMIO] %s error aislado: %s" % (label, e), xbmc.LOGWARNING)
    except Exception as e:
        errors.append(str(e))

    out.sort(key=lambda x: (int(x.get("seeders") or 0), int(x.get("size") or 0)), reverse=True)
    return out, errors
