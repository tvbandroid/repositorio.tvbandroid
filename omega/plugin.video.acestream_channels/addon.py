import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import sys
import os
import urllib.request
import zipfile
import json
import re 
from urllib.parse import urlencode, parse_qsl, urljoin
import xbmcvfs

# Configuración para la gestión de dependencias
LIBRARIES_ZIP_URL = "https://github.com/Gunter257/repoachannels/raw/refs/heads/main/bibliotecas.zip"

ADDON = xbmcaddon.Addon()
# Define PROFILE_PATH para que todas las rutas persistentes usen este base
PROFILE_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))

try:
    ADDON.setSetting('addon_initialized_test', 'true')
    xbmc.log("[Acestream Channels] INFO: Setting 'addon_initialized_test' saved.", xbmc.LOGINFO)
    xbmc.sleep(1000)
    xbmc.log("[Acestream Channels] INFO: Sleep finished after setting save.", xbmc.LOGINFO)
except Exception as e:
    xbmc.log(f"[Acestream Channels] ERROR: Failed to save initial setting with sleep: {e}", xbmc.LOGERROR)

# La ruta del archivo ZIP descargado se mueve al perfil
LIBRARIES_ZIP_PATH = os.path.join(PROFILE_PATH, 'bibliotecas.zip') 
LIBRARIES_PATH = os.path.join(PROFILE_PATH, 'lib') 

addon_handle = int(sys.argv[1])
BASE_URL = sys.argv[0]

addon_path = ADDON.getAddonInfo('path')
RESOURCES_PATH = os.path.join(addon_path, 'resources')

COLOR_ORANGE = "FF00A5FF"
COLOR_RED = "FFFF0000"
COLOR_CYAN = "FF00FFFF"
COLOR_BLUE = "FF0000FF"
COLOR_GREEN = "FF00FF00"
COLOR_YELLOW = "FFFFFF00"
COLOR_WHITE = "FFFFFFFF"

COLOR_TIME = "FF87CEEB"
COLOR_SPORT_CATEGORY = "FF32CD32"
COLOR_EVENT_DETAILS = "FFFFFFFF"

SCRAPING_URL = "https://www.socialcreator.com/xupimarc2/?s=289267"

# --- Configuración para la agenda (Con URL de respaldo) ---
AGENDA_URLS = [
    "https://fr.4everproxy.com/direct/aHR0cHM6Ly9jaXJpYWNvLWxpYXJ0LnZlcmNlbC5hcHAv",
    "https://eventos-uvl7.vercel.app/" 
]

CHANGELOG = {
    "1.2.3": [
        "Añadida una URL de respaldo para la Agenda en caso de que la URL principal no funcione.",
        "Mejoras en el manejo de errores de conexión para la sección Agenda.",
	"Sección de ajustes configurada con opción de reproductor externo sin HOURS.",
    ],
}

