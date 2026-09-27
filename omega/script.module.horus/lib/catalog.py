# -*- coding: utf-8 -*-
"""The engine's channel catalogue, and AceServe's own list.

The engine publishes its catalogue on /search, with no token and no authentication, and
the official AceStream app and AceServe serve it alike. Some 1800 channels with a name, a
logo, a category, a country, a language and a mark saying whether the link is alive.

Here it is downloaded, normalised and saved. Painting it is channels_ui's business.

A page of 200 channels takes close to a second, so the whole catalogue is about ten
seconds: it is saved on disk and reused. The engine's category= parameter is NEVER used,
because it is case sensitive and the data carry the same category written in several ways
(sport and Sport, tv and TV); grouping locally solves both problems.
"""
import os
import re
import time
import unicodedata

import xbmc

from lib import alternatives
from lib.utils import (data_path, dump_json_file, echar_pestillo, get_setting, hay_pestillo,
                       load_json_file, logger, quitar_pestillo, refrescar_pestillo)
from acestream.server import Server

PAGINA = 200
# Hard cap in case an engine returns endless pages. Today the catalogue is ten.
MAX_PAGINAS = 20
TTL_HORAS_POR_OMISION = 24
# The text search goes against the live engine and hangs off the user typing, so it cannot
# inherit the 10 s timeout: with the engine switched off that would be ten seconds added
# to every search.
BUSQUEDA_TIMEOUT = 4
BUSQUEDA_TOPE = 60

PESTILLO = 'ekhorus.catalog'
FICHERO_CATALOGO = 'catalogo.json'
FICHERO_PLAYLIST = 'playlist.json'

# A category with fewer than this is leftovers, like the 'Chileiptv' the catalogue carries.
MIN_POR_CATEGORIA = 5

DISPONIBLE = 2
DUDOSO = 1

# Other links kept per channel. Each one that fails costs the whole time limit of the settings
# before the next is tried, so more than this is waiting nobody would sit through.
ALTERNATIVOS_MAX = 3

# Key of the drawer for those that declare no category, country or language. It starts
# with an underscore so it never clashes with a real engine label, and it sorts last.
SIN_DATO = '_sin'

_CATEGORIAS = {
    'sport': 'Deportes', 'tv': 'Televisión', 'movies': 'Cine', 'music': 'Música',
    'news': 'Noticias', 'kids': 'Infantil', 'series': 'Series', 'regional': 'Regional',
    'documentaries': 'Documentales', 'educational': 'Educativos',
    'entertaining': 'Entretenimiento', 'informational': 'Informativos',
    'religion': 'Religión', 'fashion': 'Moda', 'ethnic': 'Étnicos',
    'teleshop': 'Teletienda', 'amateur': 'Aficionados', 'webcam': 'Webcams',
    'cyber_games': 'Videojuegos', 'erotic_18_plus': 'Adultos',
    'other_18_plus': 'Adultos (otros)', 'other': 'Otras',
}

_PAISES = {
    'es': 'España', 'int': 'Internacional', 'us': 'Estados Unidos', 'gb': 'Reino Unido',
    'ru': 'Rusia', 'de': 'Alemania', 'pl': 'Polonia', 'tr': 'Turquía', 'fr': 'Francia',
    'it': 'Italia', 'pt': 'Portugal', 'nl': 'Países Bajos', 'be': 'Bélgica',
    'ua': 'Ucrania', 'ro': 'Rumanía', 'gr': 'Grecia', 'ar': 'Argentina',
    'mx': 'México', 'cl': 'Chile', 'co': 'Colombia', 'pe': 'Perú', 'bo': 'Bolivia',
    'cr': 'Costa Rica', 'do': 'República Dominicana', 've': 'Venezuela',
    'br': 'Brasil', 'ca': 'Canadá', 'in': 'India', 'cn': 'China', 'jp': 'Japón',
    'il': 'Israel', 'cz': 'Chequia', 'sk': 'Eslovaquia', 'hu': 'Hungría',
    'bg': 'Bulgaria', 'rs': 'Serbia', 'hr': 'Croacia', 'se': 'Suecia',
    'no': 'Noruega', 'dk': 'Dinamarca', 'fi': 'Finlandia', 'at': 'Austria',
    'ch': 'Suiza', 'ie': 'Irlanda', 'kz': 'Kazajistán', 'az': 'Azerbaiyán',
    'ge': 'Georgia', 'am': 'Armenia', 'by': 'Bielorrusia', 'ee': 'Estonia',
    'lv': 'Letonia', 'lt': 'Lituania', 'si': 'Eslovenia', 'uy': 'Uruguay',
    'py': 'Paraguay', 'ec': 'Ecuador', 'gt': 'Guatemala', 'pa': 'Panamá',
}

