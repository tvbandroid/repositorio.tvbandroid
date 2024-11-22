import sys
from urllib.parse import parse_qsl
import xbmcaddon
import xbmcplugin
from resources.lib.modules.utils import create_listitem, log
from resources.lib.modules.models import Item


HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_ICON = ADDON.getAddonInfo('icon')

def main_menu():
    xbmcplugin.setPluginCategory(HANDLE, 'Main Menu')
    
    create_listitem(
        Item(
            title='[B][COLOR deepskyblue]*** Sports Central ***[/COLOR][/B]'
        )
    )
    
    create_listitem(
        Item(
            title='TV App',
            type='dir',
            mode='tvapp_main'
        )
    )
    
    create_listitem(
        Item(
            title='Daddylive',
            type='dir',
            mode='ddlive_main'
        )
    )
    
    create_listitem(
        Item(
            title='Replays',
            type='dir',
            mode='replays_main'
        )
    )
    
    #from streamed import get_categories
    #for item in get_categories():
        #create_listitem(item)
    

def router(paramstring):
    params = dict(parse_qsl(paramstring))
    mode = params.get('mode')
    
    if mode is None:
        main_menu()
    
    elif str(mode).startswith('replays'):
        from replays import runner
        runner(params)
    
    elif str(mode).startswith('tvapp'):
        from tvapp import runner
        runner(params)
    
    elif str(mode).startswith('ddlive'):
        from dd import runner
        runner(params)
    
    #elif str(mode).startswith('streamed_'):
        #from streamed import runner
        #runner(params)
        #xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE)

if __name__ == '__main__':
    router(sys.argv[2][1:])
    
    