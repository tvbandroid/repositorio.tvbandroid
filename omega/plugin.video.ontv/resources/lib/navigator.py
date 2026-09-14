# -*- coding: utf-8 -*-
"""
OnTV — Navigator  v1.0.2
Suporta: Xtream Codes, Stalker/MAC Portal, M3U por URL

MELHORIAS v1.0.2:
  - Cache HTTP em disco com TTL por URL (sobrevive entre chamadas do plugin)
  - M3U em cache disco — não descarrega duas vezes por sessão
  - Pesquisa de canais/filmes em qualquer servidor
  - Temporadas como nível intermédio nas séries
  - Progresso (DialogProgress) em todas as listas lentas
  - Filtro adulto com regex robusto (variantes codificadas, Unicode, etc.)
  - Stalker: retry automático com novo token em erro 458/459
  - Stalker: paginação agressiva (tenta perpage=100, recua para 14)
  - Reprodução sem tocar no advancedsettings.xml do utilizador
  - Credenciais mascaradas nos logs
  - Compatível com Kodi 18+ em Android, iOS, Windows, Linux, OSMC, CoreELEC
"""

import sys
import os
import re
import json
import time
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

try:
    from urllib.request import urlopen, Request
    from urllib.parse   import urlencode, parse_qsl, quote, unquote
except ImportError:
    from urllib2  import urlopen, Request
    from urllib   import urlencode, quote, unquote
    from urlparse import parse_qsl

ADDON      = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_PATH = ADDON.getAddonInfo('path')
HANDLE     = int(sys.argv[1])
BASE_URL   = sys.argv[0]
ICON       = os.path.join(ADDON_PATH, 'icon.png')
FANART     = os.path.join(ADDON_PATH, 'fanart.png')
UA_STB     = 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stb mergnat/1.1 Safari/533.3'
UA_KODI    = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Kodi/21.0'

# ── Cache HTTP em disco ────────────────────────────────────────────────────
#   Sobrevive entre invocações do plugin (o processo Kodi não persiste).
#   Estrutura: { url: { "ts": float, "data": str } }
_HTTP_CACHE_FILE = xbmcvfs.translatePath('special://temp/ontv_http_cache.json')
_HTTP_CACHE_TTL  = {
    'default': 300,    # 5 min — categorias e listas
    'm3u':     900,    # 15 min — ficheiros M3U (podem ser grandes)
    'api':     300,    # 5 min — APIs Xtream/Stalker
}
_http_mem  = {}   # cache em memória para a sessão actual (mais rápida)
_http_disk = None # cache de disco (carregada uma vez por sessão)


def _carregar_cache_disco():
    global _http_disk
    if _http_disk is not None:
        return
    try:
        if os.path.exists(_HTTP_CACHE_FILE):
            with open(_HTTP_CACHE_FILE, 'r', encoding='utf-8') as f:
                _http_disk = json.load(f)
        else:
            _http_disk = {}
    except Exception:
        _http_disk = {}


def _guardar_cache_disco():
    try:
        with open(_HTTP_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_http_disk, f, ensure_ascii=False)
    except Exception:
        pass


def _cache_get(url, ttl=None):
    """Lê da cache em memória, depois em disco. None se expirado/inexistente."""
    if ttl is None:
        ttl = _HTTP_CACHE_TTL['default']
    # Memória
    if url in _http_mem:
        entry = _http_mem[url]
        if time.time() - entry['ts'] < ttl:
            return entry['data']
    # Disco
    _carregar_cache_disco()
    entry = _http_disk.get(url)
    if entry and time.time() - entry['ts'] < ttl:
        _http_mem[url] = entry   # promover para memória
        return entry['data']
    return None


def _cache_set(url, data, ttl=None):
    """Guarda em memória e em disco."""
    if ttl is None:
        ttl = _HTTP_CACHE_TTL['default']
    _carregar_cache_disco()
    entry = {'ts': time.time(), 'data': data}
    _http_mem[url]  = entry
    _http_disk[url] = entry
    _guardar_cache_disco()


def _cache_invalidar(url):
    _http_mem.pop(url, None)
    _carregar_cache_disco()
    _http_disk.pop(url, None)
    _guardar_cache_disco()


# ── Logging (mascarando credenciais) ───────────────────────────────────────

def log(msg, level=xbmc.LOGDEBUG):
    xbmc.log('[OnTV] ' + str(msg), level)


def _mascarar_url(url):
    """Remove username/password de URLs nos logs."""
    return re.sub(r'(username=|password=)([^&\s]+)', r'\1***', str(url))


# ── Filtro adulto (robusto) ────────────────────────────────────────────────

# Regex compilado — suporta variantes com separadores (a.d.u.l.t, a-d-u-l-t, etc.)
_RE_ADULTO = re.compile(
    r'(?i)\b('
    r'a[\.\-_]?d[\.\-_]?u[\.\-_]?l[\.\-_]?t[os]?'
    r'|x{2,}'                       # xxx, xxxx …
    r'|p[\.\-_]?o[\.\-_]?r[\.\-_]?n'
    r'|s[\.\-_]?e[\.\-_]?x[\.\-_]?[yo]?'
    r'|18\s*\+'
    r'|er[o0]t[i1]c[a]?'
    r'|x[\.\-_]?rat[e3]d'
    r'|h[e3]nt[a@]i'
    r'|playboy'
    r'|nud[e3]?'
    r'|nak[e3]d'
    r'|adulte?[os]?'
    r')\b'
)

def _normalizar(nome):
    """Remove caracteres não-alfanuméricos do início e devolve em maiúsculas."""
    return re.sub(r'^[^a-zA-Z0-9]+', '', nome).strip().upper()

def e_adulto(nome):
    if not nome:
        return False
    if _RE_ADULTO.search(nome):
        return True
    # Verificar também nome normalizado (sem prefixos de emoji/pipe)
    return bool(_RE_ADULTO.search(_normalizar(nome)))

def filtrar_adulto(lista, campo='category_name'):
    return [i for i in lista if not e_adulto(i.get(campo, ''))]


# ── HTTP helpers ───────────────────────────────────────────────────────────

def url_para(params):
    return BASE_URL + '?' + urlencode(params)

def notificar(msg, tipo=xbmcgui.NOTIFICATION_ERROR, duracao=4000):
    xbmcgui.Dialog().notification(ADDON_NAME, msg, tipo, duracao)

def http_get(url, headers=None, ttl=None, forcar=False):
    """
    HTTP GET com cache disco + memória.
    forcar=True ignora cache e faz sempre pedido de rede.
    """
    if not forcar:
        cached = _cache_get(url, ttl)
        if cached is not None:
            return cached
    try:
        req  = Request(url, headers=headers or {'User-Agent': UA_STB})
        resp = urlopen(req, timeout=20)
        data = resp.read().decode('utf-8', errors='replace')
        if data:
            _cache_set(url, data, ttl)
        return data
    except Exception as e:
        log('ERRO HTTP: ' + str(e) + ' | URL: ' + _mascarar_url(url), xbmc.LOGWARNING)
        _cache_invalidar(url)
        return None

def api_json(url, headers=None, ttl=None, forcar=False):
    data = http_get(url, headers, ttl=ttl or _HTTP_CACHE_TTL['api'], forcar=forcar)
    if not data:
        return None
    try:
        return json.loads(data)
    except Exception:
        log('ERRO JSON: ' + _mascarar_url(url), xbmc.LOGWARNING)
        return None


