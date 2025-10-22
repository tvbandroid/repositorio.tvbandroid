import sys
import os
from urllib3.util import SKIP_HEADER
import xbmc
import xbmcaddon
import xbmcplugin
import xbmcgui
import xbmcvfs


base_url = 'https://dlhd.dad'
base_url_old = 'https://daddylivestream.com'
schedule_url = f'{base_url}/schedule/schedule-generated.php'
schedule_url_old = f'{base_url_old}/schedule/schedule-generated.php'
channels_url = f'{base_url}/daddy.json'
channels_url_old = f'{base_url_old}/24-7-channels.php'

user_agent = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36'
headers = {
    "User-Agent": user_agent,
    "Referer": f'{base_url}/',
    "Origin": f'{base_url}/'
}
skip_headers = {"Accept-Encoding": SKIP_HEADER}

try:
    handle = int(sys.argv[1])
except IndexError:
    handle = 0
plugin_url = sys.argv[0]
addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_path = xbmcvfs.translatePath(addon.getAddonInfo('path'))
profile_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
temp_path = xbmcvfs.translatePath('special://temp')
addon_name = addon.getAddonInfo('name')
addon_icon = addon.getAddonInfo('icon')
addon_fanart = addon.getAddonInfo('fanart')
get_setting = addon.getSetting
get_setting_bool = addon.getSettingBool
end_directory = xbmcplugin.endOfDirectory


schedule_path = os.path.join(profile_path, 'schedule.json')
cat_schedule_path = os.path.join(profile_path, 'cat_schedule.json')
fav_path = os.path.join(temp_path, 'favourites.json')
fav_old_path = os.path.join(profile_path, 'favourites.json')
ch_path = os.path.join(profile_path, 'channels.json')
ch_bak_path = os.path.join(addon_path, 'resources', 'channels.json')
set_content = xbmcplugin.setContent
set_category = xbmcplugin.setPluginCategory
set_resolved_url = xbmcplugin.setResolvedUrl
list_item = xbmcgui.ListItem
system_exit = sys.exit
execute_builtin = xbmc.executebuiltin
notify_dialog = xbmcgui.Dialog().notification
