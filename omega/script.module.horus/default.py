# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
# EKHorus by RubénSDFA1laberot, based on Horus by Caperucitaferoz and previous work by:
# - Enen92 (https://github.com/enen92)
# - Joian (https://github.com/jonian)
#
# Thanks to those who have collaborated in any way, especially to:
# - @Canna_76
# - @AceStreamMOD
# - @luisma66 (tester raspberry)
# - logon84 (EKHorus - for ass:// links, reading from txt and Pastebin)
#
# This file is part of EKHorus for Kodi
#
# EKHorus for Kodi is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Changes in this Horus Mod (EKHorus) over Caperucitaferoz's original 1.1.9 (see the credits above):
# - ass:// links (resolved by DNS over elcano.top and decoded from base64/gzip, nested lists included).
# - Direct text search on acestreamsearch.net and search-ace.stream.
# - Several sources at once, separating the addresses with ; (merges and drops duplicates).
# - New list formats: pastebin/.txt, elcano and vercel.app / netlify.app pages.
# - A second selectable engine.
# - QR code of the acestream:// link as the item cover art.
# - Listitems with the modern getVideoInfoTag API and the manual ID accepting a 40-character hash.
#-------------------------------------------------------------------------------

import sys

# The watch of "Guardar todo", started from the History when it is switched on, lasts in this
# invocation for as long as it stays on (lib/playback_watch.py). It goes before anything else
# because lib.utils keeps an Addon() alive, and Kodi only refreshes the settings of the oldest one.
# Kodi takes SystemExit as an early end, with no error in its log, and nothing below gets loaded.
if sys.argv[2:3] == ['?action=vigilar']:
    from lib import playback_watch
    playback_watch.vigilar()
    sys.exit()

from lib.utils import *
import base64
import functools
import gzip
import json
import shlex
import threading

from lib import alternatives, elementum, history, ui_common
from acestream.engine import Engine
from acestream.server import Server
from acestream.stream import Stream

error_flag = False

ICONO_ERROR = os.path.join(runtime_path, 'resources', 'media', 'error.png')


def plugin_handle():
    """Kodi directory handle, or -1 if the addon was not called as a plugin."""
    try:
        return int(sys.argv[1])
    except (IndexError, ValueError):
        return -1


_directorio_cerrado = False

def cerrar_directorio(succeeded=True, update=False, cache=False):
    """Closes the Kodi directory exactly once, if there is one at all.

    When another addon calls us with PlayMedia (that is how StreamNinja does it),
    Kodi gives us a handle and waits for an answer: if the script ends without
    giving one, it throws a "playback failed" over the video that is already
    opening. It is easy to forget in some exit branch, so it is centralised here."""
    global _directorio_cerrado

    handle = plugin_handle()
    if handle < 0 or _directorio_cerrado:
        return

    _directorio_cerrado = True
    xbmcplugin.endOfDirectory(handle=handle, succeeded=succeeded,
                              updateListing=update, cacheToDisc=cache)