def check_and_install_libraries():
    if not os.path.exists(LIBRARIES_PATH):
        xbmc.log("[Acestream Channels] INFO: Library folder not found. Starting download...", xbmc.LOGINFO)
        xbmcgui.Dialog().notification("Descargando...", "Descargando librerías necesarias. Por favor, espere...", xbmcgui.NOTIFICATION_INFO)
        try:
            os.makedirs(LIBRARIES_PATH)
            urllib.request.urlretrieve(LIBRARIES_ZIP_URL, LIBRARIES_ZIP_PATH)
            
            with zipfile.ZipFile(LIBRARIES_ZIP_PATH, 'r') as zip_ref:
                zip_ref.extractall(LIBRARIES_PATH)
            
            os.remove(LIBRARIES_ZIP_PATH)
            xbmc.log("[Acestream Channels] INFO: Librerías instaladas con éxito.", xbmc.LOGINFO)
            xbmcgui.Dialog().notification("¡Listo!", "Librerías instaladas con éxito.", xbmcgui.NOTIFICATION_INFO)
        except Exception as e:
            xbmc.log(f"[Acestream Channels] ERROR: Failed to download and extract libraries: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification("Error", f"Fallo al instalar librerías: {e}", xbmc.NOTIFICATION_ERROR)
            return False
    return True

if check_and_install_libraries():
    sys.path.insert(0, LIBRARIES_PATH)
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as e:
        xbmcgui.Dialog().notification("Error", f"No se pudieron importar los módulos: {e}", xbmc.NOTIFICATION_ERROR)
        xbmc.log(f"[Acestream Channels] ERROR: Failed to import modules: {e}", xbmc.LOGERROR)
        sys.exit()
else:
    xbmc.log("[Acestream Channels] ERROR: Failed to install libraries, exiting.", xbmc.LOGERROR)
    sys.exit()

def version_to_tuple(version_string):
    try:
        return tuple(map(int, version_string.split('.')))
    except ValueError:
        xbmc.log(f"[Acestream Channels] WARNING: Cadena de versión malformada detectada: {version_string}", xbmc.LOGWARNING)
        return (0, 0, 0)

def check_for_update_and_show_changelog():
    show_changelog = ADDON.getSettingBool('show_changelog_on_update')
    current_version = ADDON.getAddonInfo('version')
    # Corregido: Usa el ID de configuración correcto que coincide con settings.xml
    last_shown_version = ADDON.getSetting('last_changelog_version')
    xbmc.log(f"[Acestream Channels] DEBUG: Versión actual del Addon: {current_version}", xbmc.LOGDEBUG)
    xbmc.log(f"[Acestream Channels] DEBUG: Última versión del Changelog mostrada: {last_shown_version}", xbmc.LOGDEBUG)

    if not last_shown_version:
        last_shown_version = "0.0.0"

    if show_changelog and version_to_tuple(current_version) > version_to_tuple(last_shown_version):
        xbmc.log("[Acestream Channels] DEBUG: Nueva versión detectada. Mostrando registro de cambios.", xbmc.LOGDEBUG)
        changelog_message = f"[COLOR {COLOR_RED}][B]¡El Addon de Canales se ha actualizado![/B][/COLOR]\n\n"
        versions_to_display = []
        for version_str, changes in CHANGELOG.items():
            if version_to_tuple(version_str) > version_to_tuple(last_shown_version) and \
               version_to_tuple(version_str) <= version_to_tuple(current_version):
                versions_to_display.append((version_to_tuple(version_str), version_str, changes))
        
        versions_to_display.sort()

        if not versions_to_display:
            changelog_message += f"[COLOR {COLOR_YELLOW}]No hay cambios específicos documentados para esta actualización.[/COLOR]"
        else:
            for _, version_str, changes in versions_to_display:
                changelog_message += f"[COLOR {COLOR_BLUE}][B]Versión {version_str}:[/B][/COLOR]\n"
                for change in changes:
                    if "mejoras" in change.lower() or "optimizaciones" in change.lower():
                        changelog_message += f"- [COLOR {COLOR_GREEN}]{change}[/COLOR]\n"
                    elif "errores" in change.lower() or "ajustes" in change.lower():
                        changelog_message += f"- [COLOR {COLOR_ORANGE}]{change}[/COLOR]\n"
                    else:
                        changelog_message += f"- [COLOR {COLOR_WHITE}]{change}[/COLOR]\n"
                changelog_message += "\n"
        
        xbmcgui.Dialog().textviewer(f"[COLOR {COLOR_RED}]Novedades del Addon de Canales[/COLOR]", changelog_message)
        # Corregido: Usa el ID de configuración correcto que coincide con settings.xml
        ADDON.setSetting('last_changelog_version', current_version)
        xbmc.log(f"[Acestream Channels] DEBUG: 'last_changelog_version' actualizada a: {current_version}", xbmc.LOGDEBUG)
    else:
        xbmc.log("[Acestream Channels] DEBUG: El Addon está actualizado o el registro de cambios ya se mostró.", xbmc.LOGDEBUG)


def clean_text_for_display(text):
    if not isinstance(text, str):
        return ""
    text = text.replace('\xa0', ' ').replace('\u200b', '').replace('\uFEFF', '')
    cleaned_text = re.sub(r'[^\w\s.,:;\'"!?¡¿ÁÉÍÓÚÜÑáéíóúüñ\(\)\[\]\{\}\-\+\=\*\/\&\#\@\$\%\^]', '', text)
    return cleaned_text.strip()

def build_url(query):
    return BASE_URL + '?' + urlencode(query)

def scrape_channels_from_url_new(url):
    try:
        try:
            timeout = int(ADDON.getSetting('scraping_timeout'))
        except (ValueError, TypeError):
            timeout = 10
            xbmc.log("[Acestream Channels] WARNING: No se pudo leer el 'scraping_timeout'. Usando valor por defecto.", xbmc.LOGWARNING)

        xbmc.log(f"[Acestream Channels] DEBUG: Usando timeout de {timeout} segundos para el raspado.", xbmc.LOGDEBUG)
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        categorized_channels = {}
        current_category = None
        channel_name_counts = {}

        tbody = soup.find('tbody')
        if not tbody:
            xbmc.log(f"[Acestream Channels] ERROR: No se encontró el elemento <tbody> en {url}", xbmc.LOGERROR)
            return {}

        rows = tbody.find_all('tr')
        
        start_processing = False
        stop_processing_after_others = False 

        for row in rows:
            if stop_processing_after_others: 
                break

            td_header = row.find('td', {'colspan': '7'})
            if td_header:
                category_span = td_header.find('span', style=lambda value: value and 'background-color' in value)
                if category_span:
                    category_name = category_span.get_text(strip=True).replace('&nbsp;', ' ').strip()
                    
                    if category_name == "M+ LIGA":
                        start_processing = True
                    
                    if start_processing:
                        current_category = category_name
                        if current_category not in categorized_channels:
                            categorized_channels[current_category] = []
                            channel_name_counts = {}
                        xbmc.log(f"[Acestream Channels] DEBUG: Found category header: {current_category}", xbmc.LOGDEBUG)
                    
                    if category_name == "OTROS CANALES":
                        stop_processing_after_others = True

            if start_processing and current_category:
                acestream_links = row.find_all('a', href=lambda href: href and href.startswith('acestream://'))
                
                for link in acestream_links:
                    channel_url = link.get('href', '').strip()
                    acestream_id = channel_url.replace("acestream://", "")
                    
                    channel_name = ""
                    channel_icon_url = ""

                    img_tag = link.find('img')
                    if img_tag:
                        if img_tag.has_attr('alt'):
                            channel_name = img_tag['alt'].strip()
                        if img_tag.has_attr('src'):
                            channel_icon_url = urljoin(url, img_tag['src'])
                    
                    if not channel_name:
                        channel_name_element = link.find(['b', 'span']) 
                        if channel_name_element:
                            channel_name = channel_name_element.get_text(strip=True)
                        else:
                            channel_name = link.get_text(strip=True)
                    
                    display_channel_name_base = channel_name.strip()
                    
                    option_part = ""
                    if display_channel_name_base in channel_name_counts:
                        channel_name_counts[display_channel_name_base] += 1
                        option_part = f" | [COLOR {COLOR_CYAN}]OPCIÓN {channel_name_counts[display_channel_name_base]}[/COLOR]"
                    else:
                        channel_name_counts[display_channel_name_base] = 1
                    
                    status_part = ""
                    color_element = link.find(['span', 'font'], style=True) or link.find(['span', 'font'], color=True) or link 
                    
                    if color_element:
                        color_style = color_element.get('style', '')
                        font_color = color_element.get('color')

                        if 'color:#ff8c00;' in color_style or font_color == '#ff8c00':
                            status_part = f" | [COLOR {COLOR_ORANGE}]Canal Eventual[/COLOR]"
                        elif 'color:#ff0000;' in color_style or font_color == '#ff0000':
                            status_part = f" | [COLOR {COLOR_RED}]Canal Caído[/COLOR]"

                    full_channel_name = f"{display_channel_name_base}{option_part}{status_part}"
                    
                    if current_category:
                        if not any(c["url"] == acestream_id for c in categorized_channels[current_category]):
                            categorized_channels[current_category].append({
                                "name": full_channel_name, 
                                "url": acestream_id,
                                "icon": channel_icon_url 
                            })
                            xbmc.log(f"[Acestream Channels] DEBUG: Added channel '{full_channel_name}' with icon '{channel_icon_url}' to category '{current_category}'", xbmc.LOGDEBUG)
                
        xbmc.log(f"[Acestream Channels] DEBUG: Scraped {sum(len(v) for v in categorized_channels.values())} channels across {len(categorized_channels)} categories from {url}", xbmc.LOGDEBUG)
        return categorized_channels
    except requests.exceptions.Timeout:
        xbmcgui.Dialog().notification("Error de Conexión", "La solicitud de la página ha excedido el tiempo de espera.", xbmcgui.NOTIFICATION_ERROR)
        xbmc.log(f"[Acestream Channels] ERROR: Timeout accessing URL: {url}", xbmc.LOGERROR)
        return {}
    except requests.exceptions.RequestException as e:
        import traceback
        xbmcgui.Dialog().notification("Error de Red", f"No se pudo acceder a la URL de raspado: {str(e)}", xbmc.NOTIFICATION_ERROR)
        xbmc.log(f"[Acestream Channels] ERROR: Network error during scraping from {url}: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)
        return {}
    except Exception as e:
        import traceback
        xbmcgui.Dialog().notification("Error de Scrapeo", f"Error al procesar la página: {str(e)}", xbmc.NOTIFICATION_ERROR)
        xbmc.log(f"[Acestream Channels] ERROR: Error during scraping from {url}: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)
        return {}

_cached_categorized_channels = None

def get_categorized_channels_cached():
    global _cached_categorized_channels
    if _cached_categorized_channels is None:
        xbmc.log("[Acestream Channels] DEBUG: Scraping channels for the first time or cache invalid.", xbmc.LOGDEBUG)
        _cached_categorized_channels = scrape_channels_from_url_new(SCRAPING_URL)
    else:
        xbmc.log("[Acestream Channels] DEBUG: Using cached scraped channels.", xbmc.LOGDEBUG)
    return _cached_categorized_channels

def list_categories():
    check_for_update_and_show_changelog()

    agenda_list_item = xbmcgui.ListItem(label="AGENDA")
    agenda_list_item.setArt({"icon": f"{RESOURCES_PATH}/agenda.png", "thumb": f"{RESOURCES_PATH}/agenda.png"})
    agenda_url = build_url({"action": "list_channels", "category": "AGENDA"})
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=agenda_url, listitem=agenda_list_item, isFolder=True)

    dynamic_categories = get_categorized_channels_cached()
    sorted_category_names = sorted(dynamic_categories.keys())

    for category_name in sorted_category_names:
        icon_path = f"{RESOURCES_PATH}/default.png"
        channels_in_category = dynamic_categories.get(category_name)
        
        if channels_in_category:
            selected_channel_index = 0
            if category_name in ["M+ VAMOS", "M+ ELLAS"]: 
                selected_channel_index = 5
            elif category_name in ["EUROSPORT", "FÓRMULA E", "DEPORTES M+"]:
                selected_channel_index = 1
            
            if len(channels_in_category) > selected_channel_index:
                selected_channel = channels_in_category[selected_channel_index]
                if selected_channel.get("icon"):
                    icon_path = selected_channel["icon"]
                else:
                    xbmc.log(f"[Acestream Channels] WARNING: Icono no encontrado para el canal {selected_channel_index+1} en la categoría '{category_name}'. Usando icono por defecto.", xbmc.LOGWARNING)
            else:
                xbmc.log(f"[Acestream Channels] WARNING: No hay suficientes canales en la categoría '{category_name}' para el índice de icono deseado {selected_channel_index}. Usando icono por defecto.", xbmc.LOGWARNING)

        list_item = xbmcgui.ListItem(label=category_name)
        list_item.setArt({"icon": icon_path, "thumb": icon_path})
        url = build_url({"action": "list_channels", "category": category_name})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=list_item, isFolder=True)
    xbmcplugin.endOfDirectory(addon_handle)

def list_channels(category):
    if category == "AGENDA":
        list_agenda_events()
        return

    all_categorized_channels = get_categorized_channels_cached()
    
    channels_to_display = all_categorized_channels.get(category, [])

    if not channels_to_display:
        xbmcgui.Dialog().notification("Canales", f"No se encontraron canales para la categoría: {category}", xbmcgui.NOTIFICATION_INFO)
        list_item = xbmcgui.ListItem(label="No se encontraron canales")
        xbmcplugin.addDirectoryItem(handle=addon_handle, url="", listitem=list_item, isFolder=False)
        
    for channel in channels_to_display:
        list_item = xbmcgui.ListItem(label=channel["name"])
        if channel.get("icon"):
            list_item.setArt({"icon": channel["icon"], "thumb": channel["icon"]})
        else:
            list_item.setArt({"icon": f"{RESOURCES_PATH}/default.png", "thumb": f"{RESOURCES_PATH}/default.png"})
        
        url = build_url({"action": "play_acestream", "url": channel["url"]})
        list_item.setInfo("video", {"title": channel["name"]})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=list_item, isFolder=False)
    xbmcplugin.endOfDirectory(addon_handle)

