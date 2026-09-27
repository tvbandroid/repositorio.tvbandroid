# -*- coding: utf-8 -*-

# NOTE: sys and xbmcplugin look unused here and a linter will flag them as such,
# but default.py does 'from lib.utils import *' and receives them this way. If they
# are removed, the addon stops starting.
import sys, os ,re
import xbmc, xbmcgui, xbmcplugin, xbmcaddon, xbmcvfs
import ast
import base64
import itertools
import json
import subprocess
import time
import urllib.parse as urllib_parse
import urllib.request as urllib_request

from threading import Lock, get_ident

LOGINFO = xbmc.LOGINFO

try:
    translatePath = xbmcvfs.translatePath
except:
    translatePath = xbmc.translatePath

ADDON = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_VERSION = ADDON.getAddonInfo('version')
HEADING = "%s (%s)" %(ADDON_NAME,ADDON_VERSION)

runtime_path = translatePath(ADDON.getAddonInfo('Path'))
icon_path = os.path.join(runtime_path, 'icon.png')
data_path = translatePath(ADDON.getAddonInfo('Profile'))
translate = ADDON.getLocalizedString

# No network request may be left hanging: Kodi freezes along with it.
HTTP_TIMEOUT = 10
# Download cap. Playlists and .torrent files are a few KB; anything this size is
# an error or an abuse, and reading it whole would exhaust memory.
HTTP_MAX_BYTES = 16 * 1024 * 1024
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0'


def ensure_str(value, encoding='utf-8', errors='replace'):
    if isinstance(value, bytes):
        return value.decode(encoding, errors)
    return str(value)


def ensure_binary(value, encoding='utf-8'):
    if isinstance(value, str):
        return value.encode(encoding)
    return value


def parse_literal(value):
    """Turns a text into a Python object without using eval().

    Accepts JSON and Python literals (lists, dicts, numbers, strings).
    Returns None if the text is not a valid literal."""
    if not isinstance(value, str):
        return value

    try:
        return json.loads(value)
    except Exception:
        pass

    try:
        return ast.literal_eval(value)
    except Exception:
        return None


def parse_headers(headers):
    if not headers:
        return dict()
    if isinstance(headers, dict):
        return headers

    value = parse_literal(headers)
    return value if isinstance(value, dict) else dict()


def http_get_bytes(url, headers=None, timeout=HTTP_TIMEOUT, max_bytes=HTTP_MAX_BYTES):
    headers = dict(parse_headers(headers))
    headers.setdefault('User-Agent', USER_AGENT)

    req = urllib_request.Request(url, data=None, headers=headers)
    demasiado = f'respuesta demasiado grande (mas de {max_bytes} bytes): {url}'

    with urllib_request.urlopen(req, timeout=timeout) as response:
        largo = (response.headers.get('Content-Length') or '').strip()
        if largo.isdigit() and int(largo) > max_bytes:
            raise ValueError(demasiado)

        # In pieces and never read(max_bytes + 1): the Python of Kodi 19 and 20, and of Kodi 21 on
        # Windows, allocates and zeroes that whole amount before reading, 16 MB for a list of a few
        # KB. One byte more than the cap is read, to tell "exactly at it" from "over it".
        datos = bytearray()
        while len(datos) <= max_bytes:
            trozo = response.read(min(64 * 1024, max_bytes + 1 - len(datos)))
            if not trozo:
                break
            datos += trozo

    if len(datos) > max_bytes:
        raise ValueError(demasiado)

    # bytes and not the bytearray: ensure_str() only decodes bytes.
    return bytes(datos)


def http_get_text(url, headers=None, timeout=HTTP_TIMEOUT):
    return ensure_str(http_get_bytes(url, headers, timeout))


class Item(object):
    defaults = {}

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __contains__(self, item):
        return item in self.__dict__

    def __getattribute__(self, item):
        return object.__getattribute__(self, item)

    def __getattr__(self, item):
        if item.startswith("__"):
            return object.__getattribute__(self, item)
        else:
            return self.defaults.get(item, '')

    def __str__(self):
        return '{%s}' % (', '.join(['\'%s\': %s' % (k, repr(self.__dict__[k])) for k in sorted(self.__dict__.keys())]))

    def tourl(self):
        value = ensure_binary(self.__str__())
        return ensure_str(urllib_parse.quote(base64.b64encode(value)))

    def fromurl(self, url):
        str_item = ensure_str(base64.b64decode(urllib_parse.unquote(url)))
        item = ast.literal_eval(str_item)
        if not isinstance(item, dict):
            raise ValueError("item no valido: %s" % str_item)
        self.__dict__.update(item)
        return self


def logger(message, level=None):
    def format_message(data=""):
        try:
            value = str(data)
        except Exception:
            value = repr(data)

        return ensure_str(value)

    texto = '[%s] %s' % (ADDON.getAddonInfo('id'), format_message(message))

    try:
        if level == 'error':
            xbmc.log("######## ERROR #########", xbmc.LOGERROR)
            xbmc.log(texto, xbmc.LOGERROR)
        else:
            xbmc.log(texto, LOGINFO)
    except:
        xbmc.log(str([texto]), LOGINFO)


locker = Lock()


def _reintentar_si_ocupado(accion):
    """accion(), tried again a few times while Windows says the file is busy.

    There a file being replaced cannot be opened, and an open one cannot be replaced, so a
    reader and a writer from two invocations of the addon that meet get PermissionError. It
    clears up in milliseconds."""
    for pausa in (0.01, 0.03, 0.1, 0.3):
        try:
            return accion()
        except PermissionError:
            time.sleep(pausa)

    return accion()


def load_json_file(path):
    def leer():
        with open(path, 'rb') as f:
            return f.read()

    with locker:
        data = _reintentar_si_ocupado(leer)

    return load_json(ensure_str(data))


