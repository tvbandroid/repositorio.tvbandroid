# -*- coding: utf-8 -*-
# EKHorus - RubenSDFA1laberot
# Installation module for the EspaKodi ecosystem.
#
# Ported from the espakodi_installer.py in plugin.program.espakodi.installer, with the
# same three addon families (repo / official / embedded) and these differences:
#  - No requests and no six. EKHorus does not declare them in addon.xml, so the helpers
#    http_get_bytes/http_get_text from lib.utils are used, which already bring a time
#    limit, a User-Agent and a size cap
#  - The listitem urls are built with Item().tourl(), because EKHorus routes Items in
#    base64 and plain query strings only work for action=play
#  - The menu also includes the APK download, which belongs to EKHorus
#  - render_menu() does not close the directory: that is done by cerrar_directorio() in
#    default.py, which keeps count so as not to close it twice
#  - Out goes the green "new" dot (espakodi_addons_seen). In the addons it comes from
#    that setting is not even declared in settings.xml, so setSetting() does nothing
#    and the dot never goes away
#  - Elementum's repository does not travel in resources/repos. It is downloaded from GitHub
#    when installing (mode "proxy"), so every zip of EKHorus stops carrying 56 KB of someone
#    else's code that only this menu used

import json
import os
import re
import sys
import time
import zipfile

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from lib import list_screen, ui_common
from lib.utils import (Item, HEADING, apartar_musica, logger, http_get_bytes, http_get_text,
                       poner_info_video)

EK_REPO_POLL_TIMEOUT_S  = 20
EK_PROXY_POLL_TIMEOUT_S = 25  # repository.elementumorg raises its local proxy asynchronously
EK_POLL_INTERVAL_MS     = 500
EK_MAX_REPO_ZIP_BYTES   = 50 * 1024 * 1024
EK_MAX_ADDON_ZIP_BYTES  = 200 * 1024 * 1024
EK_HTTP_TIMEOUT_S       = 30

# How long the index of a repo is given to offer the addon. UpdateAddonRepos checks every
# enabled repo, the official one included, and on a slow device that takes a while
EK_INDICE_TIMEOUT_S     = 45
# For Kodi to register what has just been extracted into addons/
EK_ACTIVAR_TIMEOUT_S    = 10
# Kodi's question is given this long to appear; with both dialogs closed for EK_QUIETO_S the
# install is over. Measured on both benches: from the yes/no closing to the progress opening,
# a quarter of a second
EK_PREGUNTA_TIMEOUT_S   = 8
EK_QUIETO_S             = 2
# A look that takes this long means Kodi's interface thread is busy installing. A normal one
# is under 50 ms; on the phone the progress dialog was never caught open and a look of 1.5 s
# was the only sign
EK_MIRADA_LENTA_S       = 0.4
EK_INSTALACION_MAX_S    = 15 * 60

EK_ELEMENTUM_REPO = "repository.elementumorg"
EK_REPO_OFICIAL = "repository.xbmc.org"

# EKHorus does not appear in EK_ADDONS (installing itself makes no sense), so this never
# matches anything. It is kept for parity with the addons it comes from
EK_OWN_ADDON_ID = "script.module.horus"

# The version to fall back on: the one the EspaKodi app carries, still published as a release
# of its own on GitHub. It gets a row because a repository only ever serves its latest version,
# so Kodi offers no way back from one that misbehaves
EK_RESCATE_VERSION = "1.5.0"
EK_RESCATE_ZIP = ("https://github.com/espakodi/EKHorus/releases/download/"
                  "v{0}/{1}-{0}.zip".format(EK_RESCATE_VERSION, EK_OWN_ADDON_ID))

