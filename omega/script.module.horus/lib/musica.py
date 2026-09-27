# -*- coding: utf-8 -*-
# EKHorus - EspaKodi GTA Soundtrack: the radio that plays behind the menus.

import os
import random
import shutil
import threading
import time
from collections import namedtuple

import xbmc
import xbmcaddon
import xbmcgui

from lib.utils import (ADDON, USER_AGENT, data_path, echar_pestillo, get_setting_text,
                       hay_pestillo, icon_path, logger, poner_info_musica, quitar_pestillo,
                       refrescar_pestillo, translate, urllib_request)

TITULO = 'EspaKodi GTA Soundtrack'

# Never shipped: this recording alone is 18 MB against the 300 KB of the whole addon. It is
# fetched from here, played from the web the first time and from a copy on the device after
# that (see CARPETA). Two hostings of the very same file (identical to the byte), the second
# for the day the first takes it down, and a setting on top so that a third can be given
# without publishing a version.
URLS = ('https://media.vocaroo.com/mp3/1bMhSTsfHtUs',
        'https://files.catbox.moe/qhqr6m.mp3')

# Where each song starts, in seconds. The file is a single twenty-minute recording of six
# songs separated by silences of about three seconds; these are the ends of those silences,
# measured with ffmpeg's silencedetect (-38dB/0.7s and -45dB/0.4s find the same six) and
# rounded down, so a song is never joined already started. From each one the recording plays
# on to the end, this being a radio and not a track list.
INICIOS = (0, 253, 343, 558, 739, 997)
# Where the recording ends (ffprobe: 1208.46 s), which is where the last song does.
DURACION = 1208

PESTILLO = 'ekhorus.musica'
# Just enough for the menu to be on its way. Only the first opening, the one from the web,
# goes through here (see _poner_guardada), and it comes in at about the second or third
# second after the menu.
RETARDO = 0.5
# A turn is two infolabels, and leaving the menus has to stop the track quickly enough for
# nobody to notice it lingering.
PASO = 1
# Turns outside the menus before stopping. A single reading is not an answer: while Kodi
# swaps windows the container has no path, and that is not the user leaving.
FUERA_SEGUIDAS = 2
# Kodi opens the stream on its own thread, and everything after that needs it already open.
# Thirty seconds because it is not always instant: measured at eight on the second hosting
# with the first one timing out first, and giving up early used to leave the recording
# playing behind the back of the watch.
ESPERA_ARRANQUE = 30
# Short on purpose: the knock runs before the first note, and a device with no network must
# not sit there for the ten seconds the rest of the addon gives a request. The download reads
# with it too: a network that stalls halfway then lets go before the five seconds Kodi gives
# a script to stop when it closes, instead of being killed with an error in the log.
ESPERA_RED = 4
# The latch goes stale at 60 s and the recording runs for twenty minutes.
REFRESCO_PESTILLO = 30
# One download at a time for the whole of Kodi. Leaving the menus does not stop it, and
# coming back before it has finished plays from the web again, which without this would
# start a second one into the same file.
PESTILLO_DESCARGA = 'ekhorus.musica.descarga'
# With no key pressed and nothing touched for as long as the longest song lasts (4 min 18 s),
# the music gives way until the next key or touch (see _Presencia). Kodi takes playing audio
# for activity (screensaver.disableforaudio, on by default), so while the music plays neither
# the screensaver nor the display's power saving would ever come. And on Android, Kodi sent to
# the background by the Home button goes on playing audio over whatever is in front, with
# nothing an addon can read to tell.
INACTIVIDAD = max(fin - inicio for inicio, fin in zip(INICIOS, INICIOS[1:] + (DURACION,)))
# Modal dialogs Kodi puts up by itself while something loads: the progress one (EKHorus waiting
# for the engine, say) and the busy spinner (a menu being listed again). The focus is theirs
# while they are up, which says nothing about anybody's finger.
DE_PASO = (10101, 10138, 10160)
# The window Kodi opens for a screensaver that is an addon.
SALVAPANTALLAS = 12900
# When something was last asked to play (see callar). A key brings the music back, and the
# key that chooses a channel must not bring it back over the channel.
CALLADA = 'ekhorus.musica.callada'
# When EKHorus last put another app in front of Kodi (see apartar).
APARTADA = 'ekhorus.musica.apartada'
# When EKHorus last changed the screen by itself (see sola).
SOLA = 'ekhorus.musica.sola'
# Tries at getting into the chosen song, and how far off the mark still counts as landed:
# a second goes by between asking and reading it back, and an mp3 does not seek to the frame.
INTENTOS_SALTO = 3
MARGEN_SALTO = 10
# How long to let the player get its bearings before reading where it is.
GRACIA_SALTO = 6
# How often the opening is looked at while it happens.
PASO_ARRANQUE = 0.25

