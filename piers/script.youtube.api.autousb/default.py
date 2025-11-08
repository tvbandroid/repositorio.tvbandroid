# -*- coding: utf-8 -*-
import os, json, xbmc, xbmcgui, xbmcvfs, xbmcaddon, shutil, sys

ADDON = xbmcaddon.Addon()
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
YTDATA = xbmcvfs.translatePath("special://profile/addon_data/plugin.video.youtube/")
TARGET_JSON = os.path.join(YTDATA, "api_keys.json")
TARGET_SETTINGS = os.path.join(YTDATA, "settings.xml")

SEARCH_NAMES = ["api_keys.json", "apikeys.json"]

def notify(msg):
    try:
        xbmcgui.Dialog().notification("YouTube API Installer", msg, xbmcgui.NOTIFICATION_INFO, 3000)
    except:
        pass

def safe_listdir(path):
    try:
        return xbmcvfs.listdir(path)
    except:
        return ([],[])

def search_recursively(root, max_depth=4):
    queue = [(root,0)]
    visited = set()
    while queue:
        path, depth = queue.pop(0)
        if path in visited:
            continue
        visited.add(path)
        dirs, files = safe_listdir(path)
        if files:
            for f in files:
                if f.lower() in SEARCH_NAMES:
                    return os.path.join(path, f)
        if depth < max_depth and dirs:
            for d in dirs:
                sub = os.path.join(path, d)
                queue.append((sub, depth+1))
    return None

def find_api_file():
    candidates = []
    candidates.append("N:/")
    for L in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        candidates.append(f"{L}:/")
        candidates.append(f"{L}:/".lower())
    candidates += ["/storage","/mnt","/media","/run/media","/udisk","/storage/emulated/0","/mnt/media_rw"]
    for sp in ["special://external","special://usb","special://udisk","special://home","special://userdata"]:
        try:
            candidates.append(xbmcvfs.translatePath(sp))
        except:
            pass
    seen = set(); roots=[]
    for c in candidates:
        if c and c not in seen:
            seen.add(c); roots.append(c)
    for r in roots:
        try:
            found = search_recursively(r, max_depth=3)
            if found:
                return found
        except:
            continue
    return None

def convert_and_install(path):
    try:
        with xbmcvfs.File(path, 'r') as f:
            raw = f.read()
    except Exception as e:
        notify("Error leyendo JSON del USB")
        xbmc.log("Error leyendo JSON: %s" % str(e))
        return False
    try:
        data = json.loads(raw)
    except Exception as e:
        notify("JSON inválido")
        xbmc.log("JSON inválido: %s" % str(e))
        return False

    api = data.get("api_key","")
    cid = data.get("client_id","")
    sec = data.get("client_secret","")

    yt_json = {"keys": {"personal": {"api_key": api, "client_id": cid, "client_secret": sec}}}

    try:
        xbmcvfs.mkdirs(YTDATA)
    except:
        pass

    try:
        with xbmcvfs.File(TARGET_JSON, 'w') as f:
            f.write(json.dumps(yt_json, indent=4))
        settings = "<settings>\n"
        settings += '  <setting id="youtube.api.key" value="%s" />\n' % api
        settings += '  <setting id="youtube.api.id" value="%s" />\n' % cid
        settings += '  <setting id="youtube.api.secret" value="%s" />\n' % sec
        settings += "</settings>\n"
        with xbmcvfs.File(TARGET_SETTINGS, 'w') as f:
            f.write(settings)
    except Exception as e:
        notify("Error escribiendo en userdata")
        xbmc.log("Error escribiendo: %s" % str(e))
        return False

    try:
        shutil.copy(path, os.path.join(xbmcvfs.translatePath("special://profile"), os.path.basename(path)))
    except:
        pass

    notify("APIs instaladas correctamente")
    return True

def main():
    notify("Buscando api_keys.json en USB/HDD (incluye N:/)...")
    path = find_api_file()
    if not path:
        notify("No se encontró api_keys.json/apikeys.json en USB/HDD")
        return
    xbmc.log("API file found at: %s" % path)
    convert_and_install(path)

if __name__ == "__main__":
    main()
