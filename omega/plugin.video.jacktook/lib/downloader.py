import os
import ssl
import threading
import re
from urllib.request import Request, urlopen
from urllib.parse import parse_qsl
from lib.utils.kodi.utils import (
    ADDON_HANDLE,
    get_setting,
    kodilog,
    translatePath,
    ADDON_PATH,
    notification,
    open_file,
)
from lib.db.cached import MemoryCache
from lib.gui.custom_progress import CustomProgressDialog

from xbmcplugin import (
    addDirectoryItems,
    setContent,
    setPluginCategory,
    endOfDirectory,
)
import xbmcgui
import xbmcvfs
import xbmc


cancel_flag_cache = MemoryCache()


def normalize_file_name(file_name):
    file_name = file_name.strip()
    base, _ = os.path.splitext(file_name)
    # Remove invalid characters and dots from base name
    base = re.sub(r'[\\/*?:"<>|.]', "_", base)
    base = re.sub(r"_+", "_", base)
    return base


def handle_download_file(params):
    """
    Handles the download process for a file using the Downloader class.
    """
    kodilog("Starting download process")
    destination = params.get("destination")
    if not destination or not os.path.exists(destination):
        notification("Invalid download destination.")
        return

    file_name = normalize_file_name(params.get("file_name", ""))
    key = os.path.join(destination, file_name)

    kodilog(f"Cancel Key: {key}")
    cancel_flag_cache._set(key, False)
    downloader = Downloader(params, cancel_flag_cache)
    downloader.name = file_name 
    downloader.run()


class Downloader:
    def __init__(self, params, cancel_flag_cache):
        self.url = params.get("url")
        self.destination = params.get("destination", "")
        self.headers = {}
        self.monitor = xbmc.Monitor()
        self.file_size = 0
        self.cancel_flag = cancel_flag_cache

    def run(self):
        if not self.url:
            notification("No URL provided for download.")
            return

        thread = threading.Thread(target=self._run_download_process)
        thread.start()

    def _run_download_process(self):
        self._prepare_download()

        if not self._validate_url():
            notification("Invalid URL for download.")
            return

        self._start_download()

    def _prepare_download(self):
        try:
            self.headers = dict(parse_qsl(self.url.rsplit("|", 1)[1]))
        except:
            pass
        try:
            self.url = self.url.split("|")[0]
        except:
            pass

    def _validate_url(self):
        try:
            kodilog(f"Validating URL: {self.url}")
            request = Request(self.url, headers=self.headers)
            response = urlopen(request, context=ssl.SSLContext(ssl.PROTOCOL_SSLv23))
            self.file_size = int(response.headers.get("Content-Length", 0))
            return self.file_size > 0
        except Exception as e:
            kodilog(f"Error validating URL: {str(e)}")
            return False

    def _start_download(self):
        try:
            destination_path = os.path.join(self.destination, self.name)
            kodilog(f"Destination path: {destination_path}")

            kodilog(f"Starting download from: {self.url}")
            kodilog(f"Headers: {self.headers}")
            kodilog(f"File size: {self.file_size} bytes")

            request = Request(self.url, headers=self.headers)
            response = urlopen(request, context=ssl.SSLContext(ssl.PROTOCOL_SSLv23))

            progress_dialog = CustomProgressDialog(
                "custom_progress_dialog.xml", ADDON_PATH
            )
            progress_dialog.show_dialog()

            with open_file(destination_path, "wb") as file:
                downloaded = 0
                while not self.monitor.abortRequested():
                    chunk = response.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        kodilog("No more data to read")
                        break
                    # Handle cancellation
                    if progress_dialog.cancelled or self.cancel_flag._get(
                        destination_path
                    ):
                        notification(f"Cancelled: {self.name}")
                        self.cancel_flag._set(destination_path, True)
                        file.close()
                        return

                    file.write(chunk)
                    downloaded += len(chunk)
                    progress = int((downloaded / self.file_size) * 100)
                    progress_dialog.update_progress(
                        progress, f"{self.name}: {progress}% completed"
                    )

                    self.monitor.waitForAbort(0.1)

                if downloaded == self.file_size or self.file_size == 0:
                    notification(f"Download completed: {self.name}")

        except Exception as e:
            kodilog(f"Download error: {str(e)}")
            notification(f"Failed to download: {str(e)}")


def handle_cancel_download(params):
    kodilog("Cancelling download")
    file_path = params.get("file")
    cancel_flag = cancel_flag_cache._get(file_path)
    kodilog(f"Cancel key: {file_path}")
    kodilog(f"Cancel flag: {cancel_flag}")
    if cancel_flag is False:
        cancel_flag_cache._set(file_path, True)
        xbmc.executebuiltin("Container.Refresh")
    else:
        notification("No active download found.")


def handle_delete_file(params):
    file_path = params.get("file", "")
    if not xbmcvfs.exists(file_path):
        notification("File not found.")
        return
    try:
        xbmcvfs.delete(file_path)
        notification(f"File Deleted")
        xbmc.executebuiltin("Container.Refresh")
    except Exception as e:
        kodilog(f"Error deleting file: {str(e)}")
        notification(f"Failed to delete file: {str(e)}")


def downloads_viewer(params):
    download_dir = get_setting("download_dir")
    translated_path = translatePath(download_dir)

    item_list = []
    try:
        directories, files = xbmcvfs.listdir(translated_path)
        for item in directories + files:
            item_path = os.path.join(translated_path, item)
            list_item = xbmcgui.ListItem(label=item)
            if item in directories:
                list_item.setInfo("video", {"title": item, "mediatype": "folder"})
                list_item.setProperty("IsPlayable", "false")
                is_folder = True
            else:
                list_item.setInfo("video", {"title": item, "mediatype": "file"})
                context_menu = []

                # Add "Cancel Download" only if the file is an active download
                flag_cache = cancel_flag_cache._get(item_path)
                if flag_cache is False:
                    context_menu.append(
                        (
                            "Cancel Download",
                            f"RunPlugin(plugin://plugin.video.jacktook?action=cancel_download&file={item_path})",
                        )
                    )

                context_menu.append(
                    (
                        "Delete File",
                        f"RunPlugin(plugin://plugin.video.jacktook?action=delete_file&file={item_path})",
                    )
                )

                list_item.addContextMenuItems(context_menu)
                is_folder = False
            item_list.append((item_path, list_item, is_folder))

        addDirectoryItems(ADDON_HANDLE, item_list)
        setContent(ADDON_HANDLE, "")
        setPluginCategory(ADDON_HANDLE, params.get("name", "Downloads"))
        endOfDirectory(ADDON_HANDLE)
    except Exception as e:
        notification(f"Error: {str(e)}", "Downloads Viewer")
        endOfDirectory(ADDON_HANDLE, succeeded=False)
