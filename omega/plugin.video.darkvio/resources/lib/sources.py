# -*- coding: utf-8 -*-
import xbmc, xbmcaddon, json, os, time, hashlib, threading, urllib.parse
from .telegram_resolver import resolve as telegram_resolve
from . import telegram_bridge
from .stremio_sources import query_sources

ADDON = xbmcaddon.Addon()
_CACHE = {}
_CACHE_TTL = 300
_CACHE_LOCK = threading.Lock()

def _cache_key(info, season, episode, peerflix, torrentio):
    ident = (info or {}).get("id") or (info or {}).get("external_ids", {}).get("imdb_id") or ""
    raw = "%s|%s|%s|%s|%s|%s" % (ident, season, episode, peerflix, torrentio, _setting_bool("telegram_enabled", True))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

def _setting_bool(name, default=True):
    v = ADDON.getSetting(name)
    if v == "": return default
    return v.lower() in ("true", "1", "yes")

def elementum_url(uri, media_type="movie", tmdb_id=""):
    if not uri: return ""
    if uri.startswith("plugin://plugin.video.elementum/"):
        return uri
    if not uri.startswith("magnet:"):
        return ""
    return "plugin://plugin.video.elementum/play?uri=%s&type=%s&tmdb=%s" % (
        urllib.parse.quote(uri, safe=""), media_type or "movie", urllib.parse.quote(str(tmdb_id or ""), safe="")
    )

def _elementum(uri, media_type="movie", tmdb_id=""):
    play = elementum_url(uri, media_type, tmdb_id)
    if not play: return False
    xbmc.log("[DARKVIO][ELEMENTUM] Darktook URI -> %s" % play, xbmc.LOGINFO)
    # Lanzamos directamente el plugin de Elementum. En algunas instalaciones
    # de Kodi 21 PlayMedia queda en espera hasta que llega otra acción de GUI;
    # Player.play() evita ese bloqueo y deja que Elementum tome el foco.
    launched = False
    try:
        xbmc.log("[DARKVIO][ELEMENTUM] Player.play()", xbmc.LOGINFO)
        xbmc.Player().play(play)
        launched = True
    except Exception as e:
        xbmc.log("[DARKVIO][ELEMENTUM] Player.play fallo: %s" % e, xbmc.LOGWARNING)
    if not launched:
        try:
            xbmc.log("[DARKVIO][ELEMENTUM] Fallback PlayMedia()", xbmc.LOGINFO)
            xbmc.executebuiltin("PlayMedia(%s)" % play, True)
        except TypeError:
            xbmc.executebuiltin("PlayMedia(%s)" % play)
        except Exception as e:
            xbmc.log("[DARKVIO][ELEMENTUM] PlayMedia fallo: %s" % e, xbmc.LOGERROR)
            return False
    return True

def play(result, media_type="movie", tmdb_id=""):
    uri = result.get("url", "")
    if result.get("type") == "stremio" and _setting_bool("use_elementum", True):
        return _elementum(uri, media_type, tmdb_id)
    return False

def _manifest_base(value):
    value = (value or "").strip()
    if not value: return ""
    low = value.lower()
    if low.endswith("/manifest.json"):
        return value[:-len("/manifest.json")]
    return value.rstrip("/")

def _json_source_config():
    path = (ADDON.getSetting("stremio_json_file") or "").strip()
    if not path:
        try:
            import xbmcvfs
            path = xbmcvfs.translatePath(os.path.join(ADDON.getAddonInfo("path"), "resources", "source_manifests.json"))
        except Exception:
            path = os.path.join(ADDON.getAddonInfo("path"), "resources", "source_manifests.json")
    try:
        try:
            import xbmcvfs
            path = xbmcvfs.translatePath(path)
        except Exception:
            pass
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        xbmc.log("[DARKVIO][STREMIO] JSON inválido: %s" % e, xbmc.LOGWARNING)
        return {}

