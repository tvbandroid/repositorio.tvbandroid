# -*- coding: utf-8 -*-
# EKHorus - Control panel: the engine and the connection on a single screen.
#
# It writes to the same settings as the addon's Settings window (ace_engine, ip_addr,
# ace_port, aceserve_port, reproductor_externo, redirect_streamninja); it adds none of
# its own. All the engine logic comes from lib.utils, which is where it lives.
#
# The help texts come from GUIA_EKHORUS.md and are in Spanish here, like the plots in
# espakodi_installer.py. Only the menu label goes through strings.po.

import os
import re
import threading
import time

import xbmc
import xbmcaddon
import xbmcgui

from lib.utils import (ADDON_VERSION, ENGINE_ACESERVE, ENGINE_ACESTREAM, HEADING, Item,
                       active_engine, android_engine_launch, apartar_musica,
                       buscar_motor_en_otro_puerto, cerrar_motor_android, detect_engine,
                       echar_pestillo, engine_name, engine_port, es_host_local,
                       forget_engine, get_setting, icon_path, logger, olvidar_puerto_hallado,
                       quitar_pestillo, runtime_path, set_setting, system_platform, translate)
from lib.ui_common import (GRIS, ORO, ROJO, TINTA_ORO, TINTA_ROJA, TINTA_VERDE, VERDE,
                           Deslizador)
from acestream.server import Server, sanitize_host

ID_LISTA = 200
ID_CERRAR = 100
ID_ACE = 101
ID_SERVE = 102
ID_BARRA = 300
ID_TEXTO = 301

_PESTILLO = 'ekhorus.control_panel'

SONDEO_MS = 200
# Short on purpose: when the window is closed, Kodi waits for the script threads to
# finish before calling it done, and a hung request stretches that queue. This is far
# more than enough to ask an engine that answers for its version.
SONDA_TIMEOUT_S = 4
PING_TIMEOUT_S = 2

# After opening the engine app, Kodi goes to the background and the user takes as long
# as they take to come back. It is asked again every few seconds so that, on returning,
# the circle is already green instead of stuck on the "not answering" from before.
REINTENTO_S = 4
REINTENTOS_TRAS_ABRIR = 10

STREAMNINJA = 'plugin.video.streamninja'

_ATRAS = (9, 10, 92)  # ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, ACTION_NAV_BACK

ES_ANDROID = system_platform == 'android'


PLOT_MOTOR = (
    "Elige qué aplicación hace de motor en este aparato.\n\n"
    "[B]AceStream[/B] es la app oficial: hace de motor y además trae reproductor, así que "
    "puede reproducir ella misma el canal.\n\n"
    "[B]AceServe[/B] es ese mismo motor puesto a funcionar como servicio en segundo plano. "
    "No reproduce, pero no tiene publicidad, puede arrancar con el sistema y otros aparatos "
    "de la red pueden usarlo.\n\n"
    "Las dos quieren el mismo puerto. AceServe lo fija y no arranca si está ocupado; la app de "
    "Ace Stream, si lo encuentra ocupado, se pone en otro y EKHorus lo busca y lo guarda solo. "
    "Arriba a la derecha, el círculo verde señala cuál está contestando ahora mismo."
)

REQ_MOTOR = (
    "· Cambiar aquí no instala nada. Este ajuste tiene que coincidir con la app que de "
    "verdad tengas: si no coincide, EKHorus abre y cierra la app equivocada, y el "
    "indicador de arriba avisará de que contesta otro motor.\n"
    "· Las dos las tienes en [B]Descargar APKs[/B], en el menú principal."
)

PLOT_ACESTREAM = (
    "La aplicación oficial de Ace Stream para Android. Es motor y reproductor a la vez, así "
    "que puede reproducir ella misma el canal cuando EKHorus se lo pide.\n\n"
    "EKHorus la abre con una llamada del sistema y, al terminar, limpia su caché en "
    "[B]Android/data/org.acestream.node/files/.ACEStream/[/B], dentro de la memoria "
    "interna. En versiones antiguas de la app la carpeta tiene otro nombre, y EKHorus "
    "las prueba todas.\n\n"
    "El círculo se pone verde cuando es ella la que está contestando en la dirección de "
    "abajo. Pulsa aquí para volver a comprobarlo, o para abrirla si no responde."
)

REQ_ACESTREAM = (
    "· La app Ace Stream instalada en este mismo aparato. La tienes en [B]Descargar APKs[/B].\n"
    "· En Fire TV y Fire Stick no está en la tienda de Amazon: hay que instalar el APK "
    "aparte, por ejemplo con la app Downloader.\n"
    "· Dentro de la app, deja fijado el [B]jugador seleccionado[/B]. Si no lo haces, "
    "pregunta con qué reproducir cada vez que abres un canal."
)

