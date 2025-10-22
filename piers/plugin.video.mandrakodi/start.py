versione='1.0.0'
# Module: launcher
# Author: ElSupremo
# Created on: 22.02.2021
# Last update: 08.05.2021
# License: GPL v.3 https://www.gnu.org/copyleft/gpl.html

import sys
import logging
import xbmcgui
import xbmc
import os
import xbmcplugin
import xbmcaddon
import json
import re

# Get the plugin url in plugin:// notation.
_url = sys.argv[0]
# Get the plugin handle as an integer number.
_handle = int(sys.argv[1])

addon_id = 'plugin.video.mandrakodi'
selfAddon = xbmcaddon.Addon(id=addon_id)
debug = selfAddon.getSetting("debug")

viewmode=None

PY3 = sys.version_info[0] == 3

if PY3:
    from urllib.parse import urlencode, parse_qsl
else:
    from urlparse import urlparse, parse_qsl
    from urllib import urlencode, quote

def logga(mess):
    if debug == "on":
        logging.warning('MANDRA_LOG: '+mess)

def makeRequest(url, hdr=None):
    logga('Try to open '+url)
    html = ""
    if PY3:
	    import urllib.request as myRequest
    else:
	    import urllib2 as myRequest

    pwd = selfAddon.getSetting("password")
    version = selfAddon.getAddonInfo("version")
    if hdr is None:
        ua = "MandraKodi@@"+version+"@@"+pwd
        hdr = {"User-Agent" : ua}
    try:
        req = myRequest.Request(url, headers=hdr)
        response = myRequest.urlopen(req)
        html = response.read()
        response.close()
    except:
        logga('Error to open url')
        pass
    return html

def getSource():
    home = ''
    if PY3:
        home = xbmc.translatePath(selfAddon.getAddonInfo('path'))
    else:
        home = xbmc.translatePath(selfAddon.getAddonInfo('path').decode('utf-8'))
    
    try:
        start_file = os.path.join(home, 'start.json')
        resF = open(start_file)
        strSource = resF.read()
        resF.close()
    except:
        logga('Errore getSource')
        strSource = getTxtMessage("um.txt")
        pass
    jsonToItems(strSource)



def play_video(path):
    play_item = xbmcgui.ListItem(path=path)
    xbmcplugin.setResolvedUrl(_handle, True, listitem=play_item)

def getTxtMessage(vName):
    home = ''
    if PY3:
        home = xbmc.translatePath(selfAddon.getAddonInfo('path'))
    else:
        home = xbmc.translatePath(selfAddon.getAddonInfo('path').decode('utf-8'))
    fPath = os.path.join(home, vName)
    resF = open(fPath)
    file_content = resF.read()
    resF.close()
    return file_content

def getExternalJson(strPath):
    strSource = makeRequest(strPath)
    jsonToItems(strSource)