def dump_json_file(data, path, compacto=False):
    """Writes json atomically.

    With compacto, no indentation and no sorted keys. The engine's catalogue is 1800
    channels and in the readable format it goes from 300 KB to over a megabyte, which on a
    TV box shows both when writing and when reading."""
    # exist_ok: two invocations creating the data folder at the same moment must not clash.
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if compacto:
        texto = dump_json(data, ensure_ascii=False, separators=(',', ':'))
    else:
        texto = dump_json(data)

    # dump_json() returns '' when it cannot serialise. Writing that would erase
    # the previous content; better to fail and leave the file as it was.
    if not texto:
        raise ValueError("contenido no serializable; no se sobrescribe %s" % path)

    # Atomic write: if Kodi closes halfway through writing, the original file
    # stays intact instead of being left truncated. The thread goes in the name because every
    # invocation of the addon is a thread of the one Kodi process, and with the pid alone two
    # of them writing the same file at once shared the temporary file and left half of each.
    tmp_path = f'{path}.{os.getpid()}.{get_ident()}.tmp'
    with locker:
        try:
            with open(tmp_path, 'wb') as f:
                f.write(ensure_binary(texto))
                f.flush()
                os.fsync(f.fileno())
            _reintentar_si_ocupado(lambda: os.replace(tmp_path, path))
        except Exception:
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except OSError: pass
            raise


def load_json(*args, **kwargs):
    if "object_hook" not in kwargs:
        kwargs["object_hook"] = set_encoding

    try:
        value = json.loads(*args, **kwargs)
    except Exception:
        value = {}

    return value


def dump_json(*args, **kwargs):
    if not kwargs:
        kwargs = {
            'indent': 4,
            'skipkeys': True,
            'sort_keys': True,
            'ensure_ascii': False
        }

    try:
        value = json.dumps(*args, **kwargs)
    except Exception:
        value = ''

    return value


def set_encoding(dct):
    if isinstance(dct, dict):
        return dict((set_encoding(key), set_encoding(value)) for key, value in dct.items())
    elif isinstance(dct, list):
        return [set_encoding(element) for element in dct]
    elif isinstance(dct, (str, bytes)):
        return ensure_str(dct)
    else:
        return dct


def get_setting(name, default=None):
    value = ADDON.getSetting(name)

    if not value:
        return default
    elif value == 'true':
        return True
    elif value == 'false':
        return False

    try:
        return int(value)
    except ValueError:
        pass

    parsed = parse_literal(value)
    if isinstance(parsed, (list, dict)):
        return parsed

    return value


def get_setting_text(name, default=''):
    """A free-text setting as it was typed.

    get_setting() turns '123' into a number and 'true' into a bool, and Kodi's input box
    only takes text: with a search of '2024' saved, the search row stopped opening."""
    return ADDON.getSetting(name) or default


def set_setting(name, value):
    try:
        if isinstance(value, bool):
            value = "true" if value else "false"
        elif isinstance(value, (int, list)):
            value = str(value)
        elif not isinstance(value, str):
            value = dump_json(value)

        ADDON.setSetting(name, value)

    except Exception as ex:
        logger("Error al convertir '%s' no se guarda el valor \n%s" % (name, ex), 'error')
        return None

    return value


# Ace engines the addon knows how to launch. The first one is only the dropdown label;
# the AceServe one is also used as the package name when firing the Android intent.
ENGINE_ACESTREAM = "org.acestream.----"
ENGINE_ACESERVE = "org.free.aceserve"


def active_engine():
    """Engine chosen in the settings. Outside Android only AceStream exists."""
    if system_platform != 'android':
        return ENGINE_ACESTREAM

    return get_setting("ace_engine") or ENGINE_ACESTREAM


def engine_port(engine=None):
    """Port of the given engine, or of the active one if none is given.

    AceServe pins 6878 and does not let it be changed without root, so whoever moves
    it by editing their acestream.conf needs a separate setting. Empty means "the same
    as AceStream", so that whoever had already moved it with the only port there used
    to be is not left unable to play after updating.

    On Android the official app may sit on a port other than the configured one (see
    buscar_motor_en_otro_puerto). The one found is used for as long as the configured port
    is still the one it was found under: a port typed later, here or in Kodi's own settings
    dialog, wins without any hook."""
    if (engine or active_engine()) == ENGINE_ACESERVE:
        return get_setting("aceserve_port") or get_setting("ace_port", 6878)

    configurado = get_setting("ace_port", 6878)

    if system_platform == 'android':
        hallado = get_setting('ace_port_hallado')
        if hallado and str(get_setting('ace_port_hallado_base')) == str(configurado):
            return hallado

    return configurado


def olvidar_puerto_hallado():
    set_setting('ace_port_hallado', '')
    set_setting('ace_port_hallado_base', '')


def guardar_puerto_hallado(puerto):
    """Remembers where the engine turned out to be and points the shared Server there.

    Kept next to the configured port, so that one typed later takes over (engine_port).
    Found on the configured port itself, the app is back where it was and the memory goes."""
    configurado = get_setting("ace_port", 6878)

    if str(puerto) == str(configurado):
        olvidar_puerto_hallado()
    else:
        set_setting('ace_port_hallado', puerto)
        set_setting('ace_port_hallado_base', configurado)

    # The verdict about who answers was for the old port.
    forget_engine()
    server.cambiar_puerto(puerto)
    logger(f'motor encontrado en el puerto {puerto}')
    xbmcgui.Dialog().notification(HEADING, translate_fmt(30175, puerto), icon_path, 5000)


# Between sweeps of this device's ports: a sweep is seconds of CPU on a TV box, and one every
# second while the wait dialog counts down would be a stove.
BARRIDO_CADA_S = 4
_proximo_barrido = 0.0


def barrido_listo():
    """Whether enough time has gone by since the last sweep for another one."""
    return time.time() >= _proximo_barrido


