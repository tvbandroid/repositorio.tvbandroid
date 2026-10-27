# -*- coding: utf-8 -*-
import sys, urllib.parse, urllib.request, json, os, time
import xbmc, xbmcgui, xbmcplugin, xbmcaddon
from resources.lib import tmdb, telegram, sources
from resources.lib.telegram_bridge import bridge
from resources.lib import telegram_service

ADDON=xbmcaddon.Addon()
HANDLE=int(sys.argv[1])
BASE="plugin://plugin.video.darkvio/"

try:
    import xbmcvfs
    ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
except Exception:
    ADDON_PATH = os.path.dirname(os.path.abspath(__file__))

def log(x): xbmc.log("[DARKVIO] "+str(x), xbmc.LOGINFO)

# Fanart global del addon. Se usa como fondo de respaldo cuando un elemento
# no tiene un fanart específico definido por TMDb.
GLOBAL_FANART = os.path.join(ADDON_PATH, "fanart.jpg")

def apply_global_fanart(li):
    try:
        li.setArt({"fanart": GLOBAL_FANART})
    except Exception:
        pass

def _setting_bool(name, default=True):
    """Lee un ajuste booleano de Kodi de forma compatible con Kodi 21."""
    try:
        v = ADDON.getSetting(name)
        if v == "":
            return default
        return str(v).lower() in ("true", "1", "yes", "on")
    except Exception:
        return default
def route_url(query): return BASE + "?" + query.lstrip("?")
def image(path): return (tmdb.IMAGE + path) if path else ""
def fanart_image(path): return (tmdb.IMAGE_FANART + path) if path else ""

# Estado persistente de búsqueda. Se guarda en el perfil del addon para que
# Kodi Windows y Kodi Android recuerden la última búsqueda de forma independiente.
def _state_file():
    try:
        import xbmcvfs
        profile=xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
        if not xbmcvfs.exists(profile): xbmcvfs.mkdirs(profile)
        target=os.path.join(profile, "search_state.json")
        if not os.path.exists(target):
            old_profile=os.path.join(os.path.dirname(profile), "plugin.video.arvio")
            old_state=os.path.join(old_profile, "search_state.json")
            if os.path.exists(old_state):
                try:
                    import shutil; shutil.copy2(old_state,target)
                    xbmc.log("[DARKVIO][MIGRATION] Última búsqueda ARVIO -> DARKVIO", xbmc.LOGINFO)
                except Exception: pass
        return target
    except Exception:
        return None

def _load_last_search():
    fn=_state_file()
    if not fn: return ""
    try:
        with open(fn, "r", encoding="utf-8") as f:
            return (json.load(f).get("last_query") or "").strip()
    except Exception:
        return ""

def _save_last_search(q):
    fn=_state_file()
    if not fn: return
    try:
        with open(fn, "w", encoding="utf-8") as f:
            json.dump({"last_query": q.strip()}, f, ensure_ascii=False)
    except Exception as e:
        xbmc.log("[DARKVIO][SEARCH] No se pudo guardar búsqueda: %s" % e, xbmc.LOGWARNING)

def _save_search_counts(q, movies_count, tv_count):
    fn=_state_file()
    if not fn: return
    try:
        with open(fn, "w", encoding="utf-8") as f:
            json.dump({"last_query": q.strip(), "movies_count": int(movies_count), "tv_count": int(tv_count)}, f, ensure_ascii=False)
    except Exception as e:
        xbmc.log("[DARKVIO][SEARCH] No se pudieron guardar los resultados: %s" % e, xbmc.LOGWARNING)

def _load_search_counts():
    fn=_state_file()
    if not fn: return "", 0, 0
    try:
        with open(fn, "r", encoding="utf-8") as f:
            d=json.load(f) or {}
        return (d.get("last_query") or "").strip(), int(d.get("movies_count") or 0), int(d.get("tv_count") or 0)
    except Exception:
        return "", 0, 0

def _show_search_folders(q):
    """Muestra las dos ramas de búsqueda sin volver a consultar TMDB."""
    _, movies_count, tv_count = _load_search_counts()
    log("[SEARCH] Mostrando carpetas: peliculas=%d series=%d" % (movies_count, tv_count))
    if movies_count:
        add("🎬 Películas (%d)" % movies_count, "?mode=search_category&kind=movie&q=%s&page=1" % urllib.parse.quote(q, safe=""), True)
    if tv_count:
        add("📺 Series (%d)" % tv_count, "?mode=search_category&kind=tv&q=%s&page=1" % urllib.parse.quote(q, safe=""), True)
    end()