# How each addon is installed:
#   "repo":     the repo zip is fetched, registered and the addon installed (general case)
#   "official": it lives in the official Kodi repo, always there -> direct InstallAddon
#   "proxy":    the repo zip is fetched as in "repo", but the addons are published by a
#               service of the repo itself, which starts in its own time -> waited for
#
# (addon_id, repo_id, zip_url, source_url, name, plot, fallback_icon, mode, kind)
# kind = section of the repo where Kodi files it, only for the manual instructions
EK_ADDONS = [
    (
        "plugin.video.espatv",
        "repository.espatv",
        "https://raw.githubusercontent.com/espakodi/espatv/main/repository.espatv-1.0.0.zip",
        "https://espakodi.github.io/espatv/",
        "EspaTV",
        "TDT, RTVE a la carta, búsqueda en YouTube y Dailymotion, catálogo de vídeos, radio, podcasts, reproducción de enlaces, noticias, meteorología, agenda deportiva y mucho más.",
        "directo.png",
        "repo",
        "vídeo",
    ),
    (
        "plugin.video.espadaily",
        "repository.espadaily",
        "https://fullstackcurso.github.io/espadaily/repository.espadaily-1.0.2.zip",
        "https://fullstackcurso.github.io/espadaily/",
        "EspaDaily",
        "EspaDaily permite explorar catálogos de televisión española y buscar vídeos públicos en internet que coincidan.",
        "busqueda.png",
        "repo",
        "vídeo",
    ),
    (
        "plugin.video.atresdaily",
        "repository.atresdaily",
        "https://espatv.github.io/atresdaily/repository.atresdaily-1.0.1.zip",
        "https://espatv.github.io/atresdaily/",
        "AtresDaily",
        "Disfruta del contenido de A3Player con la potencia de AtresDaily. Búsquedas inteligentes y programación en directo.",
        "play_generic.png",
        "repo",
        "vídeo",
    ),
    (
        "plugin.program.loiolog",
        "repository.loiolog",
        "https://raw.githubusercontent.com/loioloio/loiolog/main/repository.loiolog-1.0.0.zip",
        "https://loioloio.github.io/loiolog/",
        "loiolog",
        "Visualiza y busca en el log de Kodi con un visor de colores por severidad. Filtra por addon, texto o expresiones regulares. Exporta a TXT o JSON, comparte el log subiéndolo a internet o ábrelo en el móvil desde tu red local. Consulta estadísticas del log, compara errores entre sesiones y gestiona los logs anteriores.",
        "adv_log.png",
        "repo",
        "programa",
    ),
    (
        "plugin.program.flowfavmanager",
        "repository.flowfavmanager",
        "https://loioloio.github.io/flowfav/repository.flowfavmanager-1.0.0.zip",
        "https://loioloio.github.io/flowfav/",
        "Flow FavManager",
        "Flow FavManager mejora la experiencia de gestión de favoritos en Kodi.\nPermite organizarlos, personalizar su apariencia y las acciones que realizan. Incluye herramientas de copia de seguridad, un editor intuitivo, perfiles y ordenación por secciones, entre otras funciones.",
        "favoritos.png",
        "repo",
        "programa",
    ),
    (
        "plugin.video.streamninja",
        "repository.streamninja",
        "https://raw.githubusercontent.com/fullstackcurso/estreamninja/main/repository.streamninja-1.0.0.zip",
        "https://fullstackcurso.github.io/estreamninja/",
        "StreamNinja",
        "StreamNinja permite enviar URLs a Kodi desde un móvil o PC mediante una web local efímera, o bien recibirlas directamente desde otros addons. Soporta Dailymotion, YouTube, AceStream, Torrents y casi cualquier enlace de vídeo.",
        "srch_externa.png",
        "repo",
        "vídeo",
    ),
    (
        "plugin.video.topzilla",
        "repository.topzilla",
        "https://raw.githubusercontent.com/espatv/topzilla/main/repository.topzilla-1.0.0.zip",
        "https://espatv.github.io/topzilla/",
        "TopZilla",
        "TopZilla muestra rankings, información y vídeos relacionados de películas y series. Además permite buscarlas, filtrarlas y guardarlas en tu biblioteca o consultar sus fichas con solo dos clics, estés donde estés en tu Kodi.",
        "busqueda.png",
        "repo",
        "vídeo",
    ),
    (
        "plugin.program.loiolink",
        "repository.loiolink",
        "https://loiolo.io/repository.loiolink-1.0.0.zip",
        "https://loiolo.io/",
        "loiolink",
        "• Mando a distancia: controla lo que estás viendo, navega por los menús o gestiona tus addons desde la web.\n• Toda tu colección: navega por tus películas, series y música desde el navegador y reprodúcelas en la TV.\n• Streaming al móvil: envía el vídeo desde el televisor a tu móvil, tablet o PC.\n• Favoritos: elimina, reordena o edita accesos directos desde el navegador.\n• Escribe sin el mando: escribe búsquedas o enlaces largos en el navegador y aparecerán al instante en Kodi.\n• Envío de vídeos, torrents, listas M3U o enlaces AceStream para reproducirlos al vuelo o grabarlos.\n• Escáner web y Telegram: rastrea páginas o canales para recopilar y reproducir torrents, vídeos y enlaces.\n• Instalación de addons y archivos: envía ZIPs de addons o APKs desde el navegador para instalarlos al instante.\n• Grabación HLS, explorador de archivos, apagado remoto y copia de seguridad.",
        "info.png",
        "repo",
        "programa",
    ),
    (
        "plugin.video.elementum",
        EK_ELEMENTUM_REPO,
        "https://github.com/ElementumOrg/repository.elementumorg/releases/download/v0.0.7/repository.elementumorg-0.0.7.zip",
        "https://github.com/elgatito/plugin.video.elementum",
        "Elementum",
        "Elementum es un motor de búsqueda y reproducción de torrents para Kodi. Reproduce películas y series por streaming desde la red BitTorrent mediante providers que se instalan aparte.\n\nEKHorus baja su repositorio de GitHub al instalarlo, así que no hace falta añadir ninguna fuente.",
        "srch_torrent.png",
        "proxy",
        "vídeo",
    ),
    (
        "script.module.youtube.dl",
        "repository.xbmc.org",
        "",
        "https://github.com/xbmc/repo-scripts",
        "youtube-dl",
        "Módulo youtube-dl/yt-dlp para Kodi: resuelve la URL reproducible de cientos de webs de vídeo. Lo usan otros addons como motor de extracción, no tiene interfaz propia.\n\nSe instala desde el repositorio oficial de Kodi.",
        "adv_ytdlp.png",
        "official",
        "programa",
    ),
    (
        "plugin.program.ekgames",
        "repository.ekgames",
        "https://espatv.github.io/ekgames/repository.ekgames-1.0.0.zip",
        "https://espatv.github.io/ekgames/",
        "EKGames",
        "Catorce minijuegos clásicos para echar una partida sin salir de Kodi: Snake, 2048, Tetris, Buscaminas, Memoria, Solitario, Flappy, Pong, Invaders, Burbujas, Frogger, Galaga, Asteroids y Pac-Man.\nSe juegan con el mando a distancia, con un mando de juego, con el teclado o con los dedos, guardan su récord y tienen cuatro niveles de dificultad.\nIncluye además Gamesek entero, sin instalar nada más: emuladores por sistema, tus carpetas de juegos, juegos libres que se descargan solos y el Modo Juego a pantalla completa.",
        "juegos.png",
        "repo",
        "programa",
    ),
    (
        "plugin.program.gamesek",
        "repository.gamesek",
        "https://espakodi.github.io/gamesek/repository.gamesek-1.0.0.zip",
        "https://espakodi.github.io/gamesek/",
        "Gamesek",
        "Juegos y emuladores para Kodi, en español. Trae catorce clásicos que se abren al momento, sin descargar nada y sin emulador, y otros tantos que se descargan e instalan solos.\nTambién puedes importar tus juegos, enviarlos desde el móvil por la red de casa o pedirle que los busque por tus discos. El Modo Juego lo enseña todo a pantalla completa.",
        "juegos.png",
        "repo",
        "programa",
    ),
    (
        "inputstream.adaptive",
        "repository.xbmc.org",
        "",
        "https://github.com/xbmc/inputstream.adaptive",
        "InputStream Adaptive",
        "Motor de reproducción para streaming adaptativo (DASH, HLS, Smooth Streaming). Lo usan muchos addons de vídeo (TV a la carta, directos) para reproducir. Normalmente se instala solo al instalar un addon que lo necesite; esta opción lo trae del repositorio oficial de Kodi sin esperar a que otro addon lo pida.",
        "directo.png",
        "official",
        "InputStream",
    ),
    (
        "script.module.resolveurl",
        "repository.resolveurl",
        "",
        "https://github.com/Gujal00/ResolveURL",
        "ResolveURL",
        "Módulo que resuelve el enlace reproducible de cientos de servidores de vídeo. Lo usan muchos addons para reproducir enlaces de hosters. Normalmente se instala solo al instalar un addon que lo declare; esta opción lo trae de su repositorio (incluido en EspaKodi) sin esperar a que otro addon lo pida.",
        "play_generic.png",
        "official",
        "programa",
    ),
]

_EK_BY_ID = {row[0]: row for row in EK_ADDONS}

# The screen order lives apart from the catalogue so things can be moved around without
# touching the tuples. Espanime, in an "Otros addons" block in the installer, is not here.
EK_BLOQUE_ECOSISTEMA = "Addons de EspaKodi"

EK_BLOQUES = [
    (EK_BLOQUE_ECOSISTEMA, [
        "plugin.video.espatv",
        "plugin.video.espadaily",
        "plugin.video.atresdaily",
        "plugin.program.loiolink",
        "plugin.program.flowfavmanager",
        "plugin.video.streamninja",
        "plugin.video.topzilla",
        "plugin.program.loiolog",
        "plugin.program.ekgames",
        "plugin.program.gamesek",
    ]),
    ("Dependencias y motores", [
        "script.module.youtube.dl",
        "plugin.video.elementum",
        "inputstream.adaptive",
        "script.module.resolveurl",
    ]),
]


def _ek_bloques():
    """(title, entries) of each block. Whatever is in the catalogue and in no block falls
    into a final one, so adding an addon and forgetting the list does not hide it."""
    colocados = set()
    bloques = list()

    for titulo, ids in EK_BLOQUES:
        entradas = [_EK_BY_ID[i] for i in ids if i in _EK_BY_ID]
        colocados.update(row[0] for row in entradas)
        if entradas:
            bloques.append((titulo, entradas))

    sueltos = [row for row in EK_ADDONS if row[0] not in colocados]
    if sueltos:
        bloques.append(("Otros", sueltos))

    return bloques


def _ek_download_bytes(url, max_bytes, timeout=EK_HTTP_TIMEOUT_S):
    # http_get_bytes already sets a User-Agent, a time limit and a size cap (and blows up
    # if it is exceeded). All that is left here is checking that what arrived is a real ZIP
    content = http_get_bytes(url, timeout=timeout, max_bytes=max_bytes)

    if len(content) < 4 or content[:2] != b"PK":
        raise Exception("El archivo descargado no es un ZIP valido")

    return content


def _ek_download_text(url, timeout=20):
    return http_get_text(url, timeout=timeout)


def _ek_extract_zip(zip_path, addons_dir):
    # A zip with paths like ../../ would step outside addons/ and write wherever it wanted.
    # The prefix is compared with the trailing separator (addons_dir + os.sep): without it,
    # a sibling path like ../addons_evil/x would pass the filter by starting like addons
    addons_dir_real = os.path.realpath(addons_dir)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for entry in zf.namelist():
            resolved = os.path.realpath(os.path.join(addons_dir, entry))
            if resolved != addons_dir_real and not resolved.startswith(addons_dir_real + os.sep):
                raise Exception("ZIP contiene ruta sospechosa: {0}".format(entry))
        zf.extractall(addons_dir)


class _Cancelado(Exception):
    """Cancel from a dialog, or Kodi closing: there is nothing to say about either."""


