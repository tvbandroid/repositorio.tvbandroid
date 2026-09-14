# -*- coding: utf-8 -*-
# Proxy OnTV v1.0.7 — inspirado no Eagle TV 1.1.4 proxy.py
# Melhorias criticas:
#   - ThreadingMixIn: servidor multi-threaded (cada canal numa thread)
#   - generate_ts(): generator continuo com while True + reconexao automatica
#   - stop_ts flag: detecta desconexao do Kodi limpo
#   - IP_CACHE_TS: cache dos ultimos chunks para replay na reconexao
#   - ts_max_retries=999999: reconecta indefinidamente (como Eagle TV)
#   - broken pipe detection: para limpo quando Kodi fecha
#   - _smart_retry_delay: backoff inteligente por tipo de erro

import binascii
import os
import re
import threading
import time

try:
    import xbmc
    def _plog(msg):
        xbmc.log('[OnTV/proxy] ' + str(msg), xbmc.LOGINFO)
except Exception:
    def _plog(msg):
        pass

try:
    import requests
    from requests.exceptions import ConnectionError as ReqConnError
    from requests.exceptions import RequestException, ReadTimeout, ChunkedEncodingError
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    class RequestException(Exception): pass
    class ReqConnError(RequestException): pass
    class ReadTimeout(RequestException): pass
    class ChunkedEncodingError(RequestException): pass

try:
    from http.server  import BaseHTTPRequestHandler, HTTPServer
    from socketserver import ThreadingMixIn
    from urllib.parse import urlparse, unquote, quote_plus, unquote_plus, urljoin
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from SocketServer   import ThreadingMixIn
    from urlparse       import urlparse, unquote, urljoin
    from urllib         import quote_plus, unquote_plus

try:
    from urllib.request import urlopen, Request as URequest
except ImportError:
    from urllib2 import urlopen, Request as URequest

try:
    from http.client import IncompleteRead
except ImportError:
    class IncompleteRead(Exception): pass

HOST       = '127.0.0.1'
PORT       = 52315
CHUNK_SIZE = 4096   # Eagle TV usa 4096

UA_DEFAULT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
              'AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/120.0.0.0 Safari/537.36')

UA_POOL = [
    UA_DEFAULT,
    'Mozilla/5.0 (Linux; Android 10; SM-A505G) AppleWebKit/537.36 Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'ExoPlayerLib/2.18.7',
]

# Cache dos ultimos chunks por IP — replay na reconexao
IP_CACHE_TS = {}

_lock        = threading.Lock()
_stop_flag   = False
_cur_url     = ''
GLOBAL_HEADERS = {}
HTTPS_PORT   = False
STOP_SERVER  = False


def _set_stop(val):
    global _stop_flag, STOP_SERVER
    with _lock:
        _stop_flag  = val
        STOP_SERVER = val

def _is_stopped():
    with _lock:
        return _stop_flag

def _set_url(url):
    global _cur_url
    with _lock:
        _cur_url = url

def _get_url():
    with _lock:
        return _cur_url


def _smart_retry_delay(err_kind, attempt):
    """Identico ao Eagle TV — backoff por tipo de erro."""
    if err_kind == '406':
        return min(0.45, 0.08 * max(1, attempt))
    if err_kind == 'timeout':
        return min(1.0, 0.20 * max(1, attempt))
    if err_kind == 'connection':
        return min(0.8, 0.16 * max(1, attempt))
    return min(0.75, 0.14 * max(1, attempt))


def _pick_ua(reconnects=0):
    if reconnects >= 3:
        return 'Lavf/60.3.100'
    return UA_POOL[reconnects % len(UA_POOL)]


def _is_m3u8_url(url):
    return '.m3u8' in url or ('/hl' in url and not url.endswith('.ts'))


def _basename(p):
    i = p.rfind('/') + 1
    return p[i:]


def get_headers(url):
    global GLOBAL_HEADERS
    try:
        url = url.split('url=')[1]
    except Exception:
        pass
    data = {'User-Agent': UA_DEFAULT, 'Connection': 'keep-alive',
            'Accept': '*/*', 'Accept-Encoding': 'identity'}
    if '|' in url or '&' in url or 'h123' in url:
        def _get(key):
            try:
                val = url.split(key + '=')[1]
                try: val = val.split('&')[0]
                except Exception: pass
                return unquote_plus(val)
            except Exception:
                return None
        for k, fn in [('Referer', 'Referer'), ('Origin', 'Origin'),
                      ('Cookie', 'Cookie'), ('User-Agent', 'User-Agent')]:
            v = _get(k)
            if v:
                data[fn] = v
        GLOBAL_HEADERS = data
    if not GLOBAL_HEADERS:
        GLOBAL_HEADERS = data