def jsonToItems(strJson):
    global viewmode
    dataJson = json.loads(strJson)
    xbmcplugin.setContent(_handle, 'videos')
    try:
        nvs = dataJson['name']
        if nvs == addon_id:
            vS = dataJson['groups'][0]["stations"][0]["url"]
            if not vS.startswith("http"):
                return jsonToItems(getTxtMessage(vS))
            return getExternalJson(vS)
    except:
        logga('DISPLAY ADDON MESSAGE')
        pass

    try:
        viewmode = dataJson['SetViewMode']
        skin_name = xbmc.getSkinDir()
        logga("setting view mode for "+skin_name+" on "+viewmode)
        #xbmc.executebuiltin("Container.SetViewMode("+viewmode+")")
    except:
        logga('no view mode')
        pass

    try:
        arrChan = dataJson['channels']
        logga("OK CHANNELS")
        return jsonToChannels(strJson)
    except:
        logga('no channels. GetItems')
        pass

    for item in dataJson["items"]:
        titolo = "NO TIT"
        thumb = "https://www.andreisfina.it/wp-content/uploads/2018/12/no_image.jpg"
        fanart = "https://www.andreisfina.it/wp-content/uploads/2018/12/no_image.jpg"
        genre = "generic"
        info = ""
        regExp = ""
        resolverPar = "no_par"
        link = ""
        extLink = False
        extLink2 = False
        is_folder = False
        is_magnet = False
        is_myresolve = False
        is_regex = False
        is_chrome = False
        is_pvr = False
        is_enabled = True

        if 'enabled' in item:
            is_enabled = item["enabled"]

        if is_enabled == False:
            continue
        
        if 'title' in item:
            titolo = item["title"]
        
        if 'thumbnail' in item:
            thumb = item["thumbnail"]

        if 'fanart' in item:
            fanart = item["fanart"]

        if 'info' in item:
            info = item["info"]

        if 'genre' in item:
            genre = item["genre"]

        if 'link' in item:
            link = item["link"]

        if 'externallink' in item:
            extLink = True
            is_folder = True
            link = item["externallink"]

        if 'externallink2' in item:
            extLink2 = True
            is_folder = True
            link = item["externallink2"]

        if 'myresolve' in item:
            is_myresolve = True
            is_folder = True
            link = item["myresolve"]
            if "@@" in link:
                arrT=link.split("@@")
                link=arrT[0]
                resolverPar=arrT[1]
            elif ":" in link:
                arrT=link.split(":")
                link=arrT[0]
                resolverPar=arrT[1]
        if 'regexPage' in item:
            is_regex = True
            link = item["regexPage"]
            if 'regexExpres' in item:
                regExp = item["regexExpres"]

        if 'chrome' in item:
            is_chrome = True
            is_folder = True
            link = item["chrome"]

        if 'magnet' in item:
            is_magnet = True
            link = item["magnet"]

        if 'pvr' in item:
            is_pvr = True
            link = item["pvr"]

        list_item = xbmcgui.ListItem(label=titolo)
        list_item.setInfo('video', {'title': titolo,'genre': genre,'mediatype': 'video'})
        list_item.setArt({'thumb': thumb, 'icon': thumb, 'fanart': fanart})
        
        url = ""
        if extLink == True:
            url = get_url(action='getExtData', url=link)
        elif extLink2 == True:
            url = get_url(action='getExtData2', url=link)
        elif is_regex == True:
            list_item.setProperty('IsPlayable', 'true')
            url = get_url(action='regex', url=link, exp=regExp)
        elif is_myresolve == True:
            url = get_url(action='myresolve', url=link, parIn=resolverPar)
        elif is_pvr == True:
            url = get_url(action='pvr', url=link)
        elif is_magnet == True:
            list_item.setProperty('IsPlayable', 'true')
            url = get_urlMagnet(uri=link)
        elif is_chrome == True:
            url = get_urlChrome(mode='showSite', stopPlayback='no', kiosk='no', url=link)
        else:
            if 'apk' in item:
                logga('APK MODE')
                list_item.setProperty('IsPlayable', 'true')
                is_folder = True
                apkName=item["apk"]
                url = get_url(action='apk', url=link, apk=apkName)
            else:
                list_item.setProperty('IsPlayable', 'true')
                if not link.startswith("plugin://plugin"):
                    url = get_url(action='play', url=link)
                else:
                    url = get_url(action='plugin', url=link)

        xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)
    xbmcplugin.endOfDirectory(_handle)

def get_url(**kwargs):
    return '{0}?{1}'.format(_url, urlencode(kwargs))

def get_urlMagnet(**kwargs):
    return '{0}?{1}'.format("plugin://plugin.video.elementum/play", urlencode(kwargs))

def get_urlChrome(**kwargs):
    return '{0}?{1}'.format("plugin://plugin.program.browser.launcher/", urlencode(kwargs))

def parameters_string_to_dict(parameters):
    params = dict(parse_qsl(parameters.split('?')[1]))
    return params