def _configured_manifests():
    data = _json_source_config()
    t = data.get("torrentio") if isinstance(data.get("torrentio"), dict) else {}
    p = data.get("peerflix") if isinstance(data.get("peerflix"), dict) else {}
    torrentio = t.get("manifest") or ADDON.getSetting("torrentio_manifest")
    peerflix = p.get("manifest") or ADDON.getSetting("peerflix_manifest")
    # Nunca permitimos que una configuración antigua/incompleta deje fuera
    # uno de los dos proveedores principales.
    if not torrentio:
        torrentio = "https://torrentio.strem.fun/providers=mejortorrent,wolfmax4k|language=spanish/manifest.json"
    if not peerflix:
        peerflix = "https://addon.peerflix.mov/language=es|qualityfilter=threed,vhs,screener,unknown|sort=seed-desc/manifest.json"
    if t.get("enabled") is False: torrentio = ""
    if p.get("enabled") is False: peerflix = ""
    peerflix_base, torrentio_base = _manifest_base(peerflix), _manifest_base(torrentio)
    xbmc.log("[DARKVIO][STREMIO] Configurados: Peerflix=%s | Torrentio=%s" % (peerflix_base, torrentio_base), xbmc.LOGINFO)
    return peerflix_base, torrentio_base


def clear_cache():
    with _CACHE_LOCK:
        _CACHE.clear()
    try:
        from . import telegram_resolver
        telegram_resolver.CACHE.clear()
    except Exception:
        pass

def available(info, season=None, episode=None):
    peerflix, torrentio = _configured_manifests()
    key = _cache_key(info, season, episode, peerflix, torrentio)
    now = time.time()
    telegram_enabled = _setting_bool("telegram_enabled", True)
    telegram_ready = False
    try:
        telegram_ready = bool(telegram_enabled and telegram_bridge.auth_state() == "ready")
    except Exception:
        telegram_ready = False

    xbmc.log("[DARKVIO][SOURCES] Telegram habilitado=%s auth_ready=%s" %
              (telegram_enabled, telegram_ready), xbmc.LOGINFO)

    # El caché combinado no debe ocultar Telegram. Si hay una sesión activa,
    # Telegram se consulta siempre; el caché queda reservado para Stremio.
    cached_stremio = []
    if not telegram_ready:
        with _CACHE_LOCK:
            cached = _CACHE.get(key)
            if cached and now - cached[0] < _CACHE_TTL:
                xbmc.log("[DARKVIO][CACHE] Fuentes en caché: %d" % len(cached[1]), xbmc.LOGINFO)
                return list(cached[1])
    else:
        xbmc.log("[DARKVIO][CACHE] Sesión Telegram activa: se ignora el caché combinado", xbmc.LOGINFO)

    found = []
    if telegram_enabled:
        xbmc.log("[DARKVIO][SOURCES] Consultando Telegram...", xbmc.LOGINFO)
        try:
            tg=telegram_resolve(info, season, episode) or []
            for item in tg: item.setdefault("type","telegram")
            found.extend(tg)
            xbmc.log("[DARKVIO][SOURCES] Telegram fuentes=%d" % len(tg), xbmc.LOGINFO)
        except Exception as e:
            xbmc.log("[DARKVIO][SOURCES] Telegram error (se continúa con Stremio): %s" % e, xbmc.LOGWARNING)

    if _setting_bool("stremio_enabled", True) and (peerflix or torrentio):
        try:
            st, errors = query_sources(info, season, episode, peerflix, torrentio)
            found.extend(st)
            xbmc.log("[DARKVIO][SOURCES] Stremio fuentes=%d" % len(st), xbmc.LOGINFO)
            for err in errors:
                xbmc.log("[DARKVIO][STREMIO] %s" % err, xbmc.LOGWARNING)
        except Exception as e:
            # Un 429 u otro fallo de un manifiesto no debe impedir que
            # aparezcan las fuentes de Telegram.
            xbmc.log("[DARKVIO][STREMIO] Error no fatal: %s" % e, xbmc.LOGWARNING)

    out, seen = [], set()
    for x in found:
        u = x.get("url", "")
        k = (x.get("type", ""), u)
        if u and k not in seen:
            seen.add(k); out.append(x)
    
    with _CACHE_LOCK:
        _CACHE[key] = (time.time(), list(out))
    xbmc.log("[DARKVIO][SOURCES] Total fuentes=%d" % len(out), xbmc.LOGINFO)
    xbmc.log("[DARKVIO][CACHE] Fuentes guardadas en caché: %d" % len(out), xbmc.LOGINFO)
    return out