def set_video_info(li, info, unique_ids=None):
    """Usa InfoTagVideo en Kodi 20/21 y evita el warning de setInfo()."""
    try:
        tag=li.getVideoInfoTag()
        if info.get("title") is not None: tag.setTitle(info.get("title") or "")
        if info.get("plot") is not None: tag.setPlot(info.get("plot") or "")
        if info.get("year"):
            try: tag.setYear(int(info.get("year")))
            except Exception: pass
        if info.get("genre"):
            try:
                genres=info.get("genre")
                if isinstance(genres,str): genres=[x.strip() for x in genres.split(",") if x.strip()]
                tag.setGenres(genres)
            except Exception: pass
        if info.get("mediatype"):
            try: tag.setMediaType(info.get("mediatype"))
            except Exception: pass
        if unique_ids:
            try: tag.setUniqueIDs(unique_ids)
            except Exception: pass
        return
    except Exception as e:
        xbmc.log("[DARKVIO][INFOTAG] %s" % e, xbmc.LOGDEBUG)
    # Fallback para versiones antiguas de Kodi.
    if info: li.setInfo("video",info)
    if unique_ids:
        try: li.setUniqueIDs(unique_ids)
        except Exception: pass
def add(label,url,folder=True,playable=False,thumb="",info=None):
    if url.startswith("?"): url=route_url(url)
    li=xbmcgui.ListItem(label=label)
    apply_global_fanart(li)
    if thumb:
        li.setArt({"thumb":thumb,"poster":thumb,"icon":thumb})
    if info: set_video_info(li, info)
    if playable: li.setProperty("IsPlayable","true")
    xbmcplugin.addDirectoryItem(HANDLE,url,li,folder)

def end(update=False):
    xbmcplugin.setContent(HANDLE,"videos")
    try:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=bool(update), cacheToDisc=False)
    except TypeError:
        xbmcplugin.endOfDirectory(HANDLE)

def params(): return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(sys.argv[2]).query))

def main():
    log("Abriendo menu principal")
    media_dir = os.path.join(ADDON_PATH, "resources", "media", "menu")
    add("Películas","?mode=movies",True,False,os.path.join(media_dir,"movies.png"))
    add("Series","?mode=series",True,False,os.path.join(media_dir,"series.png"))
    add("Tendencias","?mode=trending",True,False,os.path.join(media_dir,"trending.png"))
    add("Buscar Peli o Serie","?mode=search",False,False,os.path.join(media_dir,"search.png"))
    add("Televisión", "?mode=menu_television", True, False, os.path.join(media_dir, "tv.png"))
    end()

def catalog(mode,page=1):
    items=tmdb.category(mode,page)
    if not items:
        err=tmdb.last_error() or "Respuesta vacía de TMDB"
        xbmcgui.Dialog().notification("DARKvio - TMDB",err[:180],xbmcgui.NOTIFICATION_ERROR,4000)
    for r in items:
        title=r.get("title") or r.get("name") or "Sin título"
        year=(r.get("release_date") or r.get("first_air_date") or "")[:4]
        typ="tv" if r.get("media_type")=="tv" or r.get("name") else "movie"
        poster=image(r.get("poster_path"))
        fanart=fanart_image(r.get("backdrop_path"))
        info={"title":title,"year":int(year) if year.isdigit() else 0,
              "plot":r.get("overview") or "","mediatype":typ}
        url=("?mode=seasons&id=%s" % r.get("id")) if typ=="tv" else ("?mode=sources&media_type=movie&id=%s" % r.get("id"))
        li=xbmcgui.ListItem(label=((title+" ("+year+")") if year else title))
        apply_global_fanart(li)
        art={}
        if poster: art.update({"thumb":poster,"poster":poster})
        if fanart: art["fanart"]=fanart
        if art: li.setArt(art)
        set_video_info(li,info,{"tmdb":str(r.get("id"))} if r.get("id") else None)
        xbmcplugin.addDirectoryItem(HANDLE,route_url(url),li,True)
        # Añade el icono siguiente.png desde la carpeta de medios del addon
    next_icon = os.path.join(ADDON_PATH, "resources", "media", "siguiente.png")
    add("Página siguiente","?mode=%s&page=%d"%(mode,page+1), thumb=next_icon)

    end()