PLOT_ACESERVE = (
    "El motor de Ace Stream llevado a Android como servicio en segundo plano. Es el mismo "
    "motor, no una versión recortada: se conecta a la red P2P, reensambla el vídeo y lo "
    "sirve por HTTP igual que el de Windows o el de Linux.\n\n"
    "Lo que cambia es la forma de usarlo. No tiene publicidad, puede arrancar con el "
    "sistema, trae su propia interfaz web y otros aparatos de la red pueden conectarse a "
    "él. Por eso hay quien lo prefiere en televisores Android. Lo que no trae es "
    "reproductor, así que el vídeo lo pinta otra aplicación, normalmente VLC.\n\n"
    "El círculo verde dice cuándo contesta él. Pulsa para comprobarlo o para abrirlo."
)

REQ_ACESERVE = (
    "· El APK de AceServe instalado y abierto una vez para que arranque el servicio. Si "
    "trae autoarranque, actívalo. Está en [B]Descargar APKs[/B].\n"
    "· VLC o MX Player, y el [B]reproductor externo[/B] activado.\n"
    "· AceServe fija el puerto 6878 y no arranca mientras otra app lo tenga ocupado."
)

PLOT_MOTOR_ESCRITORIO = (
    "Aquí no hay motor que elegir. En Windows y en Linux EKHorus descarga y usa el suyo, y "
    "si ya tienes uno corriendo en la dirección de abajo lo aprovecha sin lanzar nada.\n\n"
    "El círculo se pone verde cuando hay un motor contestando ahí. Pulsa para volver a "
    "comprobarlo.\n\n"
    "Elegir entre la app oficial y AceServe solo tiene sentido en Android, donde el motor "
    "es una aplicación aparte."
)

PLOT_EXTERNO = (
    "Decide dónde se ve el vídeo, dentro de Kodi o en otra aplicación del aparato.\n\n"
    "Con [B]AceServe[/B] tiene que estar activado, porque AceServe no reproduce. Dentro "
    "de Kodi la imagen arranca y se corta a los pocos segundos. Activado, EKHorus lanza "
    "la dirección del vídeo y Android te ofrece abrirla con VLC o con el reproductor que "
    "tengas.\n\n"
    "Con la [B]app oficial[/B] es opcional. Activado le pasa el enlace a Ace Stream y "
    "reproduce ella; desactivado reproduce Kodi, con panel de estadísticas. "
    "Viene activado de fábrica."
)

REQ_EXTERNO = (
    "· Solo en Android.\n"
    "· Un reproductor que acepte direcciones de red, normalmente VLC. Está en "
    "[B]Descargar APKs[/B].\n"
    "· Con la app oficial, fija dentro de ella el [B]jugador seleccionado[/B] para que no "
    "pregunte en cada canal.\n"
    "· Los canales y los identificadores salen al reproductor externo; un .torrent o un "
    "magnet pegado a mano se reproduce dentro de Kodi."
)

PLOT_IP = (
    "En qué dirección está escuchando el motor. Es lo único que EKHorus necesita saber de "
    "él: si ahí responde un motor, todo funciona; si no responde nadie, sale «Engine no "
    "iniciado».\n\n"
    "[B]127.0.0.1[/B] es lo normal, y quiere decir que el motor corre en este mismo "
    "aparato.\n\n"
    "Poner la IP de otra máquina (un PC, un NAS, un contenedor Docker, un móvil con "
    "AceServe) reparte el trabajo: el aparato donde ves la tele deja de hacer el esfuerzo "
    "P2P y recibe un vídeo ya convertido. Un solo motor puede servir a varios Kodi a la vez."
)

REQ_IP = (
    "· Si el motor está en otra máquina, esa máquina tiene que dejar pasar el puerto en su "
    "cortafuegos, y conviene darle una IP fija o una reserva en el router.\n"
    "· No abras el puerto del motor hacia internet. Su API no tiene contraseña, así que "
    "cualquiera podría usar tu conexión para descargar y compartir en tu nombre."
)

PLOT_PUERTO = (
    "El puerto donde escucha el motor. [B]6878[/B] en todos los motores conocidos: la app "
    "oficial, AceServe, el snap de Ubuntu, los contenedores Docker y el motor que instala "
    "el propio EKHorus.\n\n"
    "Con una excepción: si la app de Ace Stream encuentra el 6878 ocupado (por AceServe, por "
    "ejemplo) se pone en otro puerto y ahí se queda. EKHorus lo busca solo cuando aquí no "
    "contesta nadie, lo guarda y lo enseña en esta fila.\n\n"
    "Solo hay que tocarlo si lo has cambiado a mano en el motor o si lo estás publicando "
    "por otro puerto. Lo que escribas aquí manda sobre lo encontrado."
)

REQ_PUERTO_ACESERVE = (
    "· Estás cambiando el puerto de AceServe, que se guarda aparte del de AceStream. "
    "AceServe fija el 6878 y no deja moverlo sin root, así que esto solo hace falta si has "
    "editado su acestream.conf."
)

PLOT_PROBAR = (
    "Pregunta al motor su versión y enseña el resultado en tres sitios a la vez: en esta "
    "misma fila, en los indicadores de arriba y en la barra de abajo.\n\n"
    "Es la forma rápida de saber si la dirección y el puerto son correctos antes de ponerte "
    "a buscar canales.\n\n"
    "También dice qué motor está contestando de verdad, que no siempre es el que has "
    "elegido: en Android, AceServe puede haber arrancado solo con el sistema y haberse "
    "quedado con el puerto."
)