# ════════════════════════════════════════════════════════
#  STALKER / MAC — Autenticação e API
# ════════════════════════════════════════════════════════

def stalker_base(host):
    base = host.rstrip('/')
    if base.endswith('/c'):
        base = base[:-2]
    return base

def stalker_headers(mac):
    return {
        'User-Agent':   UA_STB,
        'X-User-Agent': 'Model: MAG250; Link: WiFi',
        'Cookie':       'mac=' + mac + '; stb_lang=en; timezone=Europe/Lisbon',
        'Referer':      'http://localhost/c/',
        'Accept':       '*/*',
    }

def stalker_token(host, mac, forcar=False):
    """Obtém ou renova o token do portal Stalker."""
    cache_key = 'stalker_token_' + mac
    if not forcar and cache_key in _http_mem:
        return _http_mem[cache_key]['data']

    base = stalker_base(host)
    url  = base + '/server/load.php?type=stb&action=handshake&token=&JsHttpRequest=1-xml'
    data = api_json(url, stalker_headers(mac), forcar=True)
    if not data:
        log('Stalker handshake falhou', xbmc.LOGWARNING)
        return None

    token = data.get('js', {}).get('token', '')
    if token:
        _http_mem[cache_key] = {'ts': time.time(), 'data': token}
        log('Stalker token ' + ('renovado' if forcar else 'obtido'))
    return token or None

def stalker_call(host, mac, params_str, tentativa=0):
    """
    Chama a API Stalker. Em caso de erro de token (458/459), renova e retenta.
    Máximo 1 retentativa automática.
    """
    base  = stalker_base(host)
    token = stalker_token(host, mac, forcar=(tentativa > 0))
    if not token:
        return None
    url     = base + '/server/load.php?' + params_str + '&token=' + token + '&JsHttpRequest=1-xml'
    headers = stalker_headers(mac)
    headers['Authorization'] = 'Bearer ' + token
    data = api_json(url, headers, forcar=True)

    # Detectar erros de token e retentar uma vez
    if data and isinstance(data.get('js'), dict):
        err = str(data['js'].get('error', '') or data['js'].get('err', ''))
        if tentativa == 0 and ('458' in err or '459' in err or 'token' in err.lower()):
            log('Stalker token expirado — a renovar...', xbmc.LOGWARNING)
            return stalker_call(host, mac, params_str, tentativa=1)

    return data

def stalker_categorias(host, mac, tipo):
    action = 'get_genres' if tipo == 'itv' else 'get_categories'
    data   = stalker_call(host, mac, 'type={}&action={}'.format(tipo, action))
    if not data:
        return []
    cats = data.get('js', [])
    if isinstance(cats, dict):
        cats = list(cats.values())
    return [c for c in cats if c.get('title') or c.get('name')]

def stalker_canais(host, mac, tipo, cat_id):
    """
    Obtém canais/filmes com paginação adaptativa.
    Tenta perpage=100; se o servidor devolver menos, recua para 14.
    """
    todos       = []
    pagina      = 1
    perpage     = 100
    max_paginas = 200
    perpage_ajustado = False

    while pagina <= max_paginas:
        params = 'type={}&action=get_ordered_list&genre={}&p={}&perpage={}&sortby=number'.format(
            tipo, cat_id, pagina, perpage)
        data = stalker_call(host, mac, params)
        if not data:
            log('Stalker p{}: sem resposta'.format(pagina), xbmc.LOGWARNING)
            break
        js = data.get('js', {})
        if not isinstance(js, dict):
            break

        items          = js.get('data', [])
        total_items    = int(js.get('total_items', 0) or 0)
        max_page_items = int(js.get('max_page_items', perpage) or perpage)

        # Se o servidor ignorou o perpage e devolveu muito menos → ajustar
        if not perpage_ajustado and items and len(items) < min(perpage, 50):
            perpage          = max(max_page_items, 14)
            perpage_ajustado = True
            log('Stalker: perpage ajustado para {}'.format(perpage))

        todos.extend(items)
        log('Stalker p{}: {} itens, total={}'.format(pagina, len(items), total_items))

        if not items:
            break
        if total_items > 0 and len(todos) >= total_items:
            break
        if len(items) < max(max_page_items, 1):
            break
        pagina += 1

    log('Stalker total: {} canais'.format(len(todos)))
    return todos

def _extrair_stream_id(cmd):
    m = re.search(r'[&?]stream=(\d+)', cmd)
    return m.group(1) if m else ''

def _corrigir_stream_vazio(url, cmd_original):
    if 'stream=&' in url or url.endswith('stream='):
        stream_id = _extrair_stream_id(cmd_original)
        if stream_id:
            if url.endswith('stream='):
                url = url + stream_id
            else:
                url = url.replace('stream=&', 'stream=' + stream_id + '&')
            log('Stalker stream ID corrigido: ' + stream_id)
    return url

def _limpar_cmd(cmd):
    cmd = cmd.strip()
    if cmd.startswith('ffmpeg '):
        cmd = cmd[7:].strip()
    if ' ' in cmd:
        parts = cmd.split('?', 1)
        if len(parts) == 2:
            cmd = parts[0] + '?' + parts[1].replace(' ', '%20')
        else:
            cmd = cmd.replace(' ', '%20')
    return cmd

def stalker_create_link(host, mac, tipo, cmd):
    cmd_limpo = _limpar_cmd(cmd)
    cmd_limpo = _corrigir_stream_vazio(cmd_limpo, cmd)

    if cmd_limpo.startswith('http') and 'localhost' not in cmd_limpo and '127.0.0.1' not in cmd_limpo:
        log('Stalker: cmd direto: ' + _mascarar_url(cmd_limpo[:80]))
        return cmd_limpo

    log('Stalker: cmd é localhost — a chamar create_link')
    token = stalker_token(host, mac, forcar=True)
    if not token:
        return cmd_limpo

    base    = stalker_base(host)
    cmd_enc = quote(cmd, safe='')
    url_api = (base + '/server/load.php?type={}&action=create_link'
               '&cmd={}&series=&forced_storage=undefined&disable_ad=0&download=0'
               '&token={}&JsHttpRequest=1-xml').format(tipo, cmd_enc, token)
    headers = stalker_headers(mac)
    headers['Authorization'] = 'Bearer ' + token
    data = api_json(url_api, headers, forcar=True)

    js  = (data or {}).get('js', {})
    url = (js.get('url', '') or js.get('cmd', '')) if isinstance(js, dict) else ''
    url = _limpar_cmd(url) if url else ''
    url = _corrigir_stream_vazio(url, cmd) if url else ''

    if url and 'localhost' not in url and '127.0.0.1' not in url:
        log('Stalker create_link OK: ' + _mascarar_url(url[:80]))
        return url

    log('Stalker create_link falhou — fallback para cmd limpo', xbmc.LOGWARNING)
    return cmd_limpo


# ════════════════════════════════════════════════════════
#  Utilitário de ordenação PT-primeiro
# ════════════════════════════════════════════════════════

import re as _re_pt

# 'PT' isolado: nao pode ter letra/numero imediatamente antes ou depois.
# Evita falsos positivos como "EGYPT", "SPORT", "CAPTAIN", "OPTIMUS".
_RE_PT_ISOLADO = _re_pt.compile(r'(?<![A-Z0-9])PT(?![A-Z0-9])')