def search():
    """Solicita el texto y abre un contenedor NUEVO con las dos categorias."""
    last=_load_last_search()
    try:
        q=xbmcgui.Dialog().input("Buscar películas y series", defaultt=last, type=xbmcgui.INPUT_ALPHANUM)
    except TypeError:
        try: q=xbmcgui.Dialog().input("Buscar películas y series", last, xbmcgui.INPUT_ALPHANUM)
        except Exception as e: log("[SEARCH] Error dialogo: %s"%e); return
    except Exception as e:
        log("[SEARCH] Error dialogo: %s"%e); return
    q=(q or "").strip()
    if not q: return
    _save_last_search(q)
    log("[SEARCH] Buscando %r en peliculas y series..." % q)
    # Hacemos la consulta antes de cambiar de contenedor. Así sabemos que
    # realmente hay resultados y evitamos pintar sobre un handle ya cerrado.
    # No usamos DialogBusy: Kodi 21 puede rechazarlo desde un addon
    # ("addons must not activate DialogBusy"). Las consultas son directas.
    movies,_=tmdb.search_category(q,"movie",1)
    tv,_=tmdb.search_category(q,"tv",1)
    _save_search_counts(q, len(movies), len(tv))
    log("[SEARCH] Busqueda %r: peliculas=%d series=%d" % (q,len(movies),len(tv)))
    if not movies and not tv:
        err=tmdb.last_error() or "No se encontraron coincidencias"
        xbmcgui.Dialog().notification("DARKvio - Buscar",err[:180],xbmcgui.NOTIFICATION_INFO,3500)
        return
    # Activamos un contenedor nuevo. Container.Update sobre el handle de la
    # búsqueda era la causa de que TMDB devolviera datos pero Kodi no mostrase
    # las carpetas.
    target=route_url("?mode=search_results")
    try:
        xbmc.executebuiltin('ActivateWindow(videos,%s,return)' % target)
    except Exception as e:
        log("[SEARCH] ActivateWindow: %s" % e)
        # Fallback: ejecutar la ruta como plugin independiente.
        try: xbmc.executebuiltin("RunPlugin(%s)" % target)
        except Exception: pass

def search_results():
    q, movies_count, tv_count = _load_search_counts()
    if q and (movies_count or tv_count):
        _show_search_folders(q)
    elif q:
        xbmcgui.Dialog().notification("DARKvio - Buscar", "No se encontraron coincidencias", xbmcgui.NOTIFICATION_INFO, 3000)
        end()
    else:
        end()

def search_category():
    p=params(); q=(p.get("q") or _load_last_search()).strip(); typ=p.get("kind","movie")
    page=int(p.get("page",1) or 1)
    rows,total_pages=tmdb.search_category(q,typ,page)
    log("[SEARCH] Categoria=%s q=%r pagina=%d resultados=%d"%(typ,q,page,len(rows)))
    for r in rows:
        title=r.get("title") or r.get("name") or "Sin título"
        date=r.get("release_date") or r.get("first_air_date") or ""
        year=date[:4]
        poster=image(r.get("poster_path")); fanart=fanart_image(r.get("backdrop_path"))
        info={"title":title,"year":int(year) if year.isdigit() else 0,"plot":r.get("overview") or "","mediatype":typ}
        url=("?mode=seasons&id=%s"%r.get("id")) if typ=="tv" else ("?mode=sources&media_type=movie&id=%s"%r.get("id"))
        li=xbmcgui.ListItem(label=(title+" ("+year+")") if year else title)
        apply_global_fanart(li)
        art={}
        if poster: art.update({"thumb":poster,"poster":poster})
        if fanart: art["fanart"]=fanart
        if art: li.setArt(art)
        set_video_info(li,info,{"tmdb":str(r.get("id"))} if r.get("id") else None)
        xbmcplugin.addDirectoryItem(HANDLE,route_url(url),li,True)
    
    # Condición de paginación corregida y alineada perfectamente
    if page < total_pages:
        # Añade el icono siguiente.png desde la carpeta de medios del addon
        next_icon = os.path.join(ADDON_PATH, "resources", "media", "siguiente.png")
        add("Página siguiente", "?mode=search_category&kind=%s&q=%s&page=%d"%(typ,urllib.parse.quote(q,safe=""),page+1), True, thumb=next_icon)
    end()

def detail():
    p=params(); typ=p.get("media_type","movie"); mid=p.get("id"); info=tmdb.title(typ,mid)
    if not info:
        xbmcgui.Dialog().notification("DARKvio","No se pudo cargar la ficha",xbmcgui.NOTIFICATION_ERROR,3000); end(); return
    title=info.get("title") or info.get("name") or ""
    year=(info.get("release_date") or info.get("first_air_date") or "")[:4]
    plot=info.get("overview") or "Sin sinopsis disponible."
    li=xbmcgui.ListItem(label=title)
    poster=image(info.get("poster_path")); fanart=image(info.get("backdrop_path"))
    if poster: li.setArt({"poster":poster,"thumb":poster,"icon":poster})
    if fanart: li.setArt({"fanart":fanart})
    set_video_info(li,{"title":title,"year":int(year) if year.isdigit() else 0,"plot":plot,"genre":", ".join([g.get("name","") for g in info.get("genres",[])])},{"tmdb":str(mid)})
    xbmcplugin.addDirectoryItem(HANDLE,route_url("?mode=info&media_type=%s&id=%s"%(typ,mid)),li,True)
    if typ=="tv":
        add("📺 Temporadas","?mode=seasons&id=%s"%mid,thumb=poster)
    add("▶ Fuentes disponibles","?mode=sources&media_type=%s&id=%s"%(typ,mid),False)
    end()

def info_page():
    p=params(); info=tmdb.title(p.get("media_type","movie"),p.get("id"));
    if info:
        title=info.get("title") or info.get("name") or ""
        xbmcgui.Dialog().textviewer(title,info.get("overview") or "Sin sinopsis disponible.")
    main()