_ID_ADDON = 'script.module.horus'
_RUTA_ADDON = f'plugin://{_ID_ADDON}'

# The recording is kept on the device after the first time. From there it opens at once, with
# no network, and from the very script that paints the menu (see _poner_guardada); nothing of
# it shows (measured: no spinner, no second the menu fails to answer). From the web it has to
# be knocked on first and opened from another invocation, which the first time brings the
# music in two or three seconds late and lets a spinner be glimpsed once.
#
# It lives in a folder of its own inside the addon's data, and that folder is what tells the
# menu there is something to delete when the music is switched off.
CARPETA = 'musica'
FICHERO = 'espakodi_gta_soundtrack.mp3'
# Anything smaller than this is a leftover, not the recording.
MINIMO_GUARDADO = 1024 * 1024
# The recording is 18 MB. The cap is what stops a wrong address from filling the device.
MAXIMO_GUARDADO = 32 * 1024 * 1024
TROZO = 64 * 1024


def _ajustes():
    """The addon's settings as they are on disk right now.

    Each xbmcaddon.Addon() keeps what it read the first time it was asked, and when the
    settings dialog saves, Kodi refreshes only the oldest instance still alive. The watch
    lives for twenty minutes, and behind an older invocation (the server of the phone page,
    say) it would never see the music switched off. Writes go through a new one as well:
    setSetting() saves every setting and not only its own, so a stale copy would undo what the
    user had just saved. By id, because the download asks from a thread of its own."""
    return xbmcaddon.Addon(_ID_ADDON)


def _activada():
    return _ajustes().getSetting('musica_fondo') != 'false'


def _propia():
    """The address typed into the setting, empty when the addon's own is used."""
    return get_setting_text('musica_url', '').strip()


def _puede_arrancar():
    """Whether the music can start: nobody has walked out of the addon in the meantime.

    Looser than _en_los_menus() on purpose. This runs while the menu is still being painted,
    and a container with no path yet is a menu on its way, not a user who has left. Except on
    the home screen, which has no path either and is where a user who backed out at once is."""
    if xbmc.getCondVisibility('Window.IsActive(home)'):
        return False

    ruta = xbmc.getInfoLabel('Container.FolderPath')

    return not ruta or ruta.startswith(_RUTA_ADDON)


def _en_los_menus(ruta):
    """Whether the addon is still what is on screen, 'ruta' being the container's folder path.

    The addon's own windows do not change the container, so the folder path stays on the
    plugin while the dashboard, Channels, the guide or the settings dialog sit on top of it.
    Kodi's music visualisation counts as being in: if it is up, it is over our own track."""
    if xbmc.getCondVisibility('Window.IsVisible(visualisation)'):
        return True

    return ruta.startswith(_RUTA_ADDON)


def _hueco_libre(player):
    """Whether the music can come in right now.

    Not over anything already playing, the user's own music included, nor with a channel on
    its way: while one pre-buffers behind its progress dialog there is nothing playing yet
    for isPlaying() to see."""
    return not (player.isPlaying() or not _puede_arrancar()
                or xbmc.getCondVisibility('Window.IsActive(progressdialog)'))


def _hora(aviso):
    """When the word under 'aviso' was left (see callar, apartar and sola), 0 if there is none."""
    try:
        return float(xbmcgui.Window(10000).getProperty(aviso))
    except ValueError:
        return 0


# What the user has in front: where (window, dialog, control with the focus, folder) and, in
# the list there, how many rows it has and which of them has the focus.
_Pantalla = namedtuple('_Pantalla', 'donde filas fila')


def _pantalla(ruta):
    """The _Pantalla in front, 'ruta' being the folder path. None while it says nothing about
    the user: one of Kodi's own dialogs up (see DE_PASO), a screensaver, or no path, which is
    a window on its way."""
    ventana = xbmcgui.getCurrentWindowId()
    dialogo = xbmcgui.getCurrentWindowDialogId()
    if not ruta or dialogo in DE_PASO or ventana == SALVAPANTALLAS:
        return None

    donde = (ventana, dialogo, xbmc.getInfoLabel('System.CurrentControlId'), ruta)
    return _Pantalla(donde, xbmc.getInfoLabel('Container.NumItems'),
                     xbmc.getInfoLabel('Container.CurrentItem'))


def _tocada(antes, ahora):
    """Whether a finger on the screen came between two readings of _pantalla().

    A touch moves the focus, to a row or off the list, or opens something. A list painted
    again with another number of rows is the addon refreshing it (the engine's row going once
    the engine is up, say), not the user."""
    if antes is None or ahora is None:
        return False
    if antes.donde != ahora.donde:
        return True

    return antes.filas == ahora.filas and antes.fila != ahora.fila