def convert_to_m3u8(url):
    if '|' in url:
        url = url.split('|')[0]
    elif '&h123' in url:
        url = url.split('&h123')[0]
    if '.m3u8' not in url and '/hl' not in url             and url.count(':') == 2 and url.count('/') > 4:
        try:
            parsed = urlparse(url)
            host1  = '{}://{}'.format(parsed.scheme, parsed.netloc)
            host2  = url.split(host1)[1]
            # Correcao do bug /live/live: so adicionar /live se nao existir ja
            if not host2.startswith('/live'):
                url = host1 + '/live' + host2
            else:
                url = host1 + host2
            fname = _basename(url)
            if '.ts' in fname:
                url = url.replace(fname, fname.replace('.ts', '.m3u8'))
            elif not fname.endswith('.m3u8'):
                url = url.replace(fname, fname + '.m3u8')
        except Exception:
            pass
    return url


def prepare_url(url):
    try: url = unquote_plus(url)
    except Exception: pass
    try: url = unquote(url)
    except Exception: pass
    url = url.replace('|', '&h123=true&')
    url = quote_plus(url)
    return 'http://{}:{}/?url={}'.format(HOST, PORT, url)


def _renovar_stalker_url():
    try:
        import json as _json, os as _os
        try:
            import xbmcvfs as _xv
            sfile = _xv.translatePath('special://temp/ontv_stalker_stream.json')
        except Exception:
            import tempfile
            sfile = _os.path.join(tempfile.gettempdir(), 'ontv_stalker_stream.json')
        if not _os.path.exists(sfile):
            return None
        with open(sfile, 'r', encoding='utf-8') as f:
            info = _json.load(f)
        if info.get('tipo') != 'stalker':
            return None
        import sys
        _lib = _os.path.dirname(__file__)
        if _lib not in sys.path:
            sys.path.insert(0, _lib)
        from navigator import stalker_create_link
        new_url = stalker_create_link(
            info['host'], info['mac'],
            info['stalker_tipo'], info['cmd']
        )
        if new_url and new_url.startswith('http'):
            _set_url(new_url)
            return new_url
    except Exception:
        pass
    return None


def _rewrite_m3u8(text, proxy_base, base_url):
    def replace_url(m):
        seg = m.group(0).strip()
        if seg.startswith('#') or not seg:
            return seg
        abs_url = urljoin(base_url + '/', seg)
        return proxy_base + '/?url=' + quote_plus(abs_url)
    return re.sub(r'^(?!#)\S+', replace_url, text, flags=re.MULTILINE)


