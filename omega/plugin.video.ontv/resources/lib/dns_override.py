# -*- coding: utf-8 -*-
"""
OnTV — Override de DNS  v1.0.4

Substitui o resolver de sistema por DNS personalizados
(AdGuard, Cloudflare, OpenDNS, Google) para contornar bloqueios DNS
que impedem o acesso a servidores IPTV.

Inspirado no módulo dns.py do Eagle TV Online, reescrito sem
dependências externas (sem kodi_six, sem requests).

Funcionamento:
  - Intercepta socket.getaddrinfo com um resolver DNS-over-UDP
  - Cache em disco com TTL de 1 hora
  - Activado/desactivado pela definição dns_provider nas settings
  - Suporte a IPv4 apenas (o IPTV não precisa de IPv6)
"""

import socket
import struct
import random
import os
import json
import time
import threading

try:
    import xbmc
    import xbmcaddon
    import xbmcvfs
    def _log(msg, level=None):
        xbmc.log('[OnTV/dns] ' + str(msg), level or xbmc.LOGINFO)
    def _profile():
        return xbmcvfs.translatePath('special://temp/')
except Exception:
    def _log(msg, level=None):
        print('[OnTV/dns] ' + msg)
    def _profile():
        return os.path.dirname(__file__)

# ── Servidores DNS disponíveis ─────────────────────────────────────────────

DNS_PROVIDERS = {
    'sistema':    None,                        # desactivado — usar DNS do SO
    'adguard':    ['94.140.14.140', '94.140.14.141'],
    'cloudflare': ['1.1.1.1', '1.0.0.1'],
    'opendns':    ['208.67.222.222', '208.67.220.220'],
    'google':     ['8.8.8.8', '8.8.4.4'],
}

_CACHE_FILE = os.path.join(_profile(), 'ontv_dns_cache.json')
_CACHE_TTL  = 3600   # 1 hora
_TIMEOUT    = 3      # segundos por tentativa DNS

_state = {
    'installed':           False,
    'original_getaddrinfo': None,
    'servers':             [],
    'cache':               {},
    'lock':                threading.Lock(),
}


# ── Persistência da cache ──────────────────────────────────────────────────

def _load_cache():
    try:
        if os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE, 'r') as f:
                raw = json.load(f)
            # Remover entradas expiradas
            now = time.time()
            return {k: v for k, v in raw.items() if now - v.get('ts', 0) < _CACHE_TTL}
    except Exception:
        pass
    return {}

def _save_cache():
    try:
        with _state['lock']:
            with open(_CACHE_FILE, 'w') as f:
                json.dump(_state['cache'], f)
    except Exception:
        pass


# ── Resolver DNS-over-UDP ──────────────────────────────────────────────────

def _build_query(hostname):
    """Constrói pacote de query DNS tipo A (IPv4)."""
    txid   = random.randint(0, 65535)
    header = struct.pack('!HHHHHH', txid, 0x0100, 1, 0, 0, 0)
    parts  = hostname.rstrip('.').split('.')
    qname  = b''
    for p in parts:
        enc = p.encode('ascii', errors='replace')
        qname += struct.pack('!B', len(enc)) + enc
    qname  += b'\x00'
    qtype   = struct.pack('!HH', 1, 1)   # A, IN
    return header + qname + qtype, txid

def _parse_answer(data, txid):
    """Extrai endereços IPv4 de uma resposta DNS."""
    if len(data) < 12:
        return []
    rtxid, flags, qdcount, ancount = struct.unpack('!HHHH', data[:8])
    if rtxid != txid or ancount == 0:
        return []

    # Saltar a secção de perguntas
    pos = 12
    for _ in range(qdcount):
        while pos < len(data):
            length = data[pos]
            if length == 0:
                pos += 1
                break
            if length >= 0xC0:   # ponteiro de compressão
                pos += 2
                break
            pos += 1 + length
        pos += 4   # QTYPE + QCLASS

    ips = []
    for _ in range(ancount):
        if pos >= len(data):
            break
        # Saltar nome (pode ser ponteiro)
        if pos < len(data) and data[pos] >= 0xC0:
            pos += 2
        else:
            while pos < len(data) and data[pos] != 0:
                pos += 1 + data[pos]
            pos += 1
        if pos + 10 > len(data):
            break
        rtype, _, _, rdlen = struct.unpack('!HHIH', data[pos:pos+10])
        pos += 10
        if rtype == 1 and rdlen == 4 and pos + 4 <= len(data):
            ips.append(socket.inet_ntoa(data[pos:pos+4]))
        pos += rdlen
    return ips