PLOT_NINJA = (
    "Cuando otro addon le pide a EKHorus que reproduzca un enlace, con esto activado el "
    "enlace se le pasa a StreamNinja en vez de abrirlo aquí.\n\n"
    "Es útil si prefieres el reproductor de StreamNinja para los enlaces que llegan de "
    "fuera. No afecta a lo que reproduces desde el propio menú de EKHorus.\n\n"
    "Lleva protección contra bucles: si StreamNinja devuelve el enlace a EKHorus, se "
    "reproduce aquí en vez de rebotar sin fin."
)

PLOT_APAGAR = (
    "Android no deja que una aplicación cierre a otra: ese permiso solo lo tienen las apps "
    "de fábrica. Y al motor tampoco se le puede pedir, porque su API no trae ninguna orden "
    "para apagarse.\n\n"
    "Lo que sí se puede es llevarte de un salto a la ficha de la app, donde "
    "[B]Forzar detención[/B] está a un toque.\n\n"
    "Hace falta sobre todo con [B]AceServe[/B], que arranca con el sistema y se queda de "
    "servicio aunque cierres Kodi. Al volver aquí, el círculo de arriba se pone rojo solo."
)

REQ_APAGAR = (
    "· Que haya un motor contestando, o sea uno de los círculos de arriba en verde. Si no "
    "contesta nadie no hay nada que cerrar, y se dice.\n"
    "· Con AceServe se abre su ficha directamente. Con la app de Ace Stream no, porque su "
    "nombre de paquete cambia de una versión a otra: se abre la app y se sale desde dentro.\n"
    "· Forzarla no la desinstala. Vuelve a arrancar cuando algo la necesite, o al encender "
    "el aparato si tiene el arranque automático puesto."
)

PLOT_APAGAR_ESCRITORIO = (
    "Detiene el motor AceStream de este equipo.\n\n"
    "En Windows cierra todo proceso ace_engine.exe, lo haya arrancado EKHorus o la "
    "aplicación de AceStream; en Linux llama al script de parada de la instalación que "
    "tengas. Un motor en otra máquina se para allí.\n\n"
    "Es lo mismo que hace [B]Detener motor[/B] en el menú principal, que solo aparece "
    "cuando hay un motor contestando en este equipo."
)

PLOT_CERRAR = (
    "Cierra el cuadro de mandos y vuelve al menú de EKHorus.\n\n"
    "También se sale con el botón Atrás del mando o con el gesto de volver del móvil. Todo "
    "lo que cambies aquí queda guardado en el momento; no hay nada que confirmar."
)


# (title, icon, hint, plot, requirements)
PLOT_ASISTENTE = (
    "Repite el asistente de la primera vez.\n\n"
    "Pregunta dónde está el motor, lo busca por la red si está en otro aparato, y deja "
    "puestos la dirección y el puerto. Es la vía rápida cuando has cambiado de aparato o "
    "cuando algo se ha quedado mal configurado y no sabes qué.\n\n"
    "No borra nada: solo sobrescribe lo que tú elijas en cada paso."
)

FILAS = {
    'motor': ('Motor', 'acestreamlogo.png', 'Qué aplicación hace de motor',
              PLOT_MOTOR, REQ_MOTOR),
    'externo': ('Reproductor externo', 'play_generic.png', 'Dónde se ve el vídeo',
                PLOT_EXTERNO, REQ_EXTERNO),
    'ip': ('Dirección del motor', 'directo.png', 'En qué aparato está escuchando',
           PLOT_IP, REQ_IP),
    'puerto': ('Puerto', 'adv_ytdlp.png', 'Casi siempre el 6878', PLOT_PUERTO, ''),
    'probar': ('Comprobar el motor', 'busqueda.png', 'Pregunta su versión ahora mismo',
               PLOT_PROBAR, ''),
    'apagar': ('Cerrar el motor', 'detener.png', 'Atajo a la ficha de la app',
               PLOT_APAGAR, REQ_APAGAR),
    'ninja': ('Probar suerte en StreamNinja', 'srch_torrent.png',
              'EKHorus le pasa lo de otros addons', PLOT_NINJA, ''),
    'asistente': ('Volver a configurarlo', 'ajustes.png', 'Te guía paso a paso',
                  PLOT_ASISTENTE, ''),
}

# On desktop there is no engine to choose and no external player, so those two rows are
# not painted: a dead button takes up as much as a live one and lets you down as well.
ORDEN_ANDROID = ('motor', 'externo', 'ip', 'puerto', 'probar', 'apagar', 'ninja',
                 'asistente')
ORDEN_ESCRITORIO = ('ip', 'puerto', 'probar', 'apagar', 'ninja', 'asistente')


def _media(nombre):
    return os.path.join(runtime_path, 'resources', 'media', nombre)


def _puerto():
    """Port of the active engine, already sanitised."""
    try:
        valor = int(str(engine_port()))
    except (TypeError, ValueError):
        return 6878

    return valor if 0 < valor < 65536 else 6878


def _ajuste_puerto():
    """Which setting the port goes to: each engine keeps its own since 1.6.0."""
    return 'aceserve_port' if active_engine() == ENGINE_ACESERVE else 'ace_port'


