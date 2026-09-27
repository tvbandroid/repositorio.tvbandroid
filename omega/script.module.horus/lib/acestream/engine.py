import os
import signal
import subprocess

from lib.acestream.object import Observable
from lib.utils import no_window


class Engine(Observable):
  def __init__(self, bin, **options):
    Observable.__init__(self)

    self.process = None
    self.bin     = bin
    self.options = options
    # Whether the engine got a session of its own (setsid), which decides how it is stopped.
    self.sesion_propia = False

  def start(self, **kwargs):
    """Launches the engine and comes straight back.

    No thread of ours reads its output any more. With the pipes, one sat in communicate()
    until the engine died, and Kodi waits for every thread of a script before giving the
    invocation up: the one that started the engine outlived it for the whole session and,
    blocked in C, held Kodi five seconds on exit. The output goes nowhere; nobody read it."""
    if self.running:
      return

    sesion_propia = hasattr(os, 'setsid')
    if sesion_propia:
      kwargs['preexec_fn'] = os.setsid
    else:
      # CREATE_NO_WINDOW avoids the engine's black console over Kodi on Windows.
      kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, 'CREATE_NO_WINDOW', 0)

    kwargs['stdout'] = subprocess.DEVNULL
    kwargs['stderr'] = subprocess.DEVNULL

    try:
      try:
        self.process = subprocess.Popen(self.process_args, **kwargs)
      except RuntimeError:
        # Kodi runs scripts in sub-interpreters, where preexec_fn is refused.
        kwargs.pop('preexec_fn', None)
        kwargs.pop('creationflags', None)
        sesion_propia = False
        self.process = subprocess.Popen(self.process_args, **kwargs)
    except OSError as error:
      self.process = None
      self.emit('error', str(error))
      return

    self.sesion_propia = sesion_propia
    self.emit('started')

  def stop(self):
    process = self.process

    if not process:
      return

    try:
      if self.sesion_propia:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
      elif os.name == 'nt':
        # /T takes the engine's children with it, which terminate() would leave behind.
        subprocess.call(['taskkill', '/F', '/T', '/PID', str(process.pid)], **no_window())
      else:
        # Without setsid (Kodi's sub-interpreters refuse it) the engine sits in Kodi's own
        # process group, and killpg on that group would take Kodi down with it.
        process.terminate()
    except Exception as error:
      self.emit('error', str(error))

    # Reaped, so that no zombie is left behind on Linux; a moment is enough after a kill.
    try:
      process.wait(3)
    except subprocess.TimeoutExpired:
      pass

    self.process = None
    self.emit('terminated')

  @property
  def running(self):
    return self.process is not None and self.process.poll() is None

  @property
  def failed(self):
    """The process ended with an error code: it crashed, or refused to start.

    A clean exit is not a failure: on OSMC and LibreELEC the .start script is a launcher
    that ends at once with the engine alive behind it."""
    return self.process is not None and self.process.poll() not in (None, 0)

  @property
  def process_args(self):
    if isinstance(self.bin, (list, tuple)):
      # Preferred form: the command already comes split. A path with spaces
      # ("C:\\Users\\Juan Perez\\...") cannot be split on spaces, and the previous
      # split() broke it in two, so the engine never started.
      options = [str(a) for a in self.bin]
    elif os.path.exists(self.bin):
      options = [self.bin]
    else:
      options = self.bin.split()

    for (key, value) in self.options.items():
      options.append('--{0}'.format(key.replace('_', '-')))

      if not isinstance(value, bool):
        options.append(str(value))

    return options
