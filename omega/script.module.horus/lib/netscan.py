# -*- coding: utf-8 -*-
"""Find AceStream engines on the local network.

The scenario in the guide where the engine lives on another device requires the user to
know its IP address. This looks it up for them: it opens the port on the 254 addresses of
the subnet and asks the version of whichever ones answer.

The cheap filter is a TCP connection with a short timeout. Asking over HTTP on 254
addresses would take minutes; opening a socket to each one and keeping only those that
respond costs a couple of seconds.
"""
import socket
import threading
import time

import xbmc

from lib.utils import (ENGINE_ACESERVE, ENGINE_ACESTREAM, HOSTS_LOCALES, engine_name,
                       logger)
from acestream.server import Server

PUERTO_POR_OMISION = 6878
# 32 at a time over 254 addresses is eight rounds. More threads do not speed it up: what
# rules is the timeout, and a TV box with 254 sockets open at once does no better.
OBREROS = 32
# A device on the local network answers in milliseconds. This margin is for lossy wifi.
TIMEOUT_PUERTO = 0.4
TIMEOUT_VERSION = 3
TIMEOUT_MOTOR = 2

PESTILLO = 'ekhorus.barrido'

# Where an engine that found its port taken ends up: the system hands it one of these when it
# binds to port 0. This is the Linux default, used when the file below cannot be read.
RANGO_EFIMERO = (32768, 60999)
# The classic port and its neighbours go first: an engine moved by hand is usually next door.
PUERTOS_CLASICOS = range(6878, 6891)
# On loopback a closed port refuses at once and an open one accepts at once; what costs is
# Android itself, which runs every connect() through its network daemon. Measured on a Fire
# TV over 28,000 ports: 22 s with 32 workers, over a minute with 4 and 112 s with 64, so 32
# it is. The timeout is short because whoever answers on loopback does so in microseconds.
OBREROS_LOOPBACK = 32
TIMEOUT_LOOPBACK = 0.1
# A port that is open but does not speak HTTP keeps quiet until the request gives up, and
# it does so in a worker, so a dozen of them do not add up.
TIMEOUT_IDENTIFICAR = 0.7

_PRIVADAS = ('10.', '192.168.', '172.16.', '172.17.', '172.18.', '172.19.', '172.20.',
             '172.21.', '172.22.', '172.23.', '172.24.', '172.25.', '172.26.', '172.27.',
             '172.28.', '172.29.', '172.30.', '172.31.')


def ip_local():
    """IP of this device on its network, or an empty string."""
    direccion = ''

    try:
        direccion = (xbmc.getIPAddress() or '').strip()
    except (AttributeError, TypeError):
        pass

    if direccion and direccion not in HOSTS_LOCALES:
        return direccion

    # Kodi may not know it. The UDP socket trick does not send a single packet: connect()
    # over UDP only fixes the destination, and with that the system already picks which
    # interface it would go out through and reveals the source address.
    sonda = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sonda.connect(('10.255.255.255', 1))
        return sonda.getsockname()[0]
    except OSError as e:
        logger(f'netscan: no se pudo averiguar la ip local: {e}', 'error')
        return ''
    finally:
        sonda.close()


def es_privada(direccion):
    return bool(direccion) and direccion.startswith(_PRIVADAS)


def subred(direccion):
    """['192.168.1.1', ...] of the /24 it belongs to, without its own, the .0 or the .255."""
    partes = direccion.split('.')
    if len(partes) != 4:
        return list()

    prefijo = '.'.join(partes[:3])

    return [f'{prefijo}.{n}' for n in range(1, 255) if f'{prefijo}.{n}' != direccion]


def _puerto_abierto(direccion, puerto, timeout=TIMEOUT_PUERTO):
    # Not create_connection(): that resolves the address on every call, and over tens of
    # thousands of ports on a TV box that was most of the time. connect_ex() takes the
    # numeric address straight and answers with the error code instead of raising.
    sonda = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sonda.settimeout(timeout)
    try:
        return sonda.connect_ex((direccion, puerto)) == 0
    except OSError:
        return False
    finally:
        sonda.close()


def _repartir(trabajos, tarea, cancelar, obreros=OBREROS):
    """Runs 'tarea(trabajo)' over every job with the workers and returns what they gave back.

    The workers are daemons: their timeouts are tenths of a second, so they die on their own
    and nobody waits for them when Kodi closes. 'cancelar' set makes them drop what is left.
    'al_avanzar' is not offered here: the local sweep takes seconds and shows no progress."""
    resultados = list()
    siguiente = [0]
    candado = threading.Lock()
    # One of its own if the caller brought none: Kodi closing has to stop the workers too.
    cancelar = cancelar if cancelar is not None else threading.Event()

    def obrero():
        while not cancelar.is_set():
            with candado:
                if siguiente[0] >= len(trabajos):
                    return
                indice = siguiente[0]
                siguiente[0] += 1

            hallado = tarea(trabajos[indice])
            if hallado is not None:
                with candado:
                    resultados.append(hallado)

    hilos = [threading.Thread(target=obrero, daemon=True)
             for _ in range(min(obreros, len(trabajos)))]
    for hilo in hilos:
        hilo.start()

    monitor = xbmc.Monitor()
    for hilo in hilos:
        while hilo.is_alive():
            hilo.join(0.1)
            if monitor.abortRequested():
                cancelar.set()

    if cancelar.is_set():
        return list()

    return resultados


