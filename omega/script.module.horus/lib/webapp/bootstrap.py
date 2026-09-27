# -*- coding: utf-8 -*-
# EKHorus - Starting, finding and stopping the web server.
#
# The server lives in a daemon thread that outlives the invocation that started it: Kodi
# keeps the addon's interpreter alive while it has threads running, which is the same way
# EspaDaily and AtresDaily serve theirs.
#
# The catch is that every press of the menu is a NEW interpreter, so the module variable
# below is not shared between invocations. Without something outside Python, the second
# press would see no server, fail to bind the port, walk up the range and leave two
# servers running. The address is therefore also written in the Home window, which every
# invocation can read, and is checked against the port before being believed.

import socket
import threading
import time

import xbmc
import xbmcgui

from lib.utils import apartar_musica, get_setting, logger

PUERTO_POR_OMISION = 8099
# Ports tried when the chosen one is busy. Eight is enough to dodge another addon's
# server and few enough that a firewall rule is still writable by hand.
PUERTOS = 8
# Longest wait for the server to be down once told to stop. Normally it takes the half
# second serve_forever spends between polls.
CIERRE_S = 3
# With a browser in front Kodi drops to a background priority (oom_score_adj 700 on a Fire TV
# Stick), and once the cached apps are gone lmkd may close it, taking the server along. The
# line is an estimate, not a measurement: Fire TV Sticks have 1 to 2 GB and a current phone 4
# or more, and MemTotal reads somewhat below what the box says.
POCA_MEMORIA_KB = 3 * 1024 * 1024

_PROP_URL = 'ekhorus_webapp_url'

# The address is only believed if the port answers this, and answers it as ours: any other
# program could be sitting on the port after Kodi restarted.
RUTA_PING = '/api/ping'
FIRMA = 'ekhorus'

_servidor = None
_puerto = None
_cerrojo = threading.Lock()


def ip_lan():
    """Address of this device on the local network, or '' if there is none.

    Kodi's own answer is preferred because it is the interface Kodi is actually using. The
    UDP socket is the fallback for the cases where it comes back empty, and it sends no
    packet: connect() on a datagram socket only picks the route."""
    try:
        ip = xbmc.getIPAddress()
        if ip and ip not in ('0.0.0.0', '127.0.0.1'):
            return ip
    except Exception as e:
        logger(f'webapp: xbmc.getIPAddress: {e}')

    sonda = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sonda.connect(('8.8.8.8', 53))
        return sonda.getsockname()[0]
    except OSError:
        return ''
    finally:
        sonda.close()


def _url(puerto, ip=None):
    ip = ip or ip_lan()
    return f'http://{ip}:{puerto}/' if ip else ''


def _puerto_ajuste():
    try:
        puerto = int(get_setting('webapp_puerto', PUERTO_POR_OMISION))
    except (TypeError, ValueError):
        return PUERTO_POR_OMISION

    return puerto if 1024 <= puerto <= 65535 else PUERTO_POR_OMISION


def _contesta(url, timeout=1.5):
    """True if our own server is answering at that address."""
    import urllib.request

    try:
        with urllib.request.urlopen(url.rstrip('/') + RUTA_PING, timeout=timeout) as r:
            return FIRMA in r.read(64).decode('utf-8', 'replace')
    except Exception:
        return False


def _llamar(url, ruta, timeout=2):
    """Knocks on one of the server's doors and does not care what comes back.

    A POST: the doors that change something only open to one, so that no <img> on a page
    from elsewhere can knock on them."""
    import urllib.request

    try:
        peticion = urllib.request.Request(url.rstrip('/') + ruta, data=b'', method='POST')
        with urllib.request.urlopen(peticion, timeout=timeout) as r:
            r.read(64)
    except Exception as e:
        logger(f'webapp: {ruta} no contesto: {e}')


def ip_anotada():
    """The address the server came up on, as worked out when it started.

    Kept because xbmc.getIPAddress() answers in Kodi's own thread, and whoever needs the
    address from a server thread cannot count on getting it there."""
    url = xbmcgui.Window(10000).getProperty(_PROP_URL)

    return url.split('//', 1)[-1].split(':')[0] if url else ''


def url_activa():
    """Address of the server that is already running, or None.

    It is checked and not just read: the recorded one may belong to an interpreter Kodi
    has since torn down, and offering a dead address is worse than offering none."""
    url = xbmcgui.Window(10000).getProperty(_PROP_URL)

    if url and _contesta(url):
        return url

    if url:
        xbmcgui.Window(10000).clearProperty(_PROP_URL)

    return None