def _ek_mirar(condicion):
    # (what Kodi answers, how long the look took). While Kodi installs, its interface thread is
    # busy and the look waits: that wait is a sign of the install in itself
    antes = time.monotonic()
    valor = bool(xbmc.getCondVisibility(condicion))
    return valor, time.monotonic() - antes


def _ek_addon_is_installed(addon_id):
    # Installed AND enabled. System.HasAddon answers only the first half (IsAddonInstalled,
    # OnlyEnabled::NO), and a disabled addon opens nothing and plays nothing. It is used
    # instead of xbmcaddon.Addon() because that one logs an "EXCEPTION: Unknown addon id" in
    # kodi.log for every addon that is not installed, and is slower
    return xbmc.getCondVisibility("System.AddonIsEnabled({0})".format(addon_id))


def _ek_addon_registrado(addon_id):
    # There, switched on or not: what Kodi registers as installed
    return xbmc.getCondVisibility("System.HasAddon({0})".format(addon_id))


def _ek_addon_dir_present(addon_id):
    addon_dir = xbmcvfs.translatePath("special://home/addons/{0}/".format(addon_id))
    return os.path.isdir(addon_dir) and os.path.isfile(os.path.join(addon_dir, "addon.xml"))


def _ek_jsonrpc(method, params=None):
    req = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        req["params"] = params
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(req)))
    except Exception:
        return {}


def _ek_enabled_ids():
    # Set of installed and enabled addonids, in a single call. It paints the whole menu
    # without asking addon by addon
    resp = _ek_jsonrpc("Addons.GetAddons", {"enabled": True})
    addons = resp.get("result", {}).get("addons", []) if "result" in resp else []
    return {a.get("addonid") for a in addons}


def _ek_addon_available_in_repos(addon_id):
    # Addons that the repositories offer and are not installed yet. It tells whether the
    # repo index is ready already: in elementum, showing up here means that its local
    # proxy is answering
    resp = _ek_jsonrpc("Addons.GetAddons", {"installed": False, "properties": ["name"]})
    addons = resp.get("result", {}).get("addons", []) if "result" in resp else []
    return any(a.get("addonid") == addon_id for a in addons)


def _ek_enable_addon_jsonrpc(addon_id):
    resp = _ek_jsonrpc("Addons.SetAddonEnabled", {"addonid": addon_id, "enabled": True})
    return resp.get("result") == "OK"


def _ek_esperar(condicion, plazo, monitor, dp=None, paso=0.5):
    """True once condicion() holds, False if plazo runs out, _Cancelado if the user cancels dp
    or Kodi closes.

    waitForAbort() and not xbmc.sleep(): it lets go of Kodi's GIL and it comes back at once
    when Kodi is closing, so no wait of this file holds the closing back."""
    limite = time.monotonic() + plazo
    while True:
        # Before the condition: a Cancel given while the last step ran counts, even if there is
        # nothing left to wait for
        if dp is not None and dp.iscanceled():
            raise _Cancelado()
        if monitor.abortRequested():
            raise _Cancelado()
        if condicion():
            return True
        if time.monotonic() >= limite:
            return False
        if monitor.waitForAbort(paso):
            raise _Cancelado()


def _ek_activar(addon_id, monitor, plazo=EK_ACTIVAR_TIMEOUT_S, dp=None):
    """Switches the addon on without asking anything. True only if it ends up on.

    Whatever lands in addons/ is registered switched off (CAddonDatabase::SyncInstalled), and
    the EnableAddon builtin asks a yes/no every time, even for one already on. SetAddonEnabled
    answers OK whenever the addon is installed, enabled or not (CAddonMgr::EnableAddon), so it
    is called once, and what counts is what Kodi says afterwards; repeating it on an addon Kodi
    refuses would only pile up its error notices."""
    if not _ek_esperar(lambda: _ek_addon_registrado(addon_id), plazo, monitor, dp):
        return False
    if _ek_addon_is_installed(addon_id):
        return True

    _ek_enable_addon_jsonrpc(addon_id)
    return _ek_esperar(lambda: _ek_addon_is_installed(addon_id), 3, monitor, dp)


def _ek_try_recover_addon(addon_id, monitor):
    """Switches on an addon that is already there. Nothing to download, so it is the first
    thing to try."""
    if _ek_addon_registrado(addon_id):
        return _ek_activar(addon_id, monitor)

    if not _ek_addon_dir_present(addon_id):
        return False

    xbmc.executebuiltin("UpdateLocalAddons()")
    return _ek_activar(addon_id, monitor)


def _ek_instalar_con_kodi(addon_id, monitor):
    """Hands the install to Kodi and watches how it goes: 'instalado', 'no' (the user told Kodi
    no) or 'fallo'. The addon's own DialogProgress has to be closed first, because Kodi installs
    with that same window.

    Never executebuiltin(..., True): the builtin with wait holds Kodi's GIL and every Python of
    Kodi stops until the install is over. Measured on both benches: the rest of the Python froze
    for as long as the question was on screen (4.5 s), and a repository that serves its own zips
    from Python, like Elementum's, could not have served them."""
    xbmc.executebuiltin("InstallAddon({0})".format(addon_id))
    pregunta = instalando = abierta_antes = False
    quietas_desde = None
    limite = time.monotonic() + EK_INSTALACION_MAX_S

    while time.monotonic() < limite:
        if monitor.waitForAbort(0.25):
            raise _Cancelado()

        activo, t_activo = _ek_mirar("System.AddonIsEnabled({0})".format(addon_id))
        abierta, t_pregunta = _ek_mirar("Window.IsActive(yesnodialog)")
        abierto, t_progreso = _ek_mirar("Window.IsActive(progressdialog)")

        if activo:
            # Kodi switches it on before closing its progress, and whoever comes next may want
            # that same window.
            _ek_esperar(lambda: not _ek_mirar("Window.IsActive(progressdialog)")[0], 5, monitor)
            return "instalado"

        # A slow look tells of an install only while Kodi is not holding its question: nothing is
        # installed yet with the Yes/No on screen, and the look that straddles its closing waits
        # for that alone. On a slow device, counting those would turn a no into a 'fallo' and the
        # fallback would install it behind the answer
        lenta = max(t_activo, t_pregunta, t_progreso) >= EK_MIRADA_LENTA_S
        pregunta = pregunta or abierta
        instalando = instalando or abierto or (lenta and not abierta and not abierta_antes)
        abierta_antes = abierta

        if abierta or abierto:
            quietas_desde = None
            continue
        if quietas_desde is None:
            quietas_desde = time.monotonic()
            continue
        if time.monotonic() - quietas_desde >= (EK_QUIETO_S if pregunta else EK_PREGUNTA_TIMEOUT_S):
            break

    return "no" if pregunta and not instalando else "fallo"


def _ek_addon_icon(addon_id, fallback=None, installed=None):
    # Addon() is only instantiated if it is installed, to keep the rest out of the log
    if installed is None:
        installed = _ek_addon_is_installed(addon_id)
    if installed:
        try:
            path = xbmcaddon.Addon(addon_id).getAddonInfo("path")
            for name in ("icon.png", "icon.jpg"):
                p = os.path.join(path, name)
                if os.path.exists(p):
                    return p
        except Exception:
            pass
    return fallback or os.path.join(_media_dir(), "play_generic.png")


def _media_dir():
    return os.path.join(xbmcaddon.Addon().getAddonInfo("path"), "resources", "media")


def _addon_fanart():
    return xbmcaddon.Addon().getAddonInfo("fanart")


def _ek_get_repo_datadir(repo_id):
    repo_xml = xbmcvfs.translatePath("special://home/addons/{0}/addon.xml".format(repo_id))
    if not os.path.isfile(repo_xml):
        return None
    try:
        with open(repo_xml, "r", encoding="utf-8") as f:
            content = f.read()
        m = re.search(r"<datadir[^>]*>\s*([^<\s]+)\s*</datadir>", content)
        if m:
            url = m.group(1).strip()
            if not url.endswith("/"):
                url += "/"
            return url
    except Exception as e:
        logger("No se pudo leer datadir del repo {0}: {1}".format(repo_id, e))
    return None