_IDIOMAS = {
    'spa': 'Español', 'eng': 'Inglés', 'rus': 'Ruso', 'deu': 'Alemán',
    'fra': 'Francés', 'ita': 'Italiano', 'por': 'Portugués', 'pol': 'Polaco',
    'tur': 'Turco', 'cat': 'Catalán', 'eus': 'Euskera', 'glg': 'Gallego',
    'nld': 'Neerlandés', 'ukr': 'Ucraniano', 'ron': 'Rumano', 'ell': 'Griego',
    'ara': 'Árabe', 'hin': 'Hindi', 'zho': 'Chino', 'jpn': 'Japonés',
    'ces': 'Checo', 'slk': 'Eslovaco', 'bul': 'Búlgaro', 'srp': 'Serbio',
    'hrv': 'Croata', 'hun': 'Húngaro', 'swe': 'Sueco', 'nor': 'Noruego',
    'dan': 'Danés', 'fin': 'Finés', 'kor': 'Coreano', 'vie': 'Vietnamita',
    'tha': 'Tailandés', 'ind': 'Indonesio', 'urd': 'Urdu', 'fas': 'Persa',
    'heb': 'Hebreo', 'hye': 'Armenio', 'aze': 'Azerí', 'kaz': 'Kazajo',
    'tuk': 'Turcomano', 'uzb': 'Uzbeko', 'kat': 'Georgiano', 'lav': 'Letón',
    'lit': 'Lituano', 'est': 'Estonio', 'slv': 'Esloveno', 'mkd': 'Macedonio',
}

# The catalogue uses both sets of language codes at once, so German shows up as deu and as
# ger, and Dutch as nld and as nl. Without this there are duplicate rows.
_ALIAS_IDIOMA = {'ger': 'deu', 'fre': 'fra', 'dut': 'nld', 'nl': 'nld', 'gre': 'ell',
                 'rum': 'ron', 'chi': 'zho', 'cze': 'ces', 'ice': 'isl', 'per': 'fas'}

_RE_GRUPO = re.compile(r'group-title="([^"]*)"', re.I)
_RE_HASH = re.compile(r'[?&](?:infohash|id|content_id)=([0-9a-f]{40})', re.I)


def partir_extinf(linea):
    """(group, name) of an #EXTINF line.

    The name is everything after the first comma that is OUTSIDE quotes. Cutting at the
    first comma outright is no good: there are channels that carry one in the name, like
    'Red Bull TV,Red Bull TV HD'. Nor is it any good to trust that the attributes are well
    formed: the real list carries the odd entry with a browser header slipped inside and
    two group-title in a row."""
    resto = linea.split(':', 1)[1] if ':' in linea else linea
    dentro = False
    corte = -1

    for pos, letra in enumerate(resto):
        if letra == '"':
            dentro = not dentro
        elif letra == ',' and not dentro:
            corte = pos
            break

    if corte < 0:
        return '', ''

    atributos, nombre = resto[:corte], resto[corte + 1:].strip()
    encontrado = _RE_GRUPO.search(atributos)

    return (encontrado.group(1).strip() if encontrado else ''), nombre


def clave(texto):
    """Comparable form of a category, a country or a language.

    The engine's data carry the same label in several ways, so everything is compared in
    lower case and with the separators unified."""
    return re.sub(r'[\s\-]+', '_', str(texto or '').strip().lower())


def sin_tildes(texto):
    descompuesto = unicodedata.normalize('NFKD', str(texto or '').lower())
    return ''.join(c for c in descompuesto if not unicodedata.combining(c))


def es_adulto(etiqueta):
    """Adult categories, in the two forms the two sources use.

    The catalogue calls them erotic_18_plus and other_18_plus; AceServe's pl.m3u groups
    them as 'Erotic 18+'. That is why it goes by shape and not against a closed list."""
    c = clave(etiqueta)

    return ('18_plus' in c or '18+' in c
            or c.startswith(('erotic', 'adult', 'porn', 'xxx')))


_TABLAS = {'categorias': _CATEGORIAS, 'paises': _PAISES, 'idiomas': _IDIOMAS}

SIN_ESPECIFICAR = 'Sin especificar'


def tablas():
    """The three label tables, for whoever has to name facets outside this module."""
    return _TABLAS