def arrancar():
    """Starts the server and returns its address, or None if it could not.

    Binding goes to 0.0.0.0 because serving only this machine would defeat the point: the
    whole feature is that another device on the network opens it."""
    global _servidor, _puerto

    from .server import crear_servidor

    # Asked before binding anything. With no address on the network there is nobody to
    # hand it to, and a server nobody can be told about is just a port held open.
    ip = ip_lan()
    if not ip:
        logger('webapp: este aparato no tiene direccion en la red local', 'error')
        return None

    deseado = _puerto_ajuste()

    # Another invocation may already be serving there with the note in the Home window
    # lost. Adopting it beats walking up to the next port and leaving two servers about.
    ya = _url(deseado, ip)
    if _contesta(ya, timeout=1):
        xbmcgui.Window(10000).setProperty(_PROP_URL, ya)
        return ya

    with _cerrojo:
        if _servidor is not None:
            return _url(_puerto, ip)

        for puerto in range(deseado, deseado + PUERTOS):
            try:
                servidor = crear_servidor('0.0.0.0', puerto)
            except OSError:
                continue

            _servidor, _puerto = servidor, puerto
            threading.Thread(target=servidor.serve_forever, daemon=True,
                             name='EKHorusWeb').start()
            threading.Thread(target=_vigilar_abort, args=(servidor,), daemon=True,
                             name='EKHorusWebVigia').start()
            break
        else:
            logger(f'webapp: ningun puerto libre entre {deseado} y '
                   f'{deseado + PUERTOS - 1}', 'error')
            return None

    url = _url(_puerto, ip)
    xbmcgui.Window(10000).setProperty(_PROP_URL, url)
    logger(f'webapp: sirviendo en {url}')

    return url


def _vigilar_abort(servidor):
    """Brings the server down when Kodi is closing.

    The server thread never looks at Kodi, so without this Kodi waits for it on exit and
    gives up after five seconds. It waits on the server's own flag and not on Kodi's abort
    alone, so it leaves with the server when that is stopped by any other road: blocked on
    the abort it would keep this invocation alive until Kodi closed."""
    monitor = xbmc.Monitor()

    while not servidor.parado.wait(0.5):
        if monitor.abortRequested():
            servidor.apagar()
            return


def asegurar():
    """The address of the web interface, starting the server if it is not up."""
    return url_activa() or arrancar()


def parar():
    """Stops the server, whichever invocation of the addon owns it, and waits for it.

    From another invocation the object is not reachable, so it is asked to shut itself
    down through its own door. Either way it only returns once nobody answers there any
    more: whoever comes next must find the port free, not a server still dying."""
    global _servidor, _puerto

    with _cerrojo:
        propio = _servidor

    if propio is not None:
        propio.apagar().join(CIERRE_S)
        with _cerrojo:
            _servidor = _puerto = None
    else:
        # Checked first, because the note can be stale and another program may have taken
        # the port over. Knocking on a stranger's door is not something to do blind.
        url = xbmcgui.Window(10000).getProperty(_PROP_URL)
        if url and _contesta(url):
            _llamar(url, '/api/apagar')
            _esperar_cierre(url)

    xbmcgui.Window(10000).clearProperty(_PROP_URL)


def _esperar_cierre(url, plazo=CIERRE_S):
    """True once nothing answers at that address, False if it still did after 'plazo'."""
    fin = time.time() + plazo

    while time.time() < fin:
        if not _contesta(url, timeout=0.5):
            return True
        time.sleep(0.1)

    return False


def poca_memoria(meminfo='/proc/meminfo'):
    """True on an Android device with too little memory to keep Kodi alive behind a browser.

    When it cannot tell, it says False: the warning is not worth pestering a device that
    may well have plenty."""
    if not xbmc.getCondVisibility('System.Platform.Android'):
        return False

    try:
        with open(meminfo, encoding='ascii') as f:
            for linea in f:
                if linea.startswith('MemTotal:'):
                    return int(linea.split()[1]) < POCA_MEMORIA_KB
    except (OSError, ValueError, IndexError) as e:
        logger(f'webapp: no se pudo leer la memoria: {e}')

    return False


def abrir_en_navegador(url):
    """Opens the address in the browser of this very device. False if it could not."""
    apartar_musica()
    if xbmc.getCondVisibility('System.Platform.Android'):
        xbmc.executebuiltin(f'StartAndroidActivity("","android.intent.action.VIEW","","{url}")')
        return True

    import webbrowser

    try:
        return bool(webbrowser.open(url))
    except Exception as e:
        logger(f'webapp: no se pudo abrir el navegador: {e}', 'error')
        return False
