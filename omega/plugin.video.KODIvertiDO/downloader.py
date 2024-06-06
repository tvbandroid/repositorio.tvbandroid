################################################################################
#      Copyright (C) 2015 Surfacingx                                           #
#                                                                              #
#  This Program is free software; you can redistribute it and/or modify        #
#  it under the terms of the GNU General Public License as published by        #
#  the Free Software Foundation; either version 2, or (at your option)         #
#  any later version.                                                          #
#                                                                              #
#  This Program is distributed in the hope that it will be useful,             #
#  but WITHOUT ANY WARRANTY; without even the implied warranty of              #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the                #
#  GNU General Public License for more details.                                #
#                                                                              #
#  You should have received a copy of the GNU General Public License           #
#  along with XBMC; see the file COPYING.  If not, write to                    #
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.       #
#  http://www.gnu.org/copyleft/gpl.html                                        #
################################################################################

import xbmc, xbmcgui, urllib, sys, time, uservar, os
import wizard as wiz

ADDONTITLE     = uservar.ADDONTITLE
COLOR1         = uservar.COLOR1
COLOR2         = uservar.COLOR2

#urllib.URLopener.version = 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36 SE 2.X MetaSr 1.0'

import xbmcgui
#import urllib2
import socket
import kodi
import time


try:
    from urllib.request import urlopen, Request  # python 3.x
except ImportError:
    from urllib2 import urlopen, Request  # python 2.x

class MyException(Exception):
    pass

def download(url, dest, dp = None,timeout = None):
    if not timeout:
        timeout = 120

    try:
        if not dp:
            dp = xbmcgui.DialogProgress()
            dp.create("Status...","Checking Installation",' ', ' ')
        dp.update(0)
        start_time = time.time()
        u = urlopen(url, timeout=timeout)
        h = u.info()
        totalSize = int(h["Content-Length"])
        fp = open(dest, 'wb')
        blockSize = 8192 #100000 # urllib.urlretrieve uses 8192
        count = 0
        while True:  # and (end - start < 15):
            if time.time() - start_time > timeout:
                #kodi.message("Slow or no Download available:", 'Files could not be downloaded at this time', 'Please try again later, Attempting to continue...')
                break
            chunk = u.read(blockSize)
            if not chunk: break
            fp.write(chunk)
            count += 1
            if totalSize > 0:
                try:
                    percent = int(count * blockSize * 100 / totalSize)
                    dp.update(percent)
                except:
                    percent = 100
                    dp.update(percent)
                if dp.iscanceled():
                    dp.close()
                    raise Exception("Canceled")
        timetaken =  time.time() - start_time
        kodi.log('Duration of download was %.02f secs ' % timetaken )
    # except socket.timeout as e:
    except Exception as e:
        # For Python 2.7
        #kodi.message("There was an error: %r" % e, 'Files could not be downloaded at this time', 'Please try again later, Attempting to continue...')
        return
    except Exception as e:
        #kodi.message("There was an error:", str(e),'Please try again later, Attempting to continue...')
        return

