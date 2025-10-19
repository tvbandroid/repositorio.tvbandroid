import requests
import xbmcgui
import os


url = 'https://dl.dropbox.com/scl/fi/wjwbd5l793qb1xpvim75l/templ?rlkey=xrcaq04qc10ukaqfmrv269bvu&st=2berpfjx&dl=0'

BD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templ.db")

def mostrar_notificacion(titulo, mensaje, duracion=3000):
    xbmcgui.Dialog().notification(titulo, mensaje, time=duracion, sound=False)

def download_db():
    mostrar_notificacion("Descargando base de datos...", f"Por favor espere", 90000)
    # Realizamos la solicitud GET para descargar el archivo
    response = requests.get(url)

    # Comprobamos si la descarga fue exitosa
    if response.status_code == 200:
        # Nombre de archivo a guardar (añadiendo .bd al final)
        total_size = int(response.headers.get('Content-Length', 0))
        file_name = BD_PATH
        
    # Usar sys.stdout para imprimir la barra de progreso en la misma línea
        with open(file_name, 'wb') as file:
            downloaded_size = 0
            for data in response.iter_content(chunk_size=1024):
                file.write(data)  # Guardamos el bloque
                downloaded_size += len(data)  # Incrementamos el tamaño descargado
                
                # Calculamos el porcentaje
                percent = (downloaded_size / total_size) * 100
                
                # Imprimimos la barra de progreso
                
        mostrar_notificacion("Base de datos descargada", f"Completado", 3000)
        consultar_tablas()
    else:
        mostrar_notificacion(f"Error al descargar el archivo. Código de estado: {response.status_code}")


def consultar_tablas():
    import sqlite3
    if os.path.exists(BD_PATH):
        try:
            # Conexión a la base de datos
            conn = sqlite3.connect(BD_PATH)
            cursor = conn.cursor()
            
            # Consulta de cantidad de series
            cursor.execute("SELECT COUNT(*) FROM series")
            total_series = cursor.fetchone()[0]
            
            # Consulta de cantidad de películas
            cursor.execute("SELECT COUNT(*) FROM peliculas")
            total_peliculas = cursor.fetchone()[0]

            total_series_formateado = "{:,}".format(total_series).replace(",", ".")
            total_peliculas_formateado = "{:,}".format(total_peliculas).replace(",", ".")
            
            # Mostrar los resultados en notificaciones
            mostrar_notificacion("Completado", f"Series: {total_series_formateado}, Películas: {total_peliculas_formateado}", 5000)
            
            # Cerrar conexión
            conn.close()
        except sqlite3.Error as e:
            mostrar_notificacion("Error al consultar la base de datos", str(e), 5000)
    else:
        mostrar_notificacion("Base de datos no encontrada", "Descárguela primero", 5000)

       
        