def _source_color_label(item, label):
    """Colorea las fuentes Stremio por proveedor sin cambiar Telegram."""
    if item.get("type") == "telegram":
        return "[B][COLOR cyan]%s[/COLOR][/B]" % label
    provider = str(item.get("provider") or "").strip().lower()
    if provider == "torrentio":
        return "[B][COLOR gold]%s[/COLOR][/B]" % label
    if provider == "peerflix":
        return "[B][COLOR lightgreen]%s[/COLOR][/B]" % label
    return label


def _source_item(label, url, info, media_type):
    """Crea cada enlace de reproduccion manteniendo ficha visual de la obra."""
    title = info.get("title") or info.get("name") or ""
    plot = info.get("overview") or "Sin sinopsis disponible."
    year_s = (info.get("release_date") or info.get("first_air_date") or "")[:4]
    poster = image(info.get("poster_path"))
    fanart = fanart_image(info.get("backdrop_path"))
    li = xbmcgui.ListItem(label=label)
    apply_global_fanart(li)
    art = {}
    if poster:
        art.update({"thumb": poster, "poster": poster, "icon": poster})
    if fanart:
        art["fanart"] = fanart
    if art:
        li.setArt(art)
    vinfo = {
        "title": title,
        "year": int(year_s) if year_s.isdigit() else 0,
        "plot": plot,
        "mediatype": "episode" if media_type == "episode" else media_type,
    }
    set_video_info(li, vinfo, {"tmdb": str(info.get("id"))} if info.get("id") else None)
    # Kodi skins that use ListItem properties can also take these directly.
    if fanart:
        li.setProperty("Fanart_Image", fanart)
    if poster:
        li.setProperty("poster", poster)
    xbmcplugin.addDirectoryItem(HANDLE, route_url(url), li, False)


def _tmdb_player_path():
    try:
        import xbmcvfs
        return xbmcvfs.translatePath("special://userdata/addon_data/plugin.video.themoviedb.helper/players")
    except Exception:
        return os.path.join(xbmc.translatePath("special://userdata"), "addon_data", "plugin.video.themoviedb.helper", "players")

def _tmdb_player_json():
    return '{\n  "name": "DARKVIO",\n  "plugin": "plugin.video.darkvio",\n  "priority": 100,\n  "is_resolvable": "false",\n  "assert": {\n    "play_movie": ["tmdb"],\n    "play_episode": ["tmdb", "showname", "season", "episode"]\n  },\n  "play_movie": "plugin://plugin.video.darkvio/?mode=tmdb_play_movie&tmdb_id={tmdb}&title={title_url}&year={year}",\n  "play_episode": "plugin://plugin.video.darkvio/?mode=tmdb_play_episode&tmdb_id={tmdb}&showname={showname_url}&season={season}&episode={episode}&title={title_url}"\n}'

def install_tmdb_helper():
    """Instala TMDb Helper desde el repositorio oficial de Jurialmunkey si no está instalado."""
    import xbmcvfs
    helper_id = "plugin.video.themoviedb.helper"
    repo_id = "repository.jurialmunkey"
    repo_zip_url = "https://michaz1988.github.io/repo/repository.jurialmunkey/repository.jurialmunkey-3.5.zip"
    try:
        try:
            xbmcaddon.Addon(helper_id)
            xbmcgui.Dialog().notification("DARKvio", "TMDb Helper ya está instalado", xbmcgui.NOTIFICATION_INFO, 3500)
            log("[TMDB HELPER] Ya instalado")
            return
        except Exception:
            pass

        # Primero instala el repositorio oficial de Jurialmunkey si aún no existe.
        try:
            xbmcaddon.Addon(repo_id)
            repo_installed = True
        except Exception:
            repo_installed = False

        if not repo_installed:
            profile = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
            if not xbmcvfs.exists(profile):
                xbmcvfs.mkdirs(profile)
            zip_path = os.path.join(profile, "repository.jurialmunkey-3.5.zip")
            log("[TMDB HELPER] Descargando repositorio oficial: %s" % repo_zip_url)
            req = urllib.request.Request(repo_zip_url, headers={"User-Agent": "Kodi/21 DARKvio"})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()
            with open(zip_path, "wb") as f:
                f.write(data)
            if not os.path.getsize(zip_path):
                raise IOError("ZIP del repositorio vacío")
            xbmc.executebuiltin("InstallAddon(%s)" % zip_path, True)

        # Una vez disponible el repositorio, Kodi resuelve TMDb Helper y sus dependencias.
        log("[TMDB HELPER] Solicitando instalación de %s" % helper_id)
        xbmc.executebuiltin("InstallAddon(%s)" % helper_id, True)

        # --- NUEVA INSTRUCCIÓN DE ELIMINACIÓN ---
        # Esperamos un segundo a que Kodi procese las tareas pendientes de los addons
        time.sleep(1)
        
        # Desinstalamos el repositorio del sistema
        log("[TMDB HELPER] Eliminando repositorio %s..." % repo_id)
        xbmc.executebuiltin("UninstallAddon(%s)" % repo_id, True)
        
        # Limpieza del archivo ZIP descargado en la carpeta de datos del addon (profile)
        if os.path.exists(zip_path):
            try:
                os.remove(zip_path)
                log("[TMDB HELPER] Archivo ZIP temporal eliminado con éxito")
            except Exception as e:
                log("[TMDB HELPER] No se pudo borrar el ZIP temporal: %s" % e)
        # ----------------------------------------

        xbmcgui.Dialog().notification("DARKvio", "Instalación de TMDb Helper", xbmcgui.NOTIFICATION_INFO, 4500)
    except Exception as e:
        log("[TMDB HELPER] Error: %s" % e)
        xbmcgui.Dialog().notification("DARKvio", "No se pudo instalar TMDb Helper", xbmcgui.NOTIFICATION_ERROR, 5000)

