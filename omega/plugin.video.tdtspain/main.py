# -*- coding: utf-8 -*-
import sys
import os
from urllib.parse import parse_qs, urlencode

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

addon = xbmcaddon.Addon()
ADDON_PATH = addon.getAddonInfo("path")
HANDLE = int(sys.argv[1])

RESOURCES = os.path.join(ADDON_PATH, "resources")
MEDIA = os.path.join(RESOURCES, "media")
M3U_DOCS = os.path.join(RESOURCES, "documentales.m3u")

# ==================================================
# HELPERS
# ==================================================
def build_url(query):
    return sys.argv[0] + "?" + urlencode(query)

def play_stream(url):
    li = xbmcgui.ListItem(path=url)
    li.setProperty("IsPlayable", "true")
    li.setMimeType("application/vnd.apple.mpegurl")
    li.setContentLookup(False)
    xbmcplugin.setResolvedUrl(HANDLE, True, li)

# ==================================================
# TV CHANNELS (LOGOS 1–17)
# ==================================================
CHANNELS = [
    ("LA 1", "https://ztnr.rtve.es/ztnr/1688877.m3u8|User-Agent=Mozilla/5.0", 1),
    ("LA 2", "https://d4g9wh8d4wiaw.cloudfront.net/v1/master/3722c60a815c199d9c0ef36c5b73da68a62b09d1/cc-crbrakk0yedqb/La2ES.m3u8", 2),
    ("ANTENA 3", "http://176.65.146.237:8401/play/a0ae/index.m3u8", 3),
    ("CUATRO", "http://176.65.146.237:8401/play/a09s/index.m3u8", 4),
    ("TELECINCO", "http://176.65.146.237:8401/play/a09r/index.m3u8", 5),
    ("LA SEXTA", "http://176.65.146.237:8401/play/a0af/index.m3u8", 6),
    ("CANAL SUR", "http://176.65.146.237:8401/play/a09c/index.m3u8", 7),
    ("NEOX", "http://176.65.146.237:8401/play/a0ag/index.m3u8", 8),
    ("MEGA", "http://176.65.146.237:8401/play/a0a5/index.m3u8", 9),
    ("ATRESERIES", "http://176.65.146.237:8401/play/a0ai/index.m3u8", 10),
    ("ENERGY", "http://176.65.146.237:8401/play/a0ac/index.m3u8", 11),
    ("DIVINITY", "http://176.65.146.237:8401/play/a09q/index.m3u8", 12),
    ("CLAN", "https://dum8zv1rbdjj2.cloudfront.net/v1/master/3722c60a815c199d9c0ef36c5b73da68a62b09d1/cc-x6uutpgph4tpt/ClanES.m3u8", 13),
    ("BEMAD", "http://176.65.146.237:8401/play/a0aj/index.m3u8", 14),
    ("TRECE", "http://176.65.146.237:8401/play/a0a9/index.m3u8", 15),
    ("FDF", "http://176.65.146.237:8401/play/a09p/index.m3u8", 16),
    ("DISTRITO TV", "https://nlb2-live.emitstream.com/hls/3mn7wpcv7hbmxmdzaxap/master.m3u8", 17),
]

# ==================================================
# PLUTO FIX
# ==================================================
PLUTO_PARAMS = (
    "?deviceType=web"
    "&deviceMake=kodi"
    "&deviceModel=kodi"
    "&deviceVersion=21"
    "&appVersion=7.0"
    "&deviceDNT=0"
    "&deviceId=kodi"
    "&sid=abcd1234"
    "&serverSideAds=false"
)