def _ek_find_addon_version_in_index(addons_xml_text, addon_id):
    for pattern in (
        r'<addon[^>]*\bid="' + re.escape(addon_id) + r'"[^>]*\bversion="([^"]+)"',
        r'<addon[^>]*\bversion="([^"]+)"[^>]*\bid="' + re.escape(addon_id) + r'"',
    ):
        m = re.search(pattern, addons_xml_text)
        if m:
            return m.group(1)
    return None


def _ek_dependencias_listas(addons_xml, addon_id, version):
    """Whether everything that version of the addon needs is already installed.

    Kodi's EnableAddon only writes a line in the log for a dependency that is missing
    (CAddonMgr::EnableAddon) and switches the addon on all the same, so without this the
    fallback would leave an addon that says "installed" and breaks on opening. A repo whose
    index cannot be read is not a reason to stop: it goes on as before."""
    import xml.etree.ElementTree as ET

    try:
        raiz = ET.fromstring(addons_xml)
    except ET.ParseError as e:
        logger("Fallback ({0}): no se pudo leer el indice: {1}".format(addon_id, e))
        return True

    for addon in raiz.findall("addon"):
        if addon.get("id") != addon_id or addon.get("version") != version:
            continue
        for importa in addon.findall("requires/import"):
            necesita = importa.get("addon") or ""
            if not necesita or importa.get("optional") == "true":
                continue
            if not _ek_addon_registrado(necesita):
                logger("Fallback ({0}): falta {1}".format(addon_id, necesita))
                return False

    return True


def _ek_install_addon_zip_directly(addon_id, repo_id, friendly_name, monitor):
    # Plan B when InstallAddon() does not take. The datadir of the repo already installed is
    # read, the version is looked up in its addons.xml and the addon zip is fetched directly
    zip_path = None
    try:
        datadir = _ek_get_repo_datadir(repo_id)
        if not datadir:
            logger("Fallback ({0}): no se pudo obtener datadir de {1}".format(friendly_name, repo_id))
            return False
        # Repos with a local proxy (elementum serves on 127.0.0.1) publish no downloadable
        # datadir: if the proxy did not answer, fetching the zip by hand will not work either
        if "127.0.0.1" in datadir or "localhost" in datadir:
            logger("Fallback ({0}): datadir local, no aplica".format(friendly_name))
            return False

        try:
            addons_xml = _ek_download_text(datadir + "addons.xml")
        except Exception as e:
            logger("Fallback ({0}): no se pudo leer addons.xml: {1}".format(friendly_name, e))
            return False

        version = _ek_find_addon_version_in_index(addons_xml, addon_id)
        if not version:
            return False

        if not _ek_dependencias_listas(addons_xml, addon_id, version):
            return False

        addon_zip_url = "{0}{1}/{1}-{2}.zip".format(datadir, addon_id, version)
        try:
            content = _ek_download_bytes(addon_zip_url, EK_MAX_ADDON_ZIP_BYTES, timeout=60)
        except Exception as e:
            logger("Fallback ({0}): no se pudo bajar el zip: {1}".format(friendly_name, e))
            return False

        addons_dir = xbmcvfs.translatePath("special://home/addons/")
        zip_path = os.path.join(xbmcvfs.translatePath("special://temp/"), "{0}-{1}.zip".format(addon_id, version))
        with open(zip_path, "wb") as f:
            f.write(content)

        _ek_extract_zip(zip_path, addons_dir)

        xbmc.executebuiltin("UpdateLocalAddons()")
        if not _ek_activar(addon_id, monitor):
            # Kodi has its reasons (an addon for a newer Kodi, say) and says them itself.
            logger("Fallback ({0}): Kodi no lo ha activado".format(friendly_name), 'error')
            return False
        return True

    except _Cancelado:
        raise
    except Exception as e:
        logger("Fallback excepcion: {0}".format(e), 'error')
        return False

    finally:
        if zip_path and os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except Exception:
                pass


def _ek_notify_done(friendly_name):
    xbmcgui.Dialog().notification(HEADING, "{0} instalado correctamente".format(friendly_name),
                                  xbmcgui.NOTIFICATION_INFO, 4000)
    xbmc.executebuiltin("Container.Refresh")


def _ek_install_error(friendly_name, err):
    logger("Error instalando {0}: {1}".format(friendly_name, err), 'error')
    xbmcgui.Dialog().ok(
        "Error de instalación",
        "No se pudo instalar {0} automáticamente.\n\nError: {1}\n\n"
        "Puede que necesites activar Orígenes desconocidos en Ajustes.".format(friendly_name, err)
    )


def _ek_plan_b(addon_id, repo_id, friendly_name, monitor):
    """The fallback, in its own bar: the zip of the addon, taken from the datadir of its repo."""
    bg = xbmcgui.DialogProgressBG()
    bg.create(HEADING, "Instalación automática de {0} (alternativa)...".format(friendly_name))
    bg.update(50)
    try:
        return _ek_install_addon_zip_directly(addon_id, repo_id, friendly_name, monitor)
    finally:
        bg.close()


def _ek_esperar_indice(addon_id, dp, monitor, plazo=EK_INDICE_TIMEOUT_S):
    """Whether the repos offer the addon, refreshing their index only if they do not.

    The question is asked every two seconds and walks through every repo of the device (measured:
    120 ms on the phone, 65 ms on the PC). Refreshing is what costs: Kodi asks every repository,
    and one that answers by asking GitHub, as Elementum's does, spends part of the sixty calls an
    hour GitHub gives an address before cutting it off."""
    # Kodi never offers what is already there, switched on or off (checked on both benches), so
    # one that Kodi would not switch on goes straight to the fallback instead of waiting for an
    # index that will never name it
    if _ek_addon_registrado(addon_id):
        return False

    def ofrecido():
        return _ek_addon_available_in_repos(addon_id)

    # With no time to spare: one look, and a Cancel already given still counts
    if _ek_esperar(ofrecido, 0, monitor, dp):
        return True

    xbmc.executebuiltin("UpdateAddonRepos()")
    return _ek_esperar(ofrecido, plazo, monitor, dp, paso=2)


def _ek_pedir_a_kodi(addon_id, friendly_name, monitor):
    """Kodi installs it, asking for itself: 'instalado', 'no' or 'fallo'."""
    xbmcgui.Dialog().notification(HEADING, "Confirma la instalación de {0}".format(friendly_name),
                                  xbmcgui.NOTIFICATION_INFO, 4000)
    resultado = _ek_instalar_con_kodi(addon_id, monitor)
    if resultado == "instalado":
        _ek_notify_done(friendly_name)
    return resultado


# --- Repo mode (general case) ---------------------------------------------------------------

def _ek_asegurar_repo(repo_id, repo_zip_url, dp, monitor):
    """Leaves the repo installed and on. Returns the zip it downloaded, for the caller to delete.

    Three ways in: on already, nothing to do; there but off (or not yet registered), switched on
    without extracting anything over a repo that is already in place; missing, downloaded."""
    if _ek_addon_is_installed(repo_id):
        return None

    zip_path = None
    if not _ek_addon_dir_present(repo_id):
        dp.update(5, "Descargando repositorio...")
        content = _ek_download_bytes(repo_zip_url, EK_MAX_REPO_ZIP_BYTES)

        zip_path = os.path.join(xbmcvfs.translatePath("special://temp/"), "{0}.zip".format(repo_id))
        with open(zip_path, "wb") as f:
            f.write(content)

        dp.update(20, "Extrayendo repositorio...")
        _ek_extract_zip(zip_path, xbmcvfs.translatePath("special://home/addons/"))

    dp.update(35, "Activando el repositorio...")
    xbmc.executebuiltin("UpdateLocalAddons()")
    if not _ek_activar(repo_id, monitor, EK_REPO_POLL_TIMEOUT_S, dp):
        raise Exception("Kodi no ha activado {0} en {1}s".format(repo_id, EK_REPO_POLL_TIMEOUT_S))

    return zip_path