def buscar_motor_en_otro_puerto(cancelar=None, completo=True):
    """Looks for the engine on the other ports of this device and settles on it if found.

    Since its engine 3.1.47.3 the official Ace Stream app no longer fails when its port is
    taken (AceServe on 6878, say): it starts on whatever port the system hands it, keeps it
    for good and never goes back, and Kodi cannot ask it which. Only where that can be the
    case: Android, the official app chosen (AceServe pins its port) and the engine on this
    very device (tens of thousands of connections over the wifi to another machine is not a
    probe). The classic ports are looked at every time, in milliseconds; the whole range only
    with 'completo' and when enough time has gone by since the last sweep of it: the next one
    waits three times what the last one took, so a slow box does not chain them. Whatever
    goes wrong in the sweep is logged and counts as not found: a diagnosis must not bring a
    playback down. Returns the port, or None."""
    global _proximo_barrido

    if not (system_platform == 'android' and active_engine() == ENGINE_ACESTREAM
            and es_host_local(server.host)):
        return None

    completo = completo and barrido_listo()
    inicio = time.time()
    if completo:
        # Holds a second caller off while this one runs.
        _proximo_barrido = inicio + BARRIDO_CADA_S

    try:
        from lib import netscan  # here and not above: netscan imports this module
        puerto = netscan.buscar_puerto_local(server.host, evitar=(server.port,),
                                             cancelar=cancelar, completo=completo)
    except Exception as e:
        logger(f'buscar_motor_en_otro_puerto: {e}', 'error')
        puerto = None

    if completo:
        _proximo_barrido = time.time() + max(BARRIDO_CADA_S, 3 * (time.time() - inicio))

    if puerto:
        guardar_puerto_hallado(puerto)

    return puerto


def engine_name(engine):
    """Presentable name of the engine, for messages to the user."""
    return 'AceServe' if engine == ENGINE_ACESERVE else 'AceStream'


_ENGINE_PROP = 'ekhorus_engine_'
# Addresses where the engine runs on this very device.
HOSTS_LOCALES = ('127.0.0.1', 'localhost', '::1')


def es_host_local(host):
    """Whether the engine address points at this very device.

    Loopback, or the address Kodi has on the network: whoever types their own LAN address
    still has the engine here, and starting it or opening its app is right. Anything else is
    another machine, where nothing done on this one can start it."""
    if host in HOSTS_LOCALES or host.startswith('127.'):
        return True

    return bool(host) and host == (xbmc.getIPAddress() or '')


def forget_engine(servidor=None):
    """Forgets the detected engine. Mandatory after stopping or starting one."""
    xbmcgui.Window(10000).clearProperty(_ENGINE_PROP + (servidor or server).base)


def detect_engine(servidor=None):
    """Which engine is really answering, or None if there is no way to know.

    The only reliable signal is /pl.m3u, which AceServe serves and the AceStream engine
    does not. Guessing by version number is no good: measured in September 2026, AceStream
    is on 3.2.22 and AceServe on 3.2.14, so neither the threshold nor the order that were
    assumed hold up."""
    servidor = servidor or server

    version = servidor.version
    if not version:
        return None

    # There used to be a shortcut here: on desktop with a local engine, take it for
    # granted that it is AceStream and save the request. The assumption is false, because
    # AceServe is also shipped as a Docker container and may be running on the same
    # machine as Kodi. Assuming is what the previous version got wrong, so it always asks.
    # It comes cheap: the verdict stays cached for the whole Kodi session.
    window = xbmcgui.Window(10000)
    clave = _ENGINE_PROP + servidor.base

    # The verdict is stored next to the version that was answering back then. If that
    # version changes there is another engine on the other side, and the earlier verdict
    # no longer holds. On Android the other engine cannot be stopped from here, so without
    # this check a stale verdict lasted the whole Kodi session.
    guardado = window.getProperty(clave)
    if guardado.startswith(version + '|'):
        return guardado.split('|', 1)[1]

    sirve = servidor.playlist_status()

    # With no clear answer nothing is decided and nothing is cached. The verdict lasts the
    # whole Kodi session, so an unlucky probe while the engine is broadcasting would leave
    # the engine misidentified until a restart. Returning what the user has chosen also
    # keeps check_engine()'s warning quiet, which is right when we do not know.
    if sirve is None:
        logger('detect_engine: /pl.m3u sin respuesta, no se decide ni se cachea')
        return active_engine()

    detectado = ENGINE_ACESERVE if sirve else ENGINE_ACESTREAM

    window.setProperty(clave, version + '|' + detectado)
    return detectado


def get_system_platform():
    plataforma = arquitectura = linux_id = "unknown"
    root = True

    if 'ANDROID_STORAGE' in os.environ:
        plataforma = "android"

    elif xbmc.getCondVisibility('system.platform.linux.raspberrypi') or xbmc.getCondVisibility('system.platform.linux'):
        plataforma = "linux"
        if "arm" in os.uname()[4]:
            arquitectura = "arm"
        elif "aarch" in os.uname()[4]:
            arquitectura = "aarch"
        elif "x86" in os.uname()[4]:
            arquitectura = "x86"

        try:
            with open("/etc/os-release", 'rb') as f:
                data = ensure_str(f.read())
                linux_id = re.findall(r"""\bid\s?=\s?["']?(\w+)""", data, re.I)[0]
                set_setting("linux_id", linux_id)
        except:pass

        if os.geteuid() == 0:
            root = True
        else:
            root = False
            if arquitectura == "arm":
                if linux_id not in ['osmc','openelec','raspbian','raspios']:
                    plataforma = str(os.uname())
            elif arquitectura != "x86":
                plataforma = str(os.uname())

    elif xbmc.getCondVisibility('system.platform.windows'):
        plataforma = "windows"

    elif xbmc.getCondVisibility('system.platform.tvos'):  # Supported only on Kodi 19.x
        plataforma = "android" #"tvos"

    return (plataforma, arquitectura, root)


