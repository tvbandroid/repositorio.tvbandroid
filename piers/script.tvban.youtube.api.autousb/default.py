import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import os
import json
import platform

ADDON = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo("name")

def get_usb_paths():
    system = platform.system().lower()
    paths = []

    if system == "windows":
        for letra in "DEFGHIJKLMNOPQRSTUVWXYZ":
            ruta = f"{letra}:/"
            if os.path.exists(ruta):
                paths.append(ruta)
    else:
        posibles = [
            "/storage",
            "/mnt",
            "/mnt/media_rw",
            "/mnt/usb",
            "/storage/emulated/0",
        ]
        for base in posibles:
            if os.path.exists(base):
                for root, dirs, files in os.walk(base):
                    if "api_keys.json" in files:
                        return [root]

    return paths

def instalar_api(ruta_json):
    try:
        json_file = os.path.join(ruta_json, "api_keys.json")

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        api_key   = data.get("api_key", "")
        client_id = data.get("client_id", "")
        secret    = data.get("client_secret", "")

        youtube_settings = xbmcvfs.translatePath(
            "special://profile/addon_data/plugin.video.youtube/settings.xml"
        )

        content = (
            "<settings>\n"
            f'    <setting id="youtube.api.key" value="{api_key}" />\n'
            f'    <setting id="youtube.api.id" value="{client_id}" />\n'
            f'    <setting id="youtube.api.secret" value="{secret}" />\n'
            "</settings>"
        )

        carpeta = os.path.dirname(youtube_settings)
        if not os.path.exists(carpeta):
            os.makedirs(carpeta)

        with open(youtube_settings, "w", encoding="utf-8") as f:
            f.write(content)

        return True, youtube_settings

    except Exception as e:
        return False, str(e)


def main():
    rutas = get_usb_paths()

    if not rutas:
        xbmcgui.Dialog().ok(
            ADDON_NAME,
            "No se detectó ningún USB.\nColoque api_keys.json en la raíz."
        )
        return

    for ruta in rutas:
        if "api_keys.json" in os.listdir(ruta):
            ok, msg = instalar_api(ruta)
            if ok:
                xbmcgui.Dialog().ok(
                    ADDON_NAME,
                    f"✅ API Keys instaladas correctamente.\n\nArchivo:\n{msg}\n\nReinicia Kodi."
                )
            else:
                xbmcgui.Dialog().ok(ADDON_NAME, f"❌ Error instalando API:\n{msg}")
            return

    xbmcgui.Dialog().ok(
        ADDON_NAME,
        "No se encontró api_keys.json en el USB."
    )


if __name__ == "__main__":
    main()