def _prioridade_pt(nome_raw):
    """
    Prioriza categorias/canais relacionados com Portugal no topo da lista.
    Usa CONTAINS (nao apenas STARTSWITH) para apanhar todas as variantes:
    "PT | Geral", "PT | Esportes", "EU | PT | Variedade", etc.
    Usa regex com word-boundary real para 'PT' isolado, evitando falsos
    positivos como "EGYPT", "SPORT", "CAPTAIN", "OPTIMUS".
    Tambem deteta o simbolo de retangulo (▯) usado como separador quando
    o Kodi nao reconhece um emoji/caracter especial.
    """
    n = nome_raw.upper()

    if 'PORTUGAL' in n or 'EU | PT' in n or 'EU|PT' in n:
        return 0

    for r in ('▯', '\ufffd'):
        if (r + 'PT') in n or ('PT' + r) in n:
            return 0

    if _RE_PT_ISOLADO.search(n):
        return 0

    return 1


# ════════════════════════════════════════════════════════
#  ECRÃ 1 — Servidores
# ════════════════════════════════════════════════════════



# ════════════════════════════════════════════════════════
#  ECRÃ 2 — Tipos (Live TV / Filmes / Séries / Pesquisa)
# ════════════════════════════════════════════════════════

def mostrar_tipos(srv_idx):
    from mediacfg import carregar_servidores
    srv  = carregar_servidores()[int(srv_idx)]
    tipo = srv.get('tipo', 'xtream')
    xbmcplugin.setPluginCategory(HANDLE, srv['nome'])

    if tipo == 'm3u':
        mostrar_grupos_m3u(srv_idx)
        return

    entradas = [
        ('📺  Live TV',  'live_cats'),
        ('🎬  Filmes',   'vod_cats'),
        ('📺  Séries',   'series_cats'),
        ('🔍  Pesquisar','pesquisa'),
    ]
    for nome, acao_cat in entradas:
        li = xbmcgui.ListItem(nome)
        li.setArt({'thumb': ICON, 'fanart': FANART})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': acao_cat, 'srv_idx': srv_idx}), li, True)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


# ════════════════════════════════════════════════════════
#  ECRÃ 3 — Categorias
# ════════════════════════════════════════════════════════

def mostrar_categorias(srv_idx, tipo_cat):
    from mediacfg import carregar_servidores
    srv  = carregar_servidores()[int(srv_idx)]
    tipo = srv.get('tipo', 'xtream')

    if tipo == 'stalker':
        stalker_tipo = {'live_cats': 'itv', 'vod_cats': 'vod', 'series_cats': 'series'}[tipo_cat]
        acao_canais  = {'live_cats': 'stalker_live', 'vod_cats': 'stalker_vod', 'series_cats': 'stalker_series'}[tipo_cat]
        _mostrar_cats_stalker(srv_idx, srv, stalker_tipo, acao_canais)
        return

    # Xtream Codes
    host = srv['host']
    u    = srv['username']
    p    = srv['password']
    ep   = {
        'live_cats':   '/player_api.php?username={u}&password={p}&action=get_live_categories',
        'vod_cats':    '/player_api.php?username={u}&password={p}&action=get_vod_categories',
        'series_cats': '/player_api.php?username={u}&password={p}&action=get_series_categories',
    }[tipo_cat]

    data = api_json(host + ep.format(u=u, p=p))

    if not data:
        notificar('Erro ao carregar categorias!')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    data = filtrar_adulto(data, 'category_name')
    data = sorted(data, key=lambda c: _prioridade_pt(c.get('category_name', '')))
    acao = {'live_cats': 'live_canais', 'vod_cats': 'vod_canais', 'series_cats': 'series_canais'}[tipo_cat]

    xbmcplugin.setPluginCategory(HANDLE, srv['nome'])
    for cat in data:
        nome   = cat.get('category_name', 'Sem Nome')
        cat_id = str(cat.get('category_id', ''))
        li = xbmcgui.ListItem(nome)
        li.setArt({'thumb': ICON, 'fanart': ''})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': acao, 'srv_idx': srv_idx, 'cat_id': cat_id, 'cat_nome': nome}), li, True)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def _mostrar_cats_stalker(srv_idx, srv, stalker_tipo, acao_canais):
    cats = stalker_categorias(srv['host'], srv['mac'], stalker_tipo)

    if not cats:
        notificar('Erro ao carregar categorias! Verifica host e MAC.')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    cats = [c for c in cats if not e_adulto(c.get('title', c.get('name', '')))]
    cats = sorted(cats, key=lambda c: _prioridade_pt(c.get('title', c.get('name', ''))))

    xbmcplugin.setPluginCategory(HANDLE, srv['nome'])
    for cat in cats:
        nome   = cat.get('title', cat.get('name', 'Sem Nome'))
        cat_id = str(cat.get('id', cat.get('genre_id', '*')))
        if not nome or nome == '0':
            continue
        li = xbmcgui.ListItem(nome)
        li.setArt({'thumb': ICON, 'fanart': ''})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': acao_canais, 'srv_idx': srv_idx, 'cat_id': cat_id, 'cat_nome': nome}), li, True)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


# ════════════════════════════════════════════════════════
#  ECRÃ 4 — Canais Stalker (com progresso)
# ════════════════════════════════════════════════════════

def mostrar_canais_stalker(srv_idx, stalker_tipo, cat_id, cat_nome):
    from mediacfg import carregar_servidores
    srv = carregar_servidores()[int(srv_idx)]

    canais = stalker_canais(srv['host'], srv['mac'], stalker_tipo, cat_id)

    if not canais:
        notificar('Sem canais nesta categoria.')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    def _e_separador(ch):
        cmd = ch.get('cmd', '').strip()
        return not cmd or 'http' not in cmd.lower()

    canais = [ch for ch in canais if not _e_separador(ch) and not e_adulto(ch.get('name', ''))]

    xbmcplugin.setPluginCategory(HANDLE, cat_nome)
    for ch in canais:
        nome = ch.get('name', 'Canal')
        logo = (ch.get('logo', '') or ICON).replace(' ', '%20')
        cmd  = ch.get('cmd', '')

        li = xbmcgui.ListItem(nome)
        li.setArt({'thumb': logo, 'fanart': ''})
        li.setProperty('IsPlayable', 'true')
        li.setInfo('video', {'title': nome, 'mediatype': 'video', 'playcount': 0, 'overlay': 0})
        xbmcplugin.addDirectoryItem(
            HANDLE,
            url_para({'acao': 'stalker_play', 'srv_idx': srv_idx,
                      'stalker_tipo': stalker_tipo, 'cmd': cmd, 'nome': nome, 'logo': logo}),
            li, False
        )

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


# ════════════════════════════════════════════════════════
#  ECRÃ 4 — Canais Xtream Live
# ════════════════════════════════════════════════════════