def _ek_install_repo_and_addon(addon_id, repo_id, repo_zip_url, friendly_name):
    monitor = xbmc.Monitor()
    dp = xbmcgui.DialogProgress()
    dp.create(HEADING, "Instalando {0}...".format(friendly_name))
    zip_path = None
    try:
        zip_path = _ek_asegurar_repo(repo_id, repo_zip_url, dp, monitor)

        dp.update(65, "Actualizando índice del repositorio...")
        ofrecido = _ek_esperar_indice(addon_id, dp, monitor)
        # Closed BEFORE asking Kodi: it installs with this same window
        dp.close()

        if ofrecido:
            resultado = _ek_pedir_a_kodi(addon_id, friendly_name, monitor)
            if resultado == "instalado":
                return True
            if resultado == "no":
                # They have just told Kodi no; there is nothing else to try and nothing to say
                return False

        # Kodi has not asked, or it tried and could not: the addon may be there and off, and
        # if not, its zip is still where its repo publishes it
        if _ek_try_recover_addon(addon_id, monitor) or _ek_plan_b(addon_id, repo_id,
                                                                  friendly_name, monitor):
            _ek_notify_done(friendly_name)
            return True

        xbmcgui.Dialog().ok(
            HEADING,
            "El repositorio de {0} se instaló, pero la instalación del addon no se completó.\n\n"
            "Para terminarla a mano:\nAddons - Instalar desde repositorio - {0} - Instalar".format(friendly_name)
        )
        return False

    except _Cancelado:
        return False

    except Exception as e:
        _ek_install_error(friendly_name, e)
        return False

    finally:
        try:
            dp.close()
        except Exception:
            pass
        if zip_path and os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except Exception:
                pass


# --- Official mode (Kodi's official repo, always present) -----------------------------------

def _ek_falta_su_repo(friendly_name, source_url):
    xbmcgui.Dialog().ok(
        HEADING,
        "{0} se instala desde su propio repositorio, que ya trae la app EspaKodi.\n\n"
        "En otro Kodi puedes añadirlo desde su página:\n{1}".format(friendly_name, source_url)
    )


def _ek_install_official(addon_id, repo_id, source_url, friendly_name):
    monitor = xbmc.Monitor()
    dp = xbmcgui.DialogProgress()
    dp.create(HEADING, "Instalando {0}...".format(friendly_name))
    try:
        # Not every "official" one comes from Kodi's own repo: ResolveURL comes from its own,
        # which travels inside the EspaKodi app
        if repo_id != EK_REPO_OFICIAL and not _ek_addon_is_installed(repo_id):
            if not (_ek_addon_registrado(repo_id) or _ek_addon_dir_present(repo_id)):
                dp.close()
                _ek_falta_su_repo(friendly_name, source_url)
                return False
            dp.update(20, "Activando el repositorio...")
            xbmc.executebuiltin("UpdateLocalAddons()")
            _ek_activar(repo_id, monitor, EK_REPO_POLL_TIMEOUT_S, dp)

        dp.update(40, "Actualizando índice del repositorio...")
        ofrecido = _ek_esperar_indice(addon_id, dp, monitor)
        dp.close()

        if ofrecido:
            resultado = _ek_pedir_a_kodi(addon_id, friendly_name, monitor)
            if resultado == "instalado":
                return True
            if resultado == "no":
                return False

        if _ek_try_recover_addon(addon_id, monitor):
            _ek_notify_done(friendly_name)
            return True

        donde = ("el repositorio oficial de Kodi" if repo_id == EK_REPO_OFICIAL
                 else "su repositorio, {0},".format(repo_id))
        texto = ("No se pudo instalar {0}.\n\nComprueba que {1} está habilitado\n"
                 "(Addons - Mis addons - Repositorios) e inténtalo de nuevo.".format(friendly_name, donde))
        if xbmc.getCondVisibility("System.Platform.Linux") \
                and not xbmc.getCondVisibility("System.Platform.Android"):
            texto += "\n\nEn Linux puede que venga del gestor de paquetes."
        xbmcgui.Dialog().ok(HEADING, texto)
        return False

    except _Cancelado:
        return False

    except Exception as e:
        _ek_install_error(friendly_name, e)
        return False

    finally:
        try:
            dp.close()
        except Exception:
            pass


def instalar_oficial(addon_id):
    """Installs an addon of Kodi's official repository. True if it ends up installed and on.

    Kodi asks the user itself, and what it answers is watched for instead of waiting for the
    builtin: executebuiltin(..., True) holds Kodi's GIL and stops every Python of Kodi while
    the question is on screen."""
    monitor = xbmc.Monitor()
    try:
        if _ek_instalar_con_kodi(addon_id, monitor) == "instalado":
            return True
        return _ek_try_recover_addon(addon_id, monitor)
    except _Cancelado:
        return False


# --- Proxy mode (a repository whose own service publishes its addons, e.g. elementum) -------

def _ek_install_proxy(addon_id, repo_id, repo_zip_url, friendly_name):
    monitor = xbmc.Monitor()
    dp = xbmcgui.DialogProgress()
    dp.create(HEADING, "Preparando {0}...".format(friendly_name))
    zip_path = None
    try:
        # 1. Ensure the repository is in place. If the user already has it, it is left alone:
        #    theirs may be newer or carry their own settings
        if not _ek_addon_dir_present(repo_id):
            dp.update(10, f"Descargando el repositorio de {friendly_name}...")
            content = _ek_download_bytes(repo_zip_url, EK_MAX_REPO_ZIP_BYTES)
            zip_path = os.path.join(xbmcvfs.translatePath("special://temp/"), f"{repo_id}.zip")
            with open(zip_path, "wb") as f:
                f.write(content)

            dp.update(25, f"Instalando el repositorio de {friendly_name}...")
            _ek_extract_zip(zip_path, xbmcvfs.translatePath("special://home/addons/"))

        dp.update(40, "Activando el repositorio...")
        xbmc.executebuiltin("UpdateLocalAddons()")
        if not _ek_activar(repo_id, monitor, EK_REPO_POLL_TIMEOUT_S, dp):
            raise Exception(f"Kodi no ha activado {repo_id} en {EK_REPO_POLL_TIMEOUT_S}s")

        if not _ek_addon_available_in_repos(addon_id):
            # Kodi registers a repository dropped into addons/ but does not start its service
            # until it restarts or sees the addon enabled. Disabling and enabling it again starts
            # it at once (2 s in EspaKodi), which spares the user the restart.
            _ek_jsonrpc("Addons.SetAddonEnabled", {"addonid": repo_id, "enabled": False})
            xbmc.sleep(1000)
            _ek_enable_addon_jsonrpc(repo_id)

        # 2. Wait for the repo proxy to publish the addon. It is a service and starts
        #    asynchronously, so InstallAddon() too early finds nothing
        dp.update(60, "Esperando al repositorio de {0}...".format(friendly_name))
        proxy_ready = _ek_esperar_indice(addon_id, dp, monitor, EK_PROXY_POLL_TIMEOUT_S)
        dp.close()

        # 3. Install. If the proxy never got to publish, restarting Kodi fixes it
        if not proxy_ready:
            xbmcgui.Dialog().ok(
                HEADING,
                "El repositorio de {0} se instaló, pero su servicio aún no responde.\n\n"
                "Reinicia Kodi y vuelve a pulsar {0} para completar la instalación.".format(friendly_name)
            )
            return False

        resultado = _ek_pedir_a_kodi(addon_id, friendly_name, monitor)
        if resultado == "instalado":
            return True
        if resultado == "no":
            return False

        if _ek_try_recover_addon(addon_id, monitor):
            _ek_notify_done(friendly_name)
            return True

        xbmcgui.Dialog().ok(
            HEADING,
            "No se pudo completar la instalación de {0}.\n\n"
            "Reinicia Kodi e inténtalo de nuevo, o instálalo desde\n"
            "Addons - Instalar desde repositorio - {0}.".format(friendly_name)
        )
        return False

    except Exception as e:
        _ek_install_error(friendly_name, e)
        return False

    finally:
        try:
            dp.close()
        except Exception:
            pass
        if zip_path and os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except OSError:
                pass