class _Presencia:
    """Whether somebody is at Kodi, looked at once a turn.

    A key, the mouse or JSON-RPC set Kodi's idle time back to zero, so with nobody there it
    only ever grows. A touch does not: on Android it reaches Kodi as a gesture, which leaves
    that time running (measured, and so in Kodi 21's input manager), and it is told by what
    it changes on screen instead (see _tocada). Its quiet is counted on Kodi's idle time all
    the same, from the value it had at the touch: that time goes on counting with Kodi in the
    background, where nothing is painted."""

    def __init__(self):
        self.inactivo = xbmc.getGlobalIdleTime()
        # Where the quiet counts from. Now, to begin with: the watch starts because somebody
        # has just opened the menu, or brought the music back.
        self.cero = self.inactivo
        self.pantalla = None
        self.sola = _hora(SOLA)
        # Looks left in which a change of the screen is EKHorus's own (see sola).
        self.gracia = 0

    def mirar(self, ruta):
        """True if a key or a touch came since the last look, 'ruta' being the folder path."""
        # getGlobalIdleTime() and not the System.IdleTime condition: Kodi keeps the answer to
        # every condition until it paints the next frame, and in the background it paints
        # none (measured on Android: the condition stayed false for minutes on end).
        inactivo = xbmc.getGlobalIdleTime()
        tecla = inactivo < self.inactivo
        if tecla:
            self.cero = 0
        self.inactivo = inactivo

        # Word that EKHorus is about to change the screen by itself: this look and the next
        # count for nothing, as the change can land on either.
        vez = _hora(SOLA)
        if vez != self.sola:
            self.sola, self.gracia = vez, 2

        pantalla = _pantalla(ruta)
        toque = not self.gracia and _tocada(self.pantalla, pantalla)
        self.gracia = max(self.gracia - 1, 0)
        if toque:
            self.cero = inactivo
        self.pantalla = pantalla or self.pantalla

        return tecla or toque

    def quieto(self):
        """Seconds with neither a key nor a touch, as of the last look."""
        return self.inactivo - self.cero


def _sin_estorbo(player, monitor, desde):
    """Whether nothing got in the way of an opening that did not happen: Kodi closing, or
    something else asked to play or playing. Only then is a copy that will not open taken for
    a broken one. It is worse than none, and is dropped: the next opening plays from the web
    and saves it again."""
    return not (monitor.abortRequested() or _hora(CALLADA) >= desde or player.isPlaying())


def _suena(player, url):
    """Whether what the player has is our recording and not somebody else's video."""
    try:
        # Kodi can hand the address back with its own options stuck on after a '|'.
        return player.isPlaying() and player.getPlayingFile().split('|')[0] == url
    except RuntimeError:
        # Playback ended between the question and the answer.
        return False


def _responde(url):
    """Whether the address is one we can use and something answers at it.

    It is a knock before touching the player: without it, no network (or a recording taken
    down) answers the menu with Kodi's own "playback failed", which is the one thing a
    background track must never do. One byte is asked for, so nothing of the file is
    downloaded to find out."""
    # The setting is free text. Only the web, so a typo does not end up opening a local file
    # through urlopen's other handlers.
    if not url.startswith(('http://', 'https://')):
        logger(f'musica: {url} no es una direccion http, no se reproduce nada', 'error')
        return False

    peticion = urllib_request.Request(url, headers={'User-Agent': USER_AGENT,
                                                    'Range': 'bytes=0-0'})
    try:
        with urllib_request.urlopen(peticion, timeout=ESPERA_RED) as respuesta:
            return respuesta.status < 400
    except Exception as e:
        # Wide on purpose: a bad address typed into the setting, no network, a refused
        # connection or a redirect loop all mean the same thing here, which is no music.
        logger(f'musica: {url} no contesta, no se reproduce nada: {e}', 'error')
        return False


def _ruta_local():
    return os.path.join(data_path, CARPETA, FICHERO)


def _guardada():
    """The recording as kept on this device, or None if it is not there yet."""
    ruta = _ruta_local()

    try:
        return ruta if os.path.getsize(ruta) >= MINIMO_GUARDADO else None
    except OSError:
        return None