def no_window():
    """Stops taskkill/subprocess from opening a black console on top of Kodi."""
    kwargs = {'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL}

    if hasattr(subprocess, 'STARTUPINFO'):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs['startupinfo'] = startupinfo
        kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

    return kwargs


class DownloadCanceled(Exception):
    pass


class WriteFailed(IOError):
    """The disk turned a chunk down: it is full, or it is gone (a USB stick pulled out)."""


# Android folders where a file manager can read the APK
APK_FOLDER_CANDIDATES = (
    '/storage/emulated/0/Download/',
    '/storage/self/primary/Download/',
    '/sdcard/Download/',
)

APK_DOWNLOAD_TIMEOUT = 30
APK_CHUNK_SIZE = 128 * 1024
PM_INSTALL_TIMEOUT = 180

# Followed by the file name, the Home window property of a download under way.
_APK_LATCH = 'ekhorus_downloading_'


def translate_fmt(string_id, *args):
    # If the string is not loaded, translate() returns ''. That happens when you edit
    # strings.po and do not restart Kodi, or with an incomplete language. Formatting ''
    # with arguments raises TypeError, so it is better to show the bare data than to
    # blow up
    text = translate(string_id) or ''

    if not args:
        return text

    try:
        return text % args
    except TypeError:
        logger("Cadena %s sin cargar o con placeholders erroneos" % string_id, 'error')
        return '\n'.join([text] + [str(a) for a in args]).strip()


def poner_info_video(listitem, titulo='', plot='', tipo=''):
    """Title, plot and media type of a row, on any Kodi from 19 up.

    The InfoTagVideo setters are from Kodi 20. On 19 the tag has only getters and the way
    in is setInfo(), which from 20 on is partially deprecated; so each Kodi takes its own
    road and neither logs a warning. Only what is given is set."""
    infotag = listitem.getVideoInfoTag()

    if hasattr(infotag, 'setTitle'):
        if titulo:
            infotag.setTitle(titulo)
        if plot:
            infotag.setPlot(plot)
        if tipo:
            infotag.setMediaType(tipo)
        return

    info = {campo: valor
            for campo, valor in (('title', titulo), ('plot', plot), ('mediatype', tipo))
            if valor}
    if info:
        listitem.setInfo('video', info)


def poner_info_musica(listitem, titulo):
    """A music tag with its title, on any Kodi from 19 up; the twin of poner_info_video().

    Kodi hands an item with a music tag to its music player, which opens a file with no
    busy spinner. Same two roads as the video one: setters from Kodi 20, setInfo() on 19."""
    infotag = listitem.getMusicInfoTag()

    if hasattr(infotag, 'setTitle'):
        infotag.setTitle(titulo)
    else:
        listitem.setInfo('music', {'title': titulo})


def format_size(size):
    size = float(size)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return "%.1f %s" % (size, unit)
        size /= 1024.0
    return "%.1f TB" % size


def join_path(folder, filename):
    # On Windows os.path.join inserts '\' and breaks VFS paths like smb://
    if "://" in folder:
        return folder.rstrip('/') + '/' + filename
    return os.path.join(folder, filename)


def apk_looks_valid(path):
    # An APK is still a ZIP. If it is cut short it is missing the index at the end and it
    # shows without touching the network. It catches what the size does not, like servers
    # that do not send Content-Length or half-finished files from old versions.
    # Returns True or False, and None when there is no way to know, as in smb://
    if "://" in path:
        return None

    try:
        import zipfile
        return zipfile.is_zipfile(path)
    except Exception as ex:
        logger("No se pudo validar el APK %s: %s" % (path, ex))
        return None


def default_apk_folder():
    last = get_setting("last_apk_folder", "")
    if isinstance(last, str) and last and xbmcvfs.exists(last):
        return last

    if system_platform == 'android':
        for folder in APK_FOLDER_CANDIDATES:
            if xbmcvfs.exists(folder):
                return folder

    return ""


def apk_leftovers(filenames):
    """What Download APKs has left on the device: [(path, filename, half, size)], half being a
    download that never finished.

    Only the names on the list are looked for, so a file the user put there is never offered,
    and only where downloads land: the folder of the last one and, on Android, the public one
    the installer gets its copy in (see stage_apk_public)."""
    folders = [default_apk_folder()]
    if system_platform == 'android':
        folders.append(next((f for f in APK_FOLDER_CANDIDATES if xbmcvfs.exists(f)), ''))

    # /sdcard is /storage/emulated/0 by another name: the same file must not be offered twice.
    unique = dict()
    for folder in filter(None, folders):
        unique.setdefault(folder.rstrip('/') if '://' in folder else os.path.realpath(folder),
                          folder)

    window = xbmcgui.Window(10000)
    found = list()
    for folder, filename, half in itertools.product(unique.values(), filenames, (False, True)):
        # Still downloading is not left over, and deleting its .part would break it.
        if window.getProperty(_APK_LATCH + filename) == 'true':
            continue

        path = join_path(folder, filename) + ('.part' if half else '')
        if xbmcvfs.exists(path):
            found.append((path, filename, half, xbmcvfs.Stat(path).st_size()))

    return found


def download_to(url, dest, dp=None, message=""):
    request = urllib_request.Request(url, headers={'User-Agent': USER_AGENT})
    response = urllib_request.urlopen(request, timeout=APK_DOWNLOAD_TIMEOUT)
    downloaded = 0

    try:
        total = response.headers.get('Content-Length')
        total = int(total) if total and total.isdigit() else 0

        handle = xbmcvfs.File(dest, 'w')
        try:
            while True:
                if dp and dp.iscanceled():
                    raise DownloadCanceled()

                chunk = response.read(APK_CHUNK_SIZE)
                if not chunk:
                    break

                # write() does not raise, it returns False. If you do not look at it, a full
                # disk gives you a "correct" download with a cut APK inside
                if not handle.write(bytearray(chunk)):
                    raise WriteFailed(translate(30072) or "Error al escribir en el disco")

                downloaded += len(chunk)

                if dp:
                    if total:
                        dp.update(min(int(downloaded * 100 / total), 100),
                                  "%s\n%s / %s" % (message, format_size(downloaded), format_size(total)))
                    else:
                        dp.update(0, "%s\n%s" % (message, format_size(downloaded)))
        finally:
            handle.close()
    finally:
        response.close()

    # downloaded is the bytes that arrived from the network, not the ones written.
    # Before calling this good, the real size of the file has to be checked
    written = xbmcvfs.Stat(dest).st_size()
    if total and written < total:
        raise IOError("Descarga incompleta (%s de %s)" % (format_size(written), format_size(total)))

    return written


def kodi_major_version():
    try:
        return int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
    except Exception:
        return 0


def is_espakodi_build():
    """Whether we are inside the EspaKodi APK, which brings its own install bridge.

    It is recognised by the addon path: on Android it always hangs off the data
    folder of the application hosting Kodi."""
    return 'espakodi.kodi' in runtime_path


def apk_autoinstall_supported():
    # With the EspaKodi bridge the Kodi version does not matter, because the conversion
    # from file:// to content:// is done by the APK itself with its FileProvider. Without
    # a bridge Kodi 22 is needed: from 21 down the intent installs nothing and can even
    # close Kodi, so it is not even attempted and manual instructions are used
    if system_platform != 'android':
        return False

    return is_espakodi_build() or kodi_major_version() >= 22


# This class name is generated by the obfuscator when AceServe is compiled, so it can
# change in any version of theirs and there is no way to detect it from Kodi.
ACESERVE_LINK_ACTIVITY = 'crc644baf9324e22bb51e.LinkHandlerActivity'


def android_engine_launch(engine=None):
    """Builtin that opens the app of the given engine on Android, or of the active one."""
    if (engine or active_engine()) != ENGINE_ACESERVE:
        # The app's own scheme, which opens its main screen. No package name is needed (it
        # changes between builds: org.acestream.media, .node, .node.web...) and AceServe does
        # not handle it, so no chooser. This used to be start_content with a made-up
        # content_id, and any start_content without a real link leaves an error dialog on the
        # 3.2 app ("Malformed content id", "Missing URI"); measured on a Fire TV, 21-09-2026.
        return 'StartAndroidActivity("","android.intent.action.VIEW","","acestream+app://")'

    # The last five arguments of StartAndroidActivity are Kodi 20 onwards. On Kodi 19 the
    # class name is ignored, so there the VIEW intent is sent plain, which AceServe has
    # handled since its 1.3.5.
    if kodi_major_version() >= 20:
        return (f'StartAndroidActivity("{ENGINE_ACESERVE}","","","acestream://",'
                f'"","","","","{ACESERVE_LINK_ACTIVITY}")')

    return f'StartAndroidActivity("{ENGINE_ACESERVE}","android.intent.action.VIEW","","acestream://")'


# Kodi only exposes StartAndroidActivity, which fires intents: there is no way to kill
# processes. With an empty package and the action first, which is how AceServe opens.
AJUSTES_FICHA = ('StartAndroidActivity("","android.settings.APPLICATION_DETAILS_SETTINGS",'
                 '"","package:%s")')
AJUSTES_APPS = 'StartAndroidActivity("","android.settings.APPLICATION_SETTINGS","","")'


def cerrar_motor_android(contesta):
    """Takes the user to where Android lets them stop the engine that answers. True if it
    opened anything.

    Android lets one app open another but never close it, and the engine's API has no order
    to quit. AceServe: straight to its page in Android's settings, where "Force stop" is one
    press away. Ace Stream: its app, and the user quits from inside, because its package name
    changes between builds and there is no page to point at."""
    if contesta == ENGINE_ACESERVE:
        primera = ('Ficha de AceServe en Ajustes de Android',
                   AJUSTES_FICHA % ENGINE_ACESERVE,
                   'Pulsa «Forzar detención»')
    else:
        primera = ('Abrir Ace Stream y salir desde la app',
                   android_engine_launch(ENGINE_ACESTREAM),
                   'Sal del motor desde la propia app')

    elegida = xbmcgui.Dialog().select('Cerrar el motor', [primera[0], 'Ajustes de Android'])
    if elegida < 0:
        return False

    apartar_musica()
    xbmc.executebuiltin(primera[1] if elegida == 0 else AJUSTES_APPS)
    if elegida == 0:
        xbmcgui.Dialog().notification(HEADING, primera[2], icon_path, 6000)

    return True


def apartar_musica():
    """For whoever is about to put another app in front of Kodi, which would go on playing the
    menu music from behind it: the music gives way until the user is back (see
    musica.apartar). Switched off, the music module is not even loaded."""
    if get_setting('musica_fondo', True):
        from lib import musica  # here and not above: musica imports this module
        musica.apartar()


def pantalla_sola():
    """For whoever is about to change the screen with nobody touching it: the menu music does
    not take that for somebody at the screen (see musica.sola). Switched off, the music module
    is not even loaded."""
    if get_setting('musica_fondo', True):
        from lib import musica  # here and not above: musica imports this module
        musica.sola()


# How long an open-window mark stays valid. It only matters in the rare case where
# the previous window no longer exists: while it is open the user cannot press the
# menu row again.
_PESTILLO_VALIDEZ_S = 60


def hay_pestillo(clave):
    """True if somebody holds that mark and it has not gone stale.

    Only for looking. Whoever wants to take it calls echar_pestillo(), which is the one
    that decides and marks in one go."""
    marca = xbmcgui.Window(10000).getProperty(clave)

    if not marca:
        return False

    try:
        return (time.time() - float(marca)) < _PESTILLO_VALIDEZ_S
    except ValueError:
        # Something that is not a time is not a mark anybody can trust.
        return False


def echar_pestillo(clave):
    """Marks that a modal window of the addon just opened; False if one was already open.

    Every press of the menu launches the addon from scratch, so a double click would open
    two identical overlapping windows, and closing the top one would look as if it did
    not close. The mark lives in the Home window because a module variable is not shared
    between invocations, and it stores the time and not a plain '1': if Kodi decides to
    kill the script between setting it and clearing it, an eternal latch would leave the
    menu entry dead for the rest of the session, and silently."""
    if hay_pestillo(clave):
        return False

    xbmcgui.Window(10000).setProperty(clave, str(time.time()))
    return True


def refrescar_pestillo(clave):
    """Renews the mark of a job that is still alive.

    The latch expires after 60 s so that a dead script does not leave the menu entry
    blocked. A genuinely long job, such as downloading ten catalogue pages against a slow
    remote engine, can go past that and let a second one start. Whoever takes a while
    calls this between steps."""
    xbmcgui.Window(10000).setProperty(clave, str(time.time()))


def quitar_pestillo(clave):
    xbmcgui.Window(10000).clearProperty(clave)


def folder_is_writable(folder):
    # Better to find out now than after swallowing 100 MB
    probe = join_path(folder, '.ekhorus_write_test')
    written = False
    try:
        handle = xbmcvfs.File(probe, 'w')
        try:
            written = bool(handle.write(bytearray(b'0')))
        finally:
            handle.close()
    except Exception as ex:
        logger("Carpeta no escribible (%s): %s" % (folder, ex))
        written = False

    xbmcvfs.delete(probe)
    return written


def copy_with_progress(source_path, target_path, message):
    # xbmcvfs.copy() leaves Kodi frozen, with no bar and no way to cancel. With a 100 MB
    # APK that is no good, so it is copied in chunks the same as when downloading
    dp = xbmcgui.DialogProgress()
    dp.create(HEADING, message)

    try:
        source = xbmcvfs.File(source_path)
        try:
            total = source.size()
            target = xbmcvfs.File(target_path, 'w')
            try:
                copied = 0
                while True:
                    if dp.iscanceled():
                        raise DownloadCanceled()

                    chunk = source.readBytes(APK_CHUNK_SIZE)
                    if not chunk:
                        break

                    if not target.write(chunk):
                        raise IOError(translate(30072) or "Error al escribir en el disco")

                    copied += len(chunk)

                    if total:
                        dp.update(min(int(copied * 100 / total), 100),
                                  "%s\n%s / %s" % (message, format_size(copied), format_size(total)))
            finally:
                target.close()
        finally:
            source.close()
    finally:
        dp.close()

    written = xbmcvfs.Stat(target_path).st_size()
    if total and written < total:
        raise IOError("Copia incompleta (%s de %s)" % (format_size(written), format_size(total)))

    return written


def stage_apk_public(path):
    # The Android installer does not see Kodi's private sandbox. For the intent to work,
    # the APK has to be in public storage, that is to say in /storage/
    if path.startswith('/storage/'):
        return path

    target_dir = next((f for f in APK_FOLDER_CANDIDATES if xbmcvfs.exists(f)), None)
    if not target_dir:
        logger("Sin almacenamiento publico donde preparar el APK", 'error')
        return None

    target = join_path(target_dir, os.path.basename(path))
    # /sdcard/Download is /storage/emulated/0/Download under another name, and copying the
    # APK onto itself would begin by deleting the only copy there is.
    if '://' not in path and os.path.realpath(path) == os.path.realpath(target):
        return target

    if xbmcvfs.exists(target):
        xbmcvfs.delete(target)

    try:
        copy_with_progress(path, target, translate(30066))
    except DownloadCanceled:
        xbmcvfs.delete(target)
        logger("Preparacion del APK cancelada por el usuario")
        return None
    except Exception as ex:
        xbmcvfs.delete(target)
        logger("No se pudo copiar el APK a almacenamiento publico: %s" % ex, 'error')
        xbmcgui.Dialog().ok(HEADING, translate_fmt(30073, os.path.basename(path), ex))
        return None

    logger("APK preparado en almacenamiento publico: %s" % target)
    return target


def try_pm_install(apk_path):
    # Only works with root or with Kodi as a system app, which some Android TV boxes do
    attempts = (
        ['pm', 'install', '-r', apk_path],
        ['su', '-c', 'pm install -r "%s"' % apk_path],
    )

    for command in attempts:
        try:
            proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  timeout=PM_INSTALL_TIMEOUT, check=False)
        except Exception as ex:
            logger("pm install (%s) fallo: %s" % (command[0], ex))
            continue

        output = (proc.stdout or b'').decode('utf-8', 'replace').strip()
        logger("pm install (%s): rc=%s %s" % (command[0], proc.returncode, output))

        if proc.returncode == 0 and 'Success' in output:
            return True

    return False