def _udp_resolve(hostname, servers):
    """Consulta servidores DNS por UDP. Devolve lista de IPs ou []."""
    query, txid = _build_query(hostname)
    for server in servers:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(_TIMEOUT)
            sock.sendto(query, (server, 53))
            data, _ = sock.recvfrom(512)
            sock.close()
            ips = _parse_answer(data, txid)
            if ips:
                return ips
        except Exception:
            try:
                sock.close()
            except Exception:
                pass
    return []


# ── Interceptor de socket.getaddrinfo ─────────────────────────────────────

def _custom_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """Substitui socket.getaddrinfo usando DNS personalizado com cache."""
    # Não interceptar IPs literais nem localhost
    try:
        socket.inet_aton(str(host))
        return _state['original_getaddrinfo'](host, port, family, type, proto, flags)
    except Exception:
        pass
    if str(host) in ('localhost', '127.0.0.1', '::1'):
        return _state['original_getaddrinfo'](host, port, family, type, proto, flags)

    # Verificar cache em memória
    key = str(host)
    with _state['lock']:
        entry = _state['cache'].get(key)
        if entry and time.time() - entry['ts'] < _CACHE_TTL:
            ips = entry['ips']
        else:
            ips = None

    if ips is None:
        ips = _udp_resolve(host, _state['servers'])
        if ips:
            with _state['lock']:
                _state['cache'][key] = {'ips': ips, 'ts': time.time()}
            # Guardar em background para não bloquear
            t = threading.Thread(target=_save_cache)
            t.daemon = True
            t.start()

    if ips:
        results = []
        for ip in ips:
            try:
                results.append((socket.AF_INET, socket.SOCK_STREAM, proto, '', (ip, port or 0)))
            except Exception:
                pass
        if results:
            return results

    # Fallback para resolver do sistema
    return _state['original_getaddrinfo'](host, port, family, type, proto, flags)


# ── API pública ────────────────────────────────────────────────────────────

def activate(provider='adguard'):
    """
    Activa o override de DNS com o fornecedor indicado.
    provider deve ser uma chave de DNS_PROVIDERS.
    Se provider=='sistema', desactiva o override.
    """
    servers = DNS_PROVIDERS.get(provider)
    if not servers:
        deactivate()
        return

    _state['servers'] = servers
    _state['cache']   = _load_cache()

    if not _state['installed']:
        _state['original_getaddrinfo'] = socket.getaddrinfo
        socket.getaddrinfo = _custom_getaddrinfo
        _state['installed'] = True
        _log('DNS override activado: {} → {}'.format(provider, servers))
    else:
        _log('DNS override já activo, servidores actualizados: {}'.format(servers))


def deactivate():
    """Restaura o resolver DNS do sistema."""
    if _state['installed'] and _state['original_getaddrinfo']:
        socket.getaddrinfo = _state['original_getaddrinfo']
        _state['installed'] = False
        _log('DNS override desactivado')


def is_active():
    return _state['installed']


def current_provider():
    """Devolve o nome do fornecedor activo, ou 'sistema'."""
    if not _state['installed']:
        return 'sistema'
    for name, servers in DNS_PROVIDERS.items():
        if servers and set(servers) == set(_state.get('servers', [])):
            return name
    return 'personalizado'


def clear_cache():
    """Limpa a cache DNS em memória e em disco."""
    with _state['lock']:
        _state['cache'] = {}
    try:
        if os.path.exists(_CACHE_FILE):
            os.remove(_CACHE_FILE)
        _log('Cache DNS limpa')
    except Exception:
        pass
