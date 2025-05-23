
from xbmc import Monitor
from tmdbhelper.lib.api.kodi.rpc import get_jsonrpc
from tmdbhelper.lib.addon.plugin import get_condvisibility
from tmdbhelper.lib.addon.thread import SafeThread


class KeyboardInputter(SafeThread):
    def __init__(self, action=None, text=None, timeout=300):
        SafeThread.__init__(self)
        self.text = text
        self.action = action
        self.exit = False
        self.poll = 0.5
        self.timeout = timeout

    def run(self):
        while not Monitor().abortRequested() and not self.exit and self.timeout > 0:
            Monitor().waitForAbort(self.poll)
            self.timeout -= self.poll
            if self.text and get_condvisibility("Window.IsVisible(DialogKeyboard.xml)"):
                get_jsonrpc("Input.SendText", {"text": self.text, "done": True})
                self.exit = True
            elif self.action and get_condvisibility("Window.IsVisible(DialogSelect.xml) | Window.IsVisible(DialogConfirm.xml)"):
                get_jsonrpc(self.action)
                self.exit = True