def raspar_desde_url_respaldo(url):
    eventos = []
    try:
        try:
            timeout = int(ADDON.getSetting('scraping_timeout'))
        except (ValueError, TypeError):
            timeout = 10
        
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        tabla_eventos = soup.find('table')
        if not tabla_eventos:
            xbmc.log(f"[Acestream Channels] ERROR: No se encontró la tabla de eventos en la agenda desde {url}", xbmc.LOGERROR)
            return eventos

        for fila in tabla_eventos.find_all('tr')[1:]:
            columnas = fila.find_all('td')
            if len(columnas) >= 6:
                hora = columnas[1].text.strip()
                deporte = columnas[2].text.strip()
                competicion = columnas[3].text.strip()
                evento = columnas[4].text.strip()
                
                canales_html = columnas[5].find_all('a')
                canales = []
                for canal in canales_html:
                    nombre = canal.text.strip()
                    url_id = canal.get('href').replace("acestream://", "")
                    canales.append({"name": nombre, "url": url_id})
                
                if canales:
                    eventos.append({
                        "hora": hora,
                        "categoria": deporte,
                        "evento": f"{competicion} - {evento}", 
                        "enlaces": canales
                    })
        xbmc.log(f"[Acestream Channels] DEBUG: Se encontraron {len(eventos)} eventos en la agenda desde {url} (raspado de respaldo)", xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(f"[Acestream Channels] ERROR: Error al procesar la URL de respaldo {url}: {e}", xbmc.LOGERROR)

    return eventos

def obtener_eventos_desde_html():
    try:
        url_principal = AGENDA_URLS[0]
        try:
            timeout = int(ADDON.getSetting('scraping_timeout'))
        except (ValueError, TypeError):
            timeout = 10
        
        xbmc.log(f"[Acestream Channels] DEBUG: Usando timeout de {timeout} segundos para la agenda desde {url_principal}.", xbmc.LOGDEBUG)
        response = requests.get(url_principal, timeout=timeout)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        eventos = []
        tabla_eventos = soup.find('table')
        
        if not tabla_eventos:
            xbmc.log(f"[Acestream Channels] ERROR: No se encontró la tabla de eventos en la agenda desde {url_principal}", xbmc.LOGERROR)
        else:
            for fila in tabla_eventos.find_all('tr')[1:]:
                columnas = fila.find_all('td')
                if len(columnas) >= 5:
                    hora = columnas[0].text.strip()
                    deporte = columnas[1].text.strip()
                    competicion = columnas[2].text.strip()
                    evento = columnas[3].text.strip()
                    canales_html = columnas[4].find_all('a')
                    canales = []
                    for canal in canales_html:
                        nombre = canal.text.strip()
                        url_id = canal.get('href').replace("acestream://", "")
                        canales.append({"name": nombre, "url": url_id})
                    if canales:
                        eventos.append({
                            "hora": hora,
                            "categoria": deporte,
                            "evento": evento,
                            "enlaces": canales
                        })
            xbmc.log(f"[Acestream Channels] DEBUG: Se encontraron {len(eventos)} eventos en la agenda desde {url_principal}", xbmc.LOGDEBUG)
        if eventos:
            return eventos
    except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
        xbmc.log(f"[Acestream Channels] ERROR: Fallo al acceder a la URL principal {url_principal}: {e}", xbmc.LOGERROR)
    except Exception as e:
        xbmc.log(f"[Acestream Channels] ERROR: Error al procesar la URL principal {url_principal}: {e}", xbmc.LOGERROR)

    try:
        url_respaldo = AGENDA_URLS[1]
        xbmc.log(f"[Acestream Channels] DEBUG: Intentando con la URL de respaldo: {url_respaldo}.", xbmc.LOGDEBUG)
        eventos = raspar_desde_url_respaldo(url_respaldo)
        if eventos:
            return eventos
    except Exception as e:
        xbmc.log(f"[Acestream Channels] ERROR: Fallo al acceder a la URL de respaldo {url_respaldo}: {e}", xbmc.LOGERROR)

    xbmcgui.Dialog().notification("Error AGENDA", "No se pudo acceder a ninguna URL de la agenda.", xbmcgui.NOTIFICATION_ERROR)
    return []

def list_agenda_events():
    eventos = obtener_eventos_desde_html()
    if not eventos:
        xbmcgui.Dialog().notification("Agenda", "No hay eventos disponibles", xbmcgui.NOTIFICATION_INFO)
        list_item = xbmcgui.ListItem(label="No hay eventos disponibles")
        xbmcplugin.addDirectoryItem(handle=addon_handle, url="", listitem=list_item, isFolder=False)
        xbmcplugin.endOfDirectory(addon_handle)
        return
    
    problematic_symbols_map = {
        '⚽': 'Fútbol',
        '🏀': 'Baloncesto',
        '🎾': 'Tenis',
        '🏈': 'Fútbol Americano',
        '🏉': 'Rugby',
        '⚾': 'Béisbol',
        '🏐': 'Voleibol',
        '🏎️': 'Fórmula 1',
        '🏁': 'Carreras',
        '🥊': 'Boxeo',
        'MMA': 'MMA',
        '🏆': '',
    }

    for evento in eventos:
        hora = clean_text_for_display(evento['hora'])
        categoria = clean_text_for_display(evento['categoria'])
        evento_detalles = clean_text_for_display(evento['evento'])

        for symbol, replacement in problematic_symbols_map.items():
            categoria = categoria.replace(symbol, replacement)
            evento_detalles = evento_detalles.replace(symbol, replacement)
        
        colored_hora = f"[COLOR {COLOR_TIME}]{hora}[/COLOR]"
        colored_categoria = f"[COLOR {COLOR_SPORT_CATEGORY}]{categoria}[/COLOR]"
        colored_evento_detalles = f"[COLOR {COLOR_EVENT_DETAILS}]{evento_detalles}[/COLOR]"

        titulo_display = f"{colored_hora} | {colored_categoria}: {colored_evento_detalles}"
        
        list_item = xbmcgui.ListItem(label=titulo_display)
        list_item.setArt({"icon": f"{RESOURCES_PATH}/agenda.png", "thumb": f"{RESOURCES_PATH}/agenda.png"})

        url = build_url({"action": "mostrar_enlaces_evento", "enlaces": json.dumps(evento["enlaces"])})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=list_item, isFolder=True)
    xbmcplugin.endOfDirectory(addon_handle)