def _epg_agora(host, u, p, stream_id):
    url  = '{}/player_api.php?username={}&password={}&action=get_short_epg&stream_id={}&limit=3'.format(
        host, u, p, stream_id)
    data = api_json(url, ttl=300)
    if not data:
        return None
    try:
        lista = data.get('epg_listings', [])
        if not lista:
            return None

        agora = lista[0]
        titulo = agora.get('title', '') or agora.get('name', '')
        desc   = agora.get('description', '') or agora.get('plot', '')

        # Hora de inicio e fim
        inicio = agora.get('start', '') or agora.get('start_timestamp', '')
        fim    = agora.get('end',   '') or agora.get('stop_timestamp',  '')
        hora_txt = ''
        try:
            import datetime
            if str(inicio).isdigit():
                dt_i = datetime.datetime.fromtimestamp(int(inicio))
                dt_f = datetime.datetime.fromtimestamp(int(fim))
            else:
                dt_i = datetime.datetime.strptime(inicio[:16], '%Y-%m-%d %H:%M')
                dt_f = datetime.datetime.strptime(fim[:16],    '%Y-%m-%d %H:%M')
            hora_txt = '{}-{}'.format(dt_i.strftime('%H:%M'), dt_f.strftime('%H:%M'))
        except Exception:
            pass

        # Proximo programa
        proximo = ''
        if len(lista) > 1:
            p2 = lista[1]
            proximo = p2.get('title', '') or p2.get('name', '')

        if titulo:
            return {
                'titulo':  titulo,
                'descricao': desc,
                'horas':   hora_txt,
                'proximo': proximo,
            }
    except Exception:
        pass
    return None


def _epg_plot(epg, nome_canal):
    if not epg:
        return ''
    partes = []
    if epg.get('horas'):
        partes.append('[B]{}[/B]  {}'.format(epg['horas'], epg['titulo']))
    else:
        partes.append('[B]{}[/B]'.format(epg['titulo']))
    if epg.get('descricao'):
        partes.append(epg['descricao'])
    if epg.get('proximo'):
        partes.append('\nA seguir: {}'.format(epg['proximo']))
    return '\n'.join(partes)


def mostrar_live(srv_idx, cat_id, cat_nome):
    from mediacfg import carregar_servidores
    srv  = carregar_servidores()[int(srv_idx)]
    host = srv['host']
    u    = srv['username']
    p    = srv['password']

    data = api_json('{}/player_api.php?username={}&password={}&action=get_live_streams&category_id={}'.format(host, u, p, cat_id))

    if not data:
        notificar('Erro ao carregar canais!')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    data = [ch for ch in data
            if not e_adulto(ch.get('name', ''))
            and int(ch.get('stream_id', 0) or 0) > 0]

    xbmcplugin.setPluginCategory(HANDLE, cat_nome)
    for ch in data:
        nome       = ch.get('name', 'Canal')
        stream_id  = str(ch.get('stream_id', ''))
        logo       = (ch.get('stream_icon', '') or ICON).replace(' ', '%20')
        ext        = ch.get('container_extension', 'ts')
        stream_url = '{}/live/{}/{}/{}.{}'.format(host, u, p, stream_id, ext)

        epg        = _epg_agora(host, u, p, stream_id)
        epg_titulo = epg['titulo'] if epg else ''
        epg_horas  = epg['horas']  if epg else ''
        plot       = _epg_plot(epg, nome)

        # Label: Canal — HH:MM-HH:MM Título programa
        label = nome
        if epg_titulo and epg_horas:
            label = '{} — {} {}'.format(nome, epg_horas, epg_titulo)
        elif epg_titulo:
            label = '{} — {}'.format(nome, epg_titulo)

        li = xbmcgui.ListItem(label)
        li.setArt({'thumb': logo, 'fanart': logo if logo != ICON else ''})
        li.setProperty('IsPlayable', 'true')
        li.setInfo('video', {
            'title':     nome,
            'plot':      plot,
            'tagline':   '{} {}'.format(epg_horas, epg_titulo).strip() if epg_titulo else '',
            'mediatype': 'video',
            'playcount': 0,
            'overlay':   0,
        })
        xbmcplugin.addDirectoryItem(
            HANDLE,
            url_para({'acao': 'play', 'url': stream_url, 'nome': nome, 'logo': logo}),
            li, False
        )

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)

def mostrar_vod(srv_idx, cat_id, cat_nome):
    from mediacfg import carregar_servidores
    srv  = carregar_servidores()[int(srv_idx)]
    host = srv['host']
    u    = srv['username']
    p    = srv['password']

    data = api_json('{}/player_api.php?username={}&password={}&action=get_vod_streams&category_id={}'.format(host, u, p, cat_id))

    if not data:
        notificar('Erro ao carregar filmes!')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    data = [i for i in data
            if not e_adulto(i.get('name', ''))
            and int(i.get('stream_id', 0) or 0) > 0]

    xbmcplugin.setPluginCategory(HANDLE, cat_nome)
    for item in data:
        nome       = item.get('name', 'Filme')
        stream_id  = str(item.get('stream_id', ''))
        logo       = (item.get('stream_icon', '') or ICON).replace(' ', '%20')
        ext        = item.get('container_extension', 'mp4')
        stream_url = '{}/movie/{}/{}/{}.{}'.format(host, u, p, stream_id, ext)

        li = xbmcgui.ListItem(nome)
        li.setArt({'thumb': logo, 'fanart': ''})
        li.setProperty('IsPlayable', 'true')
        li.setInfo('video', {'title': nome, 'mediatype': 'movie', 'playcount': 0, 'overlay': 0})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': 'play', 'url': stream_url, 'nome': nome, 'logo': logo}), li, False)

    xbmcplugin.setContent(HANDLE, 'movies')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


# ════════════════════════════════════════════════════════
#  ECRÃ 4 — Séries Xtream
# ════════════════════════════════════════════════════════

def mostrar_series(srv_idx, cat_id, cat_nome):
    from mediacfg import carregar_servidores
    srv  = carregar_servidores()[int(srv_idx)]
    host = srv['host']
    u    = srv['username']
    p    = srv['password']

    data = api_json('{}/player_api.php?username={}&password={}&action=get_series&category_id={}'.format(host, u, p, cat_id))

    if not data:
        notificar('Erro ao carregar séries!')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    # Não filtrar adultos no nome da série — filtrar por categoria já feito antes
    xbmcplugin.setPluginCategory(HANDLE, cat_nome)
    for serie in data:
        nome      = serie.get('name', 'Série')
        series_id = str(serie.get('series_id', ''))
        logo      = serie.get('cover', '') or ICON

        li = xbmcgui.ListItem(nome)
        li.setArt({'thumb': logo, 'fanart': logo or FANART})
        li.setInfo('video', {'title': nome, 'mediatype': 'tvshow', 'playcount': 0, 'overlay': 0})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': 'series_temps', 'srv_idx': srv_idx, 'series_id': series_id, 'serie_nome': nome}), li, True)

    xbmcplugin.setContent(HANDLE, 'tvshows')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


# ════════════════════════════════════════════════════════
#  ECRÃ 5 — Temporadas (nível intermédio)
# ════════════════════════════════════════════════════════

