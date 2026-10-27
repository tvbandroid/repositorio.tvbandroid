# -*- coding: utf-8 -*-
"""Matcher inspirado en DARKVIO TelegramSearchMatcher, adaptado a Python/Kodi.
Acepta separadores variables, títulos pegados y formatos S01E03 / S1E3 / 1x03 / 1x3.
"""
import re, unicodedata

VIDEO_EXT=re.compile(r"\.(?:mkv|mp4|avi|mov|wmv|m4v|ts|m2ts|webm|mpg|mpeg|flv|3gp)$", re.I)
YEAR_RE=re.compile(r"\b(19|20)\d{2}\b")
SE_RE=re.compile(r"(?:s|season)?\s*0*(\d{1,2})\s*(?:e|episode)\s*0*(\d{1,4})\b", re.I)
X_RE=re.compile(r"\b0*(\d{1,2})\s*x\s*0*(\d{1,4})\b", re.I)


def norm(s):
    s=unicodedata.normalize("NFKD", s or "")
    s="".join(c for c in s if not unicodedata.combining(c))
    s=VIDEO_EXT.sub("",s)
    s=s.lower()
    s=re.sub(r"[._\-\[\](){}'!,?:+&]", " ", s)
    s=re.sub(r"\s+", " ", s).strip()
    return s


def compact(s):
    return re.sub(r"[^a-z0-9]+", "", norm(s))


def extract_se(text):
    raw=text or ""
    m=SE_RE.search(raw) or X_RE.search(raw)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def title_match(text, candidates):
    n=norm(text); c=compact(text)
    for t in candidates:
        if not t: continue
        nt=norm(t); ct=compact(t)
        if nt and nt in n: return True
        if ct and len(ct)>=4 and ct in c: return True
    return False


def _episode_tokens(text):
    """Return all explicit season/episode tokens found in text."""
    raw=text or ""
    out=[]
    for m in SE_RE.finditer(raw):
        out.append((int(m.group(1)), int(m.group(2))))
    for m in X_RE.finditer(raw):
        out.append((int(m.group(1)), int(m.group(2))))
    return out


def _has_whole_season_marker(text, season):
    """Detect season-only names such as S01, Season 1 or Temporada 1."""
    raw=text or ""
    patterns=(
        r"\bs0*%d\b" % int(season),
        r"\bseason\s*0*%d\b" % int(season),
        r"\btemporada\s*0*%d\b" % int(season),
    )
    return any(re.search(p, raw, re.I) for p in patterns)


def _episode_is_exact(text, season, episode):
    """Require an explicit token for the requested episode and reject ranges."""
    raw=text or ""
    tokens=_episode_tokens(raw)
    if not tokens:
        return False
    if (int(season), int(episode)) not in tokens:
        return False
    # Reject multi-episode/range releases such as S01E03-E10 or 1x03-1x10.
    # Also reject a second explicit episode token in the same name.
    if len(tokens) > 1:
        return False
    for pat in (
        r"(?:s0*%d|%d\s*x\s*0*%d)\s*[-–—_]\s*(?:s0*%d|%d\s*x\s*0*)?0*\d+" % (int(season), int(season), int(episode), int(season), int(season)),
        r"(?:e0*%d)\s*[-–—_]\s*e0*\d+" % int(episode),
    ):
        if re.search(pat, raw, re.I):
            return False
    return True


def quality_label(name):
    """Human-friendly quality only, used by Darkvio Telegram source labels."""
    raw=(name or "").lower()
    if re.search(r"(?:2160p|4k|uhd)", raw): return "4K"
    m=re.search(r"(4320p|2160p|1440p|1080p|900p|720p|576p|540p|480p|360p)", raw)
    if m: return m.group(1)
    if re.search(r"(?:web[- .]?dl|web[- .]?rip)", raw): return "WEB"
    if re.search(r"(?:bluray|bdrip|brrip)", raw): return "BluRay"
    if re.search(r"(?:hdtv|hdrip)", raw): return "HDTV"
    return "HD"


def format_size(size):
    try: n=float(size or 0)
    except Exception: n=0
    if n<=0: return "Tamaño desconocido"
    units=("B","KB","MB","GB","TB")
    i=0
    while n>=1024 and i<len(units)-1:
        n/=1024.0; i+=1
    if i==0: return "%d %s" % (int(n),units[i])
    return "%.2f %s" % (n,units[i])

def score(file_name, caption, title, year=None, season=None, episode=None, localized=None, english=None, original=None):
    combined=(file_name or "")+" "+(caption or "")
    candidates=[title,localized,english,original]
    if not title_match(combined,candidates):
        return 0
    score=60
    if year:
        ys=[int(x.group()) for x in YEAR_RE.finditer(combined)]
        if year in ys: score+=20
        elif not ys: score+=5
        elif any(abs(y-year)==1 for y in ys): score+=5
        else: score-=10
    if season is not None and episode is not None:
        # Para episodios nunca aceptamos archivos de temporada completa ni
        # archivos sin identificador de episodio: debe existir exactamente
        # el episodio solicitado.
        if _has_whole_season_marker(file_name, season) or _has_whole_season_marker(caption, season):
            return 0
        good=_episode_is_exact(file_name, season, episode) or _episode_is_exact(caption, season, episode)
        if good: score+=20
        else: return 0
    return max(0,min(100,score))


def series_queries(titles, season, episode):
    out=[]
    variants=[
        "s%de%d"%(season,episode), "s%02de%02d"%(season,episode),
        "s%d e%d"%(season,episode), "s%02d e%02d"%(season,episode),
        "%dx%d"%(season,episode), "%02dx%02d"%(season,episode),
        "%d x %d"%(season,episode), "%02d x %02d"%(season,episode),
    ]
    for t in titles:
        if not t: continue
        for v in variants: out.append("%s %s"%(t,v))
    return list(dict.fromkeys(out))


def movie_queries(titles, year=None):
    out=[]
    for t in titles:
        if not t: continue
        if year: out.append("%s %s"%(t,year))
        out.append(t)
    return list(dict.fromkeys(out))
