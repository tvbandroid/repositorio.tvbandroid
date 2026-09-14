# -*- coding: utf-8 -*-
"""
OnTV — Teste de Velocidade  v1.0.4

Mede a velocidade de download e latência de um servidor IPTV (ou URL genérico).
Sem dependências externas — usa apenas stdlib Python.

Inspirado na abordagem do Eagle TV Online (speedtest.py), mas mais simples
e focado em servidores IPTV em vez de servidores speedtest dedicados.
"""

import time
import threading

try:
    from urllib.request import urlopen, Request
    from urllib.error   import URLError
except ImportError:
    from urllib2 import urlopen, Request, URLError  # type: ignore

try:
    import xbmc
    import xbmcgui
    import xbmcaddon
    _ADDON_NAME = xbmcaddon.Addon().getAddonInfo('name')
    def _log(msg):
        xbmc.log('[OnTV/speedtest] ' + str(msg), xbmc.LOGINFO)
except Exception:
    _ADDON_NAME = 'OnTV'
    def _log(msg):
        print('[OnTV/speedtest] ' + str(msg))

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

# URLs de referência para teste genérico (ficheiros ~1MB de CDNs públicos)
_TEST_URLS = [
    'http://speedtest.tele2.net/1MB.zip',
    'http://ipv4.download.thinkbroadband.com/1MB.zip',
]

_CHUNK     = 65536   # 64 KB por iteração de leitura
_DURATION  = 5       # segundos máximos de descarga por teste
_TIMEOUT   = 8       # timeout de ligação


def _medir_latencia(host, porta=80):
    """Mede o tempo de ligação TCP ao host:porta em ms."""
    import socket
    try:
        t0 = time.time()
        s  = socket.create_connection((host, porta), timeout=5)
        ms = (time.time() - t0) * 1000
        s.close()
        return round(ms, 1)
    except Exception:
        return None


def _medir_download(url, duracao=_DURATION):
    """
    Faz download parcial de url durante 'duracao' segundos.
    Devolve (velocidade_Mbps, bytes_recebidos) ou (None, 0) em erro.
    """
    try:
        req  = Request(url, headers={'User-Agent': UA, 'Accept-Encoding': 'identity'})
        resp = urlopen(req, timeout=_TIMEOUT)
        total = 0
        t0    = time.time()
        while True:
            elapsed = time.time() - t0
            if elapsed >= duracao:
                break
            chunk = resp.read(_CHUNK)
            if not chunk:
                break
            total += len(chunk)
        resp.close()
        elapsed = max(time.time() - t0, 0.001)
        mbps    = round((total * 8) / (elapsed * 1_000_000), 2)
        return mbps, total
    except Exception as e:
        _log('Erro download: ' + str(e))
        return None, 0


def testar_servidor(url_stream):
    """
    Testa latência e velocidade de um URL de stream IPTV.
    Devolve dict: {'latencia_ms': float|None, 'velocidade_mbps': float|None, 'erro': str|None}
    """
    try:
        from urllib.parse import urlparse
    except ImportError:
        from urlparse import urlparse  # type: ignore

    parsed = urlparse(url_stream)
    host   = parsed.hostname
    porta  = parsed.port or (443 if parsed.scheme == 'https' else 80)

    _log('Teste servidor: {}:{}'.format(host, porta))
    resultado = {'latencia_ms': None, 'velocidade_mbps': None, 'erro': None}

    # Latência
    resultado['latencia_ms'] = _medir_latencia(host, porta)
    _log('Latência: {}ms'.format(resultado['latencia_ms']))

    # Velocidade (usando o próprio URL do stream durante _DURATION segundos)
    mbps, total = _medir_download(url_stream)
    resultado['velocidade_mbps'] = mbps
    _log('Velocidade: {} Mbps ({} bytes)'.format(mbps, total))

    return resultado


def testar_ligacao_geral(callback=None):
    """
    Testa a velocidade de ligação com URLs públicos de referência.
    callback(mbps_parcial) chamado durante o teste se fornecido.
    Devolve velocidade média em Mbps ou None.
    """
    resultados = []
    for url in _TEST_URLS:
        mbps, _ = _medir_download(url)
        if mbps is not None:
            resultados.append(mbps)
            if callback:
                try:
                    callback(mbps)
                except Exception:
                    pass
    if resultados:
        return round(sum(resultados) / len(resultados), 2)
    return None


def mostrar_resultado_kodi(url_stream=None):
    """
    Executa o teste e mostra o resultado numa caixa de diálogo Kodi.
    url_stream: URL do stream a testar, ou None para teste genérico de ligação.
    """
    try:
        dp = xbmcgui.DialogProgress()
        dp.create(_ADDON_NAME, 'A testar ligação…')
        dp.update(10, 'A medir latência…')

        if url_stream:
            resultado = testar_servidor(url_stream)
            dp.update(80, 'A calcular…')
            dp.close()

            lat  = resultado.get('latencia_ms')
            mbps = resultado.get('velocidade_mbps')

            lat_txt  = '{}ms'.format(round(lat)) if lat is not None else 'N/D'
            mbps_txt = '{} Mbps'.format(mbps)    if mbps is not None else 'N/D'

            xbmcgui.Dialog().ok(
                _ADDON_NAME,
                'Latência:  {}\nVelocidade de stream:  {}'.format(lat_txt, mbps_txt)
            )
        else:
            def _cb(m):
                dp.update(50, 'A medir… {:.1f} Mbps'.format(m))
            media = testar_ligacao_geral(callback=_cb)
            dp.close()
            txt = '{} Mbps'.format(media) if media is not None else 'Sem resultado'
            xbmcgui.Dialog().ok(_ADDON_NAME, 'Velocidade de ligação:  ' + txt)

    except Exception as e:
        try:
            dp.close()
        except Exception:
            pass
        xbmcgui.Dialog().ok(_ADDON_NAME, 'Erro no teste: ' + str(e))
