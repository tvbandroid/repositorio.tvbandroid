import json
from html.parser import unescape
import variables as var
import functions as func
from models import Item, Category, Channel

def main_menu():
    func.create_listitem(
        Item(
            title='Channels',
            type='dir',
            mode='channels'
        )
    )
    func.write_schedule()
    func.write_channels()
    for key in func.read_schedule():
        func.create_listitem(
            Item(
                title=key.split(' -')[0].strip(),
                type='dir',
                mode='categories',
                title2=key
            )
        )
    
    func.create_listitem(
        Item(
            'Favourite Channels',
            type='dir',
            mode='favourites'
        )
    )

def get_channels():
    password = var.get_setting('adult_pw')
    saved_favs = func.read_favourites()
    items = func.read_channels()
    for item in items:
        title = item['title']
        if '18+' in title and password != 'xxXXxx':
            continue
        link = item['link']
        if link not in str(saved_favs):
            cm_label = 'Add to favourite channels'
            cm_mode = 'add_fav'
        else:
            cm_label = 'Remove from favourite channels'
            cm_mode = 'remove_fav'
        cm_item = Item(
            title=title,
            mode=cm_mode,
            link=link
        )
        cm_url = f'{var.plugin_url}?{cm_item.url_encode()}'
        cm_url = f'RunPlugin({cm_url})'
        link = json.dumps([[title, link]])
        
        func.create_listitem(
            Channel(
                title=title,
                link=link,
                contextmenu=[(cm_label, cm_url)]
            )
        )

def get_categories(date):
    for key in func.read_schedule()[date].keys():
        func.create_listitem(
            Category(
                title=key,
                title2=date,
            )
        )

def get_matches(category, date):
    schedule = func.read_schedule()[date][category]
    func.write_cat_schedule(json.dumps(schedule))
    for match in schedule:
        title = match['event']
        clean_title = unescape(title)
        start_time = match.get('time', '')
        try:
            clean_title = f'{func.convert_utc_time_to_local(start_time)} - {clean_title}' if start_time else clean_title
        except:
            pass
        
        func.create_listitem(
            Channel(
                title=clean_title,
                title2=title
            )
        )

def play_video(name: str, url: str, icon: str, description, match):
    if match is not None:
        url = func.get_match_links(match)
    url = json.loads(url) if isinstance(url, str) else url
    if len(url) > 1:
        url = func.get_multilink(url)
    else:
        url = url[0][1]
    if not url:
        var.system_exit()
        
    url = func.resolve_link(url)

    list_item = var.list_item(name, path=url)
    func.set_info(list_item, {'title': name, 'plot': description})
    list_item.setArt({'thumb': icon, 'icon': icon, 'poster': icon})
    list_item.setProperty('inputstream', 'inputstream.ffmpegdirect')
    list_item.setMimeType('application/x-mpegURL')
    list_item.setProperty('inputstream.ffmpegdirect.is_realtime_stream', 'true')
    if var.get_setting_bool('timeshift') is True:
        list_item.setProperty('inputstream.ffmpegdirect.stream_mode', 'timeshift')
    list_item.setProperty('inputstream.ffmpegdirect.manifest_type', 'hls')
    var.set_resolved_url(var.handle, True, listitem=list_item)

def get_favourites():
    items = func.read_favourites()
    for title, link in items:
        cm_label = 'Remove from favourite channels'
        cm_mode = 'remove_fav'
        cm_item = Item(
            title=cm_label,
            mode=cm_mode,
            link=link
        )
        cm_url = f'{var.plugin_url}?{cm_item.url_encode()}'
        cm_url = f'RunPlugin({cm_url})'
        func.create_listitem(
            Channel(
                title,
                link=json.dumps([[title, link]]),
                contextmenu=[(cm_label, cm_url)]
            )
        )

def add_favourite(title, link):
    func.write_favourite(title, link)
    var.execute_builtin('Container.Refresh')
    var.notify_dialog(var.addon_name, f'{title} added to favourites', icon=var.addon_icon)

def remove_favourite(title, link):
    items = func.read_favourites()
    for item in items:
        if link in item:
            items.remove(item)
    func.write_file(var.fav_path, json.dumps(items))
    var.execute_builtin('Container.Refresh')
    var.notify_dialog(var.addon_name, f'{title} removed from favourites', icon=var.addon_icon)


def router(params: dict):
    mode = params.get('mode')
    title = params.get('title')
    title2 = params.get('title2')
    link = params.get('link', '')
    thumbnail = params.get('thumbnail')
    
    if mode is None:
        main_menu()
    
    elif mode == 'channels':
        get_channels()
    
    elif mode == 'categories':
        get_categories(title2)
    
    elif mode == 'matches':
        get_matches(title, title2)
    
    elif mode == 'favourites':
        get_favourites()
    
    elif mode == 'add_fav':
        add_favourite(title, link)
    
    elif mode == 'remove_fav':
        remove_favourite(title, link)
    
    elif mode == 'play':
        play_video(title, link, thumbnail, title, title2)
    
    var.set_content(var.handle, 'videos')
    var.set_category(var.handle, title)
    var.end_directory(var.handle)
    