def install_tmdb_player():
    import xbmcvfs
    helper_id = "plugin.video.themoviedb.helper"

    # El reproductor solo puede instalarse si TMDb Helper ya existe en Kodi.
    # Si no está instalado, mostramos un cartel claro y no intentamos crear
    # la carpeta de players ni mostramos un mensaje de instalación correcta.
    try:
        xbmcaddon.Addon(helper_id)
    except Exception:
        xbmcgui.Dialog().ok("DARKvio", "TMDb Helper no está instalado")
        log("[TMDB PLAYER] TMDb Helper no está instalado; no se instala el reproductor")
        return

    folder=_tmdb_player_path()
    target=os.path.join(folder,"darkvio.select.json")
    try:
        if xbmcvfs.exists(target):
            xbmcgui.Dialog().notification("DARKvio","El reproductor DARKvio se instaló correctamente",xbmcgui.NOTIFICATION_INFO,3500)
            log("[TMDB PLAYER] Ya instalado: %s" % target)
            return
        if not xbmcvfs.exists(folder) and not xbmcvfs.mkdirs(folder):
            raise IOError("No se pudo crear la carpeta de players")
        f=xbmcvfs.File(target,"w"); f.write(_tmdb_player_json()); f.close()
        if not xbmcvfs.exists(target): raise IOError("No se pudo crear el reproductor")
        xbmcgui.Dialog().notification("DARKvio","Reproductor instalado en TMDb Helper",xbmcgui.NOTIFICATION_INFO,4000)
        log("[TMDB PLAYER] Instalado: %s" % target)
    except Exception as e:
        xbmcgui.Dialog().notification("DARKvio","No se pudo instalar el reproductor",xbmcgui.NOTIFICATION_ERROR,4500)
        log("[TMDB PLAYER] Error instalando: %s" % e)

def _play_selected_source(item,info,media_type="movie",season=None,episode=None):
    url=item.get("url","") or ""; source_type=item.get("type","") or ""; tmdb_id=str(info.get("id","") or "")
    try:
        if source_type=="telegram":
            file_id=url[len("telegram://"):] if url.startswith("telegram://") else ""
            if not file_id.isdigit(): return False
            name=item.get("file_name") or item.get("name") or "video"; size=int(item.get("size") or 0)
            http_url=telegram_service.start_stream(int(file_id),name,size,str(item.get("persistent_id") or ""),int(item.get("chat_id") or 0),int(item.get("message_id") or 0))
            xbmc.log("[DARKVIO][TELEGRAM] URL de reproducción entregada por servicio: %s" % http_url, xbmc.LOGINFO)
            # El servicio ya entrega una URL con stream_id único. No añadimos
            # otro parámetro aquí porque queremos que el mismo URL sea el que
            # recibe Stat/HEAD y GET. Creamos un ListItem limpio y sin resume.
            display_name = os.path.splitext(os.path.basename(name))[0] or name or "Telegram"
            play_item = xbmcgui.ListItem(label=display_name)
            apply_global_fanart(play_item)
            play_item.setPath(http_url)
            try:
                play_item.setContentLookup(False)
            except Exception:
                pass
            try:
                play_item.setProperty("IsPlayable", "true")
                play_item.setProperty("StartOffset", "0")
                play_item.setProperty("ResumeTime", "0")
                play_item.setProperty("resume", "0")
            except Exception:
                pass
            try:
                play_item.setInfo("video", {
                    "title": display_name,
                    "originaltitle": display_name,
                    "playcount": 0,
                    "resume": 0,
                })
            except Exception:
                pass
            xbmc.log("[DARKVIO][TELEGRAM] Player.play() nuevo stream desde 0", xbmc.LOGINFO)
            xbmc.Player().play(http_url, play_item)
            return True
        if source_type=="stremio" or url.startswith("magnet:"):
            if sources.play({"url":url,"type":"stremio"},media_type,tmdb_id): return True
            xbmcgui.Dialog().notification("DARKvio","Elementum no pudo iniciar la fuente",xbmcgui.NOTIFICATION_ERROR,4000); return False
        if url: xbmc.executebuiltin("PlayMedia(%s)" % url, True); return True
    except Exception as e:
        log("[TMDB PLAYER] Error reproduciendo fuente: %s" % e)
        xbmcgui.Dialog().notification("DARKvio","No se pudo iniciar la reproducción",xbmcgui.NOTIFICATION_ERROR,3500)
    return False

