# -*- coding: utf-8 -*-
"""
OnTV — Favoritos Persistentes  v1.0.4

Guarda uma lista de streams favoritos em disco (JSON).
Funciona para Live TV, Filmes, Séries e M3U.

Estrutura de cada favorito:
  {
    "id":        str,    # hash único
    "nome":      str,
    "url":       str,    # None para séries (navegar)
    "logo":      str,
    "tipo":      str,    # "video" | "movie" | "tvshow"
    "srv_idx":   str,    # índice do servidor (para séries Xtream)
    "series_id": str,    # para séries Xtream
    "cmd":       str,    # para Stalker
    "stalker_tipo": str,
    "ts":        float,  # timestamp de adição
  }
"""

import os
import json
import hashlib
import time

try:
    import xbmcvfs
    _FAV_FILE = xbmcvfs.translatePath('special://temp/ontv_favourites.json')
except Exception:
    _FAV_FILE = os.path.join(os.path.dirname(__file__), 'ontv_favourites.json')

_cache = None   # carregado uma vez por sessão


def _load():
    global _cache
    if _cache is not None:
        return _cache
    try:
        if os.path.exists(_FAV_FILE):
            with open(_FAV_FILE, 'r', encoding='utf-8') as f:
                _cache = json.load(f)
                return _cache
    except Exception:
        pass
    _cache = []
    return _cache


def _save():
    try:
        with open(_FAV_FILE, 'w', encoding='utf-8') as f:
            json.dump(_cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _make_id(nome, url):
    raw = (nome + (url or '')).encode('utf-8')
    return hashlib.md5(raw).hexdigest()[:12]


# ── API pública ────────────────────────────────────────────────────────────

def listar():
    """Devolve lista de todos os favoritos, ordenada por nome."""
    favs = _load()
    return sorted(favs, key=lambda x: x.get('nome', '').lower())


def adicionar(nome, url='', logo='', tipo='video', **kwargs):
    """
    Adiciona um favorito. Ignora duplicados (mesmo nome+url).
    kwargs pode conter: srv_idx, series_id, cmd, stalker_tipo
    """
    favs = _load()
    fid  = _make_id(nome, url)
    if any(f['id'] == fid for f in favs):
        return False   # já existe
    fav = {
        'id':    fid,
        'nome':  nome,
        'url':   url,
        'logo':  logo,
        'tipo':  tipo,
        'ts':    time.time(),
    }
    fav.update({k: v for k, v in kwargs.items() if v})
    favs.append(fav)
    _save()
    return True


def remover(fid):
    """Remove favorito pelo id. Devolve True se removido."""
    global _cache
    favs = _load()
    antes = len(favs)
    _cache = [f for f in favs if f['id'] != fid]
    if len(_cache) < antes:
        _save()
        return True
    return False


def existe(nome, url=''):
    fid  = _make_id(nome, url)
    return any(f['id'] == fid for f in _load())


def contar():
    return len(_load())
