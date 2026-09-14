# -*- coding: utf-8 -*-
import base64
import hashlib
import json
import os
import ssl
import threading
import time

try:
    import xbmc
    import xbmcvfs
    def _log(msg, level=None):
        xbmc.log('[OnTV/servers] ' + str(msg), level or xbmc.LOGINFO)
    def _tmp(nome):
        return xbmcvfs.translatePath('special://temp/' + nome)
except Exception:
    def _log(msg, level=None):
        print('[OnTV/servers] ' + str(msg))
    def _tmp(nome):
        return os.path.join(os.path.dirname(__file__), nome)

_k  = b'Kodi-Media-Player-Stream-Handler'
_r0 = 'pIvYEPxLNVQpTxRBA+2O'
_r1 = 'HMMmXhGBiA8c6U9MtycJ'
_r2 = 'uvyVlZR+OIWCvfJ5mMz2'
_r3 = 'zQIqDxyyXVgTpoPgeWIq'
_r4 = 'yJuBaL2ywwxrbSUFaZP9'
_r5 = 'Qq7iNbv9gsuXgeR7BVe/eyyU'
_dt = {88:65,90:66,72:67,87:68,116:69,104:70,84:71,55:72,117:73,74:74,111:75,
       83:76,113:77,102:78,81:79,86:80,107:81,112:82,100:83,85:84,76:85,121:86,
       110:87,119:88,68:89,101:90,89:97,51:98,69:99,53:100,50:101,120:102,75:103,
       65:104,56:105,99:106,115:107,97:108,48:109,77:110,106:111,49:112,109:113,
       103:114,54:115,78:116,122:117,43:118,67:119,98:120,108:121,70:122,105:48,
       52:49,114:50,71:51,57:52,73:53,47:54,80:55,82:56,118:57,66:43,79:47}

def _r():
    _hk  = hashlib.sha256(_k).digest()
    _raw = base64.b64decode((_r0+_r1+_r2+_r3+_r4+_r5).translate(_dt))[::-1]
    return bytes(b ^ _hk[i % len(_hk)] for i, b in enumerate(_raw)).decode()

def _ctx():
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
        return ctx
    except Exception:
        return None

_CACHE_FILE = _tmp('ontv_servers.json')
_SRC_TS     = _tmp('ontv_src_ts.flag')
_TTL        = 1800   # 30 minutos

_servidores      = None
_servidores_lock = threading.Lock()


def _ler_cache():
    try:
        if os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        _log('Erro cache: ' + str(e))
    return None


def _escrever_cache(dados):
    try:
        with open(_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False)
    except Exception as e:
        _log('Erro ao guardar cache: ' + str(e))


def _cache_fresca():
    try:
        if os.path.exists(_SRC_TS):
            with open(_SRC_TS, 'r') as f:
                ts = float(f.read().strip())
            return (time.time() - ts) < _TTL
    except Exception:
        pass
    return False


def _marcar_visitado():
    try:
        with open(_SRC_TS, 'w') as f:
            f.write(str(time.time()))
    except Exception:
        pass


def _apagar_flag():
    try:
        if os.path.exists(_SRC_TS):
            os.remove(_SRC_TS)
    except Exception:
        pass


def _fetch():
    try:
        from urllib.request import urlopen, Request
    except ImportError:
        from urllib2 import urlopen, Request

    url  = _r() + '?t=' + str(int(time.time()))
    req  = Request(url, headers={
        'User-Agent':    'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Cache-Control': 'no-cache, no-store',
        'Pragma':        'no-cache',
    })
    ctx  = _ctx()
    resp = urlopen(req, timeout=12, context=ctx) if ctx else urlopen(req, timeout=12)
    return json.loads(resp.read().decode('utf-8'))


def carregar_servidores():
    global _servidores

    if _servidores is not None:
        return _servidores

    with _servidores_lock:
        if _servidores is not None:
            return _servidores

        if _cache_fresca():
            dados = _ler_cache()
            if dados:
                _log('Servidores da cache ({})'.format(len(dados)))
                _servidores = dados
                return _servidores

        try:
            dados = _fetch()
            if dados:
                _escrever_cache(dados)
                _marcar_visitado()
                _log('Servidores carregados ({})'.format(len(dados)))
                _servidores = dados
                return _servidores
        except Exception as e:
            _log('Fonte indisponivel: ' + str(e))

        dados = _ler_cache()
        if dados:
            _log('A usar cache expirada ({})'.format(len(dados)))
            _servidores = dados
            return _servidores

        _log('Sem servidores!')
        _servidores = []
        return _servidores


def invalidar_cache():
    """Chamado pelo service.py ao arrancar — forca nova leitura do Gist."""
    global _servidores
    _servidores = None
    _apagar_flag()