def jsonToChannels(strJson):
    channelsArray = json.loads(strJson)
    window = xbmcgui.Window(10000)
    window.setProperty("chList", strJson)
    xbmcplugin.setContent(_handle, 'videos')
    for channel in channelsArray["channels"]:
        titolo = "NO TIT"
        thumb = "https://www.andreisfina.it/wp-content/uploads/2018/12/no_image.jpg"
        fanart = "https://www.andreisfina.it/wp-content/uploads/2018/12/no_image.jpg"
        genre = "generic"
        info = ""
        link = ""

        if 'name' in channel:
            titolo = channel["name"]

        if 'thumbnail' in channel:
            thumb = channel["thumbnail"]

        if 'fanart' in channel:
            fanart = channel["fanart"]

        if 'info' in channel:
            info = channel["info"]

        list_item = xbmcgui.ListItem(label=titolo)
        list_item.setInfo('video', {'title': titolo,'genre': genre,'mediatype': 'video'})
        list_item.setArt({'thumb': thumb, 'icon': thumb, 'fanart': fanart})
        url = get_url(action='getChannel', url=titolo)
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle)
   
def channelToItems(strChName, _handle):
    window = xbmcgui.Window(10000)
    strJson = window.getProperty("chList")
    channelsArray = json.loads(strJson)
    xbmcplugin.setContent(_handle, 'videos')
    for channel in channelsArray["channels"]:
        titolo = channel["name"]
        if titolo == strChName:
            logga("FOUND CH: "+titolo)
            jsonToItems(json.dumps(channel))


def simpleRegex(page, find):
    html = makeRequest(page)
    if PY3:
        html = html.decode('utf-8')		
    urlSteam = re.findall(find, html)[0]
    return urlSteam


def callReolver(metodo, parametro):
    import myResolver
    retVal = myResolver.run(metodo, parametro)
    xbmcplugin.setContent(_handle, 'videos')
    thumb="https://cdn.pixabay.com/photo/2012/04/12/20/56/play-30619_640.png"
    fanart="https://www.stadiotardini.it/wp-content/uploads/2016/12/mandrakata.jpg"
    if isinstance(retVal, list):
        numLink=1
        
        for linkTmp in retVal:
            newList=list(retVal[0])
            newLink=newList[0]
            logga("Stream_Url ==> " + newLink)
            newTit="[COLOR lime]PLAY LINK "+str(numLink)+" ("+newLink[0:4]+")[/COLOR]"
            list_item = xbmcgui.ListItem(label=newTit)
            list_item.setInfo('video', {'title': newTit,'genre': 'generic','mediatype': 'video'})
            list_item.setArt({'thumb': thumb, 'icon': thumb, 'fanart': fanart})
            list_item.setProperty('IsPlayable', 'true')
            url = get_url(action='play', url=newLink)
            xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
            numLink += 1
    else:
        logga("StreamUrl ==> " + retVal)
        newTit="[COLOR lime]PLAY LINK ("+retVal[0:4]+")[/COLOR]"
        list_item = xbmcgui.ListItem(label=newTit)
        list_item.setInfo('video', {'title': newTit,'genre': 'generic','mediatype': 'video'})
        list_item.setArt({'thumb': thumb, 'icon': thumb, 'fanart': fanart})
        list_item.setProperty('IsPlayable', 'true')
        url = get_url(action='play', url=retVal)
        xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
    xbmcplugin.endOfDirectory(_handle)

def runApk(apkName, apkPar):
    xbmc.executebuiltin('StartAndroidActivity("'+apkName+'", "android.intent.action.VIEW", "", "'+apkPar+'")')

def getPvr():
    myPvr = None
        
    if not os.path.exists(xbmc.translatePath('special://home/addons/pvr.iptvsimple')) and not os.path.exists(xbmc.translatePath('special://xbmcbinaddons/pvr.iptvsimple')):
        xbmc.executebuiltin('InstallAddon(pvr.iptvsimple)', wait=True)
    
    pvr_enabled = '"enabled":true' in xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.GetAddonDetails","id":1,"params":{"addonid":"pvr.iptvsimple", "properties": ["enabled"]}}')
    if (not pvr_enabled):
        xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id":1, "method": "Addons.SetAddonEnabled", "params": { "addonid": "pvr.iptvsimple", "enabled": true }}')
    
    myPvr = xbmcaddon.Addon(id='pvr.iptvsimple')
    return myPvr