class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Identico ao Eagle TV — cada pedido numa thread separada."""
    daemon_threads = True
    allow_reuse_address = True


class _Handler(BaseHTTPRequestHandler):

    def handle(self):
        try:
            BaseHTTPRequestHandler.handle(self)
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass

    def finish(self):
        try:
            BaseHTTPRequestHandler.finish(self)
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass

    def log_message(self, fmt, *args):
        pass

    def _parse_url(self):
        try:
            raw = self.path.split('url=')[1]
            try: return unquote_plus(raw)
            except Exception: return unquote(raw)
        except Exception:
            return ''

    def do_HEAD(self):
        # HEAD nunca contacta o servidor remoto — apenas confirma que o
        # proxy esta vivo. Responde sempre como video/mp2t, porque o
        # conteudo real (m3u8 com fallback para ts, ou ts directo) so
        # e decidido no GET. Anunciar application/vnd.apple.mpegurl no
        # HEAD quando o GET pode acabar a servir .ts confunde o demuxer
        # do Kodi (causa observada: MSGQ_NOT_INITIALIZED + EOF imediato).
        if _is_stopped() or STOP_SERVER:
            self.send_response(503); self.end_headers(); return
        self.send_response(200)
        self.send_header('Content-Type', 'video/mp2t')
        self.send_header('Connection', 'close')
        self.end_headers()

    def do_GET(self):
        self._route('GET')

    def _route(self, method):
        global GLOBAL_HEADERS, HTTPS_PORT, STOP_SERVER
        if _is_stopped() or STOP_SERVER:
            self.send_response(503); self.end_headers(); return

        if self.path == '/check':
            self.send_response(200); self.end_headers(); return
        if self.path == '/stop':
            self.send_response(200); self.end_headers()
            _set_stop(True)
            t = threading.Thread(target=self.server.shutdown)
            t.daemon = True; t.start()
            return

        url = self._parse_url()
        if not url or not url.startswith('http'):
            url = _get_url()
        if not url:
            self.send_response(404); self.end_headers(); return

        if not GLOBAL_HEADERS:
            get_headers(url)

        url_original = url
        url = convert_to_m3u8(url)

        if ':443' in url or url.startswith('https://'):
            HTTPS_PORT = True

        proxy_base = 'http://{}:{}'.format(HOST, PORT)

        if _is_m3u8_url(url) and url != url_original:
            _plog('Xtream convertido: {} -> tentando m3u8 com fallback .ts'.format(method))
            self._serve_m3u8(url, method, proxy_base, fallback_ts=url_original)
        elif _is_m3u8_url(url):
            _plog('M3U8 directo: ' + method)
            self._serve_m3u8(url, method, proxy_base)
        else:
            _plog('TS directo: ' + method)
            self._serve_ts(url, method)

    def _serve_m3u8(self, url, method, proxy_base, fallback_ts=None):
        global GLOBAL_URL, HTTPS_PORT
        # Apenas 1 tentativa rapida (timeout curto) quando ha fallback —
        # se o servidor Xtream nao suportar HLS, cai para .ts em <2s
        # em vez de esperar 12s+ (3 tentativas x 4s) antes de desistir.
        max_tries  = 1 if fallback_ts else 20
        # timeout=(connect, read) — separa tempo de ligacao do tempo de
        # leitura. Sem isto, requests aplica o mesmo valor a cada fase,
        # e ligacoes que ficam "hanging" (sem erro nem resposta) podem
        # nunca atingir o timeout esperado.
        req_timeout = (1.5, 2.5) if fallback_ts else (3, 4)
        _plog('M3U8 a tentar: {} (fallback={})'.format(url[:70], bool(fallback_ts)))
        for i in range(max_tries):
            if _is_stopped(): break
            try:
                if HAS_REQUESTS:
                    r        = requests.get(url, headers=GLOBAL_HEADERS, timeout=req_timeout, verify=False)
                    last_url = r.url
                    text_    = r.text
                    status   = r.status_code
                    r.close()
                else:
                    resp     = urlopen(URequest(url, headers=GLOBAL_HEADERS), timeout=req_timeout[1])
                    last_url = url
                    text_    = resp.read().decode('utf-8', errors='replace')
                    status   = resp.status
                    resp.close()

                _plog('M3U8 resposta status={} len={}'.format(status, len(text_) if text_ else 0))

                r_parse  = urlparse(last_url)
                base_url = ('https://' if HTTPS_PORT else 'http://') + r_parse.netloc

                if status == 200 and '#EXTM3U' in text_:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/vnd.apple.mpegurl')
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    if method != 'HEAD':
                        if 'chunklist_' in text_ and 'http' not in text_:
                            fname     = _basename(url)
                            base_url2 = url.replace(fname, '').rstrip('/')
                            text_ = text_.replace('chunklist_', proxy_base + '/?url=' + base_url2 + '/chunklist_')
                        elif 'media_' in text_ and '.ts' in text_ and 'http' not in text_:
                            fname     = _basename(url)
                            base_url2 = url.replace(fname, '').rstrip('/')
                            text_ = text_.replace('media_', proxy_base + '/?url=' + base_url2 + '/media_')
                        elif '/hl' in text_ and 'http' not in text_:
                            text_ = text_.replace('/hl', proxy_base + '/?url=' + base_url + '/hl')
                        elif 'http' not in text_:
                            fname = _basename(last_url)
                            GLOBAL_URL = last_url.replace(fname, '')
                            base_seg   = last_url.rsplit('/', 1)[0]
                            text_      = _rewrite_m3u8(text_, proxy_base, base_seg)
                        else:
                            text_ = text_.replace('http', proxy_base + '/?url=http')
                        self.wfile.write(text_.encode('utf-8'))
                    return
                # Resposta nao e um manifesto HLS valido (404, html, etc.)
                _plog('M3U8 sem #EXTM3U valido — a cair para fallback')
                break
            except Exception as e:
                _plog('M3U8 excepcao: ' + str(e)[:120])
            if _is_stopped(): break
            if fallback_ts:
                break   # 1 unica tentativa — cair para .ts imediatamente
            else:
                time.sleep(3)

        # Esgotou tentativas — cair para .ts original (servidor Xtream
        # sem suporte HLS) em vez de devolver 404 e fechar o stream
        if fallback_ts and not _is_stopped():
            _plog('M3U8 falhou — fallback para .ts: ' + fallback_ts[:60])
            self._serve_ts(fallback_ts, method)
            return
        try:
            self.send_response(404); self.end_headers()
        except Exception:
            pass

    def _serve_ts(self, url, method):
        """
        Identico ao _handle_tsdownloader() do Eagle TV:
        - generate_ts() com while True + reconexao automatica indefinida
        - stop_ts flag para detectar desconexao do Kodi
        - IP_CACHE_TS para replay na reconexao
        - broken pipe detection
        """
        client_ip  = self.client_address[0] if self.client_address else '127.0.0.1'
        cache_key  = client_ip
        stop_ts    = [False]
        reconnects = [0]
        last_status = [None]
        current_url = [url]   # lista para permitir mutacao dentro da closure

        if HAS_REQUESTS:
            session = requests.Session()
        else:
            session = None

        def generate_ts():
            consecutive_fails = 0
            max_initial_fails = 8   # desistir apos 8 falhas seguidas sem nunca ter dados
            got_data_ever = False

            while not stop_ts[0] and not _is_stopped():
                if not got_data_ever and consecutive_fails >= max_initial_fails:
                    _plog('TS: {} falhas consecutivas sem dados — a desistir'.format(consecutive_fails))
                    return
                response = None
                try:
                    hdrs = dict(GLOBAL_HEADERS)
                    hdrs['User-Agent'] = _pick_ua(reconnects[0])
                    if reconnects[0] > 0:
                        hdrs['Connection'] = 'close'
                        hdrs.pop('Accept-Encoding', None)

                    if HAS_REQUESTS:
                        response = session.get(
                            current_url[0], headers=hdrs, stream=True,
                            verify=False,
                            timeout=(5, 15 if reconnects[0] == 0 else 20)
                        )
                        status_code = response.status_code
                        last_status[0] = status_code
                        _plog('TS GET status={} tentativa={} url={}'.format(
                            status_code, consecutive_fails, current_url[0][:70]))

                        if status_code in (401, 403, 404):
                            response.close()
                            renewed = _renovar_stalker_url()
                            if renewed:
                                current_url[0] = renewed   # actualizar URL na closure
                                reconnects[0] = 0
                            else:
                                reconnects[0] += 1
                            time.sleep(_smart_retry_delay('connection', reconnects[0]))
                            continue

                        if status_code == 200:
                            reconnects[0] = 0
                            consecutive_fails = 0
                            for chunk in response.iter_content(CHUNK_SIZE):
                                if stop_ts[0] or _is_stopped():
                                    return
                                if not chunk:
                                    continue
                                got_data_ever = True
                                # Cache dos ultimos chunks para replay
                                IP_CACHE_TS.setdefault(cache_key, []).append(chunk)
                                if len(IP_CACHE_TS[cache_key]) > 20:
                                    IP_CACHE_TS[cache_key].pop(0)
                                yield chunk
                        else:
                            reconnects[0] += 1
                            consecutive_fails += 1
                            time.sleep(_smart_retry_delay('connection', reconnects[0]))
                    else:
                        # Fallback sem requests
                        resp = urlopen(URequest(current_url[0], headers=hdrs), timeout=10)
                        if resp.status == 200:
                            reconnects[0] = 0
                            consecutive_fails = 0
                            while not stop_ts[0] and not _is_stopped():
                                chunk = resp.read(CHUNK_SIZE)
                                if not chunk:
                                    break
                                got_data_ever = True
                                IP_CACHE_TS.setdefault(cache_key, []).append(chunk)
                                if len(IP_CACHE_TS[cache_key]) > 20:
                                    IP_CACHE_TS[cache_key].pop(0)
                                yield chunk
                        else:
                            consecutive_fails += 1
                        resp.close()

                except (ReadTimeout, ChunkedEncodingError, IncompleteRead) as e:
                    reconnects[0] += 1
                    if not got_data_ever:
                        consecutive_fails += 1
                    # Replay cache durante reconexao
                    for chunk in IP_CACHE_TS.get(cache_key, [])[-5:]:
                        if not stop_ts[0]:
                            yield chunk
                    time.sleep(_smart_retry_delay('timeout', reconnects[0]))

                except ReqConnError as e:
                    reconnects[0] += 1
                    if not got_data_ever:
                        consecutive_fails += 1
                    time.sleep(_smart_retry_delay('connection', reconnects[0]))

                except GeneratorExit:
                    stop_ts[0] = True
                    return

                except Exception as e:
                    msg = str(e).lower()
                    _plog('TS excepcao: ' + str(e)[:120])
                    if 'broken pipe' in msg or 'connection reset' in msg:
                        stop_ts[0] = True
                        return
                    reconnects[0] += 1
                    if not got_data_ever:
                        consecutive_fails += 1
                    time.sleep(_smart_retry_delay('connection', reconnects[0]))

                finally:
                    if response is not None:
                        try: response.close()
                        except Exception: pass

        if method == 'HEAD':
            self.send_response(200)
            self.send_header('Content-Type', 'video/mp2t')
            self.send_header('Connection', 'close')
            self.end_headers()
            stop_ts[0] = True
            if session:
                try: session.close()
                except Exception: pass
            return

        # CRITICO: so enviar os headers HTTP (200 OK) depois de confirmar
        # que ha pelo menos 1 chunk de dados disponivel. Enviar 200 sem
        # dados faz o VideoPlayer do Kodi receber EOF imediato e desistir
        # em menos de 2 segundos (visto nos logs), mesmo que o proxy ainda
        # esteja a tentar reconectar/fallback em segundo plano.
        gen = generate_ts()
        headers_sent = False
        try:
            for chunk in gen:
                if not headers_sent:
                    self.send_response(200)
                    self.send_header('Content-Type', 'video/mp2t')
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    headers_sent = True
                try:
                    self.wfile.write(chunk)
                except Exception:
                    stop_ts[0] = True
                    return
            # Generator terminou sem nunca produzir dados — falhou de vez
            if not headers_sent:
                try:
                    self.send_response(502)
                    self.end_headers()
                except Exception:
                    pass
        finally:
            stop_ts[0] = True
            if session:
                try: session.close()
                except Exception: pass


# ── Gestao do servidor ─────────────────────────────────────────────────────

_server_instance = None
_server_thread   = None


def _serve(httpd):
    try:
        httpd.serve_forever(poll_interval=0.2)
    except Exception:
        pass
    finally:
        try: httpd.server_close()
        except Exception: pass


def in_use():
    try:
        import socket as _s
        s = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
        s.settimeout(0.35)
        result = s.connect_ex((HOST, PORT)) == 0
        s.close()
        return result
    except Exception:
        return False


def _req_shutdown():
    try:
        if HAS_REQUESTS:
            r = requests.get('http://{}:{}/stop'.format(HOST, PORT), timeout=2)
            r.close()
        else:
            resp = urlopen(URequest('http://{}:{}/stop'.format(HOST, PORT)), timeout=2)
            resp.close()
    except Exception:
        pass


def start(url):
    global _server_instance, _server_thread, GLOBAL_HEADERS
    _set_stop(False)
    _set_url(url)
    GLOBAL_HEADERS = {}
    get_headers(url)

    if in_use():
        return prepare_url(url)

    if _server_thread and _server_thread.is_alive():
        return prepare_url(url)

    try:
        _server_instance = _ThreadedHTTPServer((HOST, PORT), _Handler)
    except Exception:
        stop()
        time.sleep(1)
        try:
            _server_instance = _ThreadedHTTPServer((HOST, PORT), _Handler)
        except Exception:
            return url

    _server_thread = threading.Thread(target=_serve, args=(_server_instance,))
    _server_thread.daemon = True
    _server_thread.start()

    # Espera activa — funciona em dispositivos lentos e rapidos
    for _ in range(40):
        if in_use():
            break
        time.sleep(0.1)

    return prepare_url(url)


def stop():
    global _server_instance, _server_thread
    _set_stop(True)
    t = threading.Thread(target=_req_shutdown)
    t.daemon = True; t.start(); t.join(timeout=3)
    try:
        if _server_instance:
            _server_instance.shutdown()
            _server_instance.server_close()
    except Exception:
        pass
    _server_instance = None
    _server_thread   = None


def is_running():
    return in_use()


def update_url(url):
    _set_url(url)
