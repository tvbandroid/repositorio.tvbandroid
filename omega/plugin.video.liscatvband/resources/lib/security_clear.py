# -*- coding: utf-8 JoseaTeba -*-

import xbmc
import xbmcvfs
import xbmcgui
import xbmcaddon
import hashlib
import sys
import json
import urllib.request
import os

ADDON = xbmcaddon.Addon()

# ==============================
# URL OCULTA (igual que tenías)
# ==============================
def _u():
    x = [
        104,116,116,112,115,58,47,47,115,101,112,97,114,97,116,101,45,
        108,111,115,116,45,111,98,106,101,99,116,100,97,116,97,98,97,
        115,101,45,45,106,97,108,111,103,97,46,114,101,112,108,105,
        116,46,97,112,112,47,108,105,99,101,110,99,105,97
    ]
    return "".join([chr(i) for i in x])


# ==============================
# DEVICE ID REAL (ARREGLADO)
# ==============================
def get_device_id():

    try:
        mac = xbmc.getInfoLabel("Network.MacAddress")
        name = xbmc.getInfoLabel("System.FriendlyName")
        platform = xbmc.getInfoLabel("System.Platform")
        version = xbmc.getInfoLabel("System.BuildVersion")

        # bloque si no hay MAC válida
        if not mac or mac == "00:00:00:00:00:00":
            raise Exception("MAC inválida")

        raw = f"{mac}-{name}-{platform}-{version}"

    except:
        raw = "fallback_blocked_device"

    return hashlib.sha256(raw.encode()).hexdigest()[:12].upper()


# ==============================
# VALIDACIÓN REMOTA
# ==============================
def validar_licencia(codigo_usuario):

    try:
        codigo_usuario = codigo_usuario.replace("-", "").upper()
        device_id = get_device_id()

        data = json.dumps({
            "d": device_id,
            "l": codigo_usuario
        }).encode()

        req = urllib.request.Request(
            _u(),
            data=data,
            headers={"Content-Type": "application/json"}
        )

        res = urllib.request.urlopen(req, timeout=7)
        result = json.loads(res.read().decode())

        return result.get("ok") == 1

    except:
        return False


# ==============================
# ANTI MANIPULACIÓN
# ==============================
def _check_self():
    try:
        f = __file__
        if not os.path.exists(f):
            raise Exception("error")
    except:
        raise Exception("error")


# ==============================
# ENTRADA SEGURA
# ==============================
def secure_entry():

    _check_self()

    guardada = ADDON.getSetting("licencia_guardada")

    if guardada:
        if validar_licencia(guardada):
            return True
        else:
            ADDON.setSetting("licencia_guardada", "")

    dialog = xbmcgui.Dialog()
    device_id = get_device_id()

    # ==============================
    # PANTALLA 1
    # ==============================
    dialog.ok(
        "[B][COLOR black].......[COLOR orangered]INTRODUCE LA LICENCIA DE ACTIVACIÓN[/COLOR][/B]",
        f"[B][COLOR white]Código del Dispositivo:[/COLOR][/B]\n\n"
        f"[COLOR yellowgreen][B]{device_id}[/B][/COLOR]\n\n"
        "[B][COLOR white]Envíalo para Recibir tu Licencia.[/COLOR][/B]"
    )

    # ==============================
    # INPUT LICENCIA
    # ==============================
    licencia = dialog.input(
        "[B]INTRODUCE TU LICENCIA:[/B]",
        type=xbmcgui.INPUT_ALPHANUM
    )

    if not licencia:
        sys.exit()

    # ==============================
    # VALIDAR
    # ==============================
    if validar_licencia(licencia):

        ADDON.setSetting("licencia_guardada", licencia)

        dialog.notification(
            "[COLOR orangered]Lisca[COLOR white]TVband[/COLOR]",
            "[COLOR greenyellow]Licencia Activada Correctamente.[/COLOR]",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )

        return True

    else:

        dialog.ok(
            "[COLOR black]......................[COLOR red]ERROR DE ACTIVACIÓN[/COLOR]",
            "[B][COLOR white]Licencia Inválida.[/COLOR][/B]\n\n[B][COLOR white]Intentalo de Nuevo.[/COLOR][/B]"
        )

        sys.exit()