def _tmdb_helper_play(media_type,tmdb_id,season=None,episode=None):
    try:
        info=tmdb.title("tv" if media_type=="episode" else "movie",tmdb_id)
        if not info:
            xbmcgui.Dialog().notification("DARKvio","No se pudo obtener la información de TMDB",xbmcgui.NOTIFICATION_ERROR,4000); return
        found=sources.available(info,season,episode)
        if not found:
            xbmcgui.Dialog().notification("DARKvio","No hay fuentes disponibles",xbmcgui.NOTIFICATION_INFO,3500); return
        def key(x):
            if x.get("type")=="telegram": return (1,-int(x.get("tg_quality_rank") or 0),-int(x.get("size") or 0),x.get("label",""))
            return (0,-int(x.get("seeders") or 0),-int(x.get("size") or 0),x.get("label",""))
        ordered=sorted(found,key=key); labels=[]
        for item in ordered:
            if item.get("type")=="telegram":
                labels.append(_source_color_label(item, "▶ "+item.get("label","Telegram")))
            else:
                raw_label="▶ "+item.get("label","Fuente")+" · 🌱 %d semillas" % int(item.get("seeders") or 0)
                labels.append(_source_color_label(item, raw_label))
        idx=xbmcgui.Dialog().select("DARKVIO — Seleccionar fuente",labels,useDetails=True)
        if idx<0: return
        _play_selected_source(ordered[idx],info,media_type,season,episode)
    except Exception as e:
        log("[TMDB PLAYER] Error: %s" % e)
        xbmcgui.Dialog().notification("DARKvio","Error al buscar fuentes",xbmcgui.NOTIFICATION_ERROR,4000)

