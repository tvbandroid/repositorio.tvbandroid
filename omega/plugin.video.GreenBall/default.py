import sys
import os
import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
import requests
import urllib.parse
from urllib.parse import quote_plus
import difflib 
from search_canales import cargar_enlaces_desde_json
from directos import get_tv_programs, find_closest_channel, normalize_channel_name  # Importa find_closest_channel de directos
from tdt import obtener_canales_tdt
import time

# from directos2 import obtener_eventos
# from links_cine import obtener_eventos_nuevos, search_movies

from links_series import obtener_series, obtener_episodios, buscar_series, obtener_pelis, buscar_peliculas

from download import download_db
# from links_series import obtener_series, obtener_episodios_serie, buscar_series, obtener_imagen_de_serie

import requests, re
session = requests.Session()

def mostrar_notificacion(titulo, mensaje, duracion=3000):
    xbmcgui.Dialog().notification(titulo, mensaje, time=duracion, sound=False)

# Constants
ADDON = xbmcaddon.Addon()
PLUGIN_URL = sys.argv[0]
HANDLE = int(sys.argv[1])
BD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templ.db")

class KodiAddonWrapper:
    def __init__(self):
        self.handle = HANDLE
        self.plugin_url = PLUGIN_URL
    
    def show_main_menu(self):
        
        """Display the main menu with options."""
        # main_options = [
        # "TDT", "Directos", "Canales", 
        # "Elegir canales opcion 1", "Elegir canales opcion 2 (por defecto)", 
        # "Elegir canales opcion 3","Elegir canales opcion 4", "Elegir canales opcion 5", "Elegir canales opcion 6", "Cine", "Series", "Obtener series y pelis"
        # ]
        main_options = [
        "TDT", "Directos", "Canales", "Cine", "Series", "Obtener series y pelis"
        ]
        
        # Definir un diccionario de colores para las opciones, por ejemplo:
        colors = {
            "TDT": "white",  # Color hexadecimal
            "Directos": "white",  # RGB
            "Canales": "white",  # Nombre de color
            # "Elegir canales opcion 1": "lightyellow",  # Tomate (hexadecimal)
            # "Elegir canales opcion 2 (por defecto)": "aqua",  # Azul
            # "Elegir canales opcion 3": "yellowgreen",  # Naranja
            # "Elegir canales opcion 4": "blue",  # Naranja
            # "Elegir canales opcion 5": "yellow",
            # "Elegir canales opcion 6": "yellow",  # red
            "Cine": "white",  # Oro (hexadecimal)
            "Series": "white",  # Púrpura
            "Obtener series y pelis": "white",  # Rosa
        }

        for option in main_options:
            color = colors.get(option, "white")  # Si no hay color asignado, por defecto será blanco
            list_item = xbmcgui.ListItem(label=f"[COLOR {color}] {option} [/COLOR]")  # Aplicar color al texto
            xbmcplugin.addDirectoryItem(
                handle=self.handle,
                url=f"{self.plugin_url}?action={option.lower().replace(' ', '_')}",
                listitem=list_item,
                isFolder=True,
            )
        xbmcplugin.endOfDirectory(self.handle)

    def mostrar_canales_tdt(self):
        canales = obtener_canales_tdt()
        if not canales:
            xbmcgui.Dialog().notification("Error", "No se pudieron cargar los canales de TDT.", xbmcgui.NOTIFICATION_ERROR)
            return
        
        for canal in canales:
            if canal["url"]:
                list_item = xbmcgui.ListItem(label=canal["name"])
                list_item.setArt({'thumb': canal["logo"]})
                list_item.setInfo("video", {"title": canal["name"]})
                url = canal["url"]  # Link directo para la reproducción
                xbmcplugin.addDirectoryItem(
                    handle=self.handle, 
                    url=url, 
                    listitem=list_item, 
                    isFolder=False,
                )

        xbmcplugin.endOfDirectory(self.handle)
    
    def show_directos(self):
        """Display live events with their associated channels, grouped by date."""
        data = cargar_enlaces_desde_json()

        links = data.get("links", [])
        names = data.get("names", [])
        colortext = data.get("colortext", "white")
        last_update = data.get("last_update", "desconocida")

        data = cargar_enlaces_desde_json()
        last_update = data.get("last_update", "desconocida")

        # Mostrar un item al principio con la fecha de última actualización
        info_item = xbmcgui.ListItem(label=f"[COLOR yellow][B]Canales actualizados: {last_update}[/B][/COLOR]")
        info_item.setInfo("video", {"title": "Última actualización"})
        xbmcplugin.addDirectoryItem(
            handle=self.handle,
            url="",
            listitem=info_item,
            isFolder=False
        )

        # Obtener los eventos deportivos
        channel_map = {"names": names, "links": links}
        eventos = get_tv_programs(channel_map=channel_map)

        # Agrupar eventos por fecha
        eventos_por_fecha = {}
        for evento in eventos:
            if evento.day not in eventos_por_fecha:
                eventos_por_fecha[evento.day] = []
            eventos_por_fecha[evento.day].append(evento)

        deportes_validos = ["Fútbol", "Fórmula 1", "Motos", "Baloncesto", "Tenis", "Boxeo", "Ciclismo"]

        # Mostrar los eventos en el menú, agrupados por fecha
        for fecha, eventos_lista in eventos_por_fecha.items():
            list_item_fecha = xbmcgui.ListItem(label=f"[COLOR yellow]{fecha}[/COLOR]")
            xbmcplugin.addDirectoryItem(
                handle=self.handle,
                url="#",
                listitem=list_item_fecha,
                isFolder=False
            )

            for evento in eventos_lista:
                hora = evento.time
                nombre_evento = evento.name
                canal = evento.channel
                tipoevento = evento.sport

                if evento.sport not in deportes_validos:
                    continue

                # Buscar todos los índices que coincidan con el canal
                indices_coincidentes = [i for i, name in enumerate(names) if normalize_channel_name(name) == normalize_channel_name(canal)]
                
                if not indices_coincidentes:
                    continue

                # Mostrar el primer enlace con el nombre completo del evento
                idx_principal = indices_coincidentes[0]
                acestream_link = links[idx_principal]
                list_item = xbmcgui.ListItem(
                    label=f"[COLOR {colortext}]{hora} | {nombre_evento} | {canal} | {tipoevento}[/COLOR]"
                )
                list_item.setInfo("video", {"title": f"{nombre_evento} | {tipoevento}"})
                list_item.setProperty("IsPlayable", "true")
                xbmcplugin.addDirectoryItem(
                    handle=self.handle,
                    url=f"plugin://script.module.horus?action=play&id={acestream_link}",
                    listitem=list_item,
                    isFolder=False
                )

                # Mostrar los enlaces adicionales como opciones numeradas
                for i, idx in enumerate(indices_coincidentes[1:], start=1):
                    acestream_link = links[idx]
                    list_item = xbmcgui.ListItem(
                        label=f"{hora} | {nombre_evento} | Opción {i}"
                    )
                    list_item.setInfo("video", {"title": f"{nombre_evento} - {tipoevento} (Opción {i})"})
                    list_item.setProperty("IsPlayable", "true")
                    xbmcplugin.addDirectoryItem(
                        handle=self.handle,
                        url=f"plugin://script.module.horus?action=play&id={acestream_link}",
                        listitem=list_item,
                        isFolder=False
                    )


        xbmcplugin.endOfDirectory(self.handle)

    
    
    def show_canales(self):
        """Display the Canales menu."""
        data = cargar_enlaces_desde_json()  # Ahora devuelve también 'last_update'

        links = data.get("links", [])
        names = data.get("names", [])
        colortext = data.get("colortext", "white")
        last_update = data.get("last_update", "desconocida")

        
        data = cargar_enlaces_desde_json()
        last_update = data.get("last_update", "desconocida")

        # Mostrar un item al principio con la fecha de última actualización
        info_item = xbmcgui.ListItem(label=f"[COLOR yellow][B]Canales actualizados: {last_update}[/B][/COLOR]")
        info_item.setInfo("video", {"title": "Última actualización"})
        xbmcplugin.addDirectoryItem(
            handle=self.handle,
            url="",
            listitem=info_item,
            isFolder=False
        )

        # Mostrar los canales en el menú
        for idx, (name, link) in enumerate(zip(names, links), start=1):
            list_item = xbmcgui.ListItem(label=f"[COLOR {colortext}] {name} [/COLOR]")
            list_item.setInfo("video", {"title": name})
            xbmcplugin.addDirectoryItem(
                handle=self.handle,
                url=f"plugin://script.module.horus?action=play&id={link}",
                listitem=list_item,
                isFolder=False,
            )
        
        xbmcplugin.endOfDirectory(self.handle)


    # def update_list(self):
    #     config_eventos = {
    #         "mode": "html",
    #         "selector": "td.canales a",
    #         "attr": "href",
    #         "prefix": "acestream://",
    #         "text": True
    #     }
    #     colortext = "lightyellow"
    #     links, names, colortext  = actualizar_lista_generica("https://eventos-uvl7.vercel.app/", config_eventos, colortext)

    # def update_list2(self):
    #     """Update the list of channels el cano."""
    #     canales_url = "https://ipfs.io/ipns/k51qzi5uqu5dgg9al11vomikugim0o1i3l3fxp3ym3jwaswmy9uz8pq4brg1u9"  

    #     links, names, colortext = actualizar_lista2(canales_url)  # Llamar a la función para actualizar la lista

    # def update_list3(self):
    #     canales_url = "https://fr.4everproxy.com/direct/aHR0cHM6Ly9jaXJpYWNvLWxpYXJ0LnZlcmNlbC5hcHAv"

    #     config_freijo = {
    #         "mode": "html",            
    #         "selector": "tr td a",
    #         "attr": "href",
    #         "prefix": "acestream://",
    #         "text": True
    #     }
    #     colortext = "yellowgreen"
    #     links, names, colortext = actualizar_lista_generica(canales_url, config_freijo, colortext)

    # def update_list4(self):
    #     """Update the list of channels."""
    #     config_canalcard = {
    #         "mode": "html",
    #         "selector": "article.canal-card a.acestream-link",
    #         "attr": "href",
    #         "prefix": "acestream://",
    #         "text": False,
    #         "name_selector": "span.canal-nombre",
    #         "parent_tag": "article"   # para buscar el nombre dentro del mismo bloque
    #     }
    #     colortext = "blue"
    #     links, names, colortext = actualizar_lista_generica("https://shickat.me/", config_canalcard, colortext)


    # def update_list5(self):
    #     colortext = "yellow"
        
    #     # --- Usando la fuente DNS en lugar de la web ---
    #     codigo_dns = "681fc74c1833d17ffd9a9c59"  # Ajusta según lo que quieras
    #     links, names, colortext = actualizar_lista_dns(codigo_dns, colortext)

    #     # Aquí podrías seguir usando links, names y colortext como antes
    #     print(f"Se actualizaron {len(links)} enlaces desde DNS")
    
    # def update_list6(self):
    #     colortext = "yellow"
        
    #     # --- Usando la fuente DNS en lugar de la web ---
    #     codigo_dns = "682cb7103451b27a40bc9aa2"  # Ajusta según lo que quieras
    #     links, names, colortext = actualizar_lista_dns(codigo_dns, colortext)

    #     # Aquí podrías seguir usando links, names y colortext como antes
    #     print(f"Se actualizaron {len(links)} enlaces desde DNS")
    

    def mostrar_pelis(self, pagina=1):
        """Display new events with their associated links and images."""

        # Verificar si la base de datos existe
        if not os.path.exists(BD_PATH):
            # Si no existe la base de datos, mostrar una notificación y salir
            xbmcgui.Dialog().notification("Error", "Base de datos no encontrada, Pulsa en obtener series y pelis primero", xbmcgui.NOTIFICATION_ERROR, 5000)
            return  # Salir de la función si no se encuentra la base de datos
        
        # Agregar un enlace para buscar por título
        buscar_item = xbmcgui.ListItem(label="BUSCAR POR TITULO")
        buscar_url = f"{sys.argv[0]}?action=buscar_titulo_peli"
        xbmcplugin.addDirectoryItem(
            handle=self.handle,
            url=buscar_url,
            listitem=buscar_item,
            isFolder=True
        )

        eventos_nuevos = obtener_pelis(pagina)  

        for evento in eventos_nuevos:
            nombre_evento = evento['titulo']
            enlace = evento['url']
            url_codificada = quote_plus(enlace)
            url_imagen = evento['imagen']
            descripcion = evento.get('descripcion', "Descripción no disponible.")  #descripción

            # Crear el ListItem para Kodi
            list_item = xbmcgui.ListItem(label=nombre_evento)
            # list_item.setArt({'thumb': url_imagen})  # Establecer la imagen
            list_item.setArt({'thumb': url_imagen, 'icon': url_imagen, 'fanart': url_imagen})
            list_item.setInfo("video", {
                "title": nombre_evento,
                "plot": descripcion  # Añadir la descripción 
            })
            list_item.setProperty("IsPlayable", "true")  # Marcarlo como reproducible

            xbmcplugin.addDirectoryItem(
                handle=self.handle,
                url=f"plugin://plugin.video.elementum/play?uri={url_codificada}",  # enlace de descarga para reproducir
                listitem=list_item,
                isFolder=False
            )

        # Si hay más páginas de resultados, añadir el enlace "Mostrar más resultados"
        next_page_url = f"{sys.argv[0]}?action=cine&pagina={pagina + 1}"
        next_page_item = xbmcgui.ListItem(label="MOSTRAR MÁS RESULTADOS")
        xbmcplugin.addDirectoryItem(
            handle=self.handle,
            url=next_page_url,
            listitem=next_page_item,
            isFolder=True  # Esto indica que es un "folder" (una página más de resultados)
        )

        xbmcplugin.endOfDirectory(self.handle)

    def buscar_titulo_peli(self):
        """Función para buscar series por título."""
        dialog = xbmcgui.Dialog()
        titulo = dialog.input("Ingrese el título de la pelicula:")
        
        if titulo: 
            eventos_nuevos = buscar_peliculas(titulo)  
            
            # Verificar si se encontraron resultados
            if not eventos_nuevos:
                mostrar_notificacion("No se encontraron resultados", "No se encontraron peliculas con ese título.", 3000)
                return
        for evento in eventos_nuevos:
            nombre_evento = evento['titulo']
            enlace = evento['url']
            url_codificada = quote_plus(enlace)
            url_imagen = evento['imagen']
            descripcion = evento.get('descripcion', "Descripción no disponible.")  #descripción

            # Crear el ListItem para Kodi
            list_item = xbmcgui.ListItem(label=nombre_evento)
            # list_item.setArt({'thumb': url_imagen})  # Establecer la imagen
            list_item.setArt({'thumb': url_imagen, 'icon': url_imagen, 'fanart': url_imagen})
            list_item.setInfo("video", {
                "title": nombre_evento,
                "plot": descripcion  # Añadir la descripción 
            })
            list_item.setProperty("IsPlayable", "true")  # Marcarlo como reproducible

            xbmcplugin.addDirectoryItem(
                handle=self.handle,
                url=f"plugin://plugin.video.elementum/play?uri={url_codificada}",  # enlace de descarga para reproducir
                listitem=list_item,
                isFolder=False
            )
            
        mostrar_notificacion("Terminado", "Mostrando lista", 1000)
        xbmcplugin.endOfDirectory(self.handle)

    
    
    def mostrar_series(self, pagina=1):
        """Muestra las series con sus imágenes y descripciones en el addon de Kodi."""
        # Verificar si la base de datos existe
        if not os.path.exists(BD_PATH):
            # Si no existe la base de datos, mostrar una notificación y salir
            xbmcgui.Dialog().notification("Error", "Base de datos no encontrada, Pulsa en obtener series y pelis primero", xbmcgui.NOTIFICATION_ERROR, 5000)
            return  # Salir de la función si no se encuentra la base de datos
        # Elemento para buscar por título
        buscar_item = xbmcgui.ListItem(label="BUSCAR POR TITULO")
        buscar_url = f"{sys.argv[0]}?action=buscar_titulo_serie"
        xbmcplugin.addDirectoryItem(
            handle=self.handle,
            url=buscar_url,
            listitem=buscar_item,
            isFolder=True
        )

        # Obtener las series de la base de datos (página específica)
        series = obtener_series(pagina)  # Pasamos la página a obtener_series

        # Iterar sobre las series y añadirlas a la interfaz de Kodi
        for serie in series:
            nombre_serie = serie['titulo']
            url_imagen = serie['imagen']
            serieID = serie['serieID']
            descripcion = serie.get('descripcion', "Descripción no disponible.")
            url_serie = f"{sys.argv[0]}?action=mostrar_episodios&serieID={serieID}&imagen={url_imagen}"
            
            # Crear un ListItem para la serie
            list_item = xbmcgui.ListItem(label=nombre_serie)
            list_item.setArt({'thumb': url_imagen, 'icon': url_imagen, 'fanart': url_imagen})
            list_item.setInfo("video", {
                "title": nombre_serie,
                "plot": descripcion
            })
            
            # Añadir el item a la interfaz de Kodi
            xbmcplugin.addDirectoryItem(
                handle=self.handle,
                url=url_serie,
                listitem=list_item,
                isFolder=True  # Esto hace que sea un "folder" para navegar
            )

        # Si hay más páginas de resultados, añadir el enlace "Mostrar más resultados"
        next_page_url = f"{sys.argv[0]}?action=series&pagina={pagina + 1}"
        next_page_item = xbmcgui.ListItem(label="MOSTRAR MÁS RESULTADOS")
        xbmcplugin.addDirectoryItem(
            handle=self.handle,
            url=next_page_url,
            listitem=next_page_item,
            isFolder=True  # Esto indica que es un "folder" (una página más de resultados)
        )

        # Finaliza el directorio de la lista
        xbmcplugin.endOfDirectory(self.handle)

    def buscar_titulo_serie(self):
        """Función para buscar series por título."""
        dialog = xbmcgui.Dialog()
        titulo = dialog.input("Ingrese el título de la serie:")
        
        if titulo: 

            series = buscar_series(titulo)
            
            # Verificar si se encontraron resultados
            if not series:
                mostrar_notificacion("No se encontraron resultados", "No se encontraron series con ese título.", 3000)
                return
                        
            # Iterar sobre las series y añadirlas a la interfaz de Kodi
            for serie in series:
                nombre_serie = serie['titulo']
                url_imagen = serie['imagen']
                serieID = serie['serieID']
                descripcion = serie.get('descripcion', "Descripción no disponible.")
                url_serie = f"{sys.argv[0]}?action=mostrar_episodios&serieID={serieID}&imagen={url_imagen}"
                
                # Crear un ListItem para la serie
                list_item = xbmcgui.ListItem(label=nombre_serie)
                list_item.setArt({'thumb': url_imagen, 'icon': url_imagen, 'fanart': url_imagen})
                list_item.setInfo("video", {
                    "title": nombre_serie,
                    "plot": descripcion
                })
                
                # Añadir el item a la interfaz de Kodi
                xbmcplugin.addDirectoryItem(
                    handle=self.handle,
                    url=url_serie,
                    listitem=list_item,
                    isFolder=True  # Esto hace que sea un "folder" para navegar
                )

            mostrar_notificacion("Terminado", "Mostrando lista", 1000)
            xbmcplugin.endOfDirectory(self.handle)
    
    def mostrar_episodios(self, serieID, url_imagen):
        """Muestra los episodios de una serie específica en el addon de Kodi."""
        episodios = obtener_episodios(serieID)

        for episodio in episodios:
            nombre_episodio = episodio['titulo']
            enlace_descarga = episodio['stream_url']
            url_codificada = quote_plus(enlace_descarga)
            fecha = episodio['fecha']
            
            # Crear el ListItem para Kodi
            list_item = xbmcgui.ListItem(label=nombre_episodio)
            
            # Formatear la fecha de emisión
            descripcion = f"Emitido el {fecha}"  # Aseguramos que 'fecha' es una cadena de texto
            
            # Configurar la imagen de la serie
            list_item.setArt({'thumb': url_imagen, 'icon': url_imagen, 'fanart': url_imagen})
            
            # Establecer la información del episodio
            list_item.setInfo("video", {
                "title": nombre_episodio,
                "plot": descripcion  # Usamos la descripción formateada como cadena
            })
            
            # Indicamos que el episodio es reproducible
            list_item.setProperty("IsPlayable", "true")

            # Añadir el episodio a la interfaz de Kodi
            xbmcplugin.addDirectoryItem(
                handle=self.handle,
                url=f"plugin://plugin.video.elementum/play?uri={url_codificada}",  
                listitem=list_item,
                isFolder=False  # Esto indica que no es un folder, es un episodio reproducible
            )

        # Finalizar el directorio de la lista
        xbmcplugin.endOfDirectory(self.handle)

    def download_shows_movies(self):
        download_db()

    def run(self):
        """Run the addon by handling the current action."""
        # Parse query parameters
        params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
        action = params.get("action")
        
        if action == "directos":
            self.show_directos()
        # elif action == "directos_2_(lista_propia)":
        #     self.show_directos2()
        elif action == "obtener_series_y_pelis":
            self.download_shows_movies()
        elif action == "cine":  
            pagina = int(params.get("pagina", 1))  
            self.mostrar_pelis(pagina)
        elif action == "series":  
            pagina = int(params.get("pagina", 1))  
            self.mostrar_series(pagina)
        elif action == 'mostrar_episodios':
            serieID = params.get('serieID')
            url_imagen = params.get('imagen')  # Obtener la imagen de la serie
            self.mostrar_episodios(serieID, url_imagen)
        elif action == 'buscar_titulo_peli':
            self.buscar_titulo_peli()
        elif action == 'buscar_titulo_serie':
            self.buscar_titulo_serie()
        elif action == "tdt":
            self.mostrar_canales_tdt()
        elif action == "canales":
            self.show_canales()
        # elif action == "elegir_canales_opcion_1":
        #     self.update_list()
        #     xbmcgui.Dialog().notification("Info", "Lista actualizada exitosamente.")
        # elif action == "elegir_canales_opcion_2_(por_defecto)":
        #     self.update_list2()
        #     xbmcgui.Dialog().notification("Info", "Lista actualizada exitosamente.")
        # elif action == "elegir_canales_opcion_3":
        #     self.update_list3()
        #     xbmcgui.Dialog().notification("Info", "Lista actualizada exitosamente.")
        # elif action == "elegir_canales_opcion_4":
        #     self.update_list4()
        #     xbmcgui.Dialog().notification("Info", "Lista actualizada exitosamente.")
        # elif action == "elegir_canales_opcion_5":
        #     self.update_list5()
        #     xbmcgui.Dialog().notification("Info", "Lista actualizada exitosamente.")
        # elif action == "elegir_canales_opcion_6":
        #     self.update_list6()
        #     xbmcgui.Dialog().notification("Info", "Lista actualizada exitosamente.")
        else:
            self.show_main_menu()
            

def main():
    addon = KodiAddonWrapper()
    addon.run()


if __name__ == "__main__":
    main()