def etiqueta(campo, c):
    """Presentable name of a facet key, in Spanish when it is known."""
    if c == SIN_DATO:
        return SIN_ESPECIFICAR

    return _TABLAS.get(campo, dict()).get(c) or c.replace('_', ' ').upper()


# The catalogue's 617 logos all come from here, all over http, and the server answers a
# 301 to https for every one. Asking in https already saves that hop: measured, 0.75 s
# against 0.47 s per image the first time. Only this domain is rewritten, which is the one
# checked to serve TLS; any other is left as it comes.
_HOST_LOGOS = 'http://c1.torrentstream.info/'


def _logo(iconos):
    """First usable logo url, or an empty string.

    Only one channel in three carries a logo."""
    for icono in iconos or []:
        url = icono.get('url') if isinstance(icono, dict) else None
        if not isinstance(url, str):
            continue

        if url.startswith(_HOST_LOGOS):
            return 'https://' + url[len('http://'):]
        if url.startswith(('http://', 'https://')):
            return url

    return ''


def _servibles(items):
    """The group's links worth serving, healthiest first.

    The one the engine reports as available (status 2) goes before the rest and, among
    those, the one with the highest availability. The sort is stable, so on a tie the first
    is the same link max() used to pick back when only one was kept."""
    servibles = [i for i in items or []
                 if isinstance(i, dict) and i.get('infohash') and not i.get('disabled')]

    return sorted(servibles, reverse=True,
                  key=lambda i: (i.get('status') == DISPONIBLE, i.get('availability') or 0))


def normalizar(grupos):
    """The groups /search returns, flattened to one channel per group."""
    canales = list()

    for grupo in grupos or []:
        if not isinstance(grupo, dict):
            continue

        enlaces = _servibles(grupo.get('items'))
        if not enlaces:
            continue

        item = enlaces[0]
        nombre = str(grupo.get('name') or item.get('name') or '').strip()
        if not nombre:
            continue

        canal = {
            'nombre': nombre,
            'infohash': item['infohash'],
            'logo': _logo(grupo.get('icons')),
            'categorias': [clave(c) for c in (item.get('categories') or [])],
            'paises': [clave(p) for p in (item.get('countries') or [])],
            'idiomas': sorted({_ALIAS_IDIOMA.get(clave(i), clave(i))
                               for i in (item.get('languages') or [])}),
            'estado': item.get('status') or 0,
            'disponibilidad': item.get('availability') or 0,
        }

        # The channel's other links, for playback to try when the chosen one does not start.
        # Only when there are any, which in a page of 200 of the real catalogue were 7 channels
        # with a second link and none with a third. Playback reads them from alternatives.py.
        alternativos = list()
        for otro in enlaces[1:]:
            if otro['infohash'] != item['infohash'] and otro['infohash'] not in alternativos:
                alternativos.append(otro['infohash'])
        if alternativos:
            canal['alternativos'] = alternativos[:ALTERNATIVOS_MAX]

        canales.append(canal)

    return canales


def descargar(servidor, progreso=None, pestillo=None):
    """Every page of /search, already normalised.

    Returns (channels, complete). Complete is False when the user cancels or when the page
    cap is reached, and in that case the result must not be saved as good.

    'pestillo' is only passed by whoever holds it: renewing it without holding it would
    create one nobody is going to remove and would block the function for a minute."""
    canales = list()
    vistos = set()
    total = 0

    for pagina in range(MAX_PAGINAS):
        if progreso is not None and progreso.iscanceled():
            return canales, False

        respuesta = servidor.buscar(page=pagina, page_size=PAGINA)
        if not respuesta.success or not isinstance(respuesta.data, dict):
            # Failing on the first page is having no catalogue; failing on the seventh is
            # having seven eighths, which is more than enough to browse.
            logger(f'catalog: pagina {pagina}: {respuesta.message}', 'error')
            return canales, False

        grupos = respuesta.data.get('results') or []
        total = respuesta.data.get('total') or total

        for canal in normalizar(grupos):
            # The same channel can repeat across pages if the catalogue changes while it
            # is being downloaded. The first one wins, which is the best placed.
            if canal['infohash'] not in vistos:
                vistos.add(canal['infohash'])
                canales.append(canal)

        if progreso is not None:
            hecho = int(len(canales) * 100 / total) if total else 0
            progreso.update(min(hecho, 100), f'{len(canales)} de {total or "?"} canales')

        # The latch expires after 60 s, and ten pages against a slow remote engine can go
        # past that and let a second download start on top.
        if pestillo:
            refrescar_pestillo(pestillo)

        if len(grupos) < PAGINA:
            return canales, True

    logger(f'catalog: tope de {MAX_PAGINAS} paginas alcanzado', 'error')
    return canales, False