def launch_apk_installer(path):
    uri = 'file://' + urllib_parse.quote(path, safe='/')

    if is_espakodi_build():
        # The bridge in the APK itself, which does the conversion to content:// that Kodi 21
        # does not do. Without it, on EspaKodi the direct intent installs nothing.
        builtin = (f'StartAndroidActivity("espakodi.kodi","ekapk.install","","{uri}",'
                   f'"","","","","espakodi.kodi.EkApk")')
    else:
        builtin = ('StartAndroidActivity("", "android.intent.action.VIEW", '
                   '"application/vnd.android.package-archive", "%s", "1")' % uri)

    logger("Lanzando instalador de Android: %s" % builtin)
    apartar_musica()
    xbmc.executebuiltin(builtin)


def open_unknown_sources_settings():
    apartar_musica()
    xbmc.executebuiltin('StartAndroidActivity("", "android.settings.MANAGE_UNKNOWN_APP_SOURCES")')


def apk_post_download(dest, filename):
    if system_platform != 'android':
        xbmcgui.Dialog().ok(HEADING, translate_fmt(30060, filename, dest))
        return

    autoinstall = apk_autoinstall_supported()

    while True:
        options, actions = list(), list()

        if autoinstall:
            options.append(translate(30061))
            actions.append('install')

        options.append(translate(30062))
        actions.append('manual')
        options.append(translate(30063))
        actions.append('sources')

        if not autoinstall:
            # With no FileProvider the intent does not install, but with root or Kodi as a
            # system app pm install is still a way through
            options.append(translate(30068))
            actions.append('pm_install')

        options.append(translate(30064))
        actions.append('close')

        selected = xbmcgui.Dialog().select(translate(30065), options)
        if selected < 0:
            return

        action = actions[selected]

        if action == 'install':
            staged = stage_apk_public(dest)
            if not staged:
                continue
            launch_apk_installer(staged)
            return

        elif action == 'pm_install':
            staged = stage_apk_public(dest)
            if not staged:
                continue
            if try_pm_install(staged):
                xbmcgui.Dialog().ok(HEADING, translate(30069))
                return
            xbmcgui.Dialog().ok(HEADING, translate(30070))

        elif action == 'manual':
            xbmcgui.Dialog().ok(HEADING, translate_fmt(30055, dest))

        elif action == 'sources':
            open_unknown_sources_settings()
            return

        else:
            return


