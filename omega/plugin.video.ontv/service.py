# -*- coding: utf-8 -*-
# OnTV - Servico de background  v1.0.4
#
# Com a reconexao silenciosa no proxy.py, o servico ja nao precisa de
# fechar/reabrir o canal quando o servidor IPTV corta.
# O proxy mantem o socket do Kodi aberto e reconecta internamente.
# O servico fica apenas como watchdog do proxy e gestor de DNS/buffer.

import xbmc
import xbmcgui
import xbmcaddon
import os
import sys
import xbmcvfs

ADDON       = xbmcaddon.Addon()
ADDON_PATH  = ADDON.getAddonInfo('path')
STREAM_FILE = xbmcvfs.translatePath('special://temp/ontv_stream.json')
STOP_FILE   = xbmcvfs.translatePath('special://temp/ontv_user_stop.flag')

_LIB_PATH = os.path.join(ADDON_PATH, 'resources', 'lib')
if _LIB_PATH not in sys.path:
    sys.path.insert(0, _LIB_PATH)


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[OnTV Service] ' + str(msg), level)


def _remover_stop_flag():
    try:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
    except Exception:
        pass


def _criar_stop_flag():
    try:
        with open(STOP_FILE, 'w') as f:
            f.write('1')
    except Exception:
        pass


def _limpar_stream():
    try:
        if os.path.exists(STREAM_FILE):
            os.remove(STREAM_FILE)
    except Exception:
        pass


def _limpar_stalker():
    try:
        sfile = xbmcvfs.translatePath('special://temp/ontv_stalker_stream.json')
        if os.path.exists(sfile):
            os.remove(sfile)
    except Exception:
        pass


def _parar_proxy():
    try:
        from proxy import stop as proxy_stop
        proxy_stop()
    except Exception:
        pass


def _optimizar_buffer():
    """Ajusta o chunk do proxy conforme a RAM disponivel."""
    try:
        ram_str = xbmc.getInfoLabel('System.Memory(total)')
        ram_mb  = int(''.join(filter(str.isdigit, ram_str)))
    except Exception:
        ram_mb  = 2048

    chunk = 131072 if ram_mb >= 2048 else 65536
    try:
        import proxy as _proxy
        _proxy.CHUNK_SIZE = chunk
        log('Buffer: chunk={}KB (RAM={}MB)'.format(chunk // 1024, ram_mb))
    except Exception:
        pass


def _activar_dns():
    """Activa DNS personalizado guardado na ultima sessao."""
    try:
        dns_file = xbmcvfs.translatePath('special://temp/ontv_dns_provider.txt')
        if os.path.exists(dns_file):
            with open(dns_file, 'r') as f:
                provider = f.read().strip()
            if provider and provider != 'sistema':
                import dns_override
                dns_override.activate(provider)
                log('DNS activado: ' + provider)
    except Exception as e:
        log('Aviso DNS: ' + str(e), xbmc.LOGWARNING)


class OnTVPlayer(xbmc.Player):
    """
    Player simplificado: apenas regista eventos para logs e flag de paragem.
    A reconexao em caso de falha e feita internamente pelo proxy.py,
    sem fechar nem reabrir o canal no Kodi.
    """
    def onPlayBackStarted(self):
        _remover_stop_flag()
        log('Stream iniciado')

    def onPlayBackStopped(self):
        log('Stream parado pelo utilizador')
        _limpar_stream()
        _limpar_stalker()
        _criar_stop_flag()
        _parar_proxy()

    def onPlayBackEnded(self):
        # Com o proxy a usar Transfer-Encoding: chunked e reconexao interna,
        # onPlayBackEnded so deve ocorrer se o proxy desistiu (MAX_RETRIES esgotado)
        # ou se o utilizador fechou o player manualmente.
        # Nao tentamos reabrir - o utilizador pode escolher outro canal.
        log('Stream terminado (proxy esgotou tentativas ou utilizador parou)')
        _limpar_stream()
        _limpar_stalker()
        _parar_proxy()

    def onPlayBackError(self):
        log('Erro de reproducao reportado pelo Kodi', xbmc.LOGWARNING)


def run():
    log('Servico iniciado v1.0.4')

    _optimizar_buffer()
    _activar_dns()

    try:
        from mediacfg import invalidar_cache
        invalidar_cache()
    except Exception as e:
        log('Aviso cache: ' + str(e), xbmc.LOGWARNING)

    _remover_stop_flag()
    _limpar_stream()
    _parar_proxy()

    monitor = xbmc.Monitor()
    player  = OnTVPlayer()

    while not monitor.abortRequested():
        monitor.waitForAbort(5)

    log('Servico terminado')


if __name__ == '__main__':
    run()