# ==================================================
# FAST CHANNELS (NO SE QUITA NINGUNO)
# ==================================================
FAST = {
    "Rakuten TV": [
        ("Rakuten Action", "https://a9c57ec7ec5e4b7daeacc6316a0bb404.mediatailor.eu-west-1.amazonaws.com/v1/master/0547f18649bd788bec7b67b746e47670f558b6b2/production-LiveChannel-6069/master.m3u8"),
        ("Rakuten Comedia", "https://71db867f03ce4d71a29e92155f07ab87.mediatailor.eu-west-1.amazonaws.com/v1/master/0547f18649bd788bec7b67b746e47670f558b6b2/production-LiveChannel-6180/master.m3u8"),
        ("Rakuten Drama", "https://a7089c89d85f453d850c4a1518b43076.mediatailor.eu-west-1.amazonaws.com/v1/master/0547f18649bd788bec7b67b746e47670f558b6b2/production-LiveChannel-6092/master.m3u8"),
        ("Rakuten Family", "https://b0d59c8c98974e708e5ccb9a27cdfdfc.mediatailor.eu-west-1.amazonaws.com/v1/master/0547f18649bd788bec7b67b746e47670f558b6b2/production-LiveChannel-6205/master.m3u8"),
        ("Rakuten Top Movies", "https://ff335120300e4742a2b135ee9a9e7df8.mediatailor.eu-west-1.amazonaws.com/v1/master/0547f18649bd788bec7b67b746e47670f558b6b2/production-LiveChannel-5983/master.m3u8"),
        ("Rakuten Cine", "https://3ed8837c27bf41dabe8e2627be2e57e6.mediatailor.eu-west-1.amazonaws.com/v1/master/0547f18649bd788bec7b67b746e47670f558b6b2/production-LiveChannel-6196/master.m3u8"),
        ("Rakuten Crimen", "https://4ac0fe739f05408abf89ce151aced344.mediatailor.eu-west-1.amazonaws.com/v1/master/0547f18649bd788bec7b67b746e47670f558b6b2/production-LiveChannel-6220/master.m3u8"),
        ("Rakuten Romance", "https://4b95c0f7aa2b4cae80f6515600154151.mediatailor.eu-west-1.amazonaws.com/v1/master/0547f18649bd788bec7b67b746e47670f558b6b2/production-LiveChannel-6105/master.m3u8"),
        ("Rakuten Sci-Fi", "https://sci-fi-rakuten-tv-es.fast.rakuten.tv/v1/master/0547f18649bd788bec7b67b746e47670f558b6b2/production-LiveChannel-6740/master.m3u8"),
    ],
    "Pluto TV": [
        ("Pluto Clásico", "https://stitcher.pluto.tv/stitch/hls/channel/61373bb45168fe000773eecd/master.m3u8"),
        ("Pluto Estelar", "https://stitcher.pluto.tv/stitch/hls/channel/5f1ac1f1b66c76000790ef27/master.m3u8"),
        ("Pluto Thrillers", "https://stitcher.pluto.tv/stitch/hls/channel/5f1ac8a87cd38d000745d7cf/master.m3u8"),
        ("Pluto Acción", "https://stitcher.pluto.tv/stitch/hls/channel/5f1ac2591dd8880007bb7d6d/master.m3u8"),
        ("Pluto Western", "https://stitcher.pluto.tv/stitch/hls/channel/6385e82900ab2e000768a058/master.m3u8"),
    ],
    "RTVE Play": [
        ("RTVE 4 Estrellas", "https://ztnr.rtve.es/ztnr/2472038.m3u8"),
        ("RTVE Cuéntame", "https://ztnr.rtve.es/ztnr/6909843.m3u8"),
        ("RTVE Cine", "https://ztnr.rtve.es/ztnr/6909845.m3u8"),
        ("RTVE Series", "https://ztnr.rtve.es/ztnr/6922467.m3u8"),
    ],
    "Runtime": [
        ("Runtime Acción", "https://stream.ads.ottera.tv/playlist.m3u8?network_id=2550"),
        ("Runtime Comedia", "https://stream.ads.ottera.tv/playlist.m3u8?network_id=2551"),
        ("Runtime Crimen", "https://stream.ads.ottera.tv/playlist.m3u8?network_id=3533"),
        ("Runtime Romance", "https://stream.ads.ottera.tv/playlist.m3u8?network_id=3532"),
        ("Runtime Cine y Series", "https://stream.ads.ottera.tv/playlist.m3u8?network_id=2152"),
        ("Runtime Familia", "https://stream.ads.ottera.tv/playlist.m3u8?network_id=3528"),
        ("Runtime Terror", "https://stream.ads.ottera.tv/playlist.m3u8?network_id=3529"),
    ],
}

# ==================================================
# MENUS
# ==================================================
def main_menu():
    xbmcplugin.addDirectoryItem(HANDLE, build_url({"mode": "tv"}), xbmcgui.ListItem("📺 Canales TV"), True)
    xbmcplugin.addDirectoryItem(HANDLE, build_url({"mode": "docs"}), xbmcgui.ListItem("🎬 Documentales"), True)
    xbmcplugin.addDirectoryItem(HANDLE, build_url({"mode": "fast"}), xbmcgui.ListItem("📡 Cine Plataformas"), True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_tv():
    xbmcplugin.setContent(HANDLE, "videos")
    for name, stream, logo_id in CHANNELS:
        li = xbmcgui.ListItem(name)
        li.setProperty("IsPlayable", "true")
        logo = os.path.join(MEDIA, f"{logo_id}.png")
        if os.path.exists(logo):
            li.setArt({"thumb": logo, "icon": logo, "poster": logo})
        url = build_url({"mode": "play", "stream": stream})
        xbmcplugin.addDirectoryItem(HANDLE, url, li, False)
    xbmcplugin.endOfDirectory(HANDLE)

def list_docs():
    xbmcplugin.setContent(HANDLE, "videos")
    if not os.path.exists(M3U_DOCS):
        xbmcplugin.endOfDirectory(HANDLE)
        return
    with open(M3U_DOCS, "r", encoding="utf-8", errors="ignore") as f:
        name = None
        for line in f:
            line = line.strip()
            if line.startswith("#EXTINF"):
                name = line.split(",", 1)[-1]
            elif line.startswith("http"):
                li = xbmcgui.ListItem(name or "Documental")
                li.setProperty("IsPlayable", "true")
                url = build_url({"mode": "play", "stream": line})
                xbmcplugin.addDirectoryItem(HANDLE, url, li, False)
    xbmcplugin.endOfDirectory(HANDLE)

def list_fast_platforms():
    for platform in FAST:
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({"mode": "fast_list", "platform": platform}),
            xbmcgui.ListItem(platform),
            True
        )
    xbmcplugin.endOfDirectory(HANDLE)

def list_fast_channels(platform):
    xbmcplugin.setContent(HANDLE, "videos")
    for name, stream in FAST.get(platform, []):
        li = xbmcgui.ListItem(name)
        li.setProperty("IsPlayable", "true")

        if "pluto.tv" in stream:
            stream = stream + PLUTO_PARAMS

        stream += "|User-Agent=Mozilla/5.0"

        url = build_url({"mode": "play", "stream": stream})
        xbmcplugin.addDirectoryItem(HANDLE, url, li, False)

    xbmcplugin.endOfDirectory(HANDLE)

# ==================================================
# ROUTER
# ==================================================
def router():
    params = parse_qs(sys.argv[2][1:])
    mode = params.get("mode", [None])[0]

    if mode == "tv":
        list_tv()
    elif mode == "docs":
        list_docs()
    elif mode == "fast":
        list_fast_platforms()
    elif mode == "fast_list":
        list_fast_channels(params["platform"][0])
    elif mode == "play":
        play_stream(params["stream"][0])
    else:
        main_menu()

if __name__ == "__main__":
    router()