# --- Dispatcher -----------------------------------------------------------------------------

def _ek_dispatch_install(entry):
    addon_id, repo_id, zip_url, source, name, _plot, _icon, mode, _kind = entry
    if mode == "official":
        return _ek_install_official(addon_id, repo_id, source, name)
    if mode == "proxy":
        return _ek_install_proxy(addon_id, repo_id, zip_url, name)
    return _ek_install_repo_and_addon(addon_id, repo_id, zip_url, name)


def _ek_open_installed(entry):
    addon_id, _repo_id, _zip, _src, name, _plot, _icon, _mode, _kind = entry
    # Only plugins have an interface. A script.module.* (youtube-dl) cannot be opened
    if addon_id.startswith("plugin."):
        xbmcgui.Dialog().notification(HEADING, "Abriendo {0}...".format(name), xbmcgui.NOTIFICATION_INFO, 2000)
        xbmc.executebuiltin("RunAddon({0})".format(addon_id))
    else:
        xbmcgui.Dialog().notification(HEADING, "{0} ya esta instalado".format(name),
                                      xbmcgui.NOTIFICATION_INFO, 3000)


def _ek_manual_instructions(entry):
    _addon_id, _repo_id, zip_url, source, name, _plot, _icon, mode, kind = entry

    if mode == "official":
        text = (
            "[B]Cómo instalar {0} a mano[/B]\n\n"
            "Viene del repositorio oficial de Kodi, no hace falta añadir ninguna fuente.\n\n"
            "1. Addons - Instalar desde repositorio - Repositorio oficial de Kodi\n\n"
            "2. Addons de {1} - {0} - Instalar".format(name, kind)
        )
    elif mode == "proxy":
        text = (
            f"[B]Cómo instalar {name} a mano[/B]\n\n"
            "Su repositorio se instala desde su zip, no hace falta añadir ninguna fuente.\n\n"
            "1. Ajustes - Sistema - Addons - activa Orígenes desconocidos\n\n"
            f"2. Pulsa {name} en este menú. EKHorus baja el repositorio de GitHub y espera a "
            "su servicio\n\n"
            f"3. Si el servicio no responde, reinicia Kodi y vuelve a pulsar {name}\n\n"
            f"4. Sin este menú, baja el zip de\n   {zip_url}\n   y ve a Addons - Instalar desde un "
            f"archivo zip. Después, Instalar desde repositorio - ElementumOrg repository - Addons "
            f"de {kind} - {name}"
        )
    else:
        text = (
            "[B]Cómo instalar {0} a mano[/B]\n\n"
            "1. Ajustes - Sistema - Addons - activa Orígenes desconocidos\n\n"
            "2. Ajustes - Explorador de archivos - Añadir fuente:\n   {1}\n\n"
            "3. Addons - Instalar desde un archivo zip - {0}\n   repository.xxx-x.x.x.zip\n\n"
            "4. Instalar desde repositorio - {0} - Addons de {2} - {0}".format(name, source, kind)
        )

    xbmcgui.Dialog().textviewer("Instrucciones - {0}".format(name), text)


def launch_by_id(addon_id):
    entry = _EK_BY_ID.get(addon_id)
    if not entry:
        logger("launch_by_id: addon desconocido {0}".format(addon_id))
        return

    name = entry[4]

    # If it is already installed, it is opened and that is that
    if _ek_addon_is_installed(addon_id):
        _ek_open_installed(entry)
        return

    # If it is there but disabled, re-enabling is enough
    if _ek_try_recover_addon(addon_id, xbmc.Monitor()):
        xbmcgui.Dialog().notification(HEADING, "{0} reactivado correctamente".format(name),
                                      xbmcgui.NOTIFICATION_INFO, 3000)
        xbmc.executebuiltin("Container.Refresh")
        return

    idx = xbmcgui.Dialog().select(
        "{0} - instalación".format(name),
        ["Instalar automáticamente", "Ver instrucciones de instalación manual"]
    )
    if idx == 0:
        if xbmcgui.Dialog().yesno(HEADING, "{0} no está instalado.\n\n¿Descargar e instalar automáticamente?".format(name)):
            _ek_dispatch_install(entry)
    elif idx == 1:
        _ek_manual_instructions(entry)


# --- Menu -----------------------------------------------------------------------------------

def _ek_open_url(url, titulo, pregunta, aviso_android):
    abrir = xbmcgui.Dialog().yesno(
        titulo,
        '{0}\n\n[B]{1}[/B]\n\n¿Abrir en el navegador?'.format(pregunta, url),
        nolabel='Cerrar',
        yeslabel='Abrir navegador',
    )
    if not abrir:
        return

    apartar_musica()
    if xbmc.getCondVisibility('System.Platform.Android'):
        xbmc.executebuiltin('StartAndroidActivity("","android.intent.action.VIEW","","{0}")'.format(url))
        xbmcgui.Dialog().notification(HEADING, aviso_android, xbmcgui.NOTIFICATION_INFO, 2000)
    else:
        import webbrowser
        try:
            ok = webbrowser.open(url)
        except Exception:
            ok = False
        if not ok:
            xbmcgui.Dialog().ok(HEADING, 'No se pudo abrir el navegador.\n\nAccede a mano a:\n{0}'.format(url))


def open_web():
    _ek_open_url(
        'https://espatv.github.io',
        'EspaKodi en la web',
        'Todos los addons del ecosistema y la app, en un sitio:',
        'Abriendo la web...',
    )


def open_repo_unificado():
    _ek_open_url(
        'https://loiolo.io',
        'Repositorio Unificado',
        'Añade esta URL como fuente en Kodi e instala desde ella el repositorio de loiolink, '
        'que trae EspaTV, TopZilla, loiolog, Flow FavManager y loiolink:',
        'Abriendo repositorio...',
    )


def open_apk_latest():
    # Download APKs carries the EspaKodi of its own list, which is only as new as the last
    # edit of that list. The web always has the latest one.
    _ek_open_url(
        'https://espakodi.github.io/apk/',
        'Última versión EspaKodi APK',
        'Descarga la última versión de la app EspaKodi, en 32 y en 64 bits:',
        'Abriendo descarga...',
    )


def open_guia():
    _ek_open_url(
        'https://espakodi.github.io/ekstreaming/',
        'Guia de EKHorus',
        'La guia explica los montajes habituales de AceStream y AceServe, el motor en otro '
        'equipo y el diagnostico con VLC:',
        'Abriendo la guia...',
    )


def instalar_si_falta(addon_id):
    """Makes sure an addon of the ecosystem is available. Returns True if it is.

    Unlike launch_by_id(), it does NOT open the addon when it is already installed: here
    only its existence matters, because the caller is going to carry on with its own
    business (the control panel, for one, just wants to toggle the redirection)."""
    entry = _EK_BY_ID.get(addon_id)
    if not entry:
        logger("instalar_si_falta: addon desconocido {0}".format(addon_id))
        return False

    if _ek_addon_is_installed(addon_id):
        return True

    name = entry[4]

    # It may be installed but disabled, and re-enabling is faster than reinstalling
    if _ek_try_recover_addon(addon_id, xbmc.Monitor()):
        xbmcgui.Dialog().notification(HEADING, "{0} reactivado correctamente".format(name),
                                      xbmcgui.NOTIFICATION_INFO, 3000)
        return True

    idx = xbmcgui.Dialog().select(
        "{0} - instalación".format(name),
        ["Instalar automáticamente", "Ver instrucciones de instalación manual"]
    )
    if idx == 0:
        _ek_dispatch_install(entry)
    elif idx == 1:
        _ek_manual_instructions(entry)

    return _ek_addon_is_installed(addon_id)