def _guardar(url):
    """Brings the recording down to the device for the times to come.

    It writes beside the real name and only takes that name once the whole file is there, so
    a download cut short (Kodi ending the script, the network going) leaves nothing that
    could be taken for the recording. It gives way to Kodi closing, which must not wait on
    18 MB, and to a video, which must not share the connection while it pre-buffers, both
    looked at between every piece. The setting is looked at once a second instead, since
    each look reads the settings file (see _ajustes)."""
    if not echar_pestillo(PESTILLO_DESCARGA):
        return

    destino = _ruta_local()
    parcial = f'{destino}.parte'

    try:
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        peticion = urllib_request.Request(url, headers={'User-Agent': USER_AGENT})

        with urllib_request.urlopen(peticion, timeout=ESPERA_RED) as respuesta:
            esperado = int(respuesta.headers.get('Content-Length') or 0)
            if not MINIMO_GUARDADO <= esperado <= MAXIMO_GUARDADO:
                logger(f'musica: {url} dice medir {esperado} bytes, no se guarda', 'error')
                return

            monitor = xbmc.Monitor()
            mirado = time.time()
            with open(parcial, 'wb') as fichero:
                while not (monitor.abortRequested()
                           or xbmc.getCondVisibility('Player.HasVideo')):
                    trozo = respuesta.read(TROZO)
                    if not trozo:
                        break
                    fichero.write(trozo)

                    if time.time() - mirado >= PASO:
                        if not _activada():
                            break
                        mirado = time.time()
                        refrescar_pestillo(PESTILLO_DESCARGA)

        if not _activada():
            # Switched off while it came down: nothing of it stays, the folder included.
            limpiar()
        elif os.path.getsize(parcial) != esperado:
            # Cut short. The next opening plays from the web again and tries once more.
            logger('musica: la descarga no se ha completado, se descarta')
            os.remove(parcial)
        else:
            os.replace(parcial, destino)
            logger(f'musica: grabacion guardada en {destino}')

    except Exception as e:
        # Whatever happened, the next opening plays from the web as usual and tries again.
        logger(f'musica: no se ha podido guardar la grabacion: {e}', 'error')
        try:
            os.remove(parcial)
        except OSError:
            pass

    finally:
        quitar_pestillo(PESTILLO_DESCARGA)


def _esperar_descarga(monitor):
    """Gives a download still running the moment it takes to see the switch-off and let go of
    its piece, which until then is an open file that cannot be deleted on Windows."""
    limite = time.time() + ESPERA_RED + PASO

    while hay_pestillo(PESTILLO_DESCARGA) and time.time() < limite:
        if monitor.waitForAbort(PASO_ARRANQUE):
            return


def _guardar_de_fondo(url):
    """Asks for the download without holding up the music that is already playing."""
    hilo = threading.Thread(target=_guardar, args=(url,))
    hilo.daemon = True
    hilo.start()


def limpiar():
    """Leaves nothing of the recording on the device. For when the music is switched off."""
    carpeta = os.path.join(data_path, CARPETA)
    if not os.path.isdir(carpeta):
        return

    try:
        shutil.rmtree(carpeta)
        logger(f'musica: se borra la copia guardada en {carpeta}')
    except OSError as e:
        logger(f'musica: no se ha podido borrar {carpeta}: {e}', 'error')


def _elegir_url(propia):
    """The first address that answers, or None if none does.

    An address typed into the setting replaces both of ours instead of falling back on
    them: whoever puts their own recording there wants that one or nothing."""
    for url in (propia,) if propia else URLS:
        if _responde(url):
            return url

    return None


def _nuestra_sonando(player):
    """The address of our recording if it is what is playing, None otherwise."""
    try:
        if not player.isPlaying():
            return None
        actual = player.getPlayingFile().split('|')[0]
    except RuntimeError:
        return None

    propia = _propia()
    nuestras = ((propia,) if propia else URLS) + (_ruta_local(),)

    return actual if actual in nuestras else None


def _sonadas(texto):
    """Songs already played in this round, oldest first, from what the setting says.

    The setting is free text written by us, but it is read as if anybody could have typed
    into it: anything that is not the index of a song is dropped."""
    ya = list()

    for trozo in texto.split(','):
        trozo = trozo.strip()
        if not trozo.isdigit():
            continue

        indice = int(trozo)
        if indice < len(INICIOS) and indice not in ya:
            ya.append(indice)

    return ya


def _elegir_inicio(ajustes):
    """The second to start at: a different song each time, all six before any repeats.

    It is one single recording, so another song means another second. Drawing at random
    every time would bring the same one back one opening in five, and going in order would
    make it predictable, so the round is drawn without replacement and, when it is over, the
    next one cannot open with the song that has just played. It is kept in a setting and not
    in a window property because the property dies with Kodi, and then the first opening of
    every session would land on the same song.

    'ajustes' is where the round is read and written: a fresh instance (see _ajustes), except
    in the script that paints the menu, whose own was read a moment ago. A fresh one there
    would add to the menu the time to read the settings file again, 10 ms on a phone
    (measured)."""
    ya = _sonadas(ajustes.getSetting('musica_ultima'))
    faltan = [i for i in range(len(INICIOS)) if i not in ya]

    if not faltan:
        # The 'or' is for a recording that ever had a single song: without it, a round with
        # nothing left to draw from would come down to random.choice([]).
        faltan = [i for i in range(len(INICIOS)) if i != ya[-1]] or list(range(len(INICIOS)))
        ya = list()

    elegido = random.choice(faltan)
    ajustes.setSetting('musica_ultima', ','.join(str(i) for i in ya + [elegido]))

    return INICIOS[elegido]


