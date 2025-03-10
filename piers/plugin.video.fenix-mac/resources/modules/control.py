# -*- coding: utf-8 -*-

'''
    Tulip routine libraries, based on lambda's lamlib
    Author Twilight0

        License summary below, for more details please read license.txt file

        This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
        the Free Software Foundation, either version 2 of the License, or
        (at your option) any later version.
        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
        GNU General Public License for more details.
        You should have received a copy of the GNU General Public License
        along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''


import os, six
from kodi_six import xbmc, xbmcgui, xbmcplugin, xbmcaddon, xbmcvfs

translatePath = xbmc.translatePath if six.PY2 else xbmcvfs.translatePath

integer = 1000
addon = xbmcaddon.Addon
lang = xbmcaddon.Addon().getLocalizedString
setting = xbmcaddon.Addon().getSetting
setSetting = xbmcaddon.Addon().setSetting
addonInfo = xbmcaddon.Addon().getAddonInfo

addItem = xbmcplugin.addDirectoryItem
directory = xbmcplugin.endOfDirectory
content = xbmcplugin.setContent
property = xbmcplugin.setProperty
resolve = xbmcplugin.setResolvedUrl

infoLabel = xbmc.getInfoLabel
condVisibility = xbmc.getCondVisibility
jsonrpc = xbmc.executeJSONRPC
keyboard = xbmc.Keyboard
sleep = xbmc.sleep
execute = xbmc.executebuiltin
skin = xbmc.getSkinDir()
player = xbmc.Player()
playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

transPath = translatePath
skinPath = translatePath('special://skin/')
addonPath = translatePath(addonInfo('path'))
dataPath = translatePath(addonInfo('profile'))

window = xbmcgui.Window(10000)
dialog = xbmcgui.Dialog()
progressDialog = xbmcgui.DialogProgress()
windowDialog = xbmcgui.WindowDialog()
button = xbmcgui.ControlButton
image = xbmcgui.ControlImage
alphanum_input = xbmcgui.INPUT_ALPHANUM
password_input = xbmcgui.INPUT_PASSWORD
hide_input = xbmcgui.ALPHANUM_HIDE_INPUT
item = xbmcgui.ListItem

openFile = xbmcvfs.File
makeFile = xbmcvfs.mkdir
deleteFile = xbmcvfs.delete
deleteDir = xbmcvfs.rmdir
listDir = xbmcvfs.listdir
exists = xbmcvfs.exists

join = os.path.join
settingsFile = os.path.join(dataPath, 'settings.xml')
bookmarksFile = os.path.join(dataPath, 'bookmarks.db')
cacheFile = os.path.join(dataPath, 'cache.db')


def infoDialog(message, heading=addonInfo('name'), icon='', time=3000):
    if icon == '':
        icon = addonInfo('icon')
    try:
        dialog.notification(heading, message, icon, time, sound=False)
    except:
        if six.PY3:
            execute("Notification(%s, %s, %s, %s)" % (heading, message, time, icon))
        else:
            execute("XBMC.Notification(%s, %s, %s, %s)" % (heading, message, time, icon))


def okDialog(heading, line1):
    return dialog.ok(heading, line1)


def inputDialog(heading, _type_=''):
    return dialog.input(heading, _type_)


def yesnoDialog(line1, line2, line3, heading=addonInfo('name'), nolabel='', yeslabel=''):
    return dialog.yesno(heading, line1, line2, line3, nolabel, yeslabel)


def selectDialog(list, heading=addonInfo('name')):
    return dialog.select(heading, list)

def openSettings(query=None, id=addonInfo('id')):
    try:
        idle()
        execute('Addon.OpenSettings(%s)' % id)
        if query is None:
            raise Exception()
        c, f = query.split('.')
        execute('SetFocus(%i)' % (int(c) + 100))
        execute('SetFocus(%i)' % (int(f) + 200))
    except:
        return


def openSettings_alt():
    try:
        idle()
        xbmcaddon.Addon().openSettings()
    except:
        return


def openPlaylist():
    return execute('ActivateWindow(VideoPlaylist)')


def refresh():
    return execute('Container.Refresh')


def idle():
    return execute('Dialog.Close(busydialog)')


def set_view_mode(vmid):
    return execute('Container.SetViewMode({0})'.format(vmid))