def _motor_entre(host, candidatos, cancelar):
    """(lowest port of 'candidatos' where an engine answers or None, how many were open)."""
    abiertos = _repartir(candidatos,
                         lambda p: p if _puerto_abierto(host, p, TIMEOUT_LOOPBACK) else None,
                         cancelar, OBREROS_LOOPBACK)

    def es_motor(puerto):
        servidor = Server(host=host, port=puerto, timeout=TIMEOUT_IDENTIFICAR)
        return puerto if servidor.version else None

    # Here the workers do hide waiting: an open port that is not HTTP sits out the timeout.
    motores = _repartir(sorted(abiertos), es_motor, cancelar)

    return (min(motores) if motores else None), len(abiertos)


def rango_efimero():
    """(low, high) of the ports the system hands out, from the kernel or the Linux default."""
    try:
        with open('/proc/sys/net/ipv4/ip_local_port_range') as f:
            bajo, alto = (int(x) for x in f.read().split())
        if 0 < bajo <= alto < 65536:
            return bajo, alto
    except (OSError, ValueError):
        pass

    return RANGO_EFIMERO


def buscar_puerto_local(host, evitar=(), cancelar=None, completo=True):
    """Lowest port of 'host' where an engine answers get_version, or None.

    For the Ace Stream app on Android. Since its engine 3.1.47.3 it no longer fails when its
    port is taken (AceServe on 6878, say): it starts on whatever port the system gives it,
    keeps that port for good and never goes back, and Kodi has no way of asking it which.
    So the loopback is swept. The classic ports go first and on their own: an engine back on
    6878 is found in milliseconds instead of after the whole range, and that pass is cheap
    enough to repeat every second while an engine is coming up ('completo' False stops
    there). The ephemeral range comes after: a closed loopback port refuses at once, but tens
    of thousands of them are still tens of seconds on a TV box. Linux can connect a port to
    itself when the source port it picks is the one being tried; that gives an open port
    with nobody behind it, and the version request rules it out like any other open port
    that is not an engine.

    'evitar' are ports already known to be silent, and 'cancelar' a threading.Event."""
    clasicos = [p for p in PUERTOS_CLASICOS if p not in evitar]
    hallado, _ = _motor_entre(host, clasicos, cancelar)
    if hallado is not None:
        logger(f'netscan: motor en el puerto {hallado}')
        return hallado

    if not completo:
        return None

    bajo, alto = rango_efimero()
    candidatos = [p for p in range(bajo, alto + 1)
                  if p not in evitar and p not in PUERTOS_CLASICOS]
    inicio = time.time()
    hallado, abiertos = _motor_entre(host, candidatos, cancelar)

    logger(f'netscan: barrido de {host}: {len(candidatos)} puertos, {abiertos} abiertos, '
           f'motor en {hallado or "ninguno"}, {time.time() - inicio:.1f} s')

    return hallado


def barrer(puerto=PUERTO_POR_OMISION, al_avanzar=None, cancelar=None):
    """[(ip, version, engine)] of the engines found, sorted by address.

    'al_avanzar(hechas, total)' is called by the thread that calls this, not by the
    workers, because the one holding the progress dialog is the main thread. 'cancelar'
    is a threading.Event: once set, the workers finish the address they have in hand and
    leave."""
    propia = ip_local()

    if not es_privada(propia):
        logger(f'netscan: {propia or "sin ip"} no es una red domestica, no se barre')
        return None

    direcciones = subred(propia)
    total = len(direcciones)
    abiertas = list()
    siguiente = [0]
    candado = threading.Lock()

    def obrero():
        while True:
            if cancelar is not None and cancelar.is_set():
                return

            with candado:
                if siguiente[0] >= total:
                    return
                indice = siguiente[0]
                siguiente[0] += 1

            if _puerto_abierto(direcciones[indice], puerto):
                with candado:
                    abiertas.append(direcciones[indice])

    hilos = [threading.Thread(target=obrero, daemon=True) for _ in range(OBREROS)]
    for hilo in hilos:
        hilo.start()

    monitor = xbmc.Monitor()
    ultimo = -1

    while any(h.is_alive() for h in hilos):
        with candado:
            hechas = min(siguiente[0], total)

        # Only when the number changes. Reporting on every turn would tie the dialog's
        # repaint rate to this loop's, and it only takes waitForAbort returning early to
        # end up repainting thousands of times a second.
        if al_avanzar is not None and hechas != ultimo:
            ultimo = hechas
            al_avanzar(hechas, total)

        # If Kodi is shutting down there is no point in carrying on sweeping the network.
        if monitor.waitForAbort(0.2):
            if cancelar is not None:
                cancelar.set()
            break

    # No join: the workers are daemons and their timeout is tenths of a second, so they
    # die on their own. Waiting for them here would leave Kodi hung when closing the
    # script.
    if cancelar is not None and cancelar.is_set():
        return list()

    encontrados = list()
    for direccion in sorted(abiertas, key=lambda d: [int(x) for x in d.split('.')]):
        servidor = Server(host=direccion, port=puerto, timeout=TIMEOUT_VERSION)
        version = servidor.version

        if not version:
            # The port was open but there is no engine on the other side: a router, a
            # printer, anything. It is not an error, it simply is not of interest.
            logger(f'netscan: {direccion}:{puerto} abierto pero no es un motor')
            continue

        # With no clear answer to /pl.m3u the engine is not named: better to show the
        # address and the version than to hang a label on it that may be false.
        sirve = servidor.playlist_status(timeout=TIMEOUT_MOTOR)
        motor = '' if sirve is None else engine_name(ENGINE_ACESERVE if sirve
                                                     else ENGINE_ACESTREAM)
        encontrados.append((direccion, version, motor))

    return encontrados