def _elemento(segundo):
    """The item handed to the player, asking to be opened already inside the chosen song.

    The start offset is what keeps the first notes of the recording from being heard before
    the jump: the player starts decoding there, before a single sample comes out. Seeking
    afterwards works too, but by then the top of the file has already been played for the
    fraction of a second it takes to ask."""
    # No art on purpose. With a thumbnail the skin paints it over the menu as the cover of
    # what is playing, and EKHorus's own round logo sitting in the middle of the screen
    # looks exactly like something loading. The label does stay: the skin writes the name of
    # what is playing in a corner either way, and "EspaKodi GTA Soundtrack" reads better
    # there than the id of the file.
    elemento = xbmcgui.ListItem(label=TITULO)
    # The address carries no extension. Without this Kodi can take it for a video and lay a
    # black full screen over the menu.
    elemento.setMimeType('audio/mpeg')
    elemento.setContentLookup(False)

    # A music tag, so that Kodi hands it to its music player. The video one opens every file
    # behind its busy spinner, and that was the spinner seen over the menu (the log said
    # CVideoPlayer). For the same reason the start is StartOffset, which the music player
    # honours, and not ResumeTime/TotalTime: those create a video tag on the item.
    poner_info_musica(elemento, TITULO)

    if segundo:
        elemento.setProperty('StartOffset', str(segundo))

    return elemento


def _posicion(player):
    """Where the player is, or None if it cannot say."""
    try:
        return player.getTime()
    except RuntimeError:
        return None


def _asegurar_inicio(player, monitor, segundo):
    """Leaves the recording inside the chosen song, jumping only if it did not open there.

    The start offset on the item does the job by itself, and then there is nothing to do
    here. What there is, is waiting before deciding: a player that has just opened answers
    getTime() with a flat zero for a few seconds even when the stream is already sitting on
    the right second, and a seek asked for in that gap is not honoured, keeps Kodi busy and
    holds the menu frozen for longer. So the position is only trusted once it starts
    counting. Jumping is the fallback for a Kodi that ignores the start offset."""
    if not segundo:
        return

    limite = time.time() + GRACIA_SALTO
    ahora = _posicion(player)

    while (ahora or 0) <= 0 and time.time() < limite:
        if monitor.waitForAbort(PASO_ARRANQUE):
            return
        ahora = _posicion(player)

    if ahora is None:
        return

    for _ in range(INTENTOS_SALTO):
        if abs(ahora - segundo) <= MARGEN_SALTO:
            return

        try:
            player.seekTime(segundo)
        except (RuntimeError, ValueError) as e:
            logger(f'musica: no se ha podido saltar al segundo {segundo}: {e}', 'error')
            return

        if monitor.waitForAbort(1):
            return

        ahora = _posicion(player)
        if ahora is None:
            return

    logger(f'musica: el salto al segundo {segundo} no ha cuajado', 'error')


def _vaciar_cola(url):
    """Leaves nothing of the recording in Kodi's queue.

    A file played this way can be left in it, and there it would go on being what Kodi says
    is playing: on Kodi 21 for Windows nothing is queued (measured), and this covers the
    versions and platforms where something is. It is only emptied when what is in it is
    ours, since the user may have their own music in there."""
    try:
        lista = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        if len(lista) == 1 and lista[0].getPath().split('|')[0] == url:
            lista.clear()
    except Exception as e:
        # Emptying the queue is tidying up, never a reason to leave an exception loose in a
        # script the user did not ask for.
        logger(f'musica: al vaciar la lista de reproduccion: {e}', 'error')


def _soltar(player, url):
    """Stops the recording, which frees the stream and its buffer, and empties the queue."""
    try:
        player.stop()
    except Exception as e:
        logger(f'musica: al parar la pista: {e}', 'error')

    _vaciar_cola(url)


