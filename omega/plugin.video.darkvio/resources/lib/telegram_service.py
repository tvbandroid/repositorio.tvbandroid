# -*- coding: utf-8 -*-
"""Control del servicio persistente de reproducción Telegram de DARKVIO."""
import json, time, urllib.parse, urllib.request

HOST = "127.0.0.1"
PORT = 38980


def _request(path, timeout=4):
    url = "http://%s:%d%s" % (HOST, PORT, path)
    req = urllib.request.Request(url, headers={"User-Agent": "DARKVIO/1.4.7"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def available(timeout=1.5):
    try:
        return _request("/ping", timeout).strip() == "DARKVIO-TELEGRAM-SERVICE"
    except Exception:
        return False


def start_stream(file_id, name="video", size=0, persistent_id="", chat_id=0, message_id=0):
    q = urllib.parse.urlencode({
        "file_id": int(file_id),
        "name": name or "video",
        "size": int(size or 0),
        "pid": persistent_id or "",
        "chat_id": int(chat_id or 0),
        "message_id": int(message_id or 0),
    })
    last = None
    # Kodi can be a little slow starting a newly installed service. Give it a
    # short grace period rather than reporting a false playback failure.
    for _ in range(8):
        try:
            raw = _request("/start?" + q, timeout=8)
            data = json.loads(raw)
            if data.get("ok") and data.get("url"):
                return data["url"]
            last = data.get("error") or "Servicio Telegram sin URL"
        except Exception as e:
            last = e
        time.sleep(0.5)
    raise RuntimeError(str(last or "Servicio Telegram no disponible"))


def stop_playback():
    try:
        _request("/stop", timeout=4)
        return True
    except Exception:
        return False