# --- The rescue version ---------------------------------------------------------------------

def _ek_version_propia():
    return xbmcaddon.Addon().getAddonInfo('version')


def _ek_comprobar_rescate(zip_path):
    """Checks that the zip really carries that version of EKHorus.

    It is about to be extracted over the addon that is running, and something else in its
    place would leave neither the new version nor the old one."""
    manifiesto = "{0}/addon.xml".format(EK_OWN_ADDON_ID)
    with zipfile.ZipFile(zip_path, "r") as zf:
        if manifiesto not in zf.namelist():
            raise Exception("el zip descargado no es el de EKHorus")
        addon_xml = zf.read(manifiesto).decode("utf-8", "replace")

    if 'version="{0}"'.format(EK_RESCATE_VERSION) not in addon_xml:
        raise Exception("el zip descargado no es la {0}".format(EK_RESCATE_VERSION))


def instalar_rescate():
    """Puts EKHorus back to the version of EK_RESCATE_ZIP. True if it got installed.

    Kodi's installer only offers what a repository publishes, which is the latest version, so
    the zip is fetched and extracted the way the fallback of any other addon does. It is
    extracted OVER the running addon without emptying its folder first: deleting the files of
    a version while its own code runs from them would leave nothing to fall back to if the
    download or the extraction broke halfway. What the older version does not use, it does
    not read."""
    actual = _ek_version_propia()
    if actual == EK_RESCATE_VERSION:
        xbmcgui.Dialog().notification(
            HEADING, "Ya tienes la {0} instalada".format(EK_RESCATE_VERSION),
            xbmcgui.NOTIFICATION_INFO, 4000)
        return False

    if not xbmcgui.Dialog().yesno(
            "Volver a EKHorus {0}".format(EK_RESCATE_VERSION),
            "Se descargará y sustituirá a la {0} que tienes.\n"
            "Tus ajustes, historial y favoritos se conservan.\n"
            "Al terminar hay que reiniciar Kodi.".format(actual)):
        return False

    dp = xbmcgui.DialogProgress()
    dp.create(HEADING, "Descargando EKHorus {0}...".format(EK_RESCATE_VERSION))
    zip_path = None
    try:
        content = _ek_download_bytes(EK_RESCATE_ZIP, EK_MAX_ADDON_ZIP_BYTES, timeout=60)

        zip_path = os.path.join(xbmcvfs.translatePath("special://temp/"),
                                "{0}-{1}.zip".format(EK_OWN_ADDON_ID, EK_RESCATE_VERSION))
        with open(zip_path, "wb") as f:
            f.write(content)
        _ek_comprobar_rescate(zip_path)

        dp.update(70, "Instalando EKHorus {0}...".format(EK_RESCATE_VERSION))
        _ek_extract_zip(zip_path, xbmcvfs.translatePath("special://home/addons/"))
        xbmc.executebuiltin("UpdateLocalAddons()")
        dp.close()

        xbmcgui.Dialog().ok(
            HEADING,
            "EKHorus {0} instalado. Reinicia Kodi para usarlo.\n\n"
            "Si Kodi lo actualiza solo, desactiva su actualización automática en "
            "Mis add-ons.".format(EK_RESCATE_VERSION))
        return True

    except Exception as e:
        logger("Rescate a la {0}: {1}".format(EK_RESCATE_VERSION, e), 'error')
        xbmcgui.Dialog().ok(
            HEADING,
            "No se pudo instalar EKHorus {0}.\n\nError: {1}\n\n"
            "Sigues con la {2}.".format(EK_RESCATE_VERSION, e, actual))
        return False

    finally:
        try:
            dp.close()
        except Exception:
            pass
        if zip_path and os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except OSError:
                pass


_PLOT_APK_LATEST = (
    'Abre espakodi.github.io/apk en el navegador, que es donde están siempre las últimas '
    'versiones de la app EspaKodi, tanto de 32 bits (armeabi-v7a) como de 64 bits (arm64-v8a). '
    'En "Descargar APKs" también está, pero en la versión de su lista, que puede ir por detrás.'
)


_PLOT_REPO_UNIFICADO = (
    'Una sola fuente para instalar EspaTV, TopZilla, loiolog, Flow FavManager y loiolink. '
    'Con Orígenes desconocidos activado (Ajustes - Sistema - Add-ons), son tres pasos:\n\n'
    '1. Ajustes - Explorador de archivos - Añadir fuente: https://loiolo.io\n'
    '2. Add-ons - Instalar desde un archivo .zip - esa fuente - repository.loiolink-1.0.0.zip\n'
    '3. Add-ons - Instalar desde repositorio - loiolink Repository\n\n'
    'Los cinco están ahí dentro, cada uno en su apartado. Los demás addons de EspaKodi se '
    'instalan desde esta misma pantalla.'
)

_PLOT_PORTAL = (
    'Portal de EspaKodi: acceso a todos los addons del ecosistema y a la app EspaKodi '
    'lista para usar. Se abre en el navegador (espatv.github.io).'
)

_PLOT_RESCATE = (
    'La versión {0} de EKHorus, la que lleva la app EspaKodi, tal cual se publicó en su día. '
    'Está aquí para volver a ella si la última versión te falla: se descarga su zip y '
    'sustituye a la que tienes, conservando ajustes, historial y favoritos.\n\n'
    'Después hay que reiniciar Kodi. Si tienes el repositorio de EKHorus, Kodi puede volver '
    'a ofrecerte la última versión; para quedarte en la {0}, desactiva su actualización '
    'automática desde Mis add-ons.\n\n'
    'Ten en cuenta que la {0} es como era entonces: en Windows y en algunos Linux se '
    'descarga el motor AceStream nada más abrirla, sin preguntar (en el PC, unos 240 MB). '
    'La versión nueva también lo instala, pero solo cuando vas a reproducir algo y te '
    'hace falta.'.format(EK_RESCATE_VERSION)
)


def _ek_url(**kwargs):
    # EKHorus routes Items in base64, not query strings. Building it with urlencode the way
    # espadaily and atresdaily do would not work here
    return '%s?%s' % (sys.argv[0], Item(**kwargs).tourl())