def _avisar_la_primera_vez():
    """Says once, the first time the music comes in on this device, where it is switched off.

    A notification and not a dialog: it goes by on its own and holds nothing up. It is marked
    as said before it is shown, so that two invocations can never show it twice. Not once the
    user has left the addon: the music is about to stop, and the notice would land on another
    screen with nothing to explain. Then it waits for another time."""
    if not _en_los_menus(xbmc.getInfoLabel('Container.FolderPath')):
        return

    ajustes = _ajustes()
    if ajustes.getSetting('musica_avisada') == 'true':
        return

    ajustes.setSetting('musica_avisada', 'true')
    xbmcgui.Dialog().notification(TITULO, translate(30166), icon_path, 6000)


def _esperar_arranque(player, monitor, url, desde):
    """True once Kodi really has the stream open, False if it never got there.

    Giving up here hands the player back the way it was found. Without that, an opening that
    took longer than the wait went on playing with nobody watching it: no jump into a song,
    and nothing stopping it on the way out of the menus. Something else asked to play in the
    meantime (see callar) is given up on at once, and handed back the same way."""
    limite = time.time() + ESPERA_ARRANQUE

    while not _suena(player, url):
        if monitor.waitForAbort(PASO_ARRANQUE):
            return False

        callada = _hora(CALLADA) >= desde
        if callada or time.time() >= limite:
            if not callada:
                logger('musica: el reproductor no ha llegado a arrancar la pista', 'error')
            # With nothing playing, the stop still matters: an order to play that Kodi has not
            # got round to yet is ahead of it in the queue, and is stopped as soon as it is
            # carried out instead of playing later with nobody watching. Only then, though: by
            # now somebody else may have the player, and stopping it would cut off whatever
            # they put on.
            if not player.isPlaying():
                _soltar(player, url)
            return False

    return True


def _vigilar(player, monitor, url, desde):
    """Holds the recording while the menus are up and somebody is using them. When nobody has
    touched anything for INACTIVIDAD, or EKHorus puts another app in front (see apartar), it
    gives way until the next key or touch, which brings it back where it was.

    'desde' is when the menu asked for the music: whatever is asked to play after that (see
    callar) ends the watch, and the key that asked for it brings nothing back."""
    pedida = desde

    while True:
        segundo = _sostener(player, monitor, url, desde, pedida)
        if segundo is None:
            return

        url = _esperar_tecla(player, monitor, desde)
        if not url:
            return

        # The last renewal can be half a minute old, and the knock on the address plus the
        # opening below can take the rest of the latch's minute and more.
        refrescar_pestillo(PESTILLO)
        pedida = time.time()
        player.play(url, _elemento(segundo), True)
        if not _esperar_arranque(player, monitor, url, desde):
            return


def _sostener(player, monitor, url, desde, pedida):
    """Holds the recording while the menus are up and somebody is using them.

    Anybody else taking the player (a channel, another addon, the user pressing stop) ends
    the watch there and then, without touching what they have put on. The second it had got to
    if it gave way, None if the watch is over. 'pedida' is when this playing of it was asked
    for, and another app put in front since then is what makes it give way."""
    fuera = 0
    presencia = _Presencia()
    # What came before (the knock, the opening, the jump) can use up most of the latch's
    # minute, and the first renewal below would come too late.
    refrescar_pestillo(PESTILLO)
    refrescado = time.time()

    while True:
        if monitor.waitForAbort(PASO):
            # Kodi closing stops the player before it tells any script. Still playing, it is
            # this script alone being stopped (the StopScript builtin, say), and the music
            # would outlive its watch.
            if _suena(player, url):
                _soltar(player, url)
            return None

        if not _suena(player, url):
            # Ours running out on its own still leaves the file queued. If somebody else is
            # playing, that queue is theirs and is left alone. There is nothing to stop.
            if not player.isPlaying():
                _vaciar_cola(url)
            return None

        ruta = xbmc.getInfoLabel('Container.FolderPath')
        fuera = 0 if _en_los_menus(ruta) else fuera + 1
        apagada = not _activada()

        # callar() stops the music itself, unless the order to play it was still on its way.
        if fuera >= FUERA_SEGUIDAS or apagada or _hora(CALLADA) >= desde:
            _soltar(player, url)
            # Switched off while it played: the copy on the device goes with it, right away
            # and not on the next opening of a menu that may not come.
            if apagada:
                _esperar_descarga(monitor)
                limpiar()
            return None

        presencia.mirar(ruta)
        apartada = _hora(APARTADA) >= pedida
        if apartada or presencia.quieto() >= INACTIVIDAD:
            # Paused from the remote, it is stopped all the same, since paused audio still
            # keeps the screen from resting, but no key brings back what the user paused.
            pausada = not apartada and xbmc.getCondVisibility('Player.Paused')
            segundo = _posicion(player)
            _soltar(player, url)
            return None if pausada else int(segundo or 0)

        if time.time() - refrescado >= REFRESCO_PESTILLO:
            refrescado = time.time()
            refrescar_pestillo(PESTILLO)


