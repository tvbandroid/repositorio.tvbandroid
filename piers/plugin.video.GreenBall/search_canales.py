import os
import json
import xbmcgui
import base64
import requests

# Constants
CWD = os.path.dirname(os.path.abspath(__file__))
LINKS_FILE = os.path.join(CWD, 'acestream_links.json')
KEY = b"mi_clave_super_segura_para_XOR"  # misma clave usada al guardar
GITHUB_RAW_URL = "https://raw.githubusercontent.com/ajsm90/greenball.repo/refs/heads/master/d.json"


def mostrar_notificacion(titulo, mensaje, duracion=3000):
    xbmcgui.Dialog().notification(titulo, mensaje, time=duracion, sound=False)

# --- XOR + base64 decode ---
def xor_bytes(data, key=KEY):
    return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])

def cargar_enlaces_desde_json():
    try:
        # Si no necesitas headers especiales, solo usa un dict vacío
        headers = {}
        r = requests.get(GITHUB_RAW_URL, headers=headers, timeout=10)
        r.raise_for_status()

        encrypted_data = r.text
        if not encrypted_data:
            raise ValueError("El archivo GitHub está vacío")

        decoded = base64.b64decode(encrypted_data)
        decrypted = xor_bytes(decoded)
        data = json.loads(decrypted.decode("utf-8"))

        last_update = data.get("last_update", "desconocida")

        return {
            "links": data.get("links", []),
            "names": data.get("names", []),
            "colortext": data.get("colortext", "white"),
            "last_update": last_update
        }

    except Exception as e:
        mostrar_notificacion("Error cargando canales", str(e))
        return {
            "links": [],
            "names": [],
            "colortext": "white",
            "last_update": "desconocida"
        }