def route():
    q=params(); mode=q.get("mode",""); action=q.get("action","")

    # TvVoo genera sus propias URLs usando el parámetro "action".
    # Se mantiene separado de las rutas normales de DARKvio para no alterar
    # el funcionamiento existente del resto del addon.
    if not mode and action in ("home", "genres_menu", "catalog", "search", "search_country", "search_tvvoo", "play_tvvoo"):
        import tvvoo
        if action == "home":
            tvvoo.home()
        elif action == "genres_menu":
            tvvoo.genres_menu(q.get('catalog', ''))
        elif action == "catalog":
            tvvoo.show_catalog(q.get('catalog', ''), int(q.get('skip', '0') or 0), q.get('search', '') or None, q.get('genre', '') or None)
        elif action == "search":
            tvvoo.do_search(q.get('catalog', ''))
        elif action == "search_country":
            tvvoo.search_country()
        elif action == "search_tvvoo":
            tvvoo.do_search(q.get('catalog', ''))
        elif action == "play_tvvoo":
            tvvoo.play(q.get('id', ''), q.get('title', ''), q.get('thumb', ''))
        return

    if not mode: main(); return
    if mode=="search": search(); return
    if mode == 'menu_television':
        import tvvoo
        tvvoo.home()
        return
    elif mode == 'genres_menu':
        import tvvoo
        tvvoo.genres_menu(q.get('catalog', ''))
        return
    elif mode == 'catalog':
        import tvvoo
        tvvoo.show_catalog(q.get('catalog', ''), int(q.get('skip', '0') or 0), q.get('search', '') or None, q.get('genre', '') or None)
        return
    elif mode == 'search_country':
        import tvvoo
        tvvoo.search_country()
        return
    elif mode == 'search_tvvoo':
        import tvvoo
        tvvoo.do_search(q.get('catalog', ''))
        return
    elif mode == 'play_tvvoo':
        import tvvoo
        tvvoo.play(q.get('id', ''), q.get('title', ''), q.get('thumb', ''))
        return
    if mode=="search_results": search_results(); return
    if mode=="search_category": search_category(); return
    if mode in ("movies","series","trending"):
        catalog(mode,int(q.get("page",1))); return
    if mode=="detail": detail(); return
    if mode=="info": info_page(); return
    if mode in ("telegram_settings", "settings"):
        ADDON.openSettings(); return
    # Rutas internas usadas exclusivamente por los botones de Ajustes.
    # No aparecen en el menu principal.
    if mode == "telegram_login":
        ok = telegram.configure()
        if ok:
            xbmcgui.Dialog().notification("DARKvio", "Telegram conectado correctamente", xbmcgui.NOTIFICATION_INFO, 3500)
        return
    if mode == "telegram_logout":
        # Si el usuario pulsa NO, disconnect() devuelve False y no se modifica nada.
        telegram.disconnect()
        return
    if mode == "install_tmdb_helper":
        install_tmdb_helper()
        return
    if mode == "install_tmdb_player":
        install_tmdb_player()
        return
    if mode == "tmdb_play_movie":
        _tmdb_helper_play("movie", q.get("tmdb_id", ""))
        return
    if mode == "tmdb_play_episode":
        try:
            season=int(q.get("season", "0") or 0); episode=int(q.get("episode", "0") or 0)
        except Exception:
            season,episode=0,0
        _tmdb_helper_play("episode",q.get("tmdb_id", ""),season,episode)
        return
    if mode=="seasons":
        info=tmdb.title("tv",q.get("id")); poster=image(info.get("poster_path"))
        for s in info.get("seasons",[]):
            n=int(s.get("season_number",0) or 0)
            if n>0: add("Temporada %d"%n,"?mode=episodes&id=%s&season=%d"%(q.get("id"),n),thumb=image(s.get("poster_path")) or poster,info={"title":"Temporada %d"%n,"plot":s.get("overview") or ""})
        end(); return
    if mode=="episodes":
        eps=tmdb.episodes(q.get("id"),q.get("season"))
        for e in eps:
            n=int(e.get("episode_number",0) or 0); label="E%02d — %s"%(n,e.get("name") or "")
            add(label,"?mode=episode_sources&id=%s&season=%s&episode=%s"%(q.get("id"),q.get("season"),n),thumb=image(e.get("still_path")),info={"title":label,"plot":e.get("overview") or "","episode":n,"season":int(q.get("season",0) or 0)})
        end(); return
    if mode=="sources":
        info=tmdb.title(q.get("media_type","movie"),q.get("id"))
        found=sources.available(info)
        if not found:
            add("No hay fuentes disponibles todavía", "?mode=settings", False)
            end(); return
        def _source_sort_key(x):
            if x.get("type") == "telegram":
                return (1, -int(x.get("tg_quality_rank") or 0), -int(x.get("size") or 0), x.get("label", ""))
            return (0, -int(x.get("seeders") or 0), -int(x.get("size") or 0), x.get("label", ""))
        
        for item in sorted(found, key=_source_sort_key):
            # --- NUEVO FILTRO DE SEMILLAS ---
            seeds = int(item.get("seeders") or 0)
            if item.get("type") != "telegram" and seeds <= 0:
                continue # Se salta esta fuente si no es Telegram y tiene 0 semillas
            # ---------------------------------

            if item.get("type") == "telegram":
                label=item.get("label", "Telegram")
            else:
                suffix=" · 🌱 %d semillas" % seeds
                label=item.get("label","Fuente") + suffix
            u="?mode=play_source&type=%s&media_type=movie&id=%s&url=%s&name=%s&size=%s&pid=%s&chat_id=%s&message_id=%s" % (urllib.parse.quote(item.get("type", ""), safe=""), urllib.parse.quote(str(info.get("id","")), safe=""), urllib.parse.quote(item.get("url",""), safe=""), urllib.parse.quote(str(item.get("file_name") or item.get("name") or ""), safe=""), str(item.get("size") or 0), urllib.parse.quote(str(item.get("persistent_id") or ""), safe=""), urllib.parse.quote(str(item.get("chat_id") or ""), safe=""), urllib.parse.quote(str(item.get("message_id") or ""), safe=""))
            _source_item(_source_color_label(item, "▶ "+label), u, info, "movie")
        end(); return

    if mode=="episode_sources":
        info=tmdb.title("tv",q.get("id"))
        found=sources.available(info,int(q.get("season")),int(q.get("episode")))
        if not found:
            add("No hay fuentes disponibles todavía", "?mode=settings", False)
        else:
            def _source_sort_key(x):
                if x.get("type") == "telegram":
                    return (1, -int(x.get("tg_quality_rank") or 0), -int(x.get("size") or 0), x.get("label", ""))
                return (0, -int(x.get("seeders") or 0), -int(x.get("size") or 0), x.get("label", ""))
            
            for item in sorted(found, key=_source_sort_key):
                # --- NUEVO FILTRO DE SEMILLAS ---
                seeds = int(item.get("seeders") or 0)
                if item.get("type") != "telegram" and seeds <= 0:
                    continue # Se salta esta fuente si no es Telegram y tiene 0 semillas
                # ---------------------------------

                if item.get("type") == "telegram":
                    label=item.get("label", "Telegram")
                else:
                    suffix=" · 🌱 %d semillas" % seeds
                    label=item.get("label","Fuente")+suffix
                u="?mode=play_source&type=%s&media_type=episode&tmdb_id=%s&season=%s&episode=%s&url=%s&name=%s&size=%s&pid=%s&chat_id=%s&message_id=%s" % (urllib.parse.quote(item.get("type", ""), safe=""), urllib.parse.quote(str(info.get("id","")), safe=""), q.get("season",""), q.get("episode",""), urllib.parse.quote(item.get("url",""), safe=""), urllib.parse.quote(str(item.get("file_name") or item.get("name") or ""), safe=""), str(item.get("size") or 0), urllib.parse.quote(str(item.get("persistent_id") or ""), safe=""), urllib.parse.quote(str(item.get("chat_id") or ""), safe=""), urllib.parse.quote(str(item.get("message_id") or ""), safe=""))
                _source_item(_source_color_label(item, "▶ "+label), u, info, "episode")
        end(); return

    if mode=="play_source":
        url=q.get("url", "")
        source_type=q.get("type", "")
        media_type=q.get("media_type", "movie") or "movie"
        tmdb_id=q.get("tmdb_id", "") or q.get("id", "")
        try:
            url=urllib.parse.unquote(url)
            if source_type == "telegram":
                # La URL de la fuente es un identificador interno telegram://ID.
                # Solo aquí descargamos el archivo, después de que el usuario
                # haya elegido la fuente de Telegram.
                file_id=url[len("telegram://"):] if url.startswith("telegram://") else ""
                if not file_id.isdigit():
                    xbmcgui.Dialog().notification("DARKvio", "Fuente de Telegram no válida", xbmcgui.NOTIFICATION_ERROR, 3500)
                    return
                # Telegram se reproduce mediante HTTP local, no mediante Elementum.
                # La URL se crea al pulsar la fuente y Kodi recibe un stream HTTP
                # con soporte para Range/seek; TDLib descarga solo los rangos que
                # el reproductor va solicitando.
                name=q.get("name", "video") or "video"
                try:
                    size=int(q.get("size", "0") or 0)
                except Exception:
                    size=0
                try:
                    http_url=telegram_service.start_stream(int(file_id), name, size, urllib.parse.unquote(q.get("pid", "") or ""), int(q.get("chat_id", "0") or 0), int(q.get("message_id", "0") or 0))
                except Exception as e:
                    xbmcgui.Dialog().notification("DARKvio", "No se pudo iniciar el streaming de Telegram", xbmcgui.NOTIFICATION_ERROR, 4000)
                    xbmc.log("[DARKVIO][TELEGRAM] Error HTTP: %s" % e, xbmc.LOGERROR)
                    return
                xbmc.log("[DARKVIO][TELEGRAM] Streaming HTTP: %s" % http_url, xbmc.LOGINFO)
                # Telegram siempre usa un ListItem nuevo. El URL ya contiene
                # un identificador de stream único y el ListItem se fuerza a
                # comenzar en 0; de esta forma Kodi no reutiliza el bookmark de
                # otra película y tampoco bloqueamos el hilo GUI con PlayMedia.
                display_name = os.path.splitext(os.path.basename(name))[0] or name or "Telegram"
                play_item = xbmcgui.ListItem(label=display_name)
                apply_global_fanart(play_item)
                play_item.setPath(http_url)
                try:
                    play_item.setContentLookup(False)
                except Exception:
                    pass
                try:
                    play_item.setProperty("IsPlayable", "true")
                    play_item.setProperty("StartOffset", "0")
                except Exception:
                    pass
                try:
                    tag = play_item.getVideoInfoTag()
                    tag.setTitle(display_name)
                    tag.setOriginalTitle(display_name)
                    tag.setPlayCount(0)
                    tag.setResumePoint(0.0, 0.0)
                except Exception:
                    try:
                        play_item.setInfo("video", {
                            "title": display_name,
                            "originaltitle": display_name,
                            "playcount": 0,
                        })
                    except Exception:
                        pass
                xbmc.log("[DARKVIO][TELEGRAM] %s -> Player.play() nuevo stream desde 0" % ("Windows" if os.name == "nt" else "Android"), xbmc.LOGINFO)
                xbmc.Player().play(http_url, play_item)
                return
            if source_type == "stremio" or url.startswith("magnet:"):
                # Modelo Darktook: Elementum recibe magnet + tipo + TMDB.
                if sources.play({"url":url, "type":"stremio"}, media_type, tmdb_id):
                    return
                xbmcgui.Dialog().notification("DARKvio", "Elementum no pudo iniciar la fuente", xbmcgui.NOTIFICATION_ERROR, 4000)
                xbmc.log("[DARKVIO][PLAY] Elementum rechazó la fuente", xbmc.LOGERROR)
                return
            xbmc.executebuiltin("PlayMedia(%s)" % url, True)
        except Exception as e:
            xbmcgui.Dialog().notification("DARKvio", "No se pudo iniciar la reproducción", xbmcgui.NOTIFICATION_ERROR, 3000)
            xbmc.log("[DARKVIO][PLAY] %s" % e, xbmc.LOGERROR)
        return
    main()

route()