def _ruta(fichero):
    return os.path.join(data_path, fichero)


def leer(base, fichero=FICHERO_CATALOGO, ttl_horas=None):
    """What is saved for that engine, or None if it is no good.

    The base takes part in the comparison because whoever alternates between a local and a
    remote engine must not see the other one's catalogue."""
    ruta = _ruta(fichero)
    if not os.path.isfile(ruta):
        return None

    try:
        sobre = load_json_file(ruta)
    except OSError as e:
        logger(f'catalog: no se pudo leer {fichero}: {e}', 'error')
        return None

    if not isinstance(sobre, dict) or sobre.get('base') != base:
        return None

    if ttl_horas is None:
        ttl_horas = get_setting('catalogo_ttl_horas', TTL_HORAS_POR_OMISION)

    try:
        ttl_horas = int(ttl_horas)
    except (TypeError, ValueError):
        ttl_horas = TTL_HORAS_POR_OMISION

    # Zero means it never expires, for whoever prefers to refresh by hand.
    if ttl_horas > 0 and time.time() - (sobre.get('guardado') or 0) > ttl_horas * 3600:
        return None

    canales = sobre.get('canales')
    return canales if isinstance(canales, list) and canales else None


def guardar(base, canales, fichero=FICHERO_CATALOGO):
    sobre = {'base': base, 'guardado': time.time(),
             'total': len(canales), 'canales': canales}

    try:
        dump_json_file(sobre, _ruta(fichero), compacto=True)
    except (OSError, ValueError) as e:
        # Being left with no cache is a nuisance, not a failure: it downloads again next.
        logger(f'catalog: no se pudo guardar {fichero}: {e}', 'error')
        return

    # Playback looks up the other links of a channel on every press, so they go to a small
    # file of their own and it never has to read this one.
    if fichero == FICHERO_CATALOGO:
        alternatives.guardar(base, canales)


def asegurar(servidor, progreso=None, forzar=False):
    """The catalogue's channels, downloading them if need be. Empty list if it could not.

    The latch stops two presses in a row from firing twenty requests at an engine that may
    well be broadcasting."""
    base = servidor.base

    if not forzar:
        guardados = leer(base)
        if guardados:
            return guardados

    if not echar_pestillo(PESTILLO):
        logger('catalog: ya hay una descarga en marcha')
        # Whatever there is, even expired, beats nothing while the other one finishes.
        return leer(base, ttl_horas=0) or list()

    try:
        canales, completo = descargar(servidor, progreso, pestillo=PESTILLO)
    finally:
        quitar_pestillo(PESTILLO)

    if canales and completo:
        guardar(base, canales)

    return canales


def descargando():
    """True if another invocation of the addon is downloading the catalogue right now."""
    return hay_pestillo(PESTILLO)


def visibles(canales, mostrar_adultos=None):
    if mostrar_adultos is None:
        mostrar_adultos = bool(get_setting('mostrar_adultos', False))

    if mostrar_adultos:
        return list(canales)

    return [c for c in canales if not any(es_adulto(x) for x in c.get('categorias') or [])]


def indexar(canales, campo):
    """{key: [channel]} by 'categorias', 'paises' or 'idiomas'.

    Channels that do not declare the field go to SIN_DATO, which is a different drawer
    from the catalogue's own 'other': one means 'it does not say' and the other 'none of
    the above', and mixing them leaves the user unsure which one they are looking at.

    In categories, besides, labels with four channels or fewer are merged into 'other'.
    The catalogue carries leftovers like 'Chileiptv' that do not deserve a row."""
    indice = dict()

    for canal in canales:
        for valor in canal.get(campo) or [SIN_DATO]:
            indice.setdefault(valor or SIN_DATO, list()).append(canal)

    if campo == 'categorias':
        restos = [e for e, c in indice.items()
                  if len(c) < MIN_POR_CATEGORIA and e not in ('other', SIN_DATO)]
        for e in restos:
            indice.setdefault('other', list()).extend(indice.pop(e))

    return indice


# The group list writes adults as 'Erotic 18+' and the catalogue as 'erotic_18_plus';
# clave() does not bridge the two forms because '+' is not a separator.
_ALIAS_GRUPO = {'erotic_18+': 'erotic_18_plus'}


def clave_grupo(grupo):
    """Category matching a group of the list, or its own key if there is none."""
    c = clave(grupo)

    return _ALIAS_GRUPO.get(c, c)


