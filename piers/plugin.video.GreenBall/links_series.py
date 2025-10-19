
import sqlite3
import os
from datetime import datetime  # Importa el módulo datetime

BD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templ.db")

def obtener_series(pagina=1):
    """Obtiene las series de la base de datos de 30 en 30 según la página solicitada, ordenadas por los episodios más recientes."""
    
    # Definir el número de ítems por página
    items_por_pagina = 30
    
    # Calcular el OFFSET para la consulta
    offset = (pagina - 1) * items_por_pagina
    
    # Conectar a la base de datos
    conn = sqlite3.connect(BD_PATH)
    cursor = conn.cursor()
    
    # Ejecutar la consulta para obtener las series con el OFFSET, LIMIT, y ordenadas por la fecha más reciente de los episodios
    cursor.execute("""
        SELECT s.id_one, s.serieID, s.seriename, s.url_serie, s.img_serie, s.descripcion
        FROM series s
        JOIN episodios e ON s.serieID = e.serieID
        GROUP BY s.id_one
        ORDER BY MAX(e.fecha) DESC
        LIMIT ? OFFSET ?
    """, (items_por_pagina, offset))
    
    series_registros = cursor.fetchall()
    
    # Crear una lista para las series
    series = []
    for serie in series_registros:
        id_one, serieID, seriename, url_serie, img_serie, descripcion = serie
        series.append({
            'titulo': seriename,
            'imagen': img_serie,
            'serieID': serieID,
            'descripcion': descripcion,
            'url': url_serie
        })
    
    # Cerrar la conexión a la base de datos
    conn.close()
    
    return series

def buscar_series(searchserie):
    """Obtiene las series de la base de datos de 30 en 30 según la página solicitada, ordenadas por los episodios más recientes."""
        
    # Conectar a la base de datos
    conn = sqlite3.connect(BD_PATH)
    cursor = conn.cursor()
    
    # Ejecutar la consulta para obtener las series con el OFFSET, LIMIT, y ordenadas por la fecha más reciente de los episodios
    cursor.execute("""
        SELECT s.id_one, s.serieID, s.seriename, s.url_serie, s.img_serie, s.descripcion
        FROM series s
        WHERE s.seriename LIKE ?
    """, ('%' + searchserie + '%',))
    
    series_registros = cursor.fetchall()
    
    # Crear una lista para las series
    series = []
    for serie in series_registros:
        id_one, serieID, seriename, url_serie, img_serie, descripcion = serie
        series.append({
            'titulo': seriename,
            'imagen': img_serie,
            'serieID': serieID,
            'descripcion': descripcion,
            'url': url_serie
        })
    
    # Cerrar la conexión a la base de datos
    conn.close()
    
    return series

def obtener_episodios(serieID):
    """Obtiene todos los episodios de una serie específica de la base de datos."""
    
    # Conectar a la base de datos
    conn = sqlite3.connect(BD_PATH)
    cursor = conn.cursor()
    
    # Ejecutar la consulta para obtener todos los episodios de la serie
    cursor.execute("""
        SELECT capitulo, 
        link_capitulo, 
        strftime('%d-%m-%Y', fecha) AS fecha_formateada
        FROM episodios
        WHERE serieID = ?
        ORDER BY capitulo ASC
    """, (serieID,))
    
    episodios_registros = cursor.fetchall()
    
    # Crear una lista para los episodios
    episodios = []
    for episodio in episodios_registros:
        capitulo, link_capitulo, fecha = episodio
        
        # Asegurar que los enlaces tengan el esquema completo
        if link_capitulo.startswith("//"):
            link_capitulo = f"https:{link_capitulo}"
        episodios.append({
            'titulo': capitulo,
            'stream_url': link_capitulo,
            'fecha': f"Subido el {fecha}"  # Puedes ajustar esta descripción según lo que desees mostrar.
        })
    
    # Cerrar la conexión a la base de datos
    conn.close()
    
    return episodios

def obtener_pelis(pagina=1):
    """Obtiene las películas de la base de datos con paginación."""
    
    # Definir el número de ítems por página
    items_por_pagina = 30
    
    # Calcular el OFFSET para la consulta
    offset = (pagina - 1) * items_por_pagina
    
    # Conectar a la base de datos
    conn = sqlite3.connect(BD_PATH)
    cursor = conn.cursor()
    
    # Ejecutar la consulta para obtener las películas con LIMIT y OFFSET
    cursor.execute("""
        SELECT peliID, peliname, urlpeli, img_peli, descripcion
        FROM peliculas
        ORDER BY fecha DESC
        LIMIT ? OFFSET ?
    """, (items_por_pagina, offset))  # Pasa items_por_pagina y offset

    peliculas_registros = cursor.fetchall()
    
    # Crear una lista para las películas
    peliculas = []
    for peli in peliculas_registros:
        peliID, peliname, urlpeli, img_peli, descripcion = peli
        peliculas.append({
            'titulo': peliname,
            'imagen': img_peli,
            'peliID': peliID,
            'descripcion': descripcion,
            'url': urlpeli
        })
    
    # Cerrar la conexión a la base de datos
    conn.close()
    
    return peliculas

def buscar_peliculas(searchpeli):
    """Obtiene las series de la base de datos de 30 en 30 según la página solicitada, ordenadas por los episodios más recientes."""
        
    # Conectar a la base de datos
    conn = sqlite3.connect(BD_PATH)
    cursor = conn.cursor()
    
    # Ejecutar la consulta para obtener las series con el OFFSET, LIMIT, y ordenadas por la fecha más reciente de los episodios
    cursor.execute("""
        SELECT peliID, peliname, urlpeli, img_peli, descripcion 
        FROM peliculas
        WHERE peliname LIKE ?
    """, ('%' + searchpeli + '%',))
    
    peliculas_registros = cursor.fetchall()
    
    # Crear una lista para las películas
    peliculas = []
    for peli in peliculas_registros:
        peliID, peliname, urlpeli, img_peli, descripcion = peli
        peliculas.append({
            'titulo': peliname,
            'imagen': img_peli,
            'peliID': peliID,
            'descripcion': descripcion,
            'url': urlpeli
        })
    
    # Cerrar la conexión a la base de datos
    conn.close()
    
    return peliculas