def mostrar_temporadas(srv_idx, series_id, serie_nome):
    """
    Nível intermédio: lista as temporadas de uma série.
    Se só houver 1 temporada, vai directamente para os episódios.
    """
    from mediacfg import carregar_servidores
    srv  = carregar_servidores()[int(srv_idx)]
    host = srv['host']
    u    = srv['username']
    p    = srv['password']

    data = api_json('{}/player_api.php?username={}&password={}&action=get_series_info&series_id={}'.format(host, u, p, series_id))

    if not data:
        notificar('Erro ao carregar série!')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    episodes = data.get('episodes', {})
    temporadas = sorted(episodes.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)

    # Se só houver 1 temporada, saltar directamente para episódios
    if len(temporadas) == 1:
        mostrar_episodios_de_temporada(srv_idx, series_id, serie_nome, temporadas[0], data)
        return

    capa = data.get('info', {}).get('cover', '') or ICON
    xbmcplugin.setPluginCategory(HANDLE, serie_nome)

    for season_num in temporadas:
        eps   = episodes[season_num]
        total = len(eps)
        label = 'Temporada {:02d}  ({} ep.)'.format(int(season_num) if str(season_num).isdigit() else 0, total)
        li = xbmcgui.ListItem(label)
        li.setArt({'thumb': capa, 'fanart': capa or FANART})
        li.setInfo('video', {'title': label, 'mediatype': 'season'})
        xbmcplugin.addDirectoryItem(
            HANDLE,
            url_para({'acao': 'series_eps', 'srv_idx': srv_idx,
                      'series_id': series_id, 'serie_nome': serie_nome, 'temporada': str(season_num)}),
            li, True
        )

    xbmcplugin.setContent(HANDLE, 'seasons')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


# ════════════════════════════════════════════════════════
#  ECRÃ 6 — Episódios de uma temporada
# ════════════════════════════════════════════════════════

def mostrar_episodios(srv_idx, series_id, serie_nome, temporada=None):
    """Wrapper que carrega info da série e chama mostrar_episodios_de_temporada."""
    from mediacfg import carregar_servidores
    srv  = carregar_servidores()[int(srv_idx)]
    host = srv['host']
    u    = srv['username']
    p    = srv['password']

    data = api_json('{}/player_api.php?username={}&password={}&action=get_series_info&series_id={}'.format(host, u, p, series_id))

    if not data:
        notificar('Erro ao carregar episódios!')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    mostrar_episodios_de_temporada(srv_idx, series_id, serie_nome, temporada, data)


def mostrar_episodios_de_temporada(srv_idx, series_id, serie_nome, temporada, data):
    from mediacfg import carregar_servidores
    srv  = carregar_servidores()[int(srv_idx)]
    host = srv['host']
    u    = srv['username']
    p    = srv['password']

    episodes = data.get('episodes', {})

    # Se temporada especificada, mostrar só essa; caso contrário todas
    if temporada is not None:
        seasons_to_show = [str(temporada)]
    else:
        seasons_to_show = sorted(episodes.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)

    titulo_secao = serie_nome
    if temporada is not None:
        titulo_secao += ' — T{:02d}'.format(int(temporada) if str(temporada).isdigit() else 0)

    xbmcplugin.setPluginCategory(HANDLE, titulo_secao)

    for season_num in seasons_to_show:
        for ep in episodes.get(season_num, []):
            titulo    = 'S{}E{} — {}'.format(
                str(season_num).zfill(2),
                str(ep.get('episode_num', '')).zfill(2),
                ep.get('title', 'Episódio')
            )
            ep_id      = str(ep.get('id', ''))
            logo       = ep.get('info', {}).get('movie_image', '') or ICON
            ext        = ep.get('container_extension', 'mp4')
            stream_url = '{}/series/{}/{}/{}.{}'.format(host, u, p, ep_id, ext)

            li = xbmcgui.ListItem(titulo)
            li.setArt({'thumb': logo, 'fanart': ''})
            li.setProperty('IsPlayable', 'true')
            li.setInfo('video', {'title': titulo, 'mediatype': 'episode', 'playcount': 0, 'overlay': 0})
            xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': 'play', 'url': stream_url, 'nome': titulo, 'logo': logo}), li, False)

    xbmcplugin.setContent(HANDLE, 'episodes')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


# ════════════════════════════════════════════════════════
#  PESQUISA universal
# ════════════════════════════════════════════════════════