def _esperar_tecla(player, monitor, desde):
    """With the music given way: waits for the next key or touch (see _Presencia), and gives
    the address to play from then; None if the wait is over instead.

    The latch stays taken all the while, so a painting of the menu in between does not start
    a second recording."""
    fuera = 0
    tecla = False
    refrescado = time.time()
    presencia = _Presencia()
    apartada = _hora(APARTADA)

    while True:
        if monitor.waitForAbort(PASO):
            return None

        # Somebody has the player, or has asked for it: callar() comes before the progress
        # dialog of a channel does.
        if player.isPlaying() or _hora(CALLADA) >= desde:
            return None

        ruta = xbmc.getInfoLabel('Container.FolderPath')
        fuera = 0 if _en_los_menus(ruta) else fuera + 1
        if fuera >= FUERA_SEGUIDAS:
            return None

        if not _activada():
            _esperar_descarga(monitor)
            limpiar()
            return None

        nueva = presencia.mirar(ruta)
        # Another app put in front while it waited: that key or touch was for the app, and the
        # one that brings the music back is the first after it.
        vez = _hora(APARTADA)
        if vez != apartada:
            apartada, tecla, nueva = vez, False, False

        # A key or a touch is acted on a turn after it is seen. If it chose a channel, the
        # invocation that plays it has had that second to say so (see callar), and the music
        # does not come in for a moment over the channel.
        if fuera == 0 and tecla and _hueco_libre(player):
            # The copy if it is there by now, which the first time it may have become.
            propia = _propia()
            guardada = None if propia else _guardada()
            if guardada:
                return guardada

            origen = _elegir_url(propia)
            if not origen:
                return None

            # Asked again, as when the music first comes in: the knock can take seconds, and
            # the turns that follow tell what happened in them.
            if _hueco_libre(player) and _hora(CALLADA) < desde:
                return origen

        tecla = tecla or nueva

        if time.time() - refrescado >= REFRESCO_PESTILLO:
            refrescado = time.time()
            refrescar_pestillo(PESTILLO)


def _poner_guardada():
    """Plays the copy on the device right now, from the script that is painting the menu.

    From here the music comes in with the menu itself. Asked for from the invocation below it
    would come a second or two later, the time Kodi takes to start a second interpreter and
    the wait that follows. play() only posts the order, so the menu does not wait for it
    (measured: 18 ms).

    Only the copy: the first time there is none, and checking the web from here would hold
    the menu for as long as the network takes. And only with the addon's own listing in
    front: Kodi also paints this menu for whoever merely lists it (a remote app, say), and
    then nobody in the addon would hear it. Coming in from a favourite or from the home screen
    the container already carries the addon's path (measured); coming in from a listing of
    Kodi's own it still carries that one, and the invocation below starts the music instead.
    True if it asked for the music."""
    guardada = None if _propia() else _guardada()
    if not guardada or not xbmc.getInfoLabel('Container.FolderPath').startswith(_RUTA_ADDON):
        return False

    player = xbmc.Player()
    if (player.isPlaying() or xbmc.getCondVisibility('Window.IsActive(progressdialog)')
            or not echar_pestillo(PESTILLO)):
        return False

    player.play(guardada, _elemento(_elegir_inicio(ADDON)), True)
    return True


def programar():
    """Asks for the music from the main menu, which has already checked it is switched on.

    With the copy on the device it starts playing here and now (see _poner_guardada). The
    rest, the waiting and the watching, goes out to an invocation of its own because it
    outlives the menu, and doing it here would hold the script that has to paint it. With the
    recording already playing there is a latch and nothing is asked for at all: starting a
    Python interpreter to do nothing is the kind of cost a menu should not pay twice. Nor
    with the home screen in front, which is a skin widget painting this menu: whoever opens
    the addon from there is already in Kodi's own listing window by the time this runs."""
    if hay_pestillo(PESTILLO) or xbmc.getCondVisibility('Window.IsActive(home)'):
        return

    # Taken before anything is played, so that the invocation below counts from here what is
    # asked to play in the meantime (see _vigilar).
    pedida = time.time()
    puesta = '&puesta=1' if _poner_guardada() else ''
    xbmc.executebuiltin(f'RunPlugin({_RUTA_ADDON}/?action=musica{puesta}&desde={pedida})')


def _seguir_la_copia(monitor, desde):
    """The watch of the copy the menu has already asked for (see _poner_guardada)."""
    player = xbmc.Player()
    origen = _ruta_local()

    if _esperar_arranque(player, monitor, origen, desde):
        _avisar_la_primera_vez()
        _vigilar(player, monitor, origen, desde)

    elif _sin_estorbo(player, monitor, desde):
        limpiar()