def render_menu(handle):
    media_dir = _media_dir()
    fanart = _addon_fanart()

    li_web = xbmcgui.ListItem(label='EspaKodi en la web')
    li_web.setArt({'icon': os.path.join(media_dir, "portal.png"), 'fanart': fanart})
    poner_info_video(li_web, plot=_PLOT_PORTAL)
    xbmcplugin.addDirectoryItem(
        handle=handle,
        url=_ek_url(action='ek_open_web'),
        listitem=li_web,
        isFolder=False
    )

    li_repo = xbmcgui.ListItem(label='Repositorio Unificado')
    li_repo.setArt({'icon': os.path.join(media_dir, "info_repo.png"), 'fanart': fanart})
    poner_info_video(li_repo, plot=_PLOT_REPO_UNIFICADO)
    xbmcplugin.addDirectoryItem(
        handle=handle,
        url=_ek_url(action='ek_open_repo'),
        listitem=li_repo,
        isFolder=False
    )

    li_apk_web = xbmcgui.ListItem(label='Última versión EspaKodi APK')
    li_apk_web.setArt({'icon': os.path.join(media_dir, "descargas_web.png"), 'fanart': fanart})
    poner_info_video(li_apk_web, plot=_PLOT_APK_LATEST)
    xbmcplugin.addDirectoryItem(
        handle=handle,
        url=_ek_url(action='ek_open_apk'),
        listitem=li_apk_web,
        isFolder=False
    )

    enabled_ids = _ek_enabled_ids()
    for titulo, entradas in _ek_bloques():
        # Kodi does not take inert rows in a plugin listing, so the separator is a normal
        # row with an empty action: default.py leaves it without opening anything
        li_sep = xbmcgui.ListItem(label="[COLOR FFD9A520]————  {0}  ————[/COLOR]".format(titulo))
        li_sep.setArt({"icon": os.path.join(media_dir, "separator.png"), "fanart": fanart})
        xbmcplugin.addDirectoryItem(
            handle=handle,
            url=_ek_url(action=''),
            listitem=li_sep,
            isFolder=False
        )

        if titulo == EK_BLOQUE_ECOSISTEMA:
            puesta = _ek_version_propia() == EK_RESCATE_VERSION
            estado = ("[COLOR lime]Instalada[/COLOR]" if puesta
                      else "[COLOR FFD9A520]Versión de rescate[/COLOR]")
            li_resc = xbmcgui.ListItem(label="EKHorus {0} - {1}".format(EK_RESCATE_VERSION, estado))
            li_resc.setArt({"icon": _ek_addon_icon(
                EK_OWN_ADDON_ID, fallback=os.path.join(media_dir, "actualizar.png")),
                "fanart": fanart})
            poner_info_video(li_resc, plot=_PLOT_RESCATE)
            xbmcplugin.addDirectoryItem(
                handle=handle,
                url=_ek_url(action='ek_rescate'),
                listitem=li_resc,
                isFolder=False
            )

        for addon_id, _repo_id, _zip, _src, name, plot, fallback_icon, _mode, _kind in entradas:
            installed = addon_id in enabled_ids
            if installed:
                status = "[COLOR lime]Instalado[/COLOR]"
            elif _ek_addon_dir_present(addon_id):
                status = "[COLOR orange]Deshabilitado[/COLOR]"
            else:
                status = "[COLOR gray]No instalado[/COLOR]"

            fallback_path = os.path.join(media_dir, fallback_icon or "play_generic.png")
            icon = _ek_addon_icon(addon_id, fallback=fallback_path, installed=installed)

            li = xbmcgui.ListItem(label="{0} - {1}".format(name, status))
            li.setArt({"icon": icon, "fanart": fanart})
            poner_info_video(li, plot=plot)
            xbmcplugin.addDirectoryItem(
                handle=handle,
                url=_ek_url(action='ek_launch', addon_id=addon_id),
                listitem=li,
                isFolder=False
            )

    xbmcplugin.addSortMethod(handle=handle, sortMethod=xbmcplugin.SORT_METHOD_NONE)
    # The directory is NOT closed here: it is closed by cerrar_directorio() in default.py,
    # which is the one keeping count so endOfDirectory() is not called twice


# --- Own window -----------------------------------------------------------------------

_PLOT_SECCION = {
    EK_BLOQUE_ECOSISTEMA: 'Los addons del ecosistema EspaKodi. Cada uno hace lo suyo y '
                          'ninguno depende de los demás; instala solo los que vayas a usar.',
    'Dependencias y motores': 'Piezas que otros addons necesitan por debajo. No tienen menú '
                              'propio: se instalan y ya está.',
    'Otros': 'Lo que hay en el catálogo y no encaja en las secciones de arriba.',
}


def _ek_estado(addon_id, instalado):
    """(pill text, colour, hint) according to how the addon stands."""
    if instalado:
        return ui_common.color('Instalado', ui_common.TINTA_VERDE), 'on', 'Pulsa para abrirlo'

    if _ek_addon_dir_present(addon_id):
        return (ui_common.color('Deshabilitado', ui_common.ORO), 'gris',
                'Está puesto pero apagado')

    return ui_common.color('No instalado', ui_common.GRIS), 'gris', 'Pulsa para instalarlo'


def _ek_filas():
    media_dir = _media_dir()
    enabled_ids = _ek_enabled_ids()

    filas = [
        list_screen.Fila(clave='web', titulo='EspaKodi en la web',
                         pista='espatv.github.io',
                         icono=os.path.join(media_dir, 'portal.png'),
                         plot=_PLOT_PORTAL),
        list_screen.Fila(clave='repo', titulo='Repositorio Unificado',
                         pista='Cinco addons desde una sola fuente',
                         icono=os.path.join(media_dir, 'info_repo.png'),
                         plot=_PLOT_REPO_UNIFICADO),
        list_screen.Fila(clave='apkweb', titulo='Última versión APK',
                         pista='32 y 64 bits, siempre al día',
                         icono=os.path.join(media_dir, 'descargas_web.png'),
                         plot=_PLOT_APK_LATEST),
    ]

    for titulo, entradas in _ek_bloques():
        filas.append(list_screen.Fila(clave='', titulo=titulo, sep=True,
                                      plot=_PLOT_SECCION.get(titulo, '')))

        if titulo == EK_BLOQUE_ECOSISTEMA:
            puesta = _ek_version_propia() == EK_RESCATE_VERSION
            filas.append(list_screen.Fila(
                clave='rescate', titulo='EKHorus {0}'.format(EK_RESCATE_VERSION),
                pista=('Ya estás en la {0}'.format(EK_RESCATE_VERSION) if puesta
                       else 'Vuelve a la {0} si la última falla'.format(EK_RESCATE_VERSION)),
                icono=_ek_addon_icon(EK_OWN_ADDON_ID,
                                     fallback=os.path.join(media_dir, 'actualizar.png')),
                pastilla=((ui_common.color('Instalada', ui_common.TINTA_VERDE), 'on') if puesta
                          else (ui_common.color('Rescate', ui_common.ORO), 'gris')),
                plot=_PLOT_RESCATE))

        for addon_id, _repo, _zip, _src, name, plot, icono, _modo, _tipo in entradas:
            instalado = addon_id in enabled_ids
            etiqueta, tinta, pista = _ek_estado(addon_id, instalado)
            fallback = os.path.join(media_dir, icono or 'play_generic.png')
            filas.append(list_screen.Fila(
                clave=addon_id, titulo=name, pista=pista,
                icono=_ek_addon_icon(addon_id, fallback=fallback, installed=instalado),
                pastilla=(etiqueta, tinta), plot=plot))

    return filas


def mostrar_ventana():
    """EspaKodi Addons in its own window. False if it could not be opened."""
    abrir_luego = list()

    def pulsar(fila):
        if fila.clave == 'web':
            open_web()
        elif fila.clave == 'repo':
            open_repo_unificado()
        elif fila.clave == 'apkweb':
            open_apk_latest()
        elif fila.clave == 'rescate':
            # What is on disk is no longer the code that painted this window, so it is left
            if instalar_rescate():
                return 'cerrar'
        elif not _ek_addon_is_installed(fila.clave):
            instalar_si_falta(fila.clave)
        elif fila.clave.startswith('plugin.'):
            # An addon launched from underneath a modal stays behind it, so the window is
            # closed first and it is opened on leaving doModal().
            abrir_luego.append(fila.clave)
            return 'cerrar'
        else:
            # A module has no screen of its own to open, so closing the window for it would
            # be a surprise: it is said and the list stays.
            _ek_open_installed(_EK_BY_ID[fila.clave])

        return None

    abierta = list_screen.mostrar(
        titulo='[COLOR FFFFB70F][B]EK[/B][/COLOR]Horus[COLOR FF8A97A5]   ·   [/COLOR]'
               'EspaKodi Addons',
        subtitulo='Todo el ecosistema',
        hacer_filas=_ek_filas,
        al_pulsar=pulsar,
        botones=(('EspaKodi en la web', open_web),
                 ('Repositorio', open_repo_unificado)),
        estado='Pulsa un addon para abrirlo, o para instalarlo si te falta')

    for addon_id in abrir_luego:
        _ek_open_installed(_EK_BY_ID[addon_id])

    return abierta
