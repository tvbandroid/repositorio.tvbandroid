# -*- coding: utf-8 -*-
"""Bloqueo interproceso ligero para que dos invocaciones de Kodi no abran
la misma base de datos TDLib al mismo tiempo."""
import os, time, platform

class TDLibProcessLock:
    def __init__(self, path, timeout=12.0):
        self.path = path
        self.timeout = float(timeout)
        self.f = None
        self.locked = False

    def acquire(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.f = open(self.path, 'a+b')
        deadline = time.time() + self.timeout
        if platform.system().lower().startswith('win'):
            import msvcrt
            while time.time() < deadline:
                try:
                    self.f.seek(0)
                    self.f.write(b'0')
                    self.f.flush()
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                    self.locked = True
                    return True
                except (OSError, IOError):
                    time.sleep(0.15)
            self.close()
            return False
        import fcntl
        while time.time() < deadline:
            try:
                fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.locked = True
                return True
            except (OSError, IOError):
                time.sleep(0.15)
        self.close()
        return False

    def close(self):
        if not self.f:
            return
        try:
            if self.locked:
                if platform.system().lower().startswith('win'):
                    import msvcrt
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            self.f.close()
        except Exception:
            pass
        self.f = None
        self.locked = False