def pesquisar(srv_idx):
    """
    Pesquisa de canais/filmes/séries em qualquer tipo de servidor (Xtream, Stalker, M3U).
    Usa teclado nativo do Kodi — compatível com todos os dispositivos (remote, touch, teclado).
    """
    from mediacfg import carregar_servidores
    srv  = carregar_servidores()[int(srv_idx)]
    tipo = srv.get('tipo', 'xtream')

    kb = xbmc.Keyboard('', 'Pesquisar em ' + srv['nome'])
    kb.doModal()
    if not kb.isConfirmed() or not kb.getText().strip():
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    termo = kb.getText().strip().lower()

    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, 'A pesquisar «{}»…'.format(termo))
    dp.update(10)

    resultados = []

    if tipo == 'xtream':
        host = srv['host']
        u    = srv['username']
        p    = srv['password']

        # Live
        dp.update(20, 'Live TV…')
        lives = api_json('{}/player_api.php?username={}&password={}&action=get_live_streams'.format(host, u, p)) or []
        for ch in lives:
            if termo in ch.get('name', '').lower() and not e_adulto(ch.get('name', '')) and int(ch.get('stream_id', 0) or 0) > 0:
                ext = ch.get('container_extension', 'ts')
                resultados.append({
                    'nome':  ch['name'],
                    'url':   '{}/live/{}/{}/{}.{}'.format(host, u, p, ch['stream_id'], ext),
                    'logo':  (ch.get('stream_icon', '') or ICON).replace(' ', '%20'),
                    'tipo':  'video',
                })

        # VOD
        dp.update(50, 'Filmes…')
        vods = api_json('{}/player_api.php?username={}&password={}&action=get_vod_streams'.format(host, u, p)) or []
        for item in vods:
            if termo in item.get('name', '').lower() and not e_adulto(item.get('name', '')) and int(item.get('stream_id', 0) or 0) > 0:
                ext = item.get('container_extension', 'mp4')
                resultados.append({
                    'nome':  item['name'],
                    'url':   '{}/movie/{}/{}/{}.{}'.format(host, u, p, item['stream_id'], ext),
                    'logo':  (item.get('stream_icon', '') or ICON).replace(' ', '%20'),
                    'tipo':  'movie',
                })

        # Séries (só nomes — não vai buscar episódios)
        dp.update(80, 'Séries…')
        series = api_json('{}/player_api.php?username={}&password={}&action=get_series'.format(host, u, p)) or []
        for serie in series:
            if termo in serie.get('name', '').lower():
                resultados.append({
                    'nome':      serie['name'],
                    'url':       None,
                    'logo':      serie.get('cover', '') or ICON,
                    'tipo':      'tvshow',
                    'series_id': str(serie.get('series_id', '')),
                })

    elif tipo == 'stalker':
        # Stalker: pesquisa em ITV, VOD, Series
        mac = srv['mac']
        host = srv['host']
        for stalker_tipo, acao_play in [('itv', 'stalker_play'), ('vod', 'stalker_play'), ('series', 'stalker_play')]:
            dp.update({'itv': 20, 'vod': 55, 'series': 80}[stalker_tipo],
                      {'itv': 'Live TV…', 'vod': 'Filmes…', 'series': 'Séries…'}[stalker_tipo])
            canais = stalker_canais(host, mac, stalker_tipo, '*')
            for ch in canais:
                if termo in ch.get('name', '').lower() and not e_adulto(ch.get('name', '')):
                    if 'http' not in ch.get('cmd', '').lower():
                        continue
                    resultados.append({
                        'nome':         ch['name'],
                        'url':          None,
                        'logo':         (ch.get('logo', '') or ICON).replace(' ', '%20'),
                        'tipo':         'video',
                        'cmd':          ch.get('cmd', ''),
                        'stalker_tipo': stalker_tipo,
                    })

    elif tipo == 'm3u':
        dp.update(40, 'Lista M3U…')
        ttl     = _HTTP_CACHE_TTL['m3u']
        conteudo = http_get(srv['url'], ttl=ttl)
        if conteudo:
            canais = parse_m3u(conteudo)
            for ch in canais:
                if termo in ch['nome'].lower() and not e_adulto(ch['nome']) and not e_adulto(ch['grupo']):
                    resultados.append({
                        'nome': ch['nome'],
                        'url':  ch['url'],
                        'logo': ch.get('logo') or ICON,
                        'tipo': 'video',
                    })

    dp.close()

    if not resultados:
        notificar('Sem resultados para «{}»'.format(termo), xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    xbmcplugin.setPluginCategory(HANDLE, 'Pesquisa: ' + termo)

    for item in resultados:
        li = xbmcgui.ListItem(item['nome'])
        li.setArt({'thumb': item['logo'], 'fanart': ''})

        if item['tipo'] == 'tvshow':
            # Série — entrada de directório
            li.setInfo('video', {'title': item['nome'], 'mediatype': 'tvshow'})
            xbmcplugin.addDirectoryItem(
                HANDLE,
                url_para({'acao': 'series_temps', 'srv_idx': srv_idx,
                          'series_id': item['series_id'], 'serie_nome': item['nome']}),
                li, True
            )
        elif item.get('cmd'):
            # Stalker live/vod com cmd
            li.setProperty('IsPlayable', 'true')
            li.setInfo('video', {'title': item['nome'], 'mediatype': 'video'})
            xbmcplugin.addDirectoryItem(
                HANDLE,
                url_para({'acao': 'stalker_play', 'srv_idx': srv_idx,
                          'stalker_tipo': item.get('stalker_tipo', 'itv'),
                          'cmd': item['cmd'], 'nome': item['nome'], 'logo': item['logo']}),
                li, False
            )
        else:
            li.setProperty('IsPlayable', 'true')
            li.setInfo('video', {'title': item['nome'], 'mediatype': item['tipo']})
            xbmcplugin.addDirectoryItem(
                HANDLE,
                url_para({'acao': 'play', 'url': item['url'],
                          'nome': item['nome'], 'logo': item['logo']}),
                li, False
            )

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


# ════════════════════════════════════════════════════════
#  M3U por URL — com cache disco
# ════════════════════════════════════════════════════════

def parse_m3u(conteudo):
    """Parser M3U robusto. Devolve lista de dicts com nome, url, grupo, logo."""
    canais = []
    linhas = conteudo.splitlines()
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        if linha.startswith('#EXTINF'):
            ch = {'nome': 'Canal', 'url': '', 'grupo': 'Sem Grupo', 'logo': ''}
            def atr(padrao, src=linha):
                m = re.search(padrao, src, re.IGNORECASE)
                return m.group(1).strip() if m else ''
            ch['logo']  = atr(r'tvg-logo="([^"]*)"')
            grupo_raw   = atr(r'group-title="([^"]*)"')
            ch['grupo'] = grupo_raw.strip() if grupo_raw.strip() else 'Sem Grupo'
            virgula     = linha.rfind(',')
            ch['nome']  = linha[virgula + 1:].strip() if virgula != -1 else 'Canal'
            i += 1
            while i < len(linhas):
                prox = linhas[i].strip()
                if prox and not prox.startswith('#'):
                    ch['url'] = prox
                    break
                i += 1
            if ch['url']:
                canais.append(ch)
        i += 1
    return canais


def mostrar_grupos_m3u(srv_idx):
    from mediacfg import carregar_servidores
    srv = carregar_servidores()[int(srv_idx)]

    # Usa cache de disco — evita descarregar a lista duas vezes
    ttl      = _HTTP_CACHE_TTL['m3u']
    conteudo = http_get(srv['url'], ttl=ttl)

    if not conteudo:
        notificar('Erro ao carregar a lista M3U!')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    canais = parse_m3u(conteudo)
    canais = [ch for ch in canais if not e_adulto(ch['grupo']) and not e_adulto(ch['nome'])]

    grupos = {}
    ordem  = []
    for ch in canais:
        g = ch['grupo']
        if g not in grupos:
            grupos[g] = []
            ordem.append(g)
        grupos[g].append(ch)

    # Ordenar grupos: PT primeiro
    ordem = sorted(ordem, key=_prioridade_pt)

    xbmcplugin.setPluginCategory(HANDLE, srv['nome'])
    for g in ordem:
        thumb = grupos[g][0].get('logo') or ICON
        li = xbmcgui.ListItem(g)
        li.setArt({'thumb': thumb, 'fanart': ''})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': 'm3u_canais', 'srv_idx': srv_idx, 'grupo': g}), li, True)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def mostrar_canais_m3u(srv_idx, grupo):
    from mediacfg import carregar_servidores
    srv = carregar_servidores()[int(srv_idx)]

    # Reutiliza a cache — não descarrega de novo
    ttl      = _HTTP_CACHE_TTL['m3u']
    conteudo = http_get(srv['url'], ttl=ttl)

    if not conteudo:
        notificar('Erro ao carregar lista M3U!')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    canais = [ch for ch in parse_m3u(conteudo) if ch['grupo'] == grupo]

    xbmcplugin.setPluginCategory(HANDLE, grupo)
    for ch in canais:
        logo = ch.get('logo') or ICON
        li   = xbmcgui.ListItem(ch['nome'])
        li.setArt({'thumb': logo, 'fanart': ''})
        li.setProperty('IsPlayable', 'true')
        li.setInfo('video', {'title': ch['nome'], 'mediatype': 'video', 'playcount': 0, 'overlay': 0})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': 'play', 'url': ch['url'], 'nome': ch['nome'], 'logo': logo}), li, False)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


# ════════════════════════════════════════════════════════
#  REPRODUÇÃO — sem tocar no advancedsettings.xml
# ════════════════════════════════════════════════════════


def reproduzir(stream_url, nome='', logo=''):
    if not stream_url:
        notificar('URL de stream inválido.')
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    log('Play: ' + _mascarar_url(stream_url), xbmc.LOGINFO)

    icon        = logo or ICON
    url_to_play = stream_url
    using_proxy = False

    try:
        from proxy import start as proxy_start
        url_to_play = proxy_start(stream_url)
        using_proxy = url_to_play.startswith('http://127.0.0.1')
    except Exception as e:
        log('Proxy indisponivel: ' + str(e), xbmc.LOGWARNING)

    li = xbmcgui.ListItem(nome, path=url_to_play)
    li.setArt({'thumb': icon, 'icon': icon, 'fanart': ''})
    li.setProperty('IsPlayable', 'true')
    li.setInfo('video', {'title': nome, 'mediatype': 'video',
                         'playcount': 0, 'overlay': 0})
    li.setMimeType('video/mp2t')
    if using_proxy:
        li.setContentLookup(False)
    li.setProperty('ForceResolvePlugin', 'true')
    li.setProperty('network.curlcachebytes', '20971520')
    li.setProperty('network.bandwidth',      '0')
    li.setProperty('network.readtimeout',    '60')
    li.setProperty('network.connecttimeout', '10')
    xbmcplugin.setResolvedUrl(HANDLE, True, li)

def reproduzir_stalker(srv_idx, stalker_tipo, cmd, nome='', logo=''):
    from mediacfg import carregar_servidores
    import json as _json
    srv        = carregar_servidores()[int(srv_idx)]
    stream_url = stalker_create_link(srv['host'], srv['mac'], stalker_tipo, cmd)
    log('Stalker stream: ' + _mascarar_url(stream_url), xbmc.LOGINFO)
    try:
        _sfile = xbmcvfs.translatePath('special://temp/ontv_stalker_stream.json')
        with open(_sfile, 'w', encoding='utf-8') as _f:
            _json.dump({'tipo':'stalker','srv_idx':srv_idx,'stalker_tipo':stalker_tipo,'cmd':cmd,'host':srv['host'],'mac':srv['mac']}, _f)
    except Exception as _e:
        log('Aviso stalker: ' + str(_e), xbmc.LOGWARNING)
    reproduzir(stream_url, nome, logo)



# ════════════════════════════════════════════════════════
#  MODULOS NOVOS (lazy, sem quebrar se ausentes)
# ════════════════════════════════════════════════════════

def _get_favourites():
    try:
        from favourites import listar, adicionar, remover, existe, contar
        return listar, adicionar, remover, existe, contar
    except Exception:
        return None, None, None, None, None

def _get_dns():
    try:
        import dns_override
        return dns_override
    except Exception:
        return None

def _get_speedtest():
    try:
        import speedtest as _st
        return _st
    except Exception:
        return None


# ════════════════════════════════════════════════════════
#  FAVORITOS
# ════════════════════════════════════════════════════════

def mostrar_favoritos(srv_idx=None):
    listar, adicionar, remover, existe, contar = _get_favourites()
    if listar is None:
        notificar('Módulo de favoritos indisponível.')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    favs = listar()
    xbmcplugin.setPluginCategory(HANDLE, '⭐  Favoritos ({})'.format(len(favs)))

    if not favs:
        li = xbmcgui.ListItem('(sem favoritos)')
        xbmcplugin.addDirectoryItem(HANDLE, '', li, False)
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    for fav in favs:
        nome  = fav.get('nome', 'Favorito')
        logo  = fav.get('logo', '') or ICON
        fid   = fav.get('id', '')
        tipo  = fav.get('tipo', 'video')
        url_f = fav.get('url', '')

        li = xbmcgui.ListItem(nome)
        li.setArt({'thumb': logo, 'fanart': ''})

        cm = [('Remover dos Favoritos',
               'RunPlugin({}?{})'.format(BASE_URL,
               'acao=fav_remover&fav_id=' + fid + '&fav_nome=' + quote(nome)))]
        li.addContextMenuItems(cm)

        if tipo == 'tvshow':
            li.setInfo('video', {'title': nome, 'mediatype': 'tvshow'})
            xbmcplugin.addDirectoryItem(
                HANDLE,
                url_para({'acao': 'series_temps', 'srv_idx': fav.get('srv_idx', '0'),
                          'series_id': fav.get('series_id', ''), 'serie_nome': nome}),
                li, True
            )
        elif fav.get('cmd'):
            li.setProperty('IsPlayable', 'true')
            li.setInfo('video', {'title': nome, 'mediatype': 'video'})
            xbmcplugin.addDirectoryItem(
                HANDLE,
                url_para({'acao': 'stalker_play', 'srv_idx': fav.get('srv_idx', '0'),
                          'stalker_tipo': fav.get('stalker_tipo', 'itv'),
                          'cmd': fav.get('cmd', ''), 'nome': nome, 'logo': logo}),
                li, False
            )
        else:
            li.setProperty('IsPlayable', 'true')
            li.setInfo('video', {'title': nome, 'mediatype': tipo})
            xbmcplugin.addDirectoryItem(
                HANDLE,
                url_para({'acao': 'play', 'url': url_f, 'nome': nome, 'logo': logo}),
                li, False
            )

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def acao_fav_adicionar(nome, url='', logo='', tipo='video', **kwargs):
    listar, adicionar, remover, existe, contar = _get_favourites()
    if adicionar is None:
        return
    ok = adicionar(nome, url, logo, tipo, **kwargs)
    if ok:
        notificar('⭐  Adicionado aos favoritos', xbmcgui.NOTIFICATION_INFO)
    else:
        notificar('Já está nos favoritos.', xbmcgui.NOTIFICATION_INFO)


def acao_fav_remover(fav_id, fav_nome=''):
    listar, adicionar, remover, existe, contar = _get_favourites()
    if remover is None:
        return
    remover(fav_id)
    notificar('Removido dos favoritos', xbmcgui.NOTIFICATION_INFO)
    xbmc.executebuiltin('Container.Refresh')


# ════════════════════════════════════════════════════════
#  DNS
# ════════════════════════════════════════════════════════

def acao_dns(provider):
    dns = _get_dns()
    if dns is None:
        notificar('Módulo DNS indisponível.')
        return
    if provider == 'sistema':
        dns.deactivate()
        notificar('DNS: sistema', xbmcgui.NOTIFICATION_INFO)
    else:
        dns.activate(provider)
        notificar('DNS: {} activado'.format(provider.upper()), xbmcgui.NOTIFICATION_INFO)
    # Guardar escolha para o servico restaurar no arranque
    try:
        f = xbmcvfs.translatePath('special://temp/ontv_dns_provider.txt')
        with open(f, 'w') as _f:
            _f.write(provider)
    except Exception:
        pass


def mostrar_dns_escolher():
    try:
        from dns_override import DNS_PROVIDERS
        dns     = _get_dns()
        actual  = dns.current_provider() if dns else 'sistema'
    except Exception:
        actual  = 'sistema'
        DNS_PROVIDERS = {'sistema': None, 'adguard': [], 'cloudflare': [], 'opendns': [], 'google': []}

    xbmcplugin.setPluginCategory(HANDLE, '🌐  Escolher DNS')

    labels = {
        'sistema':    '🔘  Sistema (padrão)',
        'adguard':    '🛡️  AdGuard (bloqueia anúncios)',
        'cloudflare': '⚡  Cloudflare (rápido e privado)',
        'opendns':    '🔒  OpenDNS (filtros de segurança)',
        'google':     '🌍  Google DNS',
    }

    for key, label in labels.items():
        prefixo = '✅  ' if key == actual else '   '
        li = xbmcgui.ListItem(prefixo + label)
        li.setArt({'thumb': ICON})
        xbmcplugin.addDirectoryItem(
            HANDLE,
            url_para({'acao': 'dns_activar', 'dns_provider': key}),
            li, False
        )

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


# ════════════════════════════════════════════════════════
#  FERRAMENTAS
# ════════════════════════════════════════════════════════

def mostrar_ferramentas(srv_idx=None):
    dns        = _get_dns()
    dns_activo = dns.current_provider() if dns else 'sistema'
    listar_f, *_ = _get_favourites()
    n_favs     = len(listar_f()) if listar_f else 0

    xbmcplugin.setPluginCategory(HANDLE, '🔧  Ferramentas')

    entradas = [
        ('🌐  DNS: {} (alterar)'.format(dns_activo.upper()),  'dns_escolher'),
        ('⚡  Teste de velocidade',                            'speed_test'),
        ('🗑️  Limpar cache HTTP',                             'limpar_cache'),
        ('🗑️  Limpar cache DNS',                              'limpar_cache_dns'),
        ('⭐  Favoritos ({})'.format(n_favs),                 'favoritos'),
    ]

    for nome, acao_t in entradas:
        li = xbmcgui.ListItem(nome)
        li.setArt({'thumb': ICON})
        params = {'acao': acao_t}
        if srv_idx:
            params['srv_idx'] = srv_idx
        xbmcplugin.addDirectoryItem(HANDLE, url_para(params), li,
                                    acao_t in ('favoritos', 'dns_escolher'))

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def acao_speed_test(url_stream=None):
    st = _get_speedtest()
    if st is None:
        notificar('Módulo de teste de velocidade indisponível.')
        return
    st.mostrar_resultado_kodi(url_stream)


def acao_limpar_cache():
    global _http_mem, _http_disk
    _http_mem  = {}
    _http_disk = {}
    try:
        if os.path.exists(_HTTP_CACHE_FILE):
            os.remove(_HTTP_CACHE_FILE)
    except Exception:
        pass
    try:
        from mediacfg import invalidar_cache
        invalidar_cache()
    except Exception:
        pass
    notificar('Cache limpa.', xbmcgui.NOTIFICATION_INFO)


def acao_limpar_cache_dns():
    dns = _get_dns()
    if dns:
        dns.clear_cache()
        notificar('Cache DNS limpa.', xbmcgui.NOTIFICATION_INFO)


# ════════════════════════════════════════════════════════
#  MENU PRINCIPAL (com Favoritos e Ferramentas)
# ════════════════════════════════════════════════════════

def mostrar_principal():
    from mediacfg import carregar_servidores
    servidores = carregar_servidores()
    xbmcplugin.setPluginCategory(HANDLE, 'OnTV')

    if not servidores:
        notificar('Sem servidores disponíveis. Verifique a ligação.')
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    for i, srv in enumerate(servidores):
        li = xbmcgui.ListItem(srv['nome'])
        li.setArt({'thumb': srv.get('icon') or ICON, 'fanart': FANART})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': 'tipos', 'srv_idx': str(i)}), li, True)

    listar_f, *_ = _get_favourites()
    n_favs = len(listar_f()) if listar_f else 0
    li_fav = xbmcgui.ListItem('⭐  Favoritos ({})'.format(n_favs))
    li_fav.setArt({'thumb': ICON, 'fanart': FANART})
    xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': 'favoritos'}), li_fav, True)

    li_tools = xbmcgui.ListItem('🔧  Ferramentas')
    li_tools.setArt({'thumb': ICON, 'fanart': FANART})
    xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': 'ferramentas'}), li_tools, True)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


# ════════════════════════════════════════════════════════
#  ROTEADOR PRINCIPAL (versao unica, limpa)
# ════════════════════════════════════════════════════════

def run():
    params = dict(parse_qsl(sys.argv[2][1:]))
    acao   = params.get('acao', 'main')
    log('Acao=' + acao)

    acoes_durante_reproducao = (
        'play', 'stalker_play', 'pesquisa',
        'fav_add', 'fav_remover', 'dns_activar',
        'speed_test', 'speed_test_url',
        'limpar_cache', 'limpar_cache_dns',
    )
    if acao not in acoes_durante_reproducao:
        try:
            if xbmc.Player().isPlaying():
                log('A reproduzir — ignorar acao=' + acao)
                xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
                return
        except Exception:
            pass

    if acao in ('play', 'stalker_play'):
        try:
            _stop = xbmcvfs.translatePath('special://temp/ontv_user_stop.flag')
            with open(_stop, 'w') as _f:
                _f.write('1')
        except Exception:
            pass

    # ── Roteamento ────────────────────────────────────────
    if   acao == 'main':             mostrar_principal()
    elif acao == 'tipos':            mostrar_tipos(params['srv_idx'])
    # Xtream
    elif acao == 'live_cats':        mostrar_categorias(params['srv_idx'], 'live_cats')
    elif acao == 'vod_cats':         mostrar_categorias(params['srv_idx'], 'vod_cats')
    elif acao == 'series_cats':      mostrar_categorias(params['srv_idx'], 'series_cats')
    elif acao == 'live_canais':      mostrar_live(params['srv_idx'], params.get('cat_id', ''), params.get('cat_nome', ''))
    elif acao == 'vod_canais':       mostrar_vod(params['srv_idx'], params.get('cat_id', ''), params.get('cat_nome', ''))
    elif acao == 'series_canais':    mostrar_series(params['srv_idx'], params.get('cat_id', ''), params.get('cat_nome', ''))
    elif acao == 'series_temps':     mostrar_temporadas(params['srv_idx'], params.get('series_id', ''), params.get('serie_nome', ''))
    elif acao == 'series_eps':       mostrar_episodios(params['srv_idx'], params.get('series_id', ''), params.get('serie_nome', ''), params.get('temporada'))
    # Stalker/MAC
    elif acao == 'stalker_live':     mostrar_canais_stalker(params['srv_idx'], 'itv',    params.get('cat_id', '*'), params.get('cat_nome', ''))
    elif acao == 'stalker_vod':      mostrar_canais_stalker(params['srv_idx'], 'vod',    params.get('cat_id', '*'), params.get('cat_nome', ''))
    elif acao == 'stalker_series':   mostrar_canais_stalker(params['srv_idx'], 'series', params.get('cat_id', '*'), params.get('cat_nome', ''))
    elif acao == 'stalker_play':     reproduzir_stalker(params['srv_idx'], params.get('stalker_tipo', 'itv'), params.get('cmd', ''), params.get('nome', ''), params.get('logo', ''))
    # M3U
    elif acao == 'm3u_canais':       mostrar_canais_m3u(params['srv_idx'], params.get('grupo', ''))
    # Pesquisa
    elif acao == 'pesquisa':         pesquisar(params['srv_idx'])
    # Play
    elif acao == 'play':             reproduzir(params.get('url', ''), params.get('nome', ''), params.get('logo', ''))
    # Favoritos
    elif acao == 'favoritos':        mostrar_favoritos(params.get('srv_idx'))
    elif acao == 'fav_add':
        acao_fav_adicionar(
            unquote(params.get('fav_nome', '')),
            url=unquote(params.get('fav_url', '')),
            logo=unquote(params.get('fav_logo', '')),
            tipo=params.get('fav_tipo', 'video'),
            srv_idx=params.get('srv_idx', ''),
            series_id=params.get('series_id', ''),
            cmd=unquote(params.get('cmd', '')),
            stalker_tipo=params.get('stalker_tipo', ''),
        )
    elif acao == 'fav_remover':      acao_fav_remover(params.get('fav_id', ''), unquote(params.get('fav_nome', '')))
    # Ferramentas
    elif acao == 'ferramentas':      mostrar_ferramentas(params.get('srv_idx'))
    elif acao == 'dns_escolher':     mostrar_dns_escolher()
    elif acao == 'dns_activar':      acao_dns(params.get('dns_provider', 'sistema'))
    elif acao == 'speed_test':       acao_speed_test()
    elif acao == 'speed_test_url':   acao_speed_test(params.get('fav_url', ''))
    elif acao == 'limpar_cache':     acao_limpar_cache()
    elif acao == 'limpar_cache_dns': acao_limpar_cache_dns()
    else:                            mostrar_principal()
