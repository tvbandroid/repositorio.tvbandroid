import requests
import json

def obtener_canales_tdt():
    url = "https://www.tdtchannels.com/lists/tv.json"
    response = requests.get(url)
    if response.status_code == 200:
        datos = response.json()
        canales = []
        for pais in datos.get("countries", []):
            if pais["name"] == "Spain":
                for ambito in pais["ambits"]:
                    for canal in ambito["channels"]:
                        # Solo tomar el primer enlace de streaming disponible
                        link_streaming = canal["options"][0]["url"] if canal["options"] else None
                        
                        if link_streaming and ("twitch.tv" in link_streaming or "youtube.com" in link_streaming):
                            continue
                        
                        # Verificar si el enlace es m3u8 y agregar encabezados
                        if link_streaming and "m3u8" in link_streaming:
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36',
                                'Referer': 'https://www.rtve.es'
                            }
                            # Añadir los headers al final de la URL
                            link_streaming = link_streaming + "|" + "&".join([f"{key}={value}" for key, value in headers.items()])

                        canales.append({
                            "name": canal["name"],
                            "web": canal["web"],
                            "logo": canal["logo"],
                            "url": link_streaming
                        })
        return canales
    else:
        print("Error al obtener los canales.")
        return []