def _host():
    return sanitize_host(get_setting('ip_addr', '127.0.0.1'))


def _addon_instalado(addon_id):
    # Installed and switched on: a switched-off StreamNinja would take the links and play
    # nothing, and HasAddon answers yes for it all the same
    return bool(xbmc.getCondVisibility(f'System.AddonIsEnabled({addon_id})'))


def _color(texto, color):
    return f'[COLOR {color}]{texto}[/COLOR]'


class Mandos(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._claves = list()
        self._cerrando = False
        self._pintado = None      # (control with the focus, row) shown in the right panel
        self._sonda = 0           # probe generation, to discard old answers
        self._sondeando = False
        self._contesta = None     # engine that answered in the last probe
        self._red = None          # the engine reaches the internet (None = not known)
        self._listo = None        # the engine has finished starting up
        self._reintentos = 0      # probes pending after sending the user out of Kodi
        self._proximo = 0.0
        self._espera = None       # 'arranque' or 'parada': what is being waited for
        self._dedo = None
        self._repintar = False    # the probe thread changed a row and cannot paint it itself
        # Set on closing: Kodi waits for the script threads when the window goes, and a sweep
        # of the ports halfway through would keep it waiting.
        self._cancelar = threading.Event()
        # The generation number is touched by the main thread (on press) and by the focus one
        # (when retrying after opening an engine), and += is not atomic.
        self._candado = threading.Lock()

    # --- life cycle --------------------------------------------------------------------

    def onInit(self):
        # Kodi may call here more than once (when reloading the skin); without this guard
        # the rows would be duplicated and a second probe thread would start.
        if self._claves:
            return

        self._claves = list(ORDEN_ANDROID if ES_ANDROID else ORDEN_ESCRITORIO)
        self._dedo = Deslizador(self, ID_BARRA, ID_TEXTO)
        self.setProperty('cm_version', f'v{ADDON_VERSION}')
        # The order matters: rows first, then the focus (the XML starts on the X) and only
        # then the panel, which paints nothing while the focus is not set.
        self._pintar_filas(0, enfocar=True)
        self._refrescar_panel(forzar=True)
        self._sondear()

        threading.Thread(target=self._bucle_foco, daemon=True).start()

    def close(self):
        self._cerrando = True
        self._cancelar.set()
        super().close()

    # --- painting ----------------------------------------------------------------------

    def _titulo(self, clave):
        # Only on Android are there two engines, each keeping its own port. Saying which one
        # is being touched stops anyone changing AceServe's port thinking it is AceStream's
        if clave == 'puerto' and ES_ANDROID:
            return f'Puerto de {engine_name(active_engine())}'

        return FILAS[clave][0]

    @staticmethod
    def _pista(clave):
        # On desktop the engine really can be stopped; on Android the user can only be taken
        # to where the system button is.
        if clave == 'apagar' and not ES_ANDROID:
            return 'Detenerlo ahora mismo'

        return FILAS[clave][2]

    def _decorar(self, item, clave):
        """Puts in the ListItem what the XML needs to paint the right-hand part of the
        row: a loose value, a two-state switch or the engine selector."""
        if clave == 'motor':
            elegido = active_engine()
            ace = elegido == ENGINE_ACESTREAM
            item.setProperty('f_motor', 'ace' if ace else 'serve')
            item.setProperty('f_ace', _color('AceStream', TINTA_ORO if ace else GRIS))
            item.setProperty('f_serve', _color('AceServe', GRIS if ace else TINTA_ORO))
            return

        if clave == 'externo':
            self._interruptor(item, bool(get_setting('reproductor_externo')))
            return

        if clave == 'ninja':
            if not _addon_instalado(STREAMNINJA):
                item.setProperty('f_estado', 'gris')
                item.setProperty('f_pastilla', _color('No instalado', GRIS))
                return
            self._interruptor(item, bool(get_setting('redirect_streamninja')))
            return

        if clave == 'ip':
            item.setLabel2(_host())

        elif clave == 'puerto':
            item.setLabel2(str(_puerto()))

        elif clave == 'probar':
            # The result is written by the probe thread, which can only touch window
            # properties; the row merely says that this text goes here.
            item.setProperty('f_resultado', '1')

    @staticmethod
    def _interruptor(item, encendido):
        item.setProperty('f_estado', 'on' if encendido else 'off')
        item.setProperty('f_pastilla', _color('ACTIVADO', TINTA_VERDE) if encendido
                         else _color('DESACTIVADO', TINTA_ROJA))

    def _pintar_filas(self, seleccion=None, enfocar=False):
        """Rebuilds the whole list. Mutating a ListItem that is already inside a container
        does not repaint reliably, and with six rows rebuilding them comes for free.

        enfocar leaves the focus on the list: needed when opening (the XML starts on the X)
        and when coming back from a keyboard or a yes/no, where the dialog that has just
        closed holds it."""
        control = self.getControl(ID_LISTA)
        if seleccion is None:
            seleccion = control.getSelectedPosition()

        items = list()
        for clave in self._claves:
            item = xbmcgui.ListItem(label=self._titulo(clave))
            item.setProperty('f_icono', _media(FILAS[clave][1]))
            item.setProperty('f_pista', self._pista(clave))
            self._decorar(item, clave)
            items.append(item)

        control.reset()
        control.addItems(items)

        if 0 <= seleccion < len(items):
            control.selectItem(seleccion)

        if enfocar:
            self.setFocusId(ID_LISTA)

    def _texto_panel(self):
        """(title, plot, requirements) of whatever holds the focus, or None if nothing is new."""
        foco = self.getFocusId()

        if foco == ID_CERRAR:
            return 'Cerrar', PLOT_CERRAR, ''

        if foco == ID_ACE:
            if not ES_ANDROID:
                return 'Motor de EKHorus', PLOT_MOTOR_ESCRITORIO, ''
            return 'AceStream (app oficial)', PLOT_ACESTREAM, REQ_ACESTREAM

        if foco == ID_SERVE:
            return 'AceServe', PLOT_ACESERVE, REQ_ACESERVE

        if foco != ID_LISTA or not self._claves:
            return None

        # The thread may read just while the main thread rebuilds the list, so the position
        # is checked against the keys before indexing.
        pos = self.getControl(ID_LISTA).getSelectedPosition()
        if not 0 <= pos < len(self._claves):
            return None

        clave = self._claves[pos]
        titulo, _, _, plot, req = FILAS[clave]

        if clave == 'puerto':
            titulo = self._titulo(clave)
            if active_engine() == ENGINE_ACESERVE:
                req = REQ_PUERTO_ACESERVE

        elif clave == 'apagar' and not ES_ANDROID:
            plot, req = PLOT_APAGAR_ESCRITORIO, ''

        return titulo, plot, req

    def _refrescar_panel(self, forzar=False):
        foco = self.getFocusId()
        pos = -1
        if foco == ID_LISTA and self._claves:
            pos = self.getControl(ID_LISTA).getSelectedPosition()

        if (foco, pos) == self._pintado and not forzar:
            return

        textos = self._texto_panel()
        if textos is None:
            return

        titulo, plot, req = textos
        if req:
            plot = f"{plot}\n\n{_color('[B]QUÉ HACE FALTA[/B]', ORO)}\n{req}"

        self._pintado = (foco, pos)
        self.setProperty('cm_titulo', titulo)
        self.setProperty('cm_plot', plot)

    def _bucle_foco(self):
        """The right panel follows the focus. It is polled instead of read in onAction
        because there getSelectedPosition() may not reflect the move just made yet."""
        monitor = xbmc.Monitor()

        while not self._cerrando and not monitor.abortRequested():
            try:
                self._refrescar_panel()
                self._reintentar_sonda()
            except Exception as e:
                # The window may have been closed between the read and the painting
                logger(f'control_panel: bucle de foco: {e}')
            if monitor.waitForAbort(SONDEO_MS / 1000):
                break

    def _reintentar_sonda(self):
        """Asks again while the user is away from Kodi opening or closing the engine.
        Without this, on coming back the circle would still be stuck on the old state."""
        if not self._reintentos or time.time() < self._proximo:
            return

        self._reintentos -= 1
        self._proximo = time.time() + REINTENTO_S
        agotado, espera = not self._reintentos, self._espera
        self._sondear()

        # The wait is over and it still does not answer. Most likely the app was not
        # installed, because the intent fails without saying a word. Closing the engine
        # raises no warning here; that one comes from whoever closes it.
        if agotado and espera == 'arranque':
            xbmcgui.Dialog().notification(HEADING, translate(30091), icon_path, 6000)

    def _esperar(self, que):
        """Probes a few more times, until the engine is seen started or stopped."""
        self._espera = que
        self._reintentos = REINTENTOS_TRAS_ABRIR
        self._proximo = time.time() + REINTENTO_S

    # --- engine state ------------------------------------------------------------------

    def _sondear(self):
        with self._candado:
            self._sonda += 1
            generacion = self._sonda

        self._sondeando = True
        self.setProperty('cm_estado', _color('Comprobando el motor…', GRIS))
        self.setProperty('cm_resultado', _color('Comprobando…', GRIS))
        self._pintar_indicadores(sondeando=True)
        threading.Thread(target=self._hilo_sonda, args=(generacion,), daemon=True).start()

    @staticmethod
    def _preguntar(host, puerto):
        """(version, engine answering, reaches the internet, finished starting) of that
        address; Nones for whatever could not be known."""
        version = contesta = red = listo = None

        try:
            servidor = Server(host=host, port=puerto, timeout=SONDA_TIMEOUT_S)
            # ping() before version: a 2s TCP probe instead of waiting for the HTTP
            # request to time out against a machine that is switched off.
            if servidor.ping(timeout=PING_TIMEOUT_S):
                version = servidor.version
                # Who answers is asked, not guessed. The version numbers of the two
                # engines overlap (AceStream 3.2.22 against AceServe 3.2.14), and the
                # indicator had been lying ever since. detect_engine() caches the verdict
                # per Kodi session, so it is not one request per probe.
                if version:
                    contesta = detect_engine(servidor)
                    # These tell "no engine" apart from "there is an engine but it does
                    # not reach the network" and from "there is an engine and it is still
                    # starting", which is just what the guide's diagnosis section says to
                    # check by hand with the browser.
                    red = (servidor.getnetwork().data or dict()).get('connected')
                    listo = (servidor.getstatus().data or dict()).get('playlist_loaded')
        except Exception as e:
            logger(f'control_panel: sonda: {e}', 'error')

        return version, contesta, red, listo

    def _hilo_sonda(self, generacion):
        host, puerto = _host(), _puerto()
        version, contesta, red, listo = self._preguntar(host, puerto)

        # Nobody on the configured port: the official app may have moved to another one (see
        # buscar_motor_en_otro_puerto). Found, it is asked there, and the port row has to be
        # painted again, which only the main thread does. The sweep takes some twenty seconds
        # on a TV box, so meanwhile the bar says what is going on instead of "checking".
        if not version and not self._cancelar.is_set():
            if generacion == self._sonda and not self._cerrando:
                self.setProperty('cm_estado', _color(
                    f'En {host}:{puerto} no responde nadie. Buscando el motor en otros '
                    f'puertos de este aparato…', GRIS))
                self.setProperty('cm_resultado', _color('Buscando…', GRIS))
            hallado = buscar_motor_en_otro_puerto(self._cancelar)
            if hallado:
                puerto = hallado
                version, contesta, red, listo = self._preguntar(host, puerto)
                self._repintar = True

        # Three presses of «Comprobar el motor» are three threads; only the last one writes.
        # It goes after ALL the network work on purpose: lengthening the work without
        # moving the guard is correct, moving it is not.
        if generacion != self._sonda or self._cerrando:
            return

        self._contesta = contesta
        self._red = red
        self._listo = listo

        # What was being waited for has been seen, so there is nothing left to ask
        if self._espera == ('arranque' if version else 'parada'):
            self._reintentos = 0
            self._espera = None

        self._sondeando = False

        try:
            self.setProperty('cm_estado', self._texto_estado(host, puerto, version))
            self.setProperty('cm_resultado', self._texto_resultado(version))
            self._pintar_indicadores()
        except Exception as e:
            logger(f'control_panel: sonda tardia: {e}')

    def _pintar_indicadores(self, sondeando=False):
        """Circle: who is answering now. Name in gold: which one is chosen."""
        elegido = active_engine()

        def punto(motor):
            if sondeando:
                return _color('●', GRIS)
            return _color('●', VERDE if self._contesta == motor else ROJO)

        if not ES_ANDROID:
            self.setProperty('cm_ace', f'{punto(ENGINE_ACESTREAM)}  Motor')
            self.setProperty('cm_serve', '')
            return

        nombre_ace = _color('AceStream', ORO if elegido == ENGINE_ACESTREAM else GRIS)
        nombre_serve = _color('AceServe', ORO if elegido == ENGINE_ACESERVE else GRIS)
        self.setProperty('cm_ace', f'{punto(ENGINE_ACESTREAM)}  {nombre_ace}')
        self.setProperty('cm_serve', f'{punto(ENGINE_ACESERVE)}  {nombre_serve}')

    def _texto_resultado(self, version):
        if not version:
            return _color('No responde', ROJO)

        if self._red is False:
            return _color('Sin internet', ROJO)

        if self._listo is False:
            return _color('Arrancando…', ORO)

        return _color(f'{engine_name(self._contesta)}  v{version}', VERDE)

    def _texto_estado(self, host, puerto, version):
        destino = f'http://{host}:{puerto}'

        if not version:
            aviso = _color('No responde. Arranca el motor o revisa la dirección', ROJO)
            return f'{destino}   {aviso}'

        # The engine answers but does not reach the network: no channel is going to start,
        # and without this warning the user blames the link and tries dead one after dead
        # one.
        if self._red is False:
            aviso = _color('El motor responde pero no tiene internet', ROJO)
            return f'{destino}   {aviso}'

        if self._listo is False:
            aviso = _color('El motor aún está arrancando, espera unos segundos', ORO)
            return f'{destino}   {aviso}'

        detalle = f'Responde {engine_name(self._contesta)} (v{version})'

        if ES_ANDROID and self._contesta != active_engine():
            elegido = engine_name(active_engine())
            aviso = _color(f'{detalle}, pero tienes elegido {elegido}', ORO)
            return f'{destino}   {aviso}'

        return f'{destino}   {_color(detalle, VERDE)}'

    # --- actions -----------------------------------------------------------------------

    def _repintar_si_hace_falta(self):
        """The probe thread found the engine on another port. It may only touch properties, so
        the rows wait for the next key or click to be painted again by this thread."""
        if self._repintar:
            self._repintar = False
            self._pintar_filas()

    def onAction(self, action):
        self._repintar_si_hace_falta()

        # Swiping over the explanation turns its pages. The list keeps its own gestures, so
        # only what happens outside it arrives here.
        if self._dedo is not None and self._dedo.accion(action):
            return

        # A Python WindowXMLDialog does not close by itself with Back.
        if action.getId() in _ATRAS:
            self.close()

    def onClick(self, controlId):
        self._repintar_si_hace_falta()

        if controlId == ID_CERRAR:
            self.close()
            return

        if controlId in (ID_ACE, ID_SERVE):
            self._pulsar_indicador(ENGINE_ACESERVE if controlId == ID_SERVE
                                   else ENGINE_ACESTREAM)
            return

        if controlId != ID_LISTA:
            return

        pos = self.getControl(ID_LISTA).getSelectedPosition()
        if 0 <= pos < len(self._claves):
            self._pulsar(self._claves[pos], pos)

    def _pulsar_indicador(self, motor):
        """Probes again and, if that engine is not the one answering, offers to open its app.

        While a probe is running nothing is offered: it is not yet known who answers, and
        offering to open an engine that may well be alive is confusing. Nor with the engine
        on another device, where opening an app of this one changes nothing."""
        if (ES_ANDROID and not self._sondeando and self._contesta != motor
                and es_host_local(_host())):
            nombre = engine_name(motor)
            if self._contesta is None:
                cuerpo = (f'En {_host()}:{_puerto()} no responde nadie.\n\n'
                          f'¿Abro {nombre} para que arranque?')
            elif motor == ENGINE_ACESERVE:
                cuerpo = (f'Ahí está contestando {engine_name(self._contesta)}.\n\n'
                          f'AceServe fija ese puerto y no arrancará hasta que cierres el otro '
                          f'motor. ¿Lo abro de todas formas?')
            else:
                cuerpo = (f'Ahí está contestando {engine_name(self._contesta)}.\n\n'
                          f'Ace Stream se pondrá en otro puerto y EKHorus lo buscará. '
                          f'¿La abro?')

            if xbmcgui.Dialog().yesno(HEADING, cuerpo, nolabel='Ahora no',
                                      yeslabel=f'Abrir {nombre}'):
                xbmcgui.Dialog().notification(HEADING, f'Abriendo {nombre}…', icon_path, 4000)
                apartar_musica()
                xbmc.executebuiltin(android_engine_launch(motor))
                # Kodi goes to the background, so it keeps asking on its own and on
                # returning the circle tells the truth without pressing anything
                self._esperar('arranque')
                return

        self._sondear()

    def _pulsar(self, clave, pos):
        if clave == 'motor':
            self._elegir_motor(ENGINE_ACESERVE if active_engine() == ENGINE_ACESTREAM
                               else ENGINE_ACESTREAM)

        elif clave == 'externo':
            self._conmutar_externo()

        elif clave == 'ip':
            self._cambiar_ip()

        elif clave == 'puerto':
            self._cambiar_puerto()

        elif clave == 'probar':
            self._sondear()
            # A tap moves the selection and presses at the same time, so the panel thread
            # may not have seen the new row yet
            self._refrescar_panel(forzar=True)
            return  # no value changes: rebuilding the list would only give a flicker

        elif clave == 'apagar':
            self._apagar_motor()

        elif clave == 'ninja':
            self._conmutar_ninja()

        elif clave == 'asistente':
            self._asistente()

        # The focus is set here on purpose: on returning from the keyboard or the
        # yes/no it belongs to the dialog just closed, and has to go back to its row.
        self._pintar_filas(pos, enfocar=True)
        self._refrescar_panel(forzar=True)

    def _elegir_motor(self, motor):
        set_setting('ace_engine', motor)
        # The cached verdict was for the previous engine and no longer holds
        forget_engine()
        externo = bool(get_setting('reproductor_externo'))

        if motor == ENGINE_ACESERVE and not externo:
            if xbmcgui.Dialog().yesno(
                    HEADING,
                    'AceServe no trae reproductor, y dentro de Kodi la imagen arranca y se '
                    'corta a los pocos segundos.\n\n'
                    '¿Activo el reproductor externo para que los canales se abran en VLC?',
                    nolabel='Ahora no', yeslabel='Activarlo'):
                set_setting('reproductor_externo', True)

        elif motor == ENGINE_ACESTREAM and externo:
            if xbmcgui.Dialog().yesno(
                    HEADING,
                    'Tienes activado el reproductor externo, así que los canales se abrirán '
                    'en la app de Ace Stream y no dentro de Kodi.\n\n'
                    '¿Lo desactivo y reproduzco en Kodi?',
                    nolabel='Dejarlo así', yeslabel='Desactivarlo'):
                set_setting('reproductor_externo', False)

        self._sondear()

    def _conmutar_externo(self):
        encendido = bool(get_setting('reproductor_externo'))

        if encendido and active_engine() == ENGINE_ACESERVE and not xbmcgui.Dialog().yesno(
                HEADING,
                'Con AceServe la reproducción dentro de Kodi arranca y se corta a los pocos '
                'segundos, porque AceServe no trae reproductor.\n\n'
                '¿Lo desactivo igualmente?',
                nolabel='Dejarlo activado', yeslabel='Desactivarlo'):
            return

        set_setting('reproductor_externo', not encendido)

    def _cambiar_ip(self):
        escrito = xbmcgui.Dialog().input('Dirección del motor (IP o nombre de host)', _host())
        if not escrito:
            return  # cancelling and wiping it all return the same thing, so nothing is touched

        # sanitize_host drops the scheme, the port and the path, and when nothing is left it
        # returns 127.0.0.1, so a blank address is never stored. What can be left is a name
        # that does not exist; the bar at the bottom warns about that.
        set_setting('ip_addr', sanitize_host(escrito))

        # If it came with the port stuck on (192.168.1.50:6878), sanitize_host drops it.
        # Before losing it silently, applying it is offered. The lookbehind demands a host
        # before the colon: without it, a "::1" was read as port 1.
        pegado = re.search(r'(?<=[\w.\-]):(\d{1,5})(?:/|$)', escrito.strip())
        if pegado:
            puerto = int(pegado.group(1))
            if 0 < puerto < 65536 and puerto != _puerto():
                if xbmcgui.Dialog().yesno(
                        HEADING,
                        f'Has escrito también el puerto {puerto}.\n\n¿Lo aplico?',
                        nolabel='No', yeslabel='Sí'):
                    set_setting(_ajuste_puerto(), puerto)

        forget_engine()
        self._sondear()

    def _cambiar_puerto(self):
        escrito = xbmcgui.Dialog().input('Puerto del motor', str(_puerto()),
                                         type=xbmcgui.INPUT_NUMERIC)
        if not escrito:
            return

        try:
            puerto = int(escrito)
        except ValueError:
            puerto = 0

        if not 0 < puerto < 65536:
            xbmcgui.Dialog().ok(HEADING, 'El puerto tiene que estar entre 1 y 65535.')
            return

        # Accepting without changing anything must not write. It matters with AceServe: its
        # empty setting means «the same as AceStream», and saving it would untie it for good.
        if puerto == _puerto():
            return

        # A port typed by hand is the user's word: the one the app was found on no longer
        # applies. engine_port() would drop it anyway, as its base changes; this keeps the
        # settings clean.
        if active_engine() == ENGINE_ACESTREAM:
            olvidar_puerto_hallado()

        set_setting(_ajuste_puerto(), puerto)
        forget_engine()
        self._sondear()

    def _apagar_motor(self):
        # With nobody answering there is nothing to close. On Android it matters twice over:
        # the shortcut to the page of an app that is not installed opens nothing, because the
        # intent fails silently, so without this a screen that never shows would be promised.
        if self._contesta is None:
            xbmcgui.Dialog().ok(
                HEADING,
                f'En {_host()}:{_puerto()} no contesta ningún motor.\n\n'
                f'No hay nada que cerrar.')
            return

        # An engine on another machine is not closed from here: neither the process nor the
        # page of any app of this device reaches over there.
        if not es_host_local(_host()):
            xbmcgui.Dialog().ok(
                HEADING,
                f'El motor está en {_host()}, en otra máquina.\n\n'
                f'Hay que pararlo allí.')
            return

        if not ES_ANDROID:
            # The action lives in default.py and is called through the plugin itself, the
            # same way the addon already calls itself to empty the history. That way
            # kill_process() need not move, nor default.py be imported from here.
            xbmc.executebuiltin(
                f'RunPlugin(plugin://script.module.horus/?{Item(action="kill").tourl()})')
            self._esperar('parada')
            return

        # The same road the menu's "Cerrar motor" takes, so both say and do the same.
        if cerrar_motor_android(self._contesta):
            self._esperar('parada')

    def _asistente(self):
        """Runs the wizard again and probes once more with whatever it left in place."""
        from lib import setup_wizard

        setup_wizard.mostrar(forzado=True)

        # The settings may have changed, so the previous verdict is no longer good.
        forget_engine()
        self._sondear()

    def _conmutar_ninja(self):
        if not _addon_instalado(STREAMNINJA):
            from lib import espakodi_installer
            if not espakodi_installer.instalar_si_falta(STREAMNINJA):
                return
            # The redirection stays off: installing StreamNinja is not the same as asking for
            # the links from other addons to stop playing here.
            xbmcgui.Dialog().notification(
                HEADING, 'Instalado. La redirección sigue apagada; enciéndela en esta fila',
                icon_path, 6000)
            return

        set_setting('redirect_streamninja', not get_setting('redirect_streamninja'))


def mostrar():
    """Opens the control panel."""
    if not echar_pestillo(_PESTILLO):
        logger('control_panel: ya hay una ventana abierta, no se abre otra')
        return

    ventana = None
    fallo = False

    try:
        # Inside the try: if it blew up while being built, the latch cannot stay closed
        ventana = Mandos('ekhorus_mandos.xml', runtime_path, 'Default', '1080i')
        ventana.doModal()

    except Exception as e:
        logger(f'control_panel: {e}', 'error')
        fallo = True

    finally:
        quitar_pestillo(_PESTILLO)
        if ventana is not None:
            # In case it closed by a route that did not go through close(): let the threads out
            ventana._cerrando = True
        # doModal does not free the controls, and in Kodi those are textures in memory
        del ventana

    # If the window could not open, the same settings are touched in Kodi's usual dialog;
    # being left unable to change anything would be worse than seeing it ugly.
    if fallo:
        xbmcgui.Dialog().notification(HEADING, translate(30106), icon_path, 6000)
        xbmcaddon.Addon().openSettings()
        from lib import playback_watch
        playback_watch.arrancar_si_falta()