def mostrar_enlaces_evento(enlaces):
    enlaces = json.loads(enlaces)
    
    base_channel_name_counts = {}
    for enlace in enlaces:
        cleaned_name = clean_text_for_display(enlace["name"])
        base_channel_name_counts[cleaned_name] = base_channel_name_counts.get(cleaned_name, 0) + 1

    current_counts_for_options = {}

    for enlace in enlaces:
        original_cleaned_name = clean_text_for_display(enlace["name"])
        display_name = original_cleaned_name

        if base_channel_name_counts[original_cleaned_name] > 1:
            current_counts_for_options[original_cleaned_name] = current_counts_for_options.get(original_cleaned_name, 0) + 1
            option_part = f" | [COLOR {COLOR_CYAN}]OPCIÓN {current_counts_for_options[original_cleaned_name]}[/COLOR]"
            display_name = f"{original_cleaned_name}{option_part}"
        
        list_item = xbmcgui.ListItem(label=display_name)
        list_item.setArt({"icon": f"{RESOURCES_PATH}/default.png", "thumb": f"{RESOURCES_PATH}/default.png"}) 
        
        url = build_url({"action": "play_acestream", "url": enlace["url"]})
        list_item.setInfo("video", {"title": display_name})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=list_item, isFolder=False)
    xbmcplugin.endOfDirectory(addon_handle)

