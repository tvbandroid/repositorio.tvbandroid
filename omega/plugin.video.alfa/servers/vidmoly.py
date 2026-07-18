# -*- coding: utf-8 -*-
# --------------------------------------------------------
# Conector vidmoly By Alfa development Group
# --------------------------------------------------------
import re
from core import httptools
from core import scrapertools
from platformcode import logger
import sys

PY3 = False
if sys.version_info[0] >= 3: PY3 = True; unicode = str; unichr = chr; long = int

kwargs = {'set_tls': False, 'set_tls_min': False, 'retries_cloudflare': 5, 'ignore_response_code': True, 'cf_assistant': False}

# Error 403  captcha
# NO PIDE el captcha  https://vidmoly.me/\\1.html
# https://vidmoly.me/embed-15e4ac1yvzfm.html  >>>  https://vidmoly.me/w/15e4ac1yvzfm
#

def test_video_exists(page_url):
    global data
    logger.info("(page_url='%s')" % page_url)
    response = httptools.downloadpage(page_url, timeout=30)
    data = response.data
    if response.code == 403:
        return False, "[vidmoly] Error"
    if response.code == 404 or "/notice.php" in data:
        return False, "[vidmoly] El archivo no existe o ha sido borrado"
    return True, ""


def get_video_url(page_url, premium=False, user="", password="", video_password=""):
    global data

    domains_alt = ["\/\/transit-", "\/\/box-[^\/]+\/hls\d+\/"]
    url_alt = "biz/embed-"
    cf_challenges_list = ["https://challenges.cloudflare.com", "https://www.google.com/recaptcha/api2/anchor?"]
    for challenge in cf_challenges_list:
        if challenge in data:
            data = resolve_captcha(page_url.replace("me/", url_alt), data)
            break

    if scrapertools.find_single_match(data, r'\{file:"([^"]+)"\}.*?label:\s"([^"]+)"'):
        url, quality = scrapertools.find_single_match(data, r'\{file:"([^"]+)"\}.*?label:\s"([^"]+)"')
    else:
        url, quality = scrapertools.find_single_match(data, r'\{\s*file:\s*\'([^\']+)\'\s*\}[^$]+label:\s*"([^"]+)"')
    for dom in domains_alt:
        if scrapertools.find_single_match(url, dom):
            break
    else:
        response = httptools.downloadpage(url, timeout=30, alfa_s=True)
        if not response.sucess:
            domains_alt += [httptools.obtain_domain(url)]
    for dom in domains_alt:
        if scrapertools.find_single_match(url, dom):
            page_url = page_url.replace("me/", url_alt)
            response = httptools.downloadpage(page_url, timeout=30, hide_infobox=True)
            data = response.data
            if response.code == 403:
                return [["[vidmoly] Error Captcha", ""]]
            if response.code == 404 or "/notice.php" in data:
                return [["[vidmoly] El archivo no existe o ha sido borrado", ""]]
            break

    logger.info("url=" + page_url)
    video_urls = []
    if scrapertools.find_single_match(data, r'\{file:"([^"]+)"\}.*?label:\s"([^"]+)"'):
        url, quality = scrapertools.find_single_match(data, r'\{file:"([^"]+)"\}.*?label:\s"([^"]+)"')
    elif scrapertools.find_single_match(data, r'\{\s*file:\s*\'([^\']+)\'\s*\}[^$]+label:\s*"([^"]+)"'):
        url, quality = scrapertools.find_single_match(data, r'\{\s*file:\s*\'([^\']+)\'\s*\}[^$]+label:\s*"([^"]+)"')
    else:
        return [["[vidmoly] Error Captcha", ""]]
    url += "|Referer=%s" % page_url
    video_urls.append(['[vidmoly] m3u8 %s' %quality, url])

    # mp4_sources = re.compile('\{file:"([^"]+)",label:"([^"]+)"', re.DOTALL).findall(data)

    # for url, qlty in mp4_sources:
        # video_urls.append(['%s [vidmoly]' % qlty, url])

    return video_urls


def resolve_captcha(url, data):
    import xbmcgui
    window = xbmcgui.Window(10000) or None
    if window and not window.getProperty("is_alfa_installed"):
        return data

    import requests
    from lib.cloudscraper.cf_assistant import get_cl
    from platformcode import config
    cf_assistant = True
    debug = config.get_setting('debug_report', default=False)
    timeout = 30 if cf_assistant is True else 0.001
    extraPostDelay = 15 if cf_assistant is True else 0
    timeout_cha = 20 if cf_assistant is True else 40
    opt =  {
             'url_save': url, 'cf_assistant': cf_assistant, 
             'cf_assistant_ua': True, 'cf_assistant_get_source': True if cf_assistant == 'force' else False, 
             'cf_no_blacklist': True, 'cf_removeAllCookies': False if cf_assistant == 'force' else True,
             'cf_challenge': 1, 'cf_returnkey': 'url', 'cf_partial': True, 'cf_jscode': None, 
             'cf_cookie': '$HOST|cf_turnstile_demo_pass_' if cf_assistant is True else '', 
             'cf_cookies_names': {r'^cf_turnstile_demo_pass_[^$]+$': False}, 
             'cf_debug': debug, 'timeout_cha': timeout_cha
           }

    req = requests.Response()
    req.status_code = 403
    req = get_cl(opt, req, cache=True, timeout=timeout, extraPostDelay=extraPostDelay)
    if req.status_code in [503, 429, 400]:
        return data

    if cf_assistant is True:
        req = httptools.downloadpage(url, timeout=30, hide_infobox=True)
        if req.sucess:
            data = req.data
    else:
        if PY3 and isinstance(req._content, bytes):
            data = "".join(chr(x) for x in bytes(req._content))
        else:
            data = req._content

    return data