def setPvr(urlM3u):
    try:
        pvrSimpleTv=getPvr()
        
        if PY3:
            xbmc.executebuiltin('xbmc.StopPVRManager')
        else:
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id":1, "method": "Addons.SetAddonEnabled", "params": { "addonid": "pvr.iptvsimple", "enabled": false }}')

        if pvrSimpleTv.getSetting('m3uPathType') != '1': 
            pvrSimpleTv.setSetting('m3uPathType', '1')
        pvrSimpleTv.setSetting('epgUrl','')
        pvrSimpleTv.setSetting('m3uUrl', urlM3u)

        xbmc.sleep(500)

        if PY3:
            xbmc.executebuiltin('xbmc.StartPVRManager')
        else:
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id":1, "method": "Addons.SetAddonEnabled", "params": { "addonid": "pvr.iptvsimple", "enabled": true }}')
            xbmc.sleep(500)
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id":1, "method": "Addons.SetAddonEnabled", "params": { "addonid": "pvr.iptvsimple", "enabled": false }}')
            xbmc.sleep(500)
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id":1, "method": "Addons.SetAddonEnabled", "params": { "addonid": "pvr.iptvsimple", "enabled": true }}')
        
        dialog = xbmcgui.Dialog()
        return dialog.ok("Mandrakodi", "PVR configurato correttamente.")
    except Exception as err:
        errMsg="ERRORE: {0}".format(err)
        raise ValueError(errMsg)


def run():
    try:
        if not sys.argv[2]:
            logga("=== ADDON START ===")
            getSource()
        else:
            params = parameters_string_to_dict(sys.argv[2])
            action =  params['action']
            url =  params['url']
            logga("ACTION ==> "+action)
            if action == 'getExtData':
                getExternalJson(url)
            elif action == 'getExtData2':
                keyboard = xbmc.Keyboard('','Insert string')
                keyboard.doModal()
                if not (keyboard.isConfirmed() == False):
                    userInput = keyboard.getText()
                    strUrl = url + userInput.replace(" ", "+")
                    getExternalJson(strUrl)
            elif action == 'apk':
                apkN =  params['apk']
                logga("RUN APK: "+apkN)
                runApk(apkN, url)
            elif action == 'getChannel':
                logga("OPEN CHANNEL: "+url)
                channelToItems(url, _handle)
            elif action == 'regex':
                express =  params['exp']
                logga("REGEX: "+url+" - "+express)
                url = simpleRegex(url, express)
                play_video(url)
            elif action == 'myresolve':
                parIn =  params['parIn']
                logga("MyResolver: "+url+" - "+parIn)
                callReolver(url, parIn)
            elif action == 'openSettings':
                xbmcaddon.Addon().openSettings()
                xbmcgui.Dialog().ok('[B][COLOR yellow]AVVISO[/COLOR][/B]','[COLOR lime]CHIUDI KODI E APRI DI NUOVO PER AGGIORNARE IMPOSTAZIONI[/COLOR]')
                xbmc.executebuiltin("XBMC.Container.Refresh()")
            elif action == 'plugin':
                logga("CALL PLUGIN: "+url)
                url2=url.replace("plugin://", "")
                url3=url2.split("?")
                pl=""
                par=""
                if ('?' in url):
                    pl=url3[0].replace("/", "")
                    par=url3[1]
                    logga("plug: "+pl+" --> "+par)
                    xbmc.executebuiltin("RunPlugin("+url+")")
                else:
                    pl=url3[0].replace("/", "")
                    logga("onlyplugin: "+pl)
                    xbmc.executebuiltin('RunAddon("'+pl+'")')
            elif action == 'play':
                play_video(url)
            elif action == 'pvr':
                setPvr(url)
            else:
                raise ValueError('Invalid paramstring: {0}!'.format(params))
    except Exception as err:
        errMsg="ERRORE: {0}".format(err)
        raise ValueError(errMsg)
    
    if not viewmode==None:
        logga("setting view mode")
        xbmc.executebuiltin("Container.SetViewMode("+viewmode+")")
        logga("setting view mode again")
        xbmc.executebuiltin("Container.SetViewMode("+viewmode+")")