def sha256_of(path):
    import hashlib

    digest = hashlib.sha256()
    handle = xbmcvfs.File(path)
    try:
        while True:
            chunk = handle.readBytes(APK_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    finally:
        handle.close()

    return digest.hexdigest()


def download_apk(filename, urls, sha256=''):
    """urls: the main address first and then the backups; the empty ones are skipped."""
    # Every click on the menu starts the plugin from scratch, so a python Lock would be
    # useless and the latch has to live in a Window property. Without it, two clicks in
    # a row write at the same time into the same .part and corrupt it
    window = xbmcgui.Window(10000)
    lock = _APK_LATCH + filename

    if window.getProperty(lock) == 'true':
        xbmcgui.Dialog().notification(HEADING, translate_fmt(30071, filename), icon_path)
        return

    window.setProperty(lock, 'true')
    try:
        _download_apk(filename, [u for u in urls if u], sha256)
    finally:
        window.clearProperty(lock)


def _apk_bad_download(partial, filename, sha256):
    """Why the downloaded file cannot be accepted, or '' if it is good."""
    # Last filter before calling it good. If the server did not send Content-Length
    # we could not check the size, so at least the ZIP is validated
    if apk_looks_valid(partial) is False:
        logger("El APK descargado esta corrupto: %s" % partial, 'error')
        return translate_fmt(30079, filename)

    # The hash only arrives if the manifest carries it. It is the only thing that tells
    # "it arrived whole" from "what was announced arrived". If it cannot be computed (a
    # read failure) we carry on: throwing away 100 MB over a local stumble is worse
    if sha256:
        try:
            descargado = sha256_of(partial)
        except Exception as ex:
            logger("No se pudo calcular el sha256 de %s: %s" % (partial, ex), 'error')
            descargado = ''

        if descargado and descargado != sha256:
            logger("sha256 no coincide en %s: %s en vez de %s" % (filename, descargado, sha256), 'error')
            return translate_fmt(30079, filename)

    return ''


def _apk_pick_folder(filename):
    """Folder to save the APK in, or '' if the user backs out.

    Kodi's browse() hands back the folder it was told to start in when it is cancelled, so
    with the last folder as that start, Back downloaded all the same (seen on the phone). The
    last folder is offered on its own instead, and the browser starts from nothing."""
    heading = translate_fmt(30053, filename)
    last = default_apk_folder()
    if last:
        choice = xbmcgui.Dialog().select(heading, [translate_fmt(30167, last), translate(30168)])
        if choice < 0:
            return ''
        if choice == 0:
            return last

    return xbmcgui.Dialog().browse(3, heading, 'files', '', False, False, '')


def _download_apk(filename, urls, sha256=''):
    folder = _apk_pick_folder(filename)
    if not folder:
        return

    if not folder_is_writable(folder):
        xbmcgui.Dialog().ok(HEADING, translate_fmt(30067, folder))
        return

    set_setting("last_apk_folder", folder)

    dest = join_path(folder, filename)
    partial = dest + '.part'

    if xbmcvfs.exists(dest):
        if apk_looks_valid(dest) is False:
            # It is corrupt, so we neither ask nor offer it; it is redone and that is that
            logger("El APK existente esta corrupto, se descarga de nuevo: %s" % dest, 'error')
            xbmcgui.Dialog().ok(HEADING, translate_fmt(30078, filename))
            xbmcvfs.delete(dest)
        else:
            redownload = xbmcgui.Dialog().yesno(HEADING, translate_fmt(30056, filename),
                                                nolabel=translate(30077), yeslabel=translate(30076))
            if not redownload:
                # The APK is already there and it is fine, so the install options are offered.
                # The other way would be stranding them or making them fetch 100 MB for nothing
                apk_post_download(dest, filename)
                return
            xbmcvfs.delete(dest)

    if xbmcvfs.exists(partial):
        xbmcvfs.delete(partial)

    message = translate_fmt(30054, filename)
    dp = xbmcgui.DialogProgress()
    dp.create(HEADING, message)

    # A cut or tampered file from the main address also moves on to the backup: it is
    # the same file, and a bad copy on one host says nothing about the other.
    error = translate_fmt(30058, filename, '')
    for url in urls:
        try:
            download_to(url, partial, dp, message)
        except DownloadCanceled:
            dp.close()
            xbmcvfs.delete(partial)
            logger("Descarga cancelada por el usuario: %s" % filename)
            xbmcgui.Dialog().notification(HEADING, translate(30057), icon_path)
            return
        except WriteFailed as ex:
            # The disk and not the host: from the backup it would fill up just the same, after
            # the same wait all over again.
            logger(f'No se pudo escribir {filename} en {folder}: {ex}', 'error')
            error = translate_fmt(30058, filename, ex)
            xbmcvfs.delete(partial)
            break
        except Exception as ex:
            logger("Error descargando %s de %s: %s" % (filename, url, ex), 'error')
            error = translate_fmt(30058, filename, ex)
        else:
            error = _apk_bad_download(partial, filename, sha256)
            if not error:
                break
        xbmcvfs.delete(partial)

    dp.close()

    if error:
        xbmcgui.Dialog().ok(HEADING, error)
        return

    # The final name is only given if the download finished whole. That way a half APK
    # never looks installable
    if not xbmcvfs.rename(partial, dest):
        if not xbmcvfs.copy(partial, dest):
            # Careful, returning the .part path is no good here. Android does not treat it
            # as an APK and we would offer to install something that cannot be installed
            logger("No se pudo dejar el APK como %s" % dest, 'error')
            xbmcvfs.delete(partial)
            xbmcgui.Dialog().ok(HEADING, translate_fmt(30080, filename))
            return
        xbmcvfs.delete(partial)

    logger("APK descargado en %s" % dest)
    apk_post_download(dest, filename)


class DescargaCancelada(Exception):
    """The user pressed Cancel on the download dialog."""


def downloadFile(url, dest, dp=None, pestillo=None):
    import socket
    from urllib.request import urlretrieve

    def _pbhook(numblocks, blocksize, filesize, url=None, dp=None):
        # The caller's latch, renewed as the bytes arrive: it expires after a minute and a
        # slow line takes longer than that.
        if pestillo:
            refrescar_pestillo(pestillo)

        if not dp:
            return

        # The only way out of urlretrieve is an exception. Until this, the Cancel button of
        # the dialog was there and did nothing: the 40 MB came down whole.
        if dp.iscanceled():
            raise DescargaCancelada(url)

        # dp.update() only accepts int. Besides, when the server does not send the size,
        # urlretrieve passes filesize = -1: without this guard the percentage came out
        # negative (or stuck at 100% after jumping to the exception) for the whole download.
        if filesize > 0:
            percent = int(min(numblocks * blocksize * 100 / filesize, 100))
        else:
            percent = 0

        dp.update(max(0, percent))

    # urlretrieve takes no timeout, so the socket one is set, to make a stuck download
    # end up cutting off instead of leaving the dialog hanging indefinitely.
    previo = socket.getdefaulttimeout()
    socket.setdefaulttimeout(HTTP_TIMEOUT * 3)
    try:
        urlretrieve(url, dest, lambda nb, bs, fs, url=url: _pbhook(nb, bs, fs, url, dp))
    finally:
        socket.setdefaulttimeout(previo)

    time.sleep(1)

    return xbmcvfs.Stat(dest).st_size()


def extractFile(source, dest):
    import tarfile
    import zipfile
    ret = True

    if tarfile.is_tarfile(source):
        tar = tarfile.open(source, "r:*")
        tar.extractall(dest)
        tar.close()

    elif zipfile.is_zipfile(source):
        zip = zipfile.ZipFile(source, 'r')
        zip.extractall(dest)
        zip.close()

    else:
        ret = False

    return ret


def ruta_motor_instalado():
    """Folder of the engine EKHorus keeps on this machine, or '' if there is none.

    The setting also holds 'motor externo' where install_acestream() installs nothing (the
    Ubuntu snap, an unsupported architecture) and 'false' before the first attempt. Neither is
    a folder, and a folder that is gone is no engine either."""
    ruta = ADDON.getSetting('install_acestream')
    return ruta if ruta and os.path.isdir(ruta) else ''


def motor_sin_instalar():
    """True when there is no engine of ours on this machine and one can be installed.

    Before the first attempt the setting holds 'false'; after one, the folder, 'motor externo'
    where nothing gets installed, or an empty string if the download failed. A folder that is
    gone counts as well: whoever deletes it by hand gets it back the next time it is needed,
    as the reinstall button would give it."""
    ruta = ADDON.getSetting('install_acestream')
    if ruta == 'motor externo':
        return False

    return ruta in ('', 'false') or not os.path.isdir(ruta)


def install_acestream(pestillo=None):
    """Downloads and unpacks the engine EKHorus runs on Windows and Linux.

    True if there is an engine to run afterwards, or nothing to install on this platform;
    False if it failed, once the user has been told. 'pestillo' is the latch the caller holds
    while bringing the engine up: it expires after a minute and a download can take longer,
    so it is renewed as the bytes arrive."""
    ruta = ruta_zip = ruta_extract = url = None
    set_setting("install_acestream", '')
    set_setting("acestream_cachefolder", '')

    if not system_platform in ['linux', 'windows']:
        logger("install_acestream: system_platform = %s" % str((system_platform, arquitectura, root)))
        return False

    elif system_platform == "windows":
        ruta = translatePath("special://home")
        ruta_zip = os.path.join(ruta, "userdata", "acestream_win.zip")
        ruta_extract = data_path
        url ="https://github.com/Carlesto/Horus/releases/download/ace/acestream_win.zip" # acestream_win

    elif arquitectura == "arm" or (arquitectura == "aarch" and root):
        ruta = translatePath("special://home")
        ruta_zip = os.path.join(ruta, "userdata", "acestream.tar.gz")
        ruta_extract = data_path
        url = "https://github.com/Carlesto/Horus/releases/download/ace/acestream_elec.tar.gz" # linaroNDK

    elif arquitectura == "x86" and root:
        ruta = translatePath("special://home")
        ruta_zip = os.path.join(ruta, "userdata", "acestream.tar.gz")
        ruta_extract = data_path
        url = "https://github.com/Carlesto/Horus/releases/download/ace/acestream_x86.tar.gz" # acestream_x86

    else:
        logger("install_acestream: motor externo system_platform = %s" % str((system_platform, arquitectura, root)))
        set_setting("install_acestream", 'motor externo')
        return True


    dp = xbmcgui.DialogProgress()
    dp.create(HEADING, translate(30000))
    logger("Descargando Acestream...")

    try:
        downloadFile(url, ruta_zip, dp, pestillo=pestillo)
    except DescargaCancelada:
        # Whoever cancels wants out, not a notice; and the piece that came down is no use.
        logger("Descarga de Acestream cancelada")
        dp.close()
        if os.path.exists(ruta_zip): os.remove(ruta_zip)
        return False
    except Exception as e:
        logger("Error descargando Acestream: %s" % e, 'error')
        dp.close()
        if os.path.exists(ruta_zip): os.remove(ruta_zip)
        xbmcgui.Dialog().ok(HEADING, translate(30050))
        return False

    dp.update(0, translate(30001))
    logger("Descarga Completa: %s" %ruta_zip)
    time.sleep(1)

    dp.update(33, translate(30002))
    if pestillo:
        refrescar_pestillo(pestillo)
    try:
        extraido = extractFile(ruta_zip, ruta_extract)
    except Exception as e:
        # A damaged archive raises from inside tarfile or zipfile; without this the dialog
        # stayed planted and the script died with it.
        logger("Error al descomprimir Acestream: %s" % e, 'error')
        extraido = False

    if extraido:
        logger("Archivos descomprimidos en %s" %ruta_extract)
    else:
        dp.update(100, translate(30003) %ruta_extract)
        logger("Error al descomprimir Archivos...")
        if os.path.exists(ruta_zip): os.remove(ruta_zip)
        time.sleep(2)
        dp.close()
        return False

    if pestillo:
        refrescar_pestillo(pestillo)

    dp.update(90, translate(30004))
    if os.path.exists(ruta_zip): os.remove(ruta_zip)
    logger("Limpiando Archivos...")

    dp.update(100, translate(30005))
    time.sleep(3)
    dp.close()
    if system_platform == "windows":
        set_setting("install_acestream", os.path.join(ruta_extract, 'acestream', 'engine'))
    else:
        set_setting("install_acestream", os.path.join(ruta_extract, 'acestream.engine'))

    return True


system_platform, arquitectura, root = get_system_platform()

# Not in the batches of "Guardar todo" (lib/playback_watch.py): there is one for every video
# watched outside EKHorus, and the log would keep the time of each.
if not ''.join(sys.argv[2:3]).startswith('?action=anotar&'):
    logger((system_platform, arquitectura, root))

    if system_platform == 'android':
        # It is left in the log whether the EspaKodi install bridge is available. It is the
        # first thing to look at when somebody says an APK will not install for them.
        logger(f"puente de instalacion de EspaKodi: {is_espakodi_build()}")
# The import goes last because Server is instantiated right here, with settings read.
from acestream.server import Server
server = Server(host=get_setting("ip_addr", "127.0.0.1"), port=engine_port())
