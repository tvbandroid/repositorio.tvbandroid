# -*- coding: utf-8 -*-
import os
import time
from .telegram_bridge import bridge
from .telegram_matcher import score, series_queries, movie_queries, VIDEO_EXT, quality_label, format_size
from .telegram_process_lock import TDLibProcessLock

CACHE={}

def _quality_rank(name):
    raw=(name or "").lower()
    import re
    if re.search(r"(?:4320p|8k)", raw): return 100
    if re.search(r"(?:2160p|4k|uhd)", raw): return 90
    if re.search(r"1080p", raw): return 80
    if re.search(r"1440p", raw): return 85
    if re.search(r"900p", raw): return 75
    if re.search(r"720p", raw): return 70
    if re.search(r"576p", raw): return 60
    if re.search(r"540p", raw): return 55
    if re.search(r"480p", raw): return 50
    if re.search(r"360p", raw): return 40
    if re.search(r"(?:bluray|bdrip|brrip)", raw): return 65
    if re.search(r"(?:web[- .]?dl|web[- .]?rip)", raw): return 64
    if re.search(r"(?:hdtv|hdrip)", raw): return 62
    return 50

def _resolve_locked(info, season=None, episode=None):
    try:
        available=bool(bridge.available())
        state=bridge.auth_state() if available else "unavailable"
        import xbmc
        xbmc.log('[DARKVIO][TELEGRAM] resolver disponible=%s estado=%s temporada=%s episodio=%s' % (available,state,season,episode), xbmc.LOGINFO)
    except Exception as e:
        try:
            import xbmc
            xbmc.log('[DARKVIO][TELEGRAM] resolver error comprobando estado: %s' % e, xbmc.LOGWARNING)
        except Exception: pass
        return []
    if not available or state != "ready":
        try:
            import xbmc
            xbmc.log('[DARKVIO][TELEGRAM] No se busca porque TDLib no está Ready: %s' % state, xbmc.LOGWARNING)
        except Exception: pass
        return []
    typ=info.get("media_type") or ("movie" if "title" in info else "tv")
    title=info.get("title") or info.get("name") or ""
    original=info.get("original_title") or info.get("original_name") or ""
    year=(info.get("release_date") or info.get("first_air_date") or "")[:4]
    year=int(year) if year.isdigit() else None
    ext=info.get("external_ids") or {}
    key=(ext.get("imdb_id") or str(info.get("id")),season,episode)
    hit=CACHE.get(key)
    if hit and time.time()<hit[0]: return hit[1]
    titles=[t for t in [title, original] if t]
    # Primero buscamos por título puro. Telegram busca por palabras y esto
    # permite encontrar archivos cuyo nombre/caption lleve el año, idioma,
    # calidad o separadores distintos. Después añadimos las variantes
    # específicas de temporada/episodio o año.
    queries=[]
    for t in titles:
        queries.append(t)
    if season is not None and episode is not None:
        queries.extend(series_queries(titles,season,episode))
    else:
        queries.extend(movie_queries(titles,year))
    queries=list(dict.fromkeys(q for q in queries if q))
    messages=[]; seen=set()
    try:
        import xbmc
        xbmc.log('[DARKVIO][TELEGRAM] Título=%r original=%r año=%r consultas=%d' % (title,original,year,len(queries)), xbmc.LOGINFO)
    except Exception: pass
    for q in queries:
        try:
            hits=bridge.search(q,100)
            # Log mínimo para poder verificar en Kodi si Telegram está
            # devolviendo resultados de grupos/canales.
            import xbmc
            xbmc.log('[DARKVIO][TELEGRAM] consulta=%r resultados=%d' % (q, len(hits)), xbmc.LOGINFO)
        except Exception as e:
            hits=[]
            try:
                import xbmc
                xbmc.log('[DARKVIO][TELEGRAM] consulta=%r error=%s' % (q,e), xbmc.LOGWARNING)
            except Exception: pass
        for m in hits:
            k=(m.get("file_name",""),int(m.get("file_size",0) or 0))
            if k not in seen: seen.add(k); messages.append(m)
    out=[]
    for m in messages:
        fname=m.get("file_name") or m.get("filename") or ""
        caption=m.get("caption") or ""
        s=score(fname,caption,title,year,season,episode,localized=title,english=title,original=original)
        if s<55: continue
        # No descargamos el archivo mientras construimos la lista de fuentes.
        # Los archivos de Telegram pueden ser grandes y downloadFile síncrono
        # bloquearía la pantalla de fuentes. La descarga se realiza solamente
        # cuando el usuario selecciona esta fuente para reproducirla.
        file_id=m.get("file_id")
        if not file_id: continue
        name=fname or caption or "Vídeo"
        ext_ok=bool(VIDEO_EXT.search(name))
        mime=str(m.get("mime_type") or '').lower()
        if m.get('content_type') != 'messageVideo' and not ext_ok and not mime.startswith('video/'):
            continue
        size=m.get("file_size") or m.get("size",0)
        # Telegram muestra únicamente título + calidad + tamaño.
        # El canal/grupo nunca forma parte de la etiqueta de la fuente.
        label="Telegram · %s · %s · %s" % (title, quality_label(name), format_size(size))
        item={"label":label,"url":"telegram://%s" % file_id,"score":s,"size":size,"source":"Telegram","file_id":file_id,"persistent_id":m.get("persistent_id") or m.get("persistent_file_id") or "","chat_id":m.get("chat_id"),"message_id":m.get("message_id"),"file_name":fname,"name":name,"tg_quality_rank":_quality_rank(name)}
        out.append(item)
        try:
            import xbmc
            xbmc.log('[DARKVIO][TELEGRAM] FUENTE ACEPTADA: %s score=%s file_id=%s' % (item.get('label'),s,file_id), xbmc.LOGINFO)
        except Exception:
            pass
    out.sort(key=lambda x:(x.get("tg_quality_rank",0),x.get("size",0),x.get("score",0)),reverse=True)
    # No conservar durante horas un resultado vacío: si un mensaje aparece
    # en Telegram después de una búsqueda fallida, debe poder detectarse enseguida.
    if out:
        CACHE[key]=(time.time()+(7200 if typ=="tv" else 86400),out)
    else:
        CACHE.pop(key,None)
    return out


def resolve(info, season=None, episode=None):
    # Cada URL plugin:// puede ejecutarse en un proceso Python distinto.
    # TDLib no permite dos clientes usando simultáneamente el mismo td.binlog.
    # Serializamos las búsquedas y liberamos el bloqueo siempre.
    import xbmc
    # TDLibManager stores the real database under the addon profile. The lock
    # MUST live beside that database; using the addon installation directory
    # would not protect td.binlog across Kodi Python processes.
    session = bridge.m.session
    lock = TDLibProcessLock(os.path.join(session, 'tdlib.process.lock'), 15.0)
    if not lock.acquire():
        xbmc.log('[DARKVIO][TDLIB] No se pudo adquirir el bloqueo interproceso; se evita abrir otra instancia TDLib', xbmc.LOGWARNING)
        return []
    try:
        return _resolve_locked(info, season, episode)
    finally:
        try:
            bridge.close()
        except Exception:
            pass
        lock.close()