def _poner(monitor, desde):
    """Waits, plays from a different song each time, and watches until the menus are gone."""
    if monitor.waitForAbort(RETARDO):
        return

    player = xbmc.Player()

    # Music of ours playing with nobody watching over it, which is what Kodi leaves behind if
    # it ever kills a watch before it can stop the music. Having got the latch, whoever is here
    # is that watch now, and the recording carries on from where it was instead of being left
    # loose for the rest of the session.
    huerfana = _nuestra_sonando(player)
    if huerfana:
        _vigilar(player, monitor, huerfana, desde)
        return

    if not _hueco_libre(player):
        return

    # The copy on the device first: it opens at once and needs no network. Not with an
    # address of the user's own, though: the copy is the addon's soundtrack, and it would
    # play instead of theirs.
    propia = _propia()
    guardada = None if propia else _guardada()
    origen = guardada or _elegir_url(propia)

    # Asked again: the knock can take seconds, and in them the user may have left the addon
    # or asked for a channel.
    if not origen or not _hueco_libre(player) or _hora(CALLADA) >= desde:
        return

    # The songs are those of the addon's recording. One of the user's own starts at its top.
    inicio = 0 if propia else _elegir_inicio(_ajustes())
    # windowed: without it Kodi answers the first note by throwing its music visualisation
    # full screen over the menu the music is supposed to be behind.
    player.play(origen, _elemento(inicio), True)

    if not _esperar_arranque(player, monitor, origen, desde):
        if guardada and _sin_estorbo(player, monitor, desde):
            limpiar()
        return

    _asegurar_inicio(player, monitor, inicio)
    _avisar_la_primera_vez()

    # Only what the addon comes with is kept, and under a name of its own. An address typed
    # into the setting is the user's, and it goes on playing from the web.
    if not guardada and origen in URLS:
        _guardar_de_fondo(origen)

    _vigilar(player, monitor, origen, desde)


def reproducir(puesta=False, desde=None):
    """The invocation the menu asks for the music with (see programar).

    'puesta' means the menu has already asked for the copy on the device, and took the latch
    to do it: what is left here is to see it start and watch over it. 'desde' is when the
    menu asked; an order that does not say is taken as asked just now.

    Every step can end in nothing: whatever goes wrong, the worst of it is that no music
    plays."""
    # Whoever finds the latch taken is a second painting of the menu, with one of these
    # already waiting or playing. It is taken here and not in programar() so that two
    # invocations at once cannot both get through.
    if not puesta and (not _activada() or not echar_pestillo(PESTILLO)):
        return

    try:
        desde = float(desde)
    except (TypeError, ValueError):
        desde = time.time()

    monitor = xbmc.Monitor()
    try:
        if puesta:
            _seguir_la_copia(monitor, desde)
        else:
            _poner(monitor, desde)

    except Exception:
        # Whatever broke, the music is not left playing with nobody left to stop it.
        callar()
        raise

    finally:
        quitar_pestillo(PESTILLO)


def recoger():
    """Deletes the copy on the device if the settings dialog has just switched the music off.

    Switched off while it plays, the watch deletes it, and while it comes down, the download
    does. With neither running (the music already over, or stopped with the remote) nobody
    would, until the next painting of the main menu."""
    if _activada() or hay_pestillo(PESTILLO) or hay_pestillo(PESTILLO_DESCARGA):
        return

    limpiar()


def callar():
    """Stops the music if it is ours, for when something else has been asked to play, and
    leaves word of it for the watch (see _vigilar). The music may be waiting for a key, or its
    order to play still on its way, and either would bring it back over what was asked for."""
    xbmcgui.Window(10000).setProperty(CALLADA, str(time.time()))
    player = xbmc.Player()
    url = _nuestra_sonando(player)

    if url:
        _soltar(player, url)


def apartar():
    """For when EKHorus is about to put another app in front of Kodi (the engine, the browser,
    Android's installer or its settings), which goes on playing audio from behind it. The
    music gives way at once and comes back where it was with the first key or touch after
    that, as it does when nobody uses the menus for a while (see _vigilar)."""
    xbmcgui.Window(10000).setProperty(APARTADA, str(time.time()))
    player = xbmc.Player()

    # Paused and not stopped: the watch has yet to read where it was, and stops it itself.
    if _nuestra_sonando(player) and not xbmc.getCondVisibility('Player.Paused'):
        player.pause()


def sola():
    """For when EKHorus is about to change the screen with nobody touching it: a window that
    closes when its time is up, say. The music does not take that change for somebody at the
    screen (see _Presencia)."""
    xbmcgui.Window(10000).setProperty(SOLA, str(time.time()))