def nombre_grupo(grupo):
    """Spanish name of a group of the list, or the one it carries if it is not known.

    The groups arrive in English and with the same labels as the categories ('Sport',
    'Movies'...), so the usual table serves. Whatever is not in it is left as is: 'Emilia
    Romagna' or 'Chileiptv' are proper names, and running them through the categories'
    mould would only put them in capitals."""
    return _CATEGORIAS.get(clave_grupo(grupo), grupo)


def facetas(indice, campo, preferido=''):
    """[(key, name, channels)] ready to paint.

    The preferred one rules, and it comes from Kodi's language: whoever has it in Spanish
    wants Spanish at the top, not Russian for having five times more channels. Behind it,
    from largest to smallest.

    'Sin especificar' always goes last however many it has: it is the drawer of what is
    not known, not a category anyone is interested in."""
    filas = [(c, etiqueta(campo, c), canales) for c, canales in indice.items()]

    return sorted(filas, key=lambda f: (f[0] != preferido, f[0] == SIN_DATO,
                                        -len(f[2]), sin_tildes(f[1])))


def idioma_preferido():
    """Three-letter code of Kodi's language, or an empty string."""
    try:
        return clave(xbmc.getLanguage(xbmc.ISO_639_2))
    except (AttributeError, TypeError):
        # getLanguage with ISO_639_2 is from Kodi 19; if it ever changes, sorting without
        # the language is still correct, only less useful.
        return ''


def ordenar(canales, idioma=None):
    """What can be understood and what works, first.

    Four criteria in this order: healthy links before doubtful ones, Kodi's language
    before the rest, availability, and name. The second matters more than it looks: the
    catalogue is international and without it a Spanish user opens 'Todos los canales' and
    the first thing they see is in Cyrillic."""
    if idioma is None:
        idioma = idioma_preferido()

    def orden(canal):
        return (canal.get('estado') != DISPONIBLE,
                not (idioma and idioma in (canal.get('idiomas') or [])),
                -(canal.get('disponibilidad') or 0),
                sin_tildes(canal.get('nombre')))

    return sorted(canales, key=orden)


def buscar(servidor, texto, tope=BUSQUEDA_TOPE):
    """Engine channels matching a text. Empty list if the engine does not answer.

    It goes live against /search?query=, which answers in tenths of a second, so it does
    not depend on the catalogue being downloaded. With its own short timeout, because this
    hangs off the user finishing their typing."""
    if not texto:
        return list()

    corto = Server(host=servidor.host, port=servidor.port, timeout=BUSQUEDA_TIMEOUT)
    respuesta = corto.buscar(query=texto, page=0, page_size=tope)

    if not respuesta.success or not isinstance(respuesta.data, dict):
        logger(f'catalog: busqueda "{texto}": {respuesta.message}', 'error')
        return list()

    # The engine does not filter adults, so the filter is applied here too.
    return ordenar(visibles(normalizar(respuesta.data.get('results'))))[:tope]


def leer_playlist(servidor, forzar=False):
    """[{'grupo', 'nombre', 'infohash'}] from the engine's /pl.m3u. Empty if not served.

    This is AceServe's own list, which until now was only used to tell which engine was
    answering. The urls inside carry 127.0.0.1 and are NOT used: the infohash is pulled
    out and playback goes the usual way, which is the one that honours the configured IP,
    the OSD, the history and the cache cleanup."""
    base = servidor.base

    if not forzar:
        guardados = leer(base, FICHERO_PLAYLIST)
        if guardados:
            return guardados

    texto = servidor.get_text('pl.m3u')
    if not texto:
        return list()

    entradas = list()
    grupo = nombre = ''

    for linea in texto.splitlines():
        linea = linea.strip()

        if linea.upper().startswith('#EXTINF'):
            grupo, nombre = partir_extinf(linea)
        elif linea and not linea.startswith('#'):
            infohash = _RE_HASH.search(linea)
            if infohash and nombre:
                # With no group-title it goes to the same drawer the engine already
                # uses, not a new one: otherwise two near-identical rows would show
                # up, 'Otras' and 'Otros'.
                entradas.append({'grupo': grupo or 'Other', 'nombre': nombre,
                                 'infohash': infohash.group(1).lower()})
            grupo = nombre = ''

    if entradas:
        guardar(base, entradas, FICHERO_PLAYLIST)

    return entradas


def playlist_visible(entradas, mostrar_adultos=None):
    if mostrar_adultos is None:
        mostrar_adultos = bool(get_setting('mostrar_adultos', False))

    if mostrar_adultos:
        return list(entradas)

    return [e for e in entradas if not es_adulto(e.get('grupo'))]