class OSD(object):
    def __init__(self, stats):
        self.showing = False
        self.window = xbmcgui.Window(12901)
        self.stats = stats

        viewport_w, viewport_h = self._get_skin_resolution() #(1280, 720)
        posX = viewport_w - 305
        posY = 75

        window_w = 300
        window_h = 250
        font_max = 'font13'
        font_min = 'font10'

        # Background
        self.horus_background = xbmcgui.ControlImage(x=posX, y=posY, width=window_w, height=window_h,
                                                     filename=os.path.join(runtime_path, 'resources', 'media' , 'background.png'))
        # icon
        self.horus_icon = xbmcgui.ControlImage(x=posX + 25, y=posY + 15, width=38, height=28,
                                               filename=os.path.join(runtime_path, 'resources', 'media' , 'acestreamlogo.png'))
        # title
        self.horus_title = xbmcgui.ControlLabel(x=posX + 78, y=posY + 13, width=window_w - 10, height=30,
                                                label="Horus", font=font_max, textColor='0xFFEB9E17')
        # sep
        self.horus_sep1 = xbmcgui.ControlImage(x=posX + 5, y=posY + 55, width=window_w - 10, height=1,
                                               filename=os.path.join(runtime_path, 'resources', 'media', 'separator.png'))
        # Stats
        self.horus_status = xbmcgui.ControlLabel(x=posX + 25, y=posY + 80, width=window_w - 10, height=30, font=font_min, label=translate(30009) % '')
        self.horus_speed_down = xbmcgui.ControlLabel(x=posX + 25, y=posY + 100, width=window_w - 10, height=30, font=font_min, label=translate(30010) % 0)
        self.horus_speed_up = xbmcgui.ControlLabel(x=posX + 25, y=posY + 120, width=window_w - 10, height=30, font=font_min, label=translate(30011) % 0)
        self.horus_peers = xbmcgui.ControlLabel(x=posX + 25, y=posY + 140, width=window_w - 10, height=30, font=font_min, label=translate(30012) % 0)
        self.horus_downloaded = xbmcgui.ControlLabel(x=posX + 25, y=posY + 170, width=window_w - 10, height=30, font=font_min, label=translate(30013) % 0)
        self.horus_uploaded = xbmcgui.ControlLabel(x=posX + 25, y=posY + 190, width=window_w - 10, height=30, font=font_min, label=translate(30014) % 0)

        # sep
        self.horus_sep2 = xbmcgui.ControlImage(x=posX + 5, y=posY + window_h - 30, width=window_w - 10, height=1,
                                               filename=os.path.join(runtime_path, 'resources', 'media', 'separator.png'))

    def update(self,**kwargs):
        if self.showing:
            status = {'dl':translate(30007), 'prebuf': translate(30008) %(self.stats.progress) + '%'}
            self.horus_status.setLabel(translate(30009) % status.get(self.stats.status, self.stats.status))
            self.horus_speed_down.setLabel(translate(30010) % self.stats.speed_down)
            self.horus_speed_up.setLabel(translate(30011) % self.stats.speed_up)
            self.horus_peers.setLabel(translate(30012) % self.stats.peers)
            self.horus_downloaded.setLabel(translate(30013) % (self.stats.downloaded // 1048576))
            self.horus_uploaded.setLabel(translate(30014) % (self.stats.uploaded // 1048576))

    def show(self):
        self.window.addControl(self.horus_background)
        self.window.addControl(self.horus_icon)
        self.window.addControl(self.horus_title)
        self.window.addControl(self.horus_sep1)
        self.window.addControl(self.horus_status)
        self.window.addControl(self.horus_speed_down)
        self.window.addControl(self.horus_speed_up)
        self.window.addControl(self.horus_peers)
        self.window.addControl(self.horus_downloaded)
        self.window.addControl(self.horus_uploaded)
        self.window.addControl(self.horus_sep2)
        self.showing = True

    def hide(self):
        self.showing = False
        self.window.removeControl(self.horus_background)
        self.window.removeControl(self.horus_icon)
        self.window.removeControl(self.horus_title)
        self.window.removeControl(self.horus_sep1)
        self.window.removeControl(self.horus_status)
        self.window.removeControl(self.horus_speed_down)
        self.window.removeControl(self.horus_speed_up)
        self.window.removeControl(self.horus_peers)
        self.window.removeControl(self.horus_downloaded)
        self.window.removeControl(self.horus_uploaded)
        self.window.removeControl(self.horus_sep2)

    def _get_skin_resolution(self):
        # If the skin does not declare a resolution (or its xml cannot be read), it
        # falls back to the classic 1280x720: a slightly misplaced OSD is better than
        # blocking playback altogether, which is what used to happen.
        try:
            import xml.etree.ElementTree as ET
            skin_path = translatePath("special://skin/")
            tree = ET.parse(os.path.join(skin_path, "addon.xml"))
            try: res = tree.findall("./res")[0]
            except IndexError: res = tree.findall("./extension/res")[0]
            return int(res.attrib["width"]), int(res.attrib["height"])
        except Exception as e:
            logger("_get_skin_resolution: %s" % e, 'error')
            return 1280, 720

    def close(self):
        try:
            self.hide()
        except:
            pass


class MyPlayer(xbmc.Player):
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MyPlayer, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        logger("MyPlayer init")
        self.total_Time = 0
        self.monitor = xbmc.Monitor()
        xbmc.Player().stop()
        while xbmc.Player().isPlaying() and not self.monitor.abortRequested():
            self.monitor.waitForAbort(1)


    def playStream(self, stream, title='', iconimage='', plot='', init_time=0.0):
        self.AVStarted = False
        self.is_active = True
        self.init_time = float(init_time)
        # If the video dies before the first valid getTime(), current_time
        # was read without ever having been assigned (AttributeError).
        self.current_time = 0.0
        self.osd = OSD(stream.stats)

        status = 'failed'

        listitem = xbmcgui.ListItem()
        # The engine may give neither filename nor id (and the caller, no title):
        # setTitle(None) raises TypeError and playback died here, mute.
        title = title or stream.filename or stream.id or ADDON_NAME
        poner_info_video(listitem, title, plot)
        art = {'icon': iconimage if iconimage else os.path.join(runtime_path, 'resources', 'media', 'icono_aces_horus.png')}
        listitem.setArt(art)

        # The watch of "Guardar todo" tells this playback from another addon's by it: both play
        # the engine's session address, and this one is noted already. Off, nothing is left.
        if get_setting('anotar_fuera'):
            from lib.playback_watch import PROPIA
            xbmcgui.Window(10000).setProperty(PROPIA, stream.playback_url)
        self.play(stream.playback_url, listitem)
        cerrar_directorio(succeeded=False, update=True)
        xbmc.executebuiltin('Dialog.Close(all,true)')

        show_stat = False
        while self.is_active and not self.monitor.abortRequested():
            try:
                self.current_time = self.getTime()
            except:
                pass
            if get_setting("show_osd"):
                """if show_stat:
                    # update stat
                    self.osd.update()"""

                if not show_stat and xbmc.getCondVisibility('Window.IsActive(videoosd)'):
                    #show windows OSD
                    self.osd.show()
                    stream.connect('stats::updated', self.osd.update)
                    show_stat = True

                elif not xbmc.getCondVisibility('Window.IsActive(videoosd)'):
                    # hide windows OSD
                    if self.osd.showing:
                        self.osd.hide()
                        stream.disconnect('stats::updated')
                    show_stat = False

            self.monitor.waitForAbort(1)

        if self.AVStarted:
            if self.current_time > 180 and stream.id:
                set_setting("last_id", stream.id)

            if self.current_time >= 0.9 * self.total_Time:
                status = 'finished'
            else:
                status = 'stopped'

            clear_cache()

        # Outside the if on purpose: if the OSD did get shown and playback never
        # started, its controls stayed stuck in the video window.
        osd = getattr(self, 'osd', None)
        if osd:
            osd.close()

        return status

    def onAVStarted(self):
        logger("PLAYBACK AVSTARTED")
        self.AVStarted = True
        self.total_Time = self.getTotalTime()
        if self.init_time:
            self.seekTime(self.init_time)

    def onPlayBackEnded(self):
        logger("PLAYBACK ENDED") # Network drop or end of video
        self.is_active = False

    def onPlayBackStopped(self):
        logger("PLAYBACK STOPPED") # Stopped by the user, or never started because of http 429
        self.is_active = False

    def onPlayBackError(self):
        logger("PLAYBACK ERROR")
        self.is_active = False

    def onPlayBackStarted(self):
        logger("PLAYBACK STARTED")

    def kill(self):
        logger("Play Kill")
        self.is_active = False


CACHE_DIR_NAME = '.acestream_cache'
# On Windows the engine calls the same thing by another name.
CACHE_DIR_NAMES = (CACHE_DIR_NAME, '_acestream_cache_')
# Margin before emptying the cache of an engine other than the one just used.
CACHE_IDLE_SECONDS = 60
# Cap on the scan, in case the tree is odd and returns a wild list.
CACHE_MAX_DIRS = 8


def is_cache_dir(path):
    """Fence around the deletion.

    The .ACEStream folders around it are the engine profile, with its acestream.conf
    and its database inside. Emptying them would leave it unconfigured, so only the
    cache folder proper is touched."""
    return os.path.basename(os.path.normpath(path)) in CACHE_DIR_NAMES


def cache_candidates():
    """(engine, path) pairs where the cache may be, per platform.

    On Android BOTH engines are ALWAYS returned. Before, only the one selected at that
    moment was looked at, so for whoever alternated between them the cache of the one
    being dropped grew without limit."""
    paths = list()
    install = ruta_motor_instalado() or None

    if system_platform == "windows":
        drive = os.getenv("SystemDrive") or "C:"
        paths.append((ENGINE_ACESTREAM, os.path.join(drive + os.sep, '_acestream_cache_')))
        for var in ("LOCALAPPDATA", "APPDATA", "USERPROFILE"):
            base = os.getenv(var)
            if base:
                paths.append((ENGINE_ACESTREAM, os.path.join(base, 'ACEStream', 'cache', CACHE_DIR_NAME)))

    elif system_platform == "linux":
        home = os.getenv("HOME")
        if home:
            paths.append((ENGINE_ACESTREAM, os.path.join(home, '.ACEStream', 'cache', CACHE_DIR_NAME)))
            paths.append((ENGINE_ACESTREAM, os.path.join(home, '.ACEStream', CACHE_DIR_NAME)))

    else:
        # node is today's official app package (checked in September 2026 against 3.2.22);
        # engine is the old one, and media and core are the ones in between, with their
        # .atv variants for Android TV. All are tried because which one exists depends on
        # the app the user has installed, and node goes first as the most likely.
        paquetes = (
            (ENGINE_ACESTREAM, 'org.acestream.node'),
            (ENGINE_ACESTREAM, 'org.acestream.node.atv'),
            (ENGINE_ACESTREAM, 'org.acestream.engine'),
            (ENGINE_ACESTREAM, 'org.acestream.media'),
            (ENGINE_ACESTREAM, 'org.acestream.media.atv'),
            (ENGINE_ACESTREAM, 'org.acestream.core'),
            (ENGINE_ACESTREAM, 'org.acestream.core.atv'),
            (ENGINE_ACESERVE, ENGINE_ACESERVE),
        )

        for engine, paquete in paquetes:
            # With scoped storage from Android 10 onwards, an app only writes under
            # Android/data. This is the path the current official app really uses, checked
            # on an Android 11: the old shape below is no longer created by anybody, but
            # it is kept for the devices still on Android 9.
            paths.append((engine,
                          f'/storage/emulated/0/Android/data/{paquete}/files/.ACEStream/{CACHE_DIR_NAME}'))
            paths.append((engine,
                          f'/storage/emulated/0/{paquete}/files/.ACEStream/{CACHE_DIR_NAME}'))
            paths.append((engine,
                          f'/storage/emulated/0/{paquete}/.ACEStream/{CACHE_DIR_NAME}'))

    if install:
        paths.append((ENGINE_ACESTREAM, os.path.join(install, CACHE_DIR_NAME)))
        paths.append((ENGINE_ACESTREAM, os.path.join(install, 'data', CACHE_DIR_NAME)))

    paths.append((ENGINE_ACESTREAM, os.path.join(data_path, CACHE_DIR_NAME)))

    # normpath: several came with a trailing slash and join produced double separators.
    return [(engine, os.path.normpath(path)) for engine, path in paths]


def find_cache_dirs(root, max_depth=4):
    """All the caches under 'root', bounding the depth.

    The original version did os.walk() from the root of the disk at the end of every
    playback, and on top of that kept only the first one it found."""
    encontradas = list()

    if not root or not os.path.isdir(root):
        return encontradas

    root = os.path.abspath(root)
    base_depth = root.rstrip(os.sep).count(os.sep)

    for dirpath, dirnames, _filenames in os.walk(root):
        # It is checked first and pruned afterwards: the other way round, a cache sitting
        # exactly at the limit level was never looked at.
        if is_cache_dir(dirpath):
            encontradas.append(dirpath)
            dirnames[:] = []  # there is no cache inside a cache
        elif dirpath.rstrip(os.sep).count(os.sep) - base_depth >= max_depth:
            dirnames[:] = []

        if len(encontradas) >= CACHE_MAX_DIRS:
            break

    return encontradas


def cache_last_write(path):
    """When the cache was last written to.

    The folder mtime is not enough, as it only changes when entries are created or
    deleted and not when writing inside a file that already exists. A cache in full
    use can look idle if only that is looked at."""
    ultimo = os.path.getmtime(path)

    try:
        with os.scandir(path) as entradas:
            for entrada in entradas:
                ultimo = max(ultimo, entrada.stat().st_mtime)
    except OSError as e:
        logger(f"cache_last_write: {path}: {e}", 'error')

    return ultimo


def purge_cache_dir(path):
    """Empties the contents of a cache, never the folder itself.

    Returns how many items it deleted."""
    if not is_cache_dir(path) or not os.path.isdir(path) or os.path.islink(path):
        logger(f"purge_cache_dir: no es una cache, no se toca: {path}", 'error')
        return 0

    borrados = 0
    dirnames, filenames = xbmcvfs.listdir(path)

    for name in filenames:
        try:
            if xbmcvfs.delete(os.path.join(path, name)):
                borrados += 1
        except Exception as e:
            logger(f"purge_cache_dir: {name}: {e}", 'error')

    for name in dirnames:
        sub = os.path.join(path, name)
        try:
            # rmdir with force also deletes whatever is inside. Before, only the loose
            # files were walked and the pieces in subfolders were left behind.
            if not os.path.islink(sub) and xbmcvfs.rmdir(sub, True):
                borrados += 1
        except Exception as e:
            logger(f"purge_cache_dir: {name}: {e}", 'error')

    return borrados


def clear_cache():
    inicio = time.time()

    try:
        recordadas = get_setting("acestream_cachefolder", None)
        # A single path used to be stored as text; now it is the list of all of them.
        if isinstance(recordadas, str):
            recordadas = [recordadas] if recordadas else list()
        elif not isinstance(recordadas, list):
            recordadas = list()

        activo = active_engine()

        # The candidates go first. That way a remembered path left stale by an engine
        # change can no longer hide the good one, which is what made the cache of the
        # wrong engine be cleaned every time.
        objetivos = dict()
        for engine, path in cache_candidates():
            if os.path.isdir(path):
                objetivos.setdefault(path, engine)
        for path in recordadas:
            if isinstance(path, str) and os.path.isdir(path):
                objetivos.setdefault(path, None)

        if not objetivos:
            # Last resort and the only expensive route: search under the engine folder
            # and the addon one. Never over the whole disk.
            for root in (ruta_motor_instalado() or None, data_path):
                for path in find_cache_dirs(root):
                    objetivos.setdefault(path, None)
                if objetivos:
                    break

        if not objetivos:
            logger("clear_cache: cache no encontrada", "error")
            return

        # It is only saved when it changes: set_setting rewrites settings.xml and this
        # runs at the end of every playback.
        encontradas = sorted(objetivos)
        if encontradas != sorted(p for p in recordadas if isinstance(p, str)):
            set_setting("acestream_cachefolder", encontradas)

        for path, engine in objetivos.items():
            # The one of the engine just used is always emptied. The other one only if it has
            # been quiet for a while: AceServe may be serving a phone on the network while
            # Kodi plays through AceStream, and emptying it cuts their video off.
            if engine is not None and engine != activo:
                try:
                    if time.time() - cache_last_write(path) <= CACHE_IDLE_SECONDS:
                        logger(f"clear_cache: {path} parece en uso, se deja")
                        continue
                except OSError:
                    pass

            logger(f"clear_cache: {purge_cache_dir(path)} elementos en {path}")

        logger(f"clear_cache: {len(objetivos)} carpetas en {time.time() - inicio:.1f}s")

    except Exception as e:
        logger(f"error clear_cache: {e}", "error")


def opciones_transcode():
    """Audio parameters for the engine, per the setting. Empty if nothing needs touching.

    Only /ace/manifest.m3u8 accepts them, which means turning them on switches playback
    from MPEG-TS to HLS. That adds some latency on live, and that is why the setting comes
    off: it is turned on when a channel sounds bad, not just in case."""
    modo = get_setting('transcode_audio', 0)

    if modo == 1:
        return {'transcode_ac3': 1}
    if modo == 2:
        return {'transcode_audio': 1}

    return dict()


def elegir_fichero(ficheros):
    """Index of the file the user picks, or None if they cancel.

    The index is the one the engine gave, never the position in the list: the numbers have
    gaps because the engine keeps the torrent's own and skips whatever is not media, and a
    made-up one opens no session."""
    if len(ficheros) == 1:
        return ficheros[0]['index']

    elegido = xbmcgui.Dialog().select(translate(30110),
                                      [f['filename'] for f in ficheros])

    return None if elegido < 0 else ficheros[elegido]['index']


def read_torrent(torrent, headers=None):
    import bencodepy
    import hashlib

    infohash = None

    try:
        if torrent.lower().startswith('http'):
            torrent_file = http_get_bytes(torrent, headers)

        elif os.path.isfile(torrent):
            with open(torrent, "rb") as f:
                torrent_file = f.read()

        else:
            logger('read_torrent: origen no valido', 'error')
            return None

        metainfo = bencodepy.decode(torrent_file)
        infohash = hashlib.sha1(bencodepy.encode(metainfo[b'info'])).hexdigest()

    except Exception as e:
        # Only the kind of failure: that of a download carries the address of the .torrent.
        logger(f'read_torrent: {type(e).__name__}', 'error')

    return infohash


def infohash_de_magnet(magnet):
    """Hex infohash of a magnet link, or None if it carries none the engine can use.

    BitTorrent writes the hash in hex (40) or in base32 (32), and some sites hand out the
    second. The engine only takes hex, so base32 is converted. Before this, a base32 hash
    that happened to start with hex letters was cut at the first that was not and sent to the
    engine as a five-letter identifier."""
    encontrado = re.search(r'xt=urn:btih:([0-9a-z]+)', magnet, re.I)
    if not encontrado:
        return None

    valor = encontrado.group(1)

    if len(valor) == 40 and re.fullmatch(r'[0-9a-f]{40}', valor, re.I):
        return valor.lower()

    if len(valor) == 32:
        try:
            return base64.b32decode(valor.upper()).hex()
        except ValueError:
            return None

    return None


PESTILLO_MOTOR = 'ekhorus.motor'


def motor_disponible():
    """server.available without ten seconds of silence against a dead remote host.

    ping() is a one-second TCP probe. On this machine it answers or is refused at once, so
    nothing is added; against an address that drops packets it is what keeps the Cancel
    button of the wait dialog alive, which used to be looked at once per request."""
    return server.ping(timeout=1) and server.available


class MotorNoDisponible(Exception):
    """The wait for an engine ended without one: cancelled, timed out, refused or impossible.

    Whoever raises it has already told the user what happened and closed its own dialog."""


def asegurar_motor():
    """Leaves an engine answering at the configured address, or raises MotorNoDisponible.

    Everything acestreams() did before asking for the stream, on its own so that Channels and
    the menu can start the engine without playing anything: on Windows and Linux it installs
    and starts the local engine, on Android it opens the engine app, with a remote address it
    only waits, and it waits with a progress dialog that can be cancelled. That dialog is
    given back if it is still open, so that whoever carries on keeps painting in it instead
    of blinking a new one; None means none was needed."""
    global error_flag
    # Hygiene: an error from an earlier invocation in the same process must not
    # contaminate this one (it matters if reuselanguageinvoker is ever enabled).
    error_flag = False
    d = None
    engine = None
    cmd_stop_acestream = None
    acestream_executable = None
    motor_lanzado = False
    remoto = not es_host_local(server.host)
    # Two presses in a row, or another addon's call during one, must not start two engines or
    # download the same zip twice. Whoever finds the latch taken only waits.
    arranca = echar_pestillo(PESTILLO_MOTOR)

    try:
        if not motor_disponible():
            if remoto:
                # Nothing to install, start or open here: the engine lives on another device,
                # and it used to get the local engine started, or the local app opened, for
                # nothing. Only the wait below.
                logger(f'asegurar_motor: motor remoto en {server.host}, solo se espera')

            elif not arranca:
                logger('asegurar_motor: otra invocacion ya esta arrancando el motor, se espera')

            else:
                install_path = ruta_motor_instalado()

                # On Windows and Linux the engine is downloaded the first time it is needed,
                # which is now. It used to happen when the menu first opened, before the wizard
                # could even ask where the engine was, and a failed download came back on every
                # press of the menu.
                if system_platform in ('windows', 'linux') and motor_sin_instalar():
                    if not install_acestream(pestillo=PESTILLO_MOTOR):
                        raise MotorNoDisponible('la instalacion del motor ha fallado')
                    install_path = ruta_motor_instalado()

                # Create an engine instance. The command ALWAYS goes as a list: passed as a
                # string, a path with spaces (C:\Users\Juan Perez\...) is split in half when
                # running it and the engine never starts.
                if system_platform == "windows":
                    if install_path:
                        acestream_executable = [os.path.join(install_path, 'ace_engine.exe')]

                elif system_platform == "linux":
                    if arquitectura == 'x86':
                        if root:
                            # LibreElec x86
                            if install_path:
                                acestream_executable = [os.path.join(install_path, 'acestream_chroot.start')]
                                cmd_stop_acestream = ["pkill", "acestream"]
                        else:
                            # Ubuntu, arch Linux, fedora, mint etc
                            if os.path.exists('/snap/acestreamplayer'):
                                acestream_executable = ['snap', 'run', 'acestreamplayer.engine']
                                cmd_stop_acestream = ["pkill", "acestream"]
                            else:
                                xbmcgui.Dialog().ok(HEADING,translate(30027))
                                raise MotorNoDisponible('sin el snap de acestreamplayer')

                    elif arquitectura == 'arm' and not root:
                        try:
                            data = ''
                            with open("/etc/os-release") as f:
                                data = ensure_str(f.read())
                            if install_path and re.search('osmc|openelec|raspios|raspbian', data, re.I):
                                # osmc, openelec, raspios and raspbian
                                acestream_executable = ['sudo', os.path.join(install_path, 'acestream.start')]
                                cmd_stop_acestream = ['sudo', os.path.join(install_path, 'acestream.stop')]
                        except: pass

                    elif install_path:
                        # LibreELEC, coreElec , alexelec, etc...
                        acestream_executable = [os.path.join(install_path, 'acestream.start')]
                        cmd_stop_acestream = [os.path.join(install_path, 'acestream.stop')]

                elif system_platform == 'android':
                    AndroidActivity = android_engine_launch()
                    # This used to be a yesno. Whoever presses a link has already said they want
                    # to play it, so asking them again only gets in the way. The one thing worth
                    # telling them is that Kodi is going to the background, and for that a notice
                    # that does not block the way is enough.
                    xbmcgui.Dialog().notification(HEADING, translate(30090), icon_path, 4000)
                    apartar_musica()
                    logger("Abriendo " + AndroidActivity)
                    xbmc.executebuiltin(AndroidActivity)
                    motor_lanzado = True

                logger("acestream_executable= %s" % acestream_executable)

                if cmd_stop_acestream:
                    set_setting("cmd_stop_acestream", cmd_stop_acestream)

                if acestream_executable and not motor_disponible():
                    engine = Engine(acestream_executable)

                elif not acestream_executable and system_platform != 'android':
                    logger("plataforma desconocida: %s" % system_platform)
                    if not xbmcgui.Dialog().yesno(HEADING, translate(30016), nolabel=translate(30017), yeslabel=translate(30018)):
                        raise MotorNoDisponible('sin motor que arrancar, y no se quiere esperar')

        # Waiting for the engine goes BEFORE the external player. That branch sends the
        # video to another app and leaves, so without waiting here VLC gets an address
        # where nobody is listening yet. The yesno that used to be here was acting as a
        # wait without meaning to, and removing it uncovered the race.
        if not acestream_executable or system_platform == 'android':
            espera = get_setting("time_limit", 30)
            # If we are the ones who opened the app, the user is outside Kodi and needs room
            # to come back with Back. With the yesno the countdown started when they answered;
            # now it starts straight away, and with the default 30 seconds, taking 40 to come
            # back gave "engine not started" with the engine already running. Not with
            # AceServe on Kodi 20+: its intent goes to its link activity and Kodi is brought
            # back to the front by itself, so nobody has to come back from anywhere.
            if motor_lanzado and not (active_engine() == ENGINE_ACESERVE
                                      and kodi_major_version() >= 20):
                espera = max(ENGINE_LAUNCH_WAIT_MIN, espera * 2)

            timedown = time.time() + espera

            # The official app may not be on the configured port (see
            # buscar_motor_en_otro_puerto): while waiting it is looked for on the others, on a
            # thread so that Cancel keeps answering. Also by whoever waits with another
            # invocation's latch: that one does not see the port the other saves, and would
            # run out of time with the engine up.
            busca = (system_platform == 'android' and not remoto
                     and active_engine() == ENGINE_ACESTREAM)
            cancelar = threading.Event()
            buscador = None
            inicio_espera = time.time()

            def barriendo():
                return buscador is not None and buscador.is_alive()

            def sigue_esperando():
                if time.time() < timedown:
                    return True
                # A sweep of this device's ports takes longer than the wait itself on a slow
                # box (up to two minutes on a Fire TV): while one runs the wait does not give
                # up, within reason, since it is the one thing that can still find the engine.
                return barriendo() and time.time() < inicio_espera + ESPERA_BARRIDO_MAX

            if not motor_disponible():
                d = xbmcgui.DialogProgress()
                d.create(HEADING, translate(30033))

                while not d.iscanceled() and not motor_disponible() and sigue_esperando() and not error_flag:
                    seg = max(0, int(timedown - time.time()))
                    progreso = int((seg * 100) / espera)
                    line1 = translate(30033)
                    line2 = translate(30178) if seg == 0 else translate(30006) % seg
                    try:
                        d.update(progreso, line1, line2)
                    except:
                        d.update(progreso, '\n'.join([line1, line2]))
                    # The latch expires after a minute and this wait can be longer.
                    if arranca:
                        refrescar_pestillo(PESTILLO_MOTOR)

                    if busca:
                        # The classic ports every turn, in milliseconds: an engine coming up on
                        # 6878 while the long sweep is still on its way through the range is
                        # caught at once, and not when that sweep is over.
                        buscar_motor_en_otro_puerto(completo=False)
                        if buscador is not None and not buscador.is_alive():
                            buscador = None
                        if buscador is None and barrido_listo() and time.time() < timedown:
                            buscador = threading.Thread(target=buscar_motor_en_otro_puerto,
                                                        args=(cancelar,), daemon=True)
                            buscador.start()

                    # While a sweep runs, Cancel is looked at more often.
                    time.sleep(0.2 if buscador is not None else 1)

                cancelar.set()

            if not motor_disponible():
                # Whoever cancels does not want explanations, they want out. With the notice
                # in a notification it made no difference, but these are modal dialogs now and
                # planting one after pressing Cancel is worse than saying nothing.
                cancelado = bool(d) and d.iscanceled()

                if d:
                    d.close()
                    d = None

                if not cancelado:
                    # If the port is taken but the API does not answer, something else has it.
                    # Both engines use the same one and the second is left out.
                    if server.ping():
                        xbmcgui.Dialog().ok(HEADING, translate_fmt(30089, server.port))
                    elif remoto:
                        # Nothing here can start it, so the notice says where it was looked for
                        # instead of sending the user off to install an app on this device.
                        xbmcgui.Dialog().ok(HEADING, translate_fmt(30153, server.host, server.port))
                    elif motor_lanzado:
                        # The intent does not report whether it opened anything. If on top of that
                        # nobody is listening, most likely there is no engine installed.
                        xbmcgui.Dialog().ok(HEADING, translate(30091))
                    else:
                        notification_error(translate(30019))

                raise MotorNoDisponible('accion cancelada o timeout')

        if engine and not motor_disponible():
            if not d:
                d = xbmcgui.DialogProgress()
                d.create(HEADING, translate(30033))
            timedown = time.time() + get_setting("time_limit", 30)

            # Start engine if the local server is not available
            engine.connect('error', notification_error)
            #engine.connect(['started', 'terminated'], notification_info)
            engine.start()

            # Wait for engine to start. All that matters is that the engine answers:
            # on OSMC/LibreELEC the .start is a launcher that starts the engine and
            # exits, so engine.running goes back to False and with the "or not
            # engine.running" the loop never ended, ran out of time and said "engine
            # not started" with the engine already working.
            muerto = False
            while not d.iscanceled() and not motor_disponible() and time.time() < timedown and error_flag == False:
                # Ended with an error code, there is nothing to wait for: a missing runtime on
                # Windows used to cost the whole wait and end in silence.
                if engine.failed:
                    muerto = True
                    break

                seg = int(timedown - time.time())
                progreso = int((seg * 100) / get_setting("time_limit", 30))
                line1 = translate(30033)
                line2 = translate(30006) % seg
                try:
                    d.update(progreso, line1, line2)
                except:
                    d.update(progreso, '\n'.join([line1, line2]))

                refrescar_pestillo(PESTILLO_MOTOR)
                time.sleep(1)

            if d.iscanceled() or time.time() >= timedown or error_flag == True or muerto: # Timed out or cancelled
                if engine.running:
                    engine.stop()
                d.close()
                d = None
                if muerto or time.time() >= timedown:
                    notification_error(translate(30019))
                raise MotorNoDisponible('el motor ha muerto al arrancar' if muerto
                                        else 'accion cancelada o timeout')

    except Exception:
        # Whatever went wrong, the dialog must not stay planted on the screen.
        if d:
            d.close()
        raise

    finally:
        if arranca:
            quitar_pestillo(PESTILLO_MOTOR)

    # There is an engine on the other side now, so now we can look at which one.
    check_engine()

    return d


def callar_musica():
    """The menu music goes quiet as soon as something is asked to play.

    Not when that finally plays: a channel can spend half a minute pre-buffering behind its
    progress dialog, and on Android the engine app or the external player can send Kodi to
    the background before that, where it goes on playing audio. Switched off, the music
    module is not even loaded."""
    if get_setting('musica_fondo', True):
        from lib import musica
        musica.callar()


def recoger_musica():
    """After the settings dialog, the saved recording goes if the music was switched off in it
    (see musica.recoger). With no recording saved, the music module is not even loaded."""
    if os.path.isdir(os.path.join(data_path, 'musica')):
        from lib import musica
        musica.recoger()


def acestreams(id=None, url=None, infohash=None, title="", iconimage="", plot="",
               desde_motor=False, clave_historial='', alternativos=(), intento=1):
    """Plays a link through the engine.

    'alternativos' are the other links of the same channel, healthiest first. If this one does
    not start inside Kodi the next is tried, and 'intento' says which of them this call is.
    With none, everything goes as it always did."""
    #logger(id)
    global error_flag
    # Hygiene: an error from an earlier invocation in the same process must not
    # contaminate this one (it matters if reuselanguageinvoker is ever enabled).
    error_flag = False
    player = None
    stream = None
    # The link to try when this one does not start. It is asked for at the very end, once
    # this stream is stopped.
    siguiente = None
    varios = bool(alternativos) or intento > 1
    d = None

    #url = 'http://dl.acestream.org/sintel/sintel.torrent'
    #url = 'https://files.grantorrent.nl/torrents/peliculas/Otra-vuelta-de-tuerca-(The-Turning)-(2020).avi53.torrent'
    #infohash = 'eebd63aa0a5edc49b253fc5741e49e32961d0f4f'


    # check arguments
    if infohash:
        url = id = None
    elif url:
        infohash = id = None
    else:
        regex = re.compile(r'[0-9a-f]{40}\Z',re.I)
        if not regex.match(id):
            xbmcgui.Dialog().ok(HEADING, translate(30015))
            return

    callar_musica()

    # The official app starts its own engine and plays what it is handed, so with the external
    # player the link goes to it straight away: no engine to start here and nothing to wait
    # for. This is what the 1.5.0 did, and was praised for, minus the start intent it fired
    # first, which the 3.2 app rejects with "Malformed content id". A pasted magnet or torrent
    # keeps playing inside Kodi: only what has an id, or an infohash from the engine's own
    # list, goes out. Not the order itself in the log, which carries the link.
    if (system_platform == 'android' and get_setting("reproductor_externo")
            and active_engine() == ENGINE_ACESTREAM and (id or (infohash and desde_motor))):
        enlace = f'content_id={id}' if id else f'infohash={infohash}'
        logger('acestreams: a la app externa')
        xbmc.executebuiltin('StartAndroidActivity("","org.acestream.action.start_content","",'
                            f'"acestream:?{enlace}")')
        return

    try:
        d = asegurar_motor()

        # Channels from the catalogue and from the engine's list arrive with an infohash,
        # and the external player branch below demands an id. Without this conversion, on
        # Android they would play inside Kodi ignoring a setting that comes on by default
        # precisely because in there they give trouble. The engine returns the same
        # broadcast either way, checked, and they go over MPEG-TS like the rest.
        #
        # It is done HERE and not on pressing: the engine is already up and answers in
        # milliseconds. Doing it earlier cost up to ten seconds of mute wait when it was
        # switched off.
        if desde_motor and infohash and not id:
            content_id = server.get_content_id(infohash)
            if content_id:
                id, infohash = content_id, None
            else:
                logger('acestreams: no se pudo resolver el content_id, se sigue con el infohash')

        if id and system_platform == 'android' and get_setting("reproductor_externo"):
            # Only AceServe gets this far: with the official app the link went out above,
            # before the engine was even looked at. AceServe brings no player, so the stream
            # address goes to whichever app Android offers (VLC, usually), and for that the
            # engine has to be up already. host and port come from the server, not from the
            # raw settings: re-reading them gave different addresses from the ones the rest of
            # the addon uses (an ip_addr with the port stuck on ended up as
            # http://ip:6878:6878/).
            if d:
                d.close()
                d = None
            AndroidActivity = 'StartAndroidActivity("","android.intent.action.VIEW","video/mp4","http://%s:%s/ace/getstream?id=%s")' % (server.host, server.port, id)
            # Not the order itself, which carries the link.
            logger('acestreams: a la app externa')
            xbmc.executebuiltin(AndroidActivity)
            return

        if not d:
            d = xbmcgui.DialogProgress()
            d.create(HEADING, translate(30033))

        hls = False
        if id:
            # Start a stream using an acestream channel ID
            stream = Stream(server, id=id)
        elif url:
            # Start a stream using an url
            hls = True
            stream = Stream(server, url=url)
        else:
            # Start a stream using an acestream infohash
            hls = True
            stream = Stream(server, infohash=infohash)

        # The engine only accepts the audio parameters on manifest.m3u8, so asking for
        # them forces playback over to HLS. The setting comes off and its text says so.
        opciones = opciones_transcode()
        if opciones:
            hls = True

        # A channel with more than one link gets a single notice at the end instead of one
        # error per link. While there are others to try, the switch is what gets announced.
        if varios:
            stream.connect('error', functools.partial(notification_error, callado=True))
        else:
            stream.connect('error', notification_error)
        stream.connect(['started','stopped'], notification_info)
        stream.start(hls=hls, **opciones)

        # When the content has several media files and none is named, the engine answers
        # with the list instead of with the stream. Until now that answer was taken for an
        # empty success and the wait below sat looking at a state that never arrived, so a
        # torrent with several episodes always ended in "engine not started" with the
        # engine perfectly alive.
        if stream.media_files:
            if d:
                d.close()

            indice = elegir_fichero(stream.media_files)
            if indice is None:
                raise Exception("seleccion de fichero cancelada")

            d = xbmcgui.DialogProgress()
            d.create(HEADING, translate(30033))

            stream.start(hls=hls, _idx=indice, **opciones)

            # Retrying without _idx would only bring the list back again.
            if stream.media_files:
                raise Exception("el motor sigue pidiendo fichero")

        # Wait for stream to start
        inicio = time.time()
        lenta_avisada = False
        # The best pre-buffering progress seen, and when it last went up. The clock starts with the
        # pre-buffering itself, because the seconds spent connecting do not make a link stuck.
        mejor_progreso = 0
        ultimo_avance = None
        timedown = time.time() + get_setting("time_limit", 30)
        while not d.iscanceled() and time.time() < timedown and (not stream.status or stream.status != 'dl') and error_flag == False:
            if stream.status != 'prebuf':
                seg = int(timedown - time.time())
                progreso = int((seg * 100) / get_setting("time_limit", 30))
            else:
                progreso = stream.stats.progress
                timedown = time.time() + 100

                if ultimo_avance is None:
                    ultimo_avance = time.time()
                if isinstance(progreso, (int, float)) and progreso > mejor_progreso:
                    mejor_progreso = progreso
                    ultimo_avance = time.time()

                # While the engine pre-buffers the wait has no end, so whoever watches the bar
                # cannot tell whether to keep waiting. Past the time limit of the settings they
                # are told once, with the seeds. A channel with other links decides for them
                # instead. A link whose buffering has not moved in that time is given up, since
                # pressing the channel again would start from this same one.
                limite = get_setting("time_limit", 30)
                if time.time() - inicio >= limite:
                    if alternativos:
                        if time.time() - ultimo_avance >= limite:
                            timedown = time.time()
                    elif not lenta_avisada:
                        lenta_avisada = True
                        # The last link of a channel comes after the others have been tried, so
                        # the notice does not send the user off to try another one.
                        aviso = (translate_fmt(30148, stream.stats.peers) if intento > 1
                                 else translate_fmt(30140, stream.stats.peers))
                        xbmcgui.Dialog().notification(HEADING, aviso, icon_path, 8000)

            if not stream.status:
                line1 = translate(30034)
            elif stream.status == 'prebuf':
                line1 = translate(30008) %(progreso) + '%'
            elif stream.status == 'dl':
                line1 = translate(30007)
            else:
                line1 = stream.status

            if varios:
                line1 = f'{line1}    {translate_fmt(30144, intento, intento + len(alternativos))}'

            line2 = translate(30010) % stream.stats.speed_down
            line3 = translate(30012) % stream.stats.peers
            try:
                d.update(progreso, line1, line2, line3)
            except:
                d.update(progreso, '\n'.join([line1, line2, line3]))

            time.sleep(0.25)

        d.close()
        if d.iscanceled() or time.time() >= timedown or error_flag == True:  # Timed out or cancelled
            cancelado = d.iscanceled()

            # This link did not start and the channel has another: this stream is stopped and
            # the next link asked for at the end of the function, with the engine still up.
            if alternativos and not cancelado:
                siguiente = alternativos[0]
                raise Exception(f'enlace {intento} de {intento + len(alternativos)} sin arrancar, '
                                'se prueba el siguiente')

            # Cancelling needs no explanation and running out of time does: before this the
            # dialog closed with nothing said, and the failure only reached the log. A refused
            # link already had the engine's own notice, except on a channel with several
            # links, where a single notice at the end says none of them started.
            if not cancelado and intento > 1:
                xbmcgui.Dialog().notification(HEADING, translate_fmt(30143, intento),
                                              ICONO_ERROR, 6000)
            elif not cancelado and not error_flag:
                xbmcgui.Dialog().notification(HEADING,
                                              translate_fmt(30141, int(time.time() - inicio)),
                                              ICONO_ERROR, 6000)
            raise Exception("error flag" if error_flag else "accion cancelada o timeout")

        # A pasted identifier arrives with no name, and by now the engine has said what it is.
        if not title and stream.filename:
            history.poner_nombre_de_fondo(clave_historial, stream.filename)

        # Open a media player to play the stream
        player = MyPlayer()
        player.playStream(stream, title, iconimage, plot)

    except MotorNoDisponible as e:
        # Whoever waited has already seen why, and nothing of ours has started: no stream to
        # stop, no player to kill, and the engine we may have launched is stopped in there.
        logger(f'acestreams: {e}')
        return

    except Exception as e:
        logger(e, 'error')
        # Without this, an error between create() and the first close() left the
        # progress dialog planted on the screen.
        try:
            if d: d.close()
        except: pass

    try:
        if player:
            player.kill()
    except: pass

    # Only if the stream got to start: stopping a stream that never started
    # asked for http://host/None and fired a second error notification.
    if stream and stream.command_url:
        stream.stop()

    if siguiente:
        # The engine is neither stopped nor restarted in between: the next link needs it up,
        # and the setting below is what would bring it down.
        xbmcgui.Dialog().notification(
            HEADING, translate_fmt(30142, intento + 1, intento + len(alternativos)), icon_path, 5000)
        return acestreams(infohash=siguiente, title=title, iconimage=iconimage, plot=plot,
                          desde_motor=desde_motor, clave_historial=clave_historial,
                          alternativos=alternativos[1:], intento=intento + 1)

    # stop Engine. Never a remote one: it cannot be stopped from here, and kill_process()
    # would only fire at whatever happens to run on this machine.
    if ((get_setting("stop_acestream", False) or get_setting("linux_id") == 'ubuntu')
            and es_host_local(server.host)):
        kill_process()


def notification_info(*args,**kwargs):
    transmitter = kwargs['class_name']
    msg = kwargs['event_name']

    logger("%s: %s" %(transmitter, msg))
    #xbmcgui.Dialog().notification('Acestream %s' % transmitter, msg, os.path.join(runtime_path, 'resources', 'media', 'icono_aces_horus.png'))


def notification_error(*args,**kwargs):
    global error_flag
    transmitter = kwargs.get('class_name', ADDON_NAME)
    event = kwargs.get('event_name','')
    # The engine may emit an error with no message: it must not blow up here.
    msg = str(args[0]) if args and args[0] else translate(30019)
    error_flag = True

    logger("Error in %s (%s): %s" % (transmitter, event, msg))

    # 'callado' is for a link of a channel that has others: trying them is already being
    # announced, and one notice per failed link would queue up behind it.
    if not kwargs.get('callado'):
        xbmcgui.Dialog().notification(f'Error Acestream {transmitter}', msg, ICONO_ERROR)


ENGINE_WARNED_PROP = 'ekhorus_engine_warned'

# Minimum margin when we are the ones opening the engine app: Kodi goes to the
# background and the user has to come back with Back.
ENGINE_LAUNCH_WAIT_MIN = 60
# How long the wait may stretch, in all, while a sweep of this device's ports is still
# running (see asegurar_motor). Two minutes of sweep were measured on a Fire TV.
ESPERA_BARRIDO_MAX = 180


def check_engine():
    """Warns if an engine other than the chosen one answers on the port.

    AceServe pins 6878 and starts on its own when Android boots, so the addon ended up
    talking to it without knowing, and whoever had chosen AceStream did not understand why
    it was not working. (The official app, finding 6878 taken, moves to another port; that
    is buscar_motor_en_otro_puerto's business.)

    It must not bring playback down: if something fails here, the video carries on."""
    try:
        detectado = detect_engine()
        elegido = active_engine()

        if not detectado or detectado == elegido:
            return detectado

        logger(f"check_engine: elegido {engine_name(elegido)}, contesta {engine_name(detectado)}")

        # The warning points at the "Motor ace" setting, which only exists on Android.
        # Elsewhere active_engine() always returns AceStream, so a remote engine that
        # turns out to be AceServe would raise a warning sending the user to check a
        # setting they do not have. It is still detected, because the channels menu needs
        # it, but it keeps quiet.
        if system_platform != 'android':
            return detectado

        # Only once per Kodi session. Repeating it on every link would be a punishment,
        # above all because playback is going to work anyway.
        window = xbmcgui.Window(10000)
        if not window.getProperty(ENGINE_WARNED_PROP):
            window.setProperty(ENGINE_WARNED_PROP, '1')
            xbmcgui.Dialog().notification(HEADING,
                                          translate_fmt(30088, engine_name(detectado), server.port),
                                          os.path.join(runtime_path, 'resources', 'media', 'error.png'),
                                          6000)

        return detectado

    except Exception as e:
        logger(f"check_engine: {e}", 'error')
        return None


QR_MAX_AGE_DAYS = 30


def limpiar_qr_viejos():
    """Deletes the QR PNGs that nobody is going to reuse.

    qr_poster() writes them in special://temp and until now nobody deleted them,
    so they piled up one per channel watched."""
    limite = time.time() - QR_MAX_AGE_DAYS * 86400

    try:
        with os.scandir(translatePath('special://temp')) as entradas:
            for entrada in entradas:
                if (entrada.name.startswith('ekhorus_qr_') and entrada.is_file()
                        and entrada.stat().st_mtime < limite):
                    os.remove(entrada.path)
    except Exception as e:
        # Cleaning up is incidental and cannot stop the menu from being painted.
        logger(f"limpiar_qr_viejos: {e}", 'error')


def icono(nombre):
    return os.path.join(runtime_path, 'resources', 'media', nombre)


def mainmenu():
    itemlist = list()

    # Only if they are enabled, because whoever does not use them has nothing to clean.
    if get_setting("show_qr_codes"):
        limpiar_qr_viejos()

    # With the classic interface, EspaKodi Addons and the APKs go back to being Kodi
    # folders instead of opening a window of their own, and the item has to say so.
    clasica = ui_common.clasica()

    itemlist.append(Item(
        label= translate(30092),
        action='cuadro_mandos',
        icon=icono('cuadro.png'),
        plot=translate(30093)
    ))

    # No network condition on purpose: knowing whether there is a catalogue means asking
    # the engine, and mainmenu() cannot pay for a request against a switched-off ip_addr.
    # If there is no engine, the screen itself explains it and offers to start it.
    itemlist.append(Item(
        label=translate(30115),
        action='catalogo',
        icon=icono('motor.png'),
        plot=translate(30116),
        isFolder=clasica
    ))

    # Right under Channels, which is where most of what ends up in them comes from. Both are
    # always there, even empty: a row that only shows up once there is something in it is a
    # row nobody knows to look for.
    itemlist.append(Item(
        label=translate(30133),
        action='favoritos',
        icon=icono('mis_favoritos.png'),
        plot=translate(30134),
        isFolder=clasica
    ))

    itemlist.append(Item(
        label=translate(30037),
        action='historial',
        icon=icono('historial.png'),
        plot=translate(30101),
        isFolder=clasica
    ))

    itemlist.append(Item(
        label= translate(30094),
        action='guia',
        icon=icono('guia.png'),
        plot=translate(30095)
    ))

    itemlist.append(Item(
        label= translate(30082),
        action='apk_menu',
        icon=icono('descargas.png'),
        plot=translate(30097),
        isFolder=clasica
    ))

    itemlist.append(Item(
        label= translate(30081),
        action='espakodi_addons',
        icon=icono('addons.png'),
        plot=translate(30098),
        isFolder=clasica
    ))

    itemlist.append(Item(
        label=translate(30020),
        action='play',
        icon=icono('reproducir.png'),
        plot=translate(30099)
    ))

    itemlist.append(Item(
        label=translate(30038),
        action='search',
        icon=icono('buscar.png'),
        plot=translate(30100)
    ))

    # Only for an engine on this machine: kill_process() reaches no further, so with a remote
    # address the stop row could only end in "engine NOT stopped". ping() instead of
    # available(): a 2s TCP probe, where available() could hold the menu for ten seconds.
    if system_platform == 'android' and es_host_local(server.host):
        # Android lets one app open another but never close it: with nothing answering the
        # row opens the app of the chosen engine, and with an engine answering it takes the
        # user to where Android lets them stop it. Which engine that is, is not asked here:
        # it costs two requests, and this menu only affords the ping.
        if server.ping():
            itemlist.append(Item(
                label=translate(30176),
                action='cerrar_motor',
                icon=icono('detener.png'),
                plot=translate(30177)
            ))
        else:
            nombre = engine_name(active_engine())
            itemlist.append(Item(
                label=translate_fmt(30162, nombre),
                action='arrancar_motor',
                icon=icono('arrancar.png'),
                plot=translate_fmt(30163, nombre)
            ))

    elif system_platform != 'android' and es_host_local(server.host):
        if server.ping():
            itemlist.append(Item(
                label= translate(30036),
                action='kill',
                icon=icono('detener.png'),
                plot=translate(30102)
            ))
        else:
            # The mirror of the row above. The engine only ever came up by playing something,
            # so whoever opened Channels first after a reboot met a dead end.
            itemlist.append(Item(
                label=translate(30154),
                action='arrancar_motor',
                icon=icono('arrancar.png'),
                plot=translate(30155)
            ))

    itemlist.append(Item(
        label=translate(30128),
        action='experimental',
        icon=icono('experimental.png'),
        plot=translate(30129)
    ))

    itemlist.append(Item(
        label= translate(30021),
        action='open_settings',
        icon=icono('ajustes.png'),
        plot=translate(30103)
    ))

    itemlist.append(Item(
        label=translate(30096),
        action='universo',
        icon=icono('universo.png'),
        plot=translate(30104)
    ))

    return itemlist


def experimental_menu():
    """What is still being tried out, gathered behind one row: the web page, which needs another
    device on the same network, and taking the channels to Kodi's TV section."""
    from lib import kodi_tv
    from lib.webapp import bootstrap

    plot = translate(30126)
    if bootstrap.poca_memoria():
        plot = f'{plot}\n\n{translate(30157)}'

    plot_tv = translate(30170)
    resumen = kodi_tv.resumen()
    if resumen:
        plot_tv = f'{plot_tv}\n\n{resumen}'

    return [
        Item(label=translate(30125),
             action='web',
             icon=icono('movil.png'),
             plot=plot),
        Item(label=translate(30169),
             action='tv_exportar',
             icon=icono('tv.png'),
             plot=plot_tv),
    ]


# The real list lives in a json published outside the addon, so when the hosting gets
# taken down (archive.org darkened a whole item once) it is fixed by editing that file,
# with no new release. The copy in resources/ is only the fallback.
#
# raw answers a couple of minutes after editing it. The release that holds the APKs is served
# from github.com, which stays up where a network blocks raw.githubusercontent.com alone; and
# archive.org holds up if GitHub is blocked on the user's network, or gone. The first valid
# list wins, so a copy left stale in the repository hides a newer one in the release.
APK_MANIFEST_URLS = (
    'https://raw.githubusercontent.com/espakodi/misappsfavoritas/main/apks.json',
    'https://github.com/espakodi/misappsfavoritas/releases/download/v0.0.1test/apks.json',
    'https://archive.org/download/ekh_20260918/apks.json',
)
APK_MANIFEST_EMBEDDED = os.path.join(runtime_path, 'resources', 'apks.json')
# Three seconds and not the ten of HTTP_TIMEOUT, because this blocks opening a menu.
APK_MANIFEST_TIMEOUT = 3
# This is not a security barrier; whoever controls the repository publishes the whole
# addon anyway. It protects against a typo when editing the manifest.
APK_ALLOWED_HOSTS = ('github.com', 'objects.githubusercontent.com',
                     'raw.githubusercontent.com', 'espakodi.github.io', 'archive.org')

_APK_MANIFEST_PROP = 'ekhorus_apk_manifest'
_APK_MANIFEST_FAILED = 'fail'


def _apk_url(url):
    """The url if an APK may be downloaded from it, or ''."""
    if not isinstance(url, str) or not url.startswith('https://'):
        return ''

    host = urllib_parse.urlparse(url).hostname or ''
    if host not in APK_ALLOWED_HOSTS:
        logger(f'apk manifest: dominio no permitido {host}', 'error')
        return ''

    return url


def _apk_entry(raw):
    """Normalises one manifest entry, or None if it cannot be used."""
    if not isinstance(raw, dict):
        return None

    url = _apk_url(raw.get('url'))
    if not url:
        return None

    # basename(): without this an entry with '../' would write outside the folder
    # the user has chosen in the dialog.
    filename = os.path.basename(str(raw.get('filename') or ''))
    if not filename:
        return None

    label = raw.get('label')
    if not label:
        label_id = raw.get('label_id')
        label = translate(label_id) if isinstance(label_id, int) else ''

    # Versions of the addon from before 'backup' read the same manifest and ignore it.
    return {'filename': filename,
            'url': url,
            'backup': _apk_url(raw.get('backup')),
            'label': label or filename,
            'note': raw.get('note') or translate(30075),
            'sha256': str(raw.get('sha256') or '').lower()}


def _apk_entries_from(data):
    """Usable entries of a parsed manifest."""
    if not isinstance(data, list):
        return list()

    entries, vistos = list(), set()
    for raw in data:
        entry = _apk_entry(raw)
        # Two entries with the same name share the target file and the download
        # latch, so the second one is dropped.
        if entry and entry['filename'] not in vistos:
            vistos.add(entry['filename'])
            entries.append(entry)
    return entries


def _apk_entries_embedded():
    try:
        # utf-8-sig reads it with or without a BOM (see apk_entries).
        with open(APK_MANIFEST_EMBEDDED, encoding='utf-8-sig') as f:
            return _apk_entries_from(json.load(f))
    except (OSError, ValueError) as e:
        logger(f'apk manifest embebido: {e}', 'error')
        return list()


def apk_entries():
    """Entries of the APK menu, from the remote manifest or from the embedded fallback.

    Both the hit and the failure are cached. Every click reimports the module, so
    without storing the failure too, going in and out of the menu with a bad network
    chains one network wait per visit."""
    window = xbmcgui.Window(10000)
    cached = window.getProperty(_APK_MANIFEST_PROP)

    if cached == _APK_MANIFEST_FAILED:
        return _apk_entries_embedded()

    if cached:
        entries = parse_literal(cached)
        if isinstance(entries, list) and entries:
            return entries

    entries = list()
    for manifest_url in APK_MANIFEST_URLS:
        try:
            # Bytes and not text: json.loads() skips the BOM some Windows editors put at the
            # start, which as text it refuses, and the whole list would be dropped unannounced.
            data = json.loads(http_get_bytes(manifest_url, timeout=APK_MANIFEST_TIMEOUT))
        except Exception as e:
            logger(f'apk manifest {manifest_url}: {e}', 'error')
            continue

        entries = _apk_entries_from(data)
        if entries:
            break
        logger(f'apk manifest {manifest_url}: ninguna entrada valida', 'error')

    # An empty list, or one where every entry is invalid, is as useless as a network
    # error, and has to end the same way: in the fallback.
    if not entries:
        window.setProperty(_APK_MANIFEST_PROP, _APK_MANIFEST_FAILED)
        return _apk_entries_embedded()

    window.setProperty(_APK_MANIFEST_PROP, dump_json(entries))
    return entries


def apk_menu():
    itemlist = list()

    for entry in apk_entries():
        itemlist.append(Item(
            label=entry['label'],
            action='download_apk',
            icon=icono('descargas.png'),
            filename=entry['filename'],
            apk_url=entry['url'],
            apk_backup=entry.get('backup', ''),
            sha256=entry.get('sha256', ''),
            plot=entry.get('note') or translate(30075),
            isFolder=False
        ))

    itemlist.append(Item(
        label=translate(30074),
        action='apk_info',
        icon=icono('info.png'),
        plot=translate(30075),
        isFolder=False
    ))

    return itemlist


def entrar_en_lista(accion):
    """Enters the screen again asking for the classic list.

    Each menu row is painted as a folder or not according to the mode at painting time,
    and Kodi only gives a directory to write in to the ones that are folders. A row drawn
    before the classic interface was turned on arrives here with no directory, so one is
    asked for by entering again."""
    xbmc.executebuiltin('ActivateWindow(programs,%s?%s,return)'
                        % (sys.argv[0], Item(action=accion, clasico=1).tourl()))


def volver_a_lo_clasico(accion):
    """A window of our own could not open, so the classic list is painted.

    Without this you would have to remember the classic interface setting to get out of
    the jam, and an emergency exit you have to remember is no emergency exit."""
    logger('no se pudo abrir la ventana de %s, se abre la lista clasica' % accion, 'error')
    xbmcgui.Dialog().notification(HEADING, translate(30106), icon_path, 6000)
    entrar_en_lista(accion)


def _apk_install_hint():
    """Status line of Download APKs: how the download ends up installed on this device."""
    # EspaKodi carries its own bridge to the installer and needs permission to install apps
    # once; Kodi 22 hands the file over by itself; an older Kodi cannot, and a computer only
    # keeps it (see apk_post_download). The line is 1130 px wide and cuts with dots: the
    # longest of these measures 1022 in the skin's NotoSans at 33.
    if system_platform != 'android':
        return 'Se descargan aquí para instalarlos en un aparato Android'
    if is_espakodi_build():
        return 'Se instalan desde aquí; la primera vez, dale permiso a EspaKodi'
    if apk_autoinstall_supported():
        return 'Se instalan desde aquí; la primera vez, Android te pedirá permiso'
    return 'Se descargan aquí y se instalan con un gestor de archivos'


def apk_ventana():
    """Download APKs in its own window. False if it could not be opened."""
    from lib import list_screen

    # The list may have to come from the network: on the first visit of a session that is
    # seconds of a frozen menu, and many more on a slow line or a weak box.
    with ui_common.ocupado():
        entradas = apk_entries()

    def filas():
        # The folder may be a Kodi path and not a system one, so xbmcvfs is asked and
        # not os.path.
        carpeta = (default_apk_folder() or '').rstrip('/')
        salida = list()
        for entrada in entradas:
            bajado = bool(carpeta) and xbmcvfs.exists(carpeta + '/' + entrada['filename'])
            salida.append(list_screen.Fila(
                clave=entrada['filename'],
                titulo=entrada['label'],
                pista=entrada['filename'],
                icono=icono('descargas.png'),
                pastilla=(ui_common.color('Descargado', ui_common.TINTA_VERDE), 'on')
                         if bajado else None,
                plot=entrada.get('note') or translate(30075)))
        return salida

    porficheros = {e['filename']: e for e in entradas}

    def pulsar(fila):
        entrada = porficheros.get(fila.clave)
        if entrada:
            download_apk(entrada['filename'], (entrada['url'], entrada.get('backup', '')),
                         entrada.get('sha256', ''))

    return list_screen.mostrar(
        titulo='[COLOR FFFFB70F][B]EK[/B][/COLOR]Horus[COLOR FF8A97A5]   ·   [/COLOR]'
               'Descargar APKs',
        subtitulo='Para Fire TV, TV box y móvil',
        hacer_filas=filas,
        al_pulsar=pulsar,
        botones=(('Última versión web', _apk_web),
                 ('Borrar descargas', lambda: _apk_delete_downloads(entradas))),
        estado=_apk_install_hint(),
        pista='[B]OK[/B] descarga    ·    [B]Derecha[/B] lee    ·    [B]Atrás[/B] cierra')


def _apk_web():
    from lib import espakodi_installer
    espakodi_installer.open_apk_latest()


def _apk_delete_downloads(entradas):
    """The "Borrar descargas" button. Once installed, an APK only takes up room, and a TV box
    is short of it."""
    restos = apk_leftovers([e['filename'] for e in entradas])
    if not restos:
        xbmcgui.Dialog().notification(HEADING, 'No hay ningún APK descargado', icon_path)
        return None

    nombres = {e['filename']: e['label'] for e in entradas}
    opciones = [f'{nombres[fichero]}  ·  {format_size(tamano)}'
                + (', descarga a medias' if a_medias else '')
                for _, fichero, a_medias, tamano in restos]
    # All marked: once they are installed the usual thing is to clear the lot, and whoever
    # wants to keep one unmarks it.
    elegidos = xbmcgui.Dialog().multiselect('Borrar lo marcado', opciones,
                                            preselect=list(range(len(restos))))
    if not elegidos:
        return None

    liberado, fallidos = 0, list()
    for ruta, _, _, tamano in (restos[i] for i in elegidos):
        # Already gone (through another name of its folder, or a file manager) is gone all
        # the same, and not something to warn about.
        if xbmcvfs.delete(ruta) or not xbmcvfs.exists(ruta):
            liberado += tamano
        else:
            fallidos.append(os.path.basename(ruta))

    if fallidos:
        xbmcgui.Dialog().ok(HEADING, 'Esto no se ha podido borrar:\n' + '\n'.join(fallidos)
                            + '\n\nPrueba desde un gestor de archivos.')
    else:
        xbmcgui.Dialog().notification(HEADING, f'Liberados {format_size(liberado)}', icon_path)

    # The "Descargado" pills go with the files.
    return 'refrescar'


# DoH resolvers: if one is blocked on the user's network, the next one is tried.
DOH_RESOLVERS = [
    "https://dns.google/resolve?name={}&type=TXT",
    "https://cloudflare-dns.com/dns-query?name={}&type=TXT",
]
ASS_MAX_DEPTH = 10

def resolve_txt(name):
    for resolver in DOH_RESOLVERS:
        try:
            data = http_get_text(resolver.format(name), headers={'Accept': 'application/dns-json'})
            response = json.loads(data)
            if response.get("Answer"):
                return response["Answer"]
        except Exception as e:
            logger("resolve_txt %s: %s" % (resolver.split('/')[2], e), 'error')

    return list()


ass_ids = list()
def ass_decoder(ass_id_or_json, depth=0):
    itemlist = list()

    if depth > ASS_MAX_DEPTH:
        logger("ass_decoder: demasiados niveles de anidamiento", 'error')
        return itemlist

    try:
        json_data = json.loads(ass_id_or_json)
        is_json = isinstance(json_data, list)
    except Exception:
        is_json = False

    if not is_json:
        # The input is an ASS ID, not a json
        if ass_id_or_json in ass_ids:
            return itemlist

        ass_ids.append(ass_id_or_json)
        host = "{}.elcano.top".format(ass_id_or_json.replace("ass://", ""))

        for answer in resolve_txt(host):
            try:
                raw = answer.get("data", "").strip('"')
                if "H4sIAAAAAAAA" in raw:
                    json_data = gzip.decompress(base64.b64decode(raw)).decode("utf-8")
                else:
                    json_data = base64.b64decode(raw).decode("utf-8")

                itemlist = itemlist + ass_decoder(json_data, depth + 1)
            except Exception as e:
                logger("ass_decoder: respuesta TXT no valida: %s" % e, 'error')
    else:
        for jsitem in json_data:
            if not isinstance(jsitem, dict):
                continue

            if "subLinks" in jsitem:
                itemlist = itemlist + ass_decoder(json.dumps(jsitem["subLinks"]), depth + 1)
            elif "ref" in jsitem:
                itemlist = itemlist + ass_decoder(jsitem["ref"], depth + 1)
            elif "url" in jsitem and re.findall('([0-9a-f]{40})', jsitem["url"], re.I):
                chan_name = jsitem.get("name") or jsitem["url"]
                chan_id = re.findall('([0-9a-f]{40})', jsitem["url"], re.I)[0]
                itemlist.append(Item(label=chan_name ,action='play',id=chan_id))
            else:
                logger("ASS decoder: item ignorado: %s" % jsitem)

    return itemlist


def search_text(query):
    """Searches by text in the public acestream search engines."""
    itemlist = list()

    try:
        data = http_get_text("https://acestreamsearch.net/en/?q={}".format(urllib_parse.quote_plus(query)))
        data = data.split("list-group\">")[1].split("</ul>")[0]
        data = re.sub(r"\n|\r|\t|\s{2}|&nbsp;", "", data)
        patron = '<a href="(.*?)">(\\w*.*?)<'
        for channel in re.findall(patron, data, re.I):
            itemlist.append(Item(label=channel[1]+ " (acestreamsearch.net)",
                        action='play',
                        id=channel[0].replace("acestream://","")))
    except Exception as e:
        logger("search acestreamsearch.net: %s" % e, 'error')

    try:
        data = json.loads(http_get_text("https://search-ace.stream/search?query={}".format(urllib_parse.quote_plus(query))))
        for entry in data:
            itemlist.append(Item(label=entry["name"] + " (search-ace.stream)",
                        action='play',
                        id=entry["content_id"]))
    except Exception as e:
        logger("search search-ace.stream: %s" % e, 'error')

    # The engine goes last so the usual order does not change: deduplication keeps the
    # first appearance, so the two web sources still give exactly the same first results
    # as before.
    if get_setting("buscar_en_motor", True):
        try:
            from lib import catalog
            for canal in catalog.buscar(server, query):
                # The other two say which website they come from; this one points at the
                # addon's own Channels section, which is where it is also found.
                itemlist.append(Item(label=canal['nombre'] + " (canales)",
                                     action='play',
                                     infohash=canal['infohash'],
                                     icon=canal.get('logo') or '',
                                     motor=1))
        except Exception as e:
            logger("search motor: %s" % e, 'error')

    return itemlist


def search(url):
    itemlist = list()
    ids = list()

    try:
        if "://" not in url:
            itemlist = search_text(url)
        elif url.startswith("ass://"):
            global ass_ids
            ass_ids = list()
            itemlist = ass_decoder(url)
        else:
            data = http_get_text(url)

            if data:
                if "pastebin" in url or ".txt" in url:
                    data = data.replace("\n\n", "\n") #remove empty lines
                    data = data.replace("acestream://", "") #remove protocol
                    patron = "(?:.*?)======\n(.*)"
                    tmp = re.findall(patron, data, re.DOTALL) #remove text before "========"
                    if len(tmp) > 0:
                        data = tmp[0]
                    data = re.sub(r'(?m)^\===.*\n?', '', data) #remove lines starting with "==="
                    for it in re.findall(r'(.+?)\n([0-9a-f]{40})(?=\n|$)', data, re.DOTALL):
                        if len(it) == 2 and len(it[1]) > 0:
                                    name = it[0].replace("\n","")
                                    id = it[1]
                                    itemlist.append(Item(label=name ,action='play',id=id))
                elif "elcano" in url:
                    data = json.loads(data.split("linksData = ")[1].split(";")[0])
                    for link in data["links"]:
                        if len(link["url"]) >= 40:
                            itemlist.append(Item(label=link["name"] ,action='play',id=link["url"].replace("acestream://","")))
                elif "vercel.app" in url or "netlify.app" in url:
                    data = re.sub(r"\n|\r|\t|\s{2}|&nbsp;", "", data)
                    data = data.replace("acestream://","")
                    patron = "<a href=[\'\"]([0-9a-f]{40})[\'\"](?:.*?)>(?: |)(\\w*.*?)(?: |)<"
                    for channel in re.findall(patron, data, re.I):
                        itemlist.append(Item(label=channel[1],
                                action='play',
                                id=channel[0]))
                else:
                    data = re.sub(r"\n|\r|\t|\s{2}|&nbsp;", "", data)

                    # 1) Structured list. parse_literal instead of eval(): before, any
                    #    remote list could run code on the machine.
                    entries = list()
                    encontrado = re.findall(r'(\[.*?])', data)
                    if encontrado:
                        aux = parse_literal(encontrado[0])
                        entries = aux if isinstance(aux, list) else list()

                    for n, it in enumerate(entries):
                        # A corrupt entry cannot bring the whole list down:
                        # that one is dropped and the rest keep being read.
                        try:
                            if not isinstance(it, dict):
                                continue

                            id = it.get("id") or it.get("url") or ''
                            id = re.findall('([0-9a-f]{40})', str(id), re.I)[0]

                            label = it.get("name") or it.get("title") or it.get("label")
                            icon = it.get("icon") or it.get("image") or it.get("thumb")

                            # n+1: the list is numbered from 1, like the other
                            # loop; before, this one started at "Opcion 0".
                            new_item = Item(label= label if label else translate(30030) % (n + 1, id), action='play', id=id)

                            if icon:
                                new_item.icon = icon

                            itemlist.append(new_item)
                        except Exception:
                            logger("search: entrada ignorada en %s: %s" % (url, it))

                    # 2) No usable structured list: m3u and, failing that, loose hashes.
                    if not itemlist:
                        for patron in [r'#EXTINF:-1.*?id="([^"]+)".*?([0-9a-f]{40})', '#EXTINF:-1.*?,(.*?)http.*?([0-9a-f]{40})']:
                            for label, id in re.findall(patron, data):
                                itemlist.append(Item(label=label, action='play', id=id))
                            if itemlist: break

                    if not itemlist:
                        for patron in [r"acestream://([0-9a-f]{40})", r'(?:"|>)([0-9a-f]{40})(?:"|<)']:
                            n = 1
                            for id in re.findall(patron, data, re.I):
                                if id not in ids:
                                    ids.append(id)
                                    itemlist.append(Item(label= translate(30030) % (n,id),
                                                         action='play',
                                                         id= id))
                                    n += 1
                            if itemlist: break

    except Exception as e:
        # This used to be 'except: pass': any network or format failure showed
        # up as "no links", with no trace in the log.
        logger("search '%s': %s" % (url, e), 'error')

    return itemlist


def kill_process():
    cmd_stop_acestream = get_setting("cmd_stop_acestream")

    if system_platform == 'windows':
        # subprocess instead of os.system: os.system opened a black console over Kodi.
        subprocess.call(['taskkill', '/F', '/IM', 'ace_engine.exe'], **no_window())

    elif cmd_stop_acestream:
        # Stored as a list; edited by hand it comes back as text, which call() would take
        # whole as the name of the executable.
        if isinstance(cmd_stop_acestream, str):
            cmd_stop_acestream = shlex.split(cmd_stop_acestream)
        logger("cmd_stop_acestream= %s" % cmd_stop_acestream)
        subprocess.call(cmd_stop_acestream)


    time.sleep(0.75)

    # The engine version is cached and has to be forgotten to know if it is still alive.
    # And the detected engine with it, or after starting the other we would name this one.
    server.invalidate()
    forget_engine()

    if not server.available:
        logger("Motor Acestream cerrado")
        xbmcgui.Dialog().notification(HEADING, translate(30035),
                                      os.path.join(runtime_path, 'resources', 'media', 'icono_aces_horus.png'))
        return True
    else:
        logger("Motor Acestream NO cerrado")
        xbmcgui.Dialog().notification(HEADING, translate(30040),
                                      os.path.join(runtime_path, 'resources', 'media', 'error.png'))
        return False


_qr_base = None


def qr_base():
    """(url template, file suffix) per the chosen QR format.

    It is worked out once per invocation: painting a list of 300 channels calls
    qr_poster() 300 times, and rereading the setting and asking for the IP on every row is
    exactly what was taken out of this loop back in the day.

    With the http format any phone with VLC opens the QR, with no need to have AceStream
    installed, which is the scenario the guide recommends for diagnosis. The host comes
    from server and not from the setting: rereading it gave addresses different from the
    ones the rest of the addon uses."""
    global _qr_base

    if _qr_base is not None:
        return _qr_base

    _qr_base = ('acestream://%s', '')

    if get_setting('qr_formato'):
        host = server.host

        # A QR with 127.0.0.1 inside is no use to anybody scanning it with a phone.
        if host in HOSTS_LOCALES:
            host = xbmc.getIPAddress() or ''

        if host and host not in HOSTS_LOCALES:
            # The suffix carries the host because the PNG is cached: without it, changing
            # format or engine would keep serving the previous file forever.
            _qr_base = (f'http://{host}:{server.port}/ace/getstream?id=%s',
                        'h%s_' % host.replace('.', ''))
        else:
            logger('qr_poster: sin direccion util para el QR http, se usa acestream://')

    return _qr_base


def qr_poster(id):
    """Generates (only once) the QR PNG of an acestream:// link.

    It used to be regenerated on every painting of the directory: on a list of 300
    channels that was 300 disk writes every time it was browsed."""
    from lib import qr

    plantilla, sufijo = qr_base()
    poster_url = os.path.join(translatePath('special://temp'),
                              'ekhorus_qr_%s%s.png' % (sufijo, id))

    return qr.generar(plantilla % id, poster_url)


def run(item):
    itemlist = list()

    if not item.action:
        logger("Item sin acción")
        return

    # The action and not the whole item, whose link and name are what is being watched.
    logger(f'Ejecutando {item.action}')
    if item.action == "mainmenu":
        # The setting is looked at here and not inside the module so as not to import it
        # on every opening of the menu: the wizard drags in lib/netscan.py and the engine
        # client, and all of that is needed once in the addon's life.
        #
        # And only with a directory of our own: from llamada_externa() this would hijack
        # the playback another addon has just asked for.
        if plugin_handle() >= 0 and not get_setting('asistente_hecho', False):
            from lib import setup_wizard
            setup_wizard.mostrar()

        # After the wizard, which is modal, and only with a directory of ours: from another
        # addon's call there is no menu on screen to put a track behind. The setting is read
        # here, before the import, so that switched off the music module is not even loaded
        # (and leaves no compiled copy of itself on disk).
        if plugin_handle() >= 0:
            if get_setting('musica_fondo', True):
                from lib import musica
                musica.programar()

            # Switched off with the recording still kept on the device (it is switched off
            # from the settings dialog, where no code of ours runs). The folder is the mark,
            # so nothing has to be loaded to find out there is nothing to clean.
            elif os.path.isdir(os.path.join(data_path, 'musica')):
                from lib import musica
                musica.limpiar()

            # "Guardar todo" switched on from Kodi's own settings dialog has no watch running
            # yet. Read before the import too, so that switched off nothing more is loaded.
            if get_setting('anotar_fuera', False):
                from lib import playback_watch
                playback_watch.arrancar_si_falta()

        itemlist = mainmenu()

    elif item.action == "experimental":
        itemlist = experimental_menu()

    elif item.action == "kill":
        if kill_process():
            xbmc.executebuiltin('Container.Refresh')

    elif item.action == 'arrancar_motor':
        # From the menu, or from Channels with no engine: the road playback takes to get one
        # up, and then back to where the user was going. Whoever waited has already seen why
        # it failed, if it did.
        try:
            d = asegurar_motor()
        except MotorNoDisponible as e:
            logger(f'arrancar_motor: {e}')
            return

        if d:
            d.close()

        if item.luego == 'catalogo':
            run(Item(action='catalogo'))
        else:
            xbmcgui.Dialog().notification(HEADING, translate(30156), icon_path, 3000)
            # The row turns into "Detener motor" or, on Android, into "Cerrar motor".
            xbmc.executebuiltin('Container.Refresh')
        return

    elif item.action == 'cerrar_motor':
        # Android's mirror of 'kill'. Who answers is asked now, with its own timeouts, and not
        # when the menu was painted. The row goes back to "Abrir" when the menu is painted
        # again: there is no way of knowing when the user stops the engine in Android's page.
        contesta = detect_engine()
        if contesta is None:
            xbmcgui.Dialog().notification(HEADING, translate(30019), ICONO_ERROR, 3000)
            xbmc.executebuiltin('Container.Refresh')
        else:
            cerrar_motor_android(contesta)
        return

    elif item.action in ("historial", "favoritos"):
        from lib import history_ui

        # As with Channels: a window of its own, and the classic listing when that is asked
        # for or the window cannot be built.
        if not (ui_common.clasica() or item.clasico):
            cerrar_directorio(succeeded=False)
            ventana = (history_ui.mostrar_historial if item.action == "historial"
                       else history_ui.mostrar_favoritos)
            if not ventana():
                volver_a_lo_clasico(item.action)
            return

        if plugin_handle() < 0:
            entrar_en_lista(item.action)
            return

        itemlist = (history_ui.items_historial() if item.action == "historial"
                    else history_ui.items_favoritos())

    elif item.action == "del_historial":
        # 'infohash' is what a listing painted by an earlier version still carries.
        clave = item.clave or (f'infohash:{item.infohash.lower()}' if item.infohash else '')
        if clave:
            history.borrar(clave)
        elif xbmcgui.Dialog().yesno(HEADING, translate(30051)):
            # Emptying the whole history has no way back, so it is confirmed.
            history.vaciar()
        else:
            return

        xbmc.executebuiltin('Container.Refresh')
        return

    elif item.action == "fav_anadir":
        # The row already carries the link and its data, so nothing has to be looked up.
        datos = {'id': item.id, 'url': item.url, 'infohash': item.infohash, 'titulo': item.label,
                 'icono': item.icon, 'plot': item.plot, 'origen': item.origen, 'motor': item.motor}
        if history.anadir_favorito(datos):
            xbmcgui.Dialog().notification(HEADING, translate(30138), icon_path, 3000)
        elif history.es_favorito(history.clave(history.normalizar(datos) or {})):
            # A search is not repainted after keeping a row, so its menu still offers to keep it.
            xbmcgui.Dialog().notification(HEADING, translate(30146), icon_path, 3000)
        if item.refrescar:
            xbmc.executebuiltin('Container.Refresh')
        return

    elif item.action == "fav_quitar":
        if history.quitar_favorito(item.clave):
            xbmcgui.Dialog().notification(HEADING, translate(30145), icon_path, 3000)
        elif not history.es_favorito(item.clave):
            # A search is not repainted after taking a row out, so its menu still offers to.
            xbmcgui.Dialog().notification(HEADING, translate(30147), icon_path, 3000)
        if item.refrescar:
            xbmc.executebuiltin('Container.Refresh')
        return

    elif item.action == "fav_renombrar":
        nombre = xbmcgui.Dialog().input(translate(30139), item.label)
        if history.renombrar_favorito(item.clave, nombre):
            xbmc.executebuiltin('Container.Refresh')
        return

    elif item.action == "fav_mover":
        # Repainted even when it could not move: then the listing was older than the file. Kodi
        # keeps the cursor on the row it was on, which is the same address in its new place.
        history.mover_favorito(item.clave, item.hacia)
        xbmc.executebuiltin('Container.Refresh')
        return

    elif item.action == "elementum":
        # From a History or My favourites menu. The link goes up the history as a playback here
        # would, since it is opened from EKHorus all the same.
        if not elementum.puede_abrir(item.url):
            return
        if not elementum.instalado():
            # It may have been uninstalled after the menu that offered it was painted.
            xbmcgui.Dialog().notification(HEADING, translate(30150), icon_path, 5000)
            return
        history.anotar_de_fondo(url=item.url, origen=item.origen, icono=item.icon, plot=item.plot,
                                titulo=item.nombre if 'nombre' in item else item.label)
        callar_musica()
        elementum.abrir(item.url)
        return

    elif item.action == "search":
        url_list = item.texto
        if not url_list:
            # Asked before any listing exists, because a window of ours opened while Kodi waits
            # for a folder fights its busy dialog for the focus. The row is no folder any more;
            # this only closes something when an old favourite still opens it as one.
            cerrar_directorio(succeeded=False)

            from lib import input_ui
            # With no earlier search the box opens empty. It used to come preloaded with
            # acetv.org, a domain that no longer exists: the user pressed accept and got
            # a network error on their first search.
            texto = input_ui.pedir_texto(translate(30032), translate(30100),
                                         get_setting_text("last_search"))
            if texto:
                destino = f"{sys.argv[0]}?{Item(action='search', texto=texto).tourl()}"
                # Container.Update keeps the menu in the history, so Back returns to it. With no
                # listing of ours in front (a favourite on the home screen) there is nothing to
                # update, and the results open in their own window.
                if xbmc.getInfoLabel('Container.FolderPath').startswith(sys.argv[0]):
                    xbmc.executebuiltin(f'Container.Update({destino})')
                else:
                    xbmc.executebuiltin(f'ActivateWindow(programs,{destino},return)')
            return

        tmp_itemlist = list()
        ids = set()
        for url in url_list.split(";"):
            if url:
                tmp_itemlist.append(Item(label=f">>>>>>>>>> Source [{url}] <<<<<<<<<<", action='', id=url))
                tmp_itemlist = tmp_itemlist + search(url)
        for found in tmp_itemlist:
            # An item with no 'id' is no good as a key: Item returns '' for whatever it
            # does not have, so everything arriving by infohash would share the same
            # one and merge into one. Today everything carries an id and the result is
            # identical.
            clave = found.id or found.infohash or found.url
            if clave not in ids:
                if found.action == 'play':
                    found.origen = 'buscar'
                itemlist.append(found)
                ids.add(clave)
        # There are results if some item is playable (separators do not count;
        # the earlier threshold by lengths failed with a trailing ';').
        if any(it.action == 'play' for it in itemlist):
            set_setting("last_search", url_list)
        else:
            xbmcgui.Dialog().ok(HEADING,  translate(30031) % url_list)
            itemlist = list()

        if not itemlist:
            # No results: the directory was left half open
            # (before it even painted a list of separators only).
            cerrar_directorio(succeeded=False)
            return

    elif item.action == 'open_settings':
        clasica_antes = ui_common.clasica()
        xbmcaddon.Addon().openSettings()
        recoger_musica()
        from lib import playback_watch
        playback_watch.arrancar_si_falta()
        # Each row of the painted menu records whether it is a folder, and that depends on
        # the mode. Changing it without repainting left EspaKodi Addons and the APKs dead.
        if ui_common.clasica() != clasica_antes:
            xbmc.executebuiltin('Container.Refresh')

    elif item.action == 'cuadro_mandos':
        # The directory is closed BEFORE opening the window: while the plugin is still
        # resolving, Kodi brings up its waiting dialog and would compete for the focus.
        cerrar_directorio(succeeded=False)

        if ui_common.clasica():
            xbmcaddon.Addon().openSettings()
            recoger_musica()
            from lib import playback_watch
            playback_watch.arrancar_si_falta()
            return

        from lib import control_panel
        control_panel.mostrar()
        return

    elif item.action == 'web':
        cerrar_directorio(succeeded=False)

        from lib import web_ui
        web_ui.mostrar()
        return

    elif item.action == 'tv_exportar':
        cerrar_directorio(succeeded=False)

        from lib import kodi_tv
        kodi_tv.exportar()
        # The row says whether there is an export and since when. Only if Experimental is still
        # on screen: the user may have gone to the TV.
        if xbmc.getInfoLabel('Container.FolderPath').startswith(sys.argv[0]):
            xbmc.executebuiltin('Container.Refresh')
        return

    elif item.action == 'anotar_fuera':
        # The switch of the classic History, whose first row says whether it is on.
        cerrar_directorio(succeeded=False)

        from lib import history_ui, playback_watch
        antes = playback_watch.activado()
        if history_ui.alternar_anotar_fuera() != antes:
            xbmc.executebuiltin('Container.Refresh')
        return

    elif item.action == 'guia':
        cerrar_directorio(succeeded=False)

        from lib import guide_ui
        guide_ui.mostrar()
        return

    elif item.action == 'universo':
        cerrar_directorio(succeeded=False)

        from lib import universe_ui
        universe_ui.mostrar()
        return

    elif item.action == 'apk_menu':
        if not (ui_common.clasica() or item.clasico):
            cerrar_directorio(succeeded=False)
            if not apk_ventana():
                volver_a_lo_clasico('apk_menu')
            return

        if plugin_handle() < 0:
            entrar_en_lista('apk_menu')
            return

        itemlist = apk_menu()

    elif item.action == 'catalogo':
        from lib import channels_ui

        # The window of our own only opens from the root. Inside it the levels do not
        # relaunch the addon, so an item that already carries a mode comes from the
        # classic route.
        if not (ui_common.clasica() or item.clasico or item.modo):
            cerrar_directorio(succeeded=False)
            if not channels_ui.mostrar_explorador():
                volver_a_lo_clasico('catalogo')
            return

        if plugin_handle() < 0:
            entrar_en_lista('catalogo')
            return

        itemlist = channels_ui.filas_clasicas(item)

    elif item.action == 'catalogo_refresh':
        from lib import channels_ui
        if channels_ui.actualizar():
            xbmc.executebuiltin('Container.Refresh')
        return

    elif item.action == 'download_apk':
        download_apk(item.filename, (item.apk_url, item.apk_backup), item.sha256)

    elif item.action == 'apk_info':
        xbmcgui.Dialog().ok(HEADING, translate(30075))

    elif item.action == 'espakodi_addons':
        # The import goes in here on purpose: if you do not enter the menu, it is not loaded
        from lib import espakodi_installer

        if not (ui_common.clasica() or item.clasico):
            cerrar_directorio(succeeded=False)
            if not espakodi_installer.mostrar_ventana():
                volver_a_lo_clasico('espakodi_addons')
            return

        handle = plugin_handle()
        if handle < 0:
            entrar_en_lista('espakodi_addons')
            return

        espakodi_installer.render_menu(handle)
        # render_menu() paints the items but does not close: the closing always goes through
        # here, which is what avoids the second endOfDirectory() in the __main__ finally
        cerrar_directorio(succeeded=True, cache=True)
        return

    elif item.action == 'ek_launch':
        from lib import espakodi_installer
        espakodi_installer.launch_by_id(item.addon_id)

    elif item.action == 'ek_open_web':
        from lib import espakodi_installer
        espakodi_installer.open_web()

    elif item.action == 'ek_open_repo':
        from lib import espakodi_installer
        espakodi_installer.open_repo_unificado()

    elif item.action == 'ek_open_apk':
        from lib import espakodi_installer
        espakodi_installer.open_apk_latest()

    elif item.action == 'ek_rescate':
        from lib import espakodi_installer
        if espakodi_installer.instalar_rescate():
            xbmc.executebuiltin('Container.Refresh')

    elif item.action == 'play':
        id = url = infohash = None
        origen = item.origen

        # Only the items that ALREADY carry a link (history, lists) bring their own
        # metadata. The "Reproducir ID" menu item does not: its label is the menu
        # text and must not end up as the video title.
        meta = {'title': '', 'iconimage': '', 'plot': '', 'desde_motor': False}

        if item.id or item.url or item.infohash:
            # The classic History and My favourites rows paint a readable label even for a
            # link that came with no name. 'nombre' is the name itself, so a made-up label
            # never becomes the video title.
            meta = {'title': item.nombre if 'nombre' in item else (item.label or item.title or ''),
                    'iconimage': item.icon or '',
                    'plot': item.plot or '',
                    'desde_motor': bool(item.motor)}

            # A channel taken to Kodi's TV section has no logo in its address, which is what IPTV
            # Simple knows it by (kodi_tv._item). The row that was pressed still shows it.
            if item.origen == 'tv' and not meta['iconimage']:
                from lib.playback_watch import icono_real
                meta['iconimage'] = icono_real(xbmc.getInfoLabel('ListItem.Icon'))

        if item.id:
            id =item.id
        elif item.url:
            url=item.url
        elif item.infohash:
            infohash=item.infohash
        else:
            origen = 'manual'
            last_id = get_setting_text("last_id", "a0270364634d9c49279ba61ae3d8467809fb7095")
            from lib import input_ui
            input = input_ui.pedir_texto(translate(30022), translate(30099),
                                         last_id if get_setting("remerber_last_id") else "")
            if re.findall('^(http|magnet)', input, re.I):
                url = input
            elif re.findall('([0-9a-f]{40})', input, re.I):
                id = re.findall('([0-9a-f]{40})', input, re.I)[0]
            elif input:
                xbmcgui.Dialog().ok(HEADING, translate(30031) % input)
                return

            # Whoever has Elementum chooses what opens a pasted magnet or .torrent, since Elementum
            # is built for torrents of films and series. It is asked before the history, so that
            # cancelling records nothing.
            if url and elementum.puede_abrir(url) and elementum.instalado():
                eleccion = xbmcgui.Dialog().select(translate(30151),
                                                   [translate(30152), 'Elementum'])
                if eleccion < 0:
                    return
                if eleccion == 1:
                    history.anotar_de_fondo(url=url, origen=origen)
                    callar_musica()
                    elementum.abrir(url)
                    return

        # To the history as soon as it is asked for, before anything can fail, and with the
        # link as it came, so that a .torrent or a magnet opened again takes the same road. The
        # writing goes on a thread and the progress dialog does not wait for the disk.
        if id or url or infohash:
            meta['clave_historial'] = history.anotar_de_fondo(
                id=id, url=url, infohash=infohash, titulo=meta['title'], icono=meta['iconimage'],
                plot=meta['plot'], origen=origen, motor=meta['desde_motor'])

        if id:
            acestreams(id=id, **meta)
        elif url and (url.lower().endswith('.torrent') or url.lower().startswith('magnet:')):
            if url.lower().startswith('magnet:'):
                infohash = infohash_de_magnet(url)
            else:
                infohash = read_torrent(url)

            if infohash:
                acestreams(infohash=infohash, **meta)
            else:
                # Said as with a bad identifier above: a link that cannot be read used to end
                # in silence here, while the same link from another addon gets a notice.
                xbmcgui.Dialog().ok(HEADING, translate_fmt(30031, url))
        elif url:
            acestreams(url=url, **meta)
        elif infohash:
            # A channel of the catalogue may carry other links, and they are looked up here so
            # that every door that plays one gets them: the list, the phone page, a search
            # result, a favourite or the history. They are an extra, so a failure looking them
            # up must never stop the channel from playing.
            alternativos = list()
            if meta['desde_motor']:
                try:
                    alternativos = alternatives.otros(server.base, infohash)
                except Exception as e:
                    # The kind only: the message may carry the address asked, with the channel.
                    logger(f'play: sin enlaces alternativos ({type(e).__name__})', 'error')
            acestreams(infohash=infohash, alternativos=alternativos, **meta)

        #xbmc.executebuiltin('Container.Refresh')

    if not itemlist:
        # An empty folder has to be closed all the same, or Kodi keeps showing the listing that
        # was there before. The History and My favourites always bring a row, even when empty.
        if item.action == "mainmenu":
            cerrar_directorio(succeeded=True)
        return

    handle = plugin_handle()
    if handle < 0:
        return

    # They are read once, not once per channel.
    icon_default = os.path.join(runtime_path, 'icon.png')
    # Only the main menu carries the addon's fanart behind it. In the listings the rows speak
    # for themselves, and a channel list would show the same picture behind every channel.
    # It goes on each row because that is what the skin paints: on Kodi's own '..' row there
    # is none, and setPluginFanart does not help, Container.Art(fanart) stays empty (measured
    # on EspaKodi 21.3).
    fanart = os.path.join(runtime_path, 'fanart.jpg') if item.action == 'mainmenu' else ''
    show_qr = get_setting("show_qr_codes")
    favoritas = (history.claves_favoritas()
                 if any(e.action == 'play' and (e.id or e.url or e.infohash) for e in itemlist)
                 else set())
    con_elementum = (any(e.action == 'play' and elementum.puede_abrir(e.url) for e in itemlist)
                     and elementum.instalado())
    # Only My favourites rows move, each one as far as its place allows.
    en_orden = ([history.clave(e) for e in history.favoritos()] if any(e.fav for e in itemlist)
                else list())

    for entrada in itemlist:
        # A catalogue row paints a filler icon and the text of its panel, which travel apart
        # because they must not reach the video or the history.
        icono_de_fila = entrada.icono_fila or entrada.icon or icon_default
        listitem = xbmcgui.ListItem(entrada.label or entrada.title)
        poner_info_video(listitem, entrada.label or entrada.title,
                         entrada.plot_fila or entrada.plot or entrada.id or entrada.url, 'video')

        poster_url = icono_de_fila
        # Only real ids (a 40-char hash) carry a QR: the source separators and the
        # search texts are not acestream links.
        if show_qr and entrada.id and re.match(r'[0-9a-f]{40}\Z', str(entrada.id), re.I):
            poster_url = qr_poster(entrada.id) or poster_url

        arte = {'icon': icono_de_fila, 'poster': poster_url}
        if fanart:
            arte['fanart'] = fanart
        listitem.setArt(arte)

        ctx = menu_contextual(entrada, favoritas, con_elementum, en_orden)
        if ctx:
            listitem.addContextMenuItems(ctx)

        if entrada.isPlayable:
            listitem.setProperty('IsPlayable', 'true')
            isFolder = False

        elif isinstance(entrada.isFolder, bool):
            isFolder = entrada.isFolder

        elif entrada.action in ["", "kill", "arrancar_motor", "cerrar_motor", "play", "open_settings", "search",
                               "cuadro_mandos", "guia", "universo", "catalogo_refresh", "web",
                               "tv_exportar"]:
            isFolder = False

        else:
            isFolder = True

        xbmcplugin.addDirectoryItem(
            handle=handle,
            url='%s?%s' % (sys.argv[0], entrada.tourl()),
            listitem=listitem,
            isFolder= isFolder,
            totalItems=len(itemlist)
        )

    xbmcplugin.addSortMethod(handle=handle, sortMethod=xbmcplugin.SORT_METHOD_NONE)
    cerrar_directorio(succeeded=True, cache=True)


def menu_contextual(entrada, favoritas, con_elementum=False, en_orden=()):
    """Context menu of a directory row: what can be done with its link without opening it.

    'favoritas' is the set of favourite keys, 'con_elementum' whether Elementum is installed and
    'en_orden' the favourite keys in their order, all asked once for the whole listing."""
    def orden(**campos):
        return f'RunPlugin({sys.argv[0]}?{Item(**campos).tourl()})'

    ctx = list()
    # Inside History and My favourites the list is repainted after the change. Anywhere else
    # it is not: repainting a search would ask for the search again.
    refrescar = 1 if (entrada.hist or entrada.fav) else ''

    if con_elementum and entrada.action == 'play' and elementum.puede_abrir(entrada.url):
        ctx.append((translate(30149), orden(
            action='elementum', url=entrada.url, origen=entrada.origen,
            label=entrada.nombre if 'nombre' in entrada else entrada.label,
            icon=entrada.icon, plot=entrada.plot)))

    if entrada.fav:
        ctx.append((translate(30137), orden(action='fav_renombrar', clave=entrada.fav,
                                            label=entrada.nombre)))
        nombres = {'subir': translate(30172), 'bajar': translate(30173),
                   'principio': translate(30174)}
        for hacia in history.movimientos(en_orden, entrada.fav):
            ctx.append((nombres[hacia], orden(action='fav_mover', clave=entrada.fav, hacia=hacia)))
        ctx.append((translate(30136), orden(action='fav_quitar', clave=entrada.fav, refrescar=1)))

    elif entrada.action == 'play':
        base = history.normalizar({'id': entrada.id, 'url': entrada.url,
                                   'infohash': entrada.infohash})
        if base is not None:
            clave = history.clave(base)
            if clave in favoritas:
                ctx.append((translate(30136), orden(action='fav_quitar', clave=clave,
                                                    refrescar=refrescar)))
            else:
                tipo, valor = history.enlace(base)
                # A classic History row plays with no origin so as to keep the one recorded, and
                # that recorded one is what the favourite takes.
                ctx.append((translate(30135), orden(
                    action='fav_anadir', refrescar=refrescar,
                    origen=entrada.origen or entrada.origen_fila,
                    label=entrada.nombre if 'nombre' in entrada else entrada.label,
                    icon=entrada.icon, plot=entrada.plot, motor=entrada.motor,
                    **{tipo: valor})))

    if entrada.hist:
        ctx.append((translate(30048), orden(action='del_historial', clave=entrada.hist)))
        ctx.append((translate(30049), orden(action='del_historial')))

    return ctx


def preguntar_al_motor(motor, metodo, infohash):
    """What the engine at motor ('http://host:port') answers to method about infohash, or None.

    With a short wait: it answers at once for what it has just played, and one it does not know
    kept it hanging for the whole default wait (measured on the Windows engine)."""
    partes = urllib_parse.urlsplit(motor)
    respuesta = Server(partes.hostname, partes.port or 6878, timeout=3).getserver(
        method=metodo, api_version=3, infohash=infohash)
    return respuesta.data if respuesta.success else None


def escribir_lote(lote):
    """Writes a batch of the service, which sends no other while this one runs (see
    playback_watch.Anotador). 'lote' is the name it left it under on the home window."""
    from lib import playback_watch

    try:
        # Taken off the window even when it is not written.
        entradas = playback_watch.recoger(lote)
        # It may have been switched off with the batch already on its way.
        if get_setting('anotar_fuera'):
            entradas = [e for e in entradas if e.get('origen') in playback_watch.ORIGENES]
            history.anotar_lote(playback_watch.repasar(entradas, preguntar_al_motor))
    except ValueError as e:
        logger(f'anotar: lote dañado, se descarta: {e}', 'error')
    finally:
        playback_watch.soltar_marca(lote)


# StreamNinja gives a link back after 17 s at most: 2 to see its engine answer and 15 to ask it for
# the session (its acestream_player.py). A call for the same link within this long is that.
REBOTE_STREAMNINJA = 30


def llamada_externa(argumentos):
    """Another addon asks us to play something (StreamNinja and company)."""
    action = argumentos.get('action', '').lower()

    # The batches of the service (lib/playback_watch.py) go before the log line below, so that
    # what Kodi played outside EKHorus goes to the History and nowhere else. Nor are they ever
    # forwarded to StreamNinja, since they play nothing.
    if action == 'anotar':
        escribir_lote(argumentos.get('lote') or '')
        return

    # What is asked for, not what: the log keeps no link nor name of anything played.
    logger(f'Llamada externa: {action}')

    if action == 'install_acestream':
        if system_platform in ['linux', 'windows']:
            install_acestream()
        return

    # Ours, not another addon's, like the button in the settings above: the menu asks for
    # the music here so that the waiting and the watching do not hold the menu itself.
    if action == 'musica':
        from lib import musica
        musica.reproducir(puesta=argumentos.get('puesta') == '1', desde=argumentos.get('desde'))
        return

    if action != 'play' or not (argumentos.get('id') or argumentos.get('url') or argumentos.get('infohash')):
        return

    titulo = argumentos.get('title') or ''
    icono = argumentos.get('iconimage') or ''
    origen = 'externa'
    # A channel of Kodi's TV section (the KODI lists of HaP) comes with no name, and the row that
    # was pressed still has it, and its logo: the channel list, the guide or a widget of the home
    # screen. Only for the history; the video takes what the call brings, as always.
    if not titulo and any(xbmc.getInfoLabel(etiqueta).startswith('pvr://')
                          for etiqueta in ('ListItem.FileNameAndPath', 'ListItem.FolderPath')):
        from lib.playback_watch import icono_real
        titulo, origen = xbmc.getInfoLabel('ListItem.ChannelName'), 'tv'
        icono = icono or icono_real(xbmc.getInfoLabel('ListItem.Icon'))

    # Recorded here, before the forwarding to StreamNinja, because it is the link the other
    # addon asked for, whoever ends up playing it.
    clave = history.anotar_de_fondo(id=argumentos.get('id'), url=argumentos.get('url'),
                                    infohash=argumentos.get('infohash'), titulo=titulo,
                                    icono=icono, plot=argumentos.get('plot') or '', origen=origen)

    # StreamNinja bounces back to Horus when its native engine does not play; without
    # this circuit breaker the forwarding enters an infinite Horus<->StreamNinja loop.
    enlace_pedido = argumentos.get('id') or argumentos.get('infohash') or argumentos.get('url') or ''
    # As StreamNinja gives it back, or an id sent in capitals was not known on its return.
    from lib.playback_watch import como_vuelve
    snb_key = 'ekhorus_snb_' + como_vuelve(enlace_pedido)
    win = xbmcgui.Window(10000)
    prev = win.getProperty(snb_key)
    bounced = False
    if prev:
        try:
            bounced = (time.time() - float(prev)) < REBOTE_STREAMNINJA
        except ValueError:
            pass

    # AddonIsEnabled and not HasAddon: a switched-off StreamNinja is still installed for Kodi,
    # and the link handed to it would play nothing. Switched off, EKHorus plays it itself.
    if get_setting("redirect_streamninja") and xbmc.getCondVisibility('System.AddonIsEnabled(plugin.video.streamninja)') and not bounced:
        win.setProperty(snb_key, str(time.time()))
        fwd = {k: v for k, v in argumentos.items() if k != 'action' and v}
        # With "Guardar todo" on, the watch would note StreamNinja's session of this same link
        # once more, under its infohash.
        if get_setting('anotar_fuera'):
            from lib import playback_watch
            playback_watch.apuntar_reenvio(fwd)
        xbmc.executebuiltin('RunPlugin(plugin://plugin.video.streamninja/?action=acestream&%s)' % urllib_parse.urlencode(fwd))
        return

    win.clearProperty(snb_key)
    if bounced:
        # Given back by StreamNinja, so EKHorus plays it itself and no session of it is coming.
        from lib import playback_watch
        playback_watch.olvidar_reenvio(enlace_pedido)
    url = argumentos.get('url') or ''

    if url.lower().endswith('.torrent'):
        infohash = read_torrent(url, argumentos.get('headers'))
        if not infohash:
            # This used to be a mute exit(0): no warning, no log, nothing.
            notification_error(translate(30031) % url)
            return
        argumentos['infohash'] = infohash
        argumentos['url'] = None

    elif url.lower().startswith('magnet:'):
        infohash = infohash_de_magnet(url)
        if not infohash:
            notification_error(translate(30031) % url)
            return
        argumentos['infohash'] = infohash
        argumentos['url'] = None

    acestreams(id=argumentos.get('id'),
               url=argumentos.get('url'),
               infohash=argumentos.get('infohash'),
               title=argumentos.get('title'),
               iconimage=argumentos.get('iconimage'),
               plot=argumentos.get('plot'),
               clave_historial=clave)


if __name__ == '__main__':
    try:
        item = None

        # len(): invoked via RunScript (with no plugin arguments) this blew up
        # with IndexError before getting anywhere.
        if len(sys.argv) > 2 and sys.argv[2]:
            try:
                item = Item().fromurl(sys.argv[2])
            except Exception:
                # It is not an item of ours: it is another addon's query.
                argumentos = dict()
                for c in sys.argv[2][1:].split('&'):
                    if '=' not in c:
                        continue
                    # split('=', 1): a value with '=' inside (base64, signed urls)
                    # broke the unpacking and brought the external call down.
                    k, v = c.split('=', 1)
                    argumentos[k] = urllib_parse.unquote_plus(ensure_str(v))

                llamada_externa(argumentos)
        else:
            item = Item(action='mainmenu')

        if item:
            run(item)

    finally:
        # Safety net. Other addons invoke us with PlayMedia, and there Kodi gives
        # us a handle and waits for an answer: if the script ends without giving
        # one (an early exit, an unknown action, an error), Kodi throws a phantom
        # "playback failed". cerrar_directorio() does nothing if there is no
        # handle or if some branch has already closed it.
        cerrar_directorio(succeeded=False)

        # The history of a playback is written on a thread, and the script must not end first.
        history.esperar()
