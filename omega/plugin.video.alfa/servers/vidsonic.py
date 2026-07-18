# -*- coding: utf-8 -*-
# -*- Server vidsonic -*-
# -*- Created for Alfa-addon -*-
# -*- By the Alfa Develop Group -*-

from core import httptools
from core import scrapertools
from platformcode import logger
from lib import jsunpack
import sys

PY3 = False
if sys.version_info[0] >= 3: PY3 = True; unicode = str; unichr = chr; long = int


##### canal Luxporn    https://vidsonic.net/e/t61ki9h9lz8u

host = "https://vidsonic.net/"


def test_video_exists(page_url):
    logger.info("(page_url='%s')" % page_url)
    global data, encoded
    
    response = httptools.downloadpage(page_url)
    data = response.data
    encoded = scrapertools.find_single_match(data, "_0x1 = '([^']+)'")
    
    if response.code == 404  or "File Not Found" in data or "File is no longer available" in data:
        return False, "[vidsonic] El fichero no existe o ha sido borrado"
    return True, ""


def get_video_url(page_url, premium=False, user="", password="", video_password=""):
    logger.info("(page_url='%s')" % page_url)
    video_urls = []
    global data, encoded
    
    video_urls.append(["[vidsonic]", decode(encoded)])
    
    return video_urls


def decode(s):
    clean = s.replace('|', '')
    out = ''

    for i in range(0, len(clean), 2):
        hex_pair = clean[i:i+2]
        out += chr(int(hex_pair, 16))

    return out[::-1]  # reverse string