def play_html5(url):
    try:
        xbmc.Player().play(url)
    except Exception as e:
        xbmcgui.Dialog().notification("Error", str(e), xbmc.NOTIFICATION_ERROR)

def play_acestream(url_id):
    try:
        use_external = ADDON.getSettingBool('use_external_player')
        
        if use_external:
            xbmc.log("[Acestream Channels] INFO: Usando reproductor externo para AceStream (API HTTP).", xbmc.LOGINFO)
            # Usamos la API HTTP del motor de AceStream.
            strm_content = f"http://127.0.0.1:6878/ace/getstream?id={url_id}"
            strm_path = os.path.join(PROFILE_PATH, 'temp_acestream.strm')
            
            with open(strm_path, 'w') as f:
                f.write(strm_content)
            
            xbmc.Player().play(strm_path)
            
        else:
            xbmc.log("[Acestream Channels] INFO: Usando reproductor interno (Horus) para AceStream.", xbmc.LOGINFO)
            horus_url = f"plugin://script.module.horus/?action=play&id={url_id}"
            xbmc.Player().play(horus_url)
            
    except Exception as e:
        xbmc.log(f"[Acestream Channels] ERROR: Error al reproducir AceStream: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Error", f"Error al reproducir: {e}", xbmc.NOTIFICATION_ERROR)

if __name__ == '__main__':
    args = dict(parse_qsl(sys.argv[2][1:]))
    action = args.get("action")
    if action == "list_channels":
        category = args.get("category")
        if category == "AGENDA":
            list_agenda_events()
        else:
            list_channels(category)
    elif action == "mostrar_enlaces_evento":
        mostrar_enlaces_evento(args["enlaces"])
    elif action == "play_html5":
        play_html5(args["url"])
    elif action == "play_acestream":
        play_acestream(args["url"]) 
    else:
        list_categories()