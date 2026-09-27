import re
import time
import hashlib

from threading import Thread
from lib.acestream.object import Extendable
from lib.acestream.object import Observable

_RE_IDX = re.compile(r'[?&]_idx=(\d+)')


def parse_media_playlist(texto):
  """[{'index', 'filename'}] of the list the engine returns for a multi-file content.

  The index comes from each url's _idx and NOT from the position in the list: the engine
  keeps the number the file has inside the torrent and skips whatever is not media, so
  there are gaps. In a measured eleven-video torrent they came out as 1, 2, 4, 5, 7, 9,
  10, 12, 13, 15 and 16. Passing an index that is not in the list opens no session."""
  ficheros = list()
  nombre = ''

  for linea in (texto or '').splitlines():
    linea = linea.strip()

    if linea.startswith('#EXTINF'):
      nombre = linea.split(',', 1)[1].strip() if ',' in linea else ''
    elif linea and not linea.startswith('#'):
      encontrado = _RE_IDX.search(linea)
      if encontrado:
        indice = int(encontrado.group(1))
        ficheros.append({'index': indice, 'filename': nombre or f'Fichero {indice}'})
      nombre = ''

  return ficheros


class Stats(Extendable, Observable):

  def __init__(self, server):
    Extendable.__init__(self)
    Observable.__init__(self)

    self.stat_url       = None
    self.status         = None
    self.peers          = 0
    self.speed_down     = 0
    self.speed_up       = 0
    self.downloaded     = 0
    self.uploaded       = 0
    self.progress       = 0
    self.total_progress = 0
    self.server         = server
    self._hilo          = None

  def watch(self, stat_url):
    self.stat_url = stat_url
    self._hilo = Thread(target=self._poll_stats)

    # setDaemon() was removed in Python 3.12
    self._hilo.daemon = True
    self._hilo.start()

  def stop(self):
    self.stat_url = None

  def _set_response_to_values(self, response):
    if response.success:
      self._set_attrs_to_values(response.data)
      self.emit('updated')

  def _poll_stats(self):
    while True:
      time.sleep(1)
      # Read once after the sleep: stopped meanwhile, a request to /None would go out
      # otherwise, and the url must not change between the check and the request.
      stat_url = self.stat_url
      if not stat_url:
        return
      self._set_response_to_values(self.server.get(stat_url))


class Stream(Extendable, Observable):

  def __init__(self, server, id=None, url=None, infohash=None):
    Extendable.__init__(self)
    Observable.__init__(self)

    self.filename            = None
    self.status              = None
    self.is_live             = None
    self.playback_session_id = None
    self.command_url         = None
    self.playback_url        = None
    self.stat_url            = None
    self.server              = server
    self.stats               = Stats(server)
    self.media_files         = list()
    self.indice              = None

    self._check_required_args(id=id, url=url, infohash=infohash)
    self._parse_stream_params(id=id, url=url, infohash=infohash)

  def start(self, hls=False, **kwargs):
    """Starts the playback session.

    If the content has several media files and none is named, the engine returns the list
    of files instead of a stream. In that case it is left in self.media_files and
    'started' is NOT emitted: the caller has to ask and come back with _idx."""
    self.media_files = list()
    self.indice = kwargs.get('_idx')

    # The kwargs used to arrive only with hls, so _idx and the transcode options were lost
    # on the most used path. Nobody else passes them today, which means removing the
    # condition changes nothing of what already works.
    kwparams = dict(kwargs, **self.params)
    response = self.server.getstream(pid=self.pid, hls=hls, **kwparams)

    if not response.success:
      self.emit('error', response.message)
      return

    lista = response.data.get('playlist') if isinstance(response.data, dict) else None
    if lista:
      self.media_files = parse_media_playlist(lista)
      if not self.media_files:
        self.emit('error', 'el motor devolvio una lista de ficheros ilegible')
      return

    self._set_attrs_to_values(response.data)
    self._start_watchers()

    self.emit('started')
    self._leer_metadatos()

  def _leer_metadatos(self):
    """File name and content_id, for the title and the history.

    It is incidental: if the engine does not give them, playback goes on the same. This
    used to live inside a bare 'except: pass' that swallowed anything, programming
    mistakes included."""
    response = self.server.getserver(method='get_media_files', api_version=3,
                                     infohash=self.infohash)

    if response.success and isinstance(response.data, dict):
      ficheros = [f for f in (response.data.get('files') or []) if isinstance(f, dict)]
      # If a file was chosen, the title is its own. Always taking the first left the user
      # watching episode 8 with the name of episode 1 on screen and in the history.
      elegido = next((f for f in ficheros if f.get('index') == self.indice), None)
      fichero = elegido or (ficheros[0] if ficheros else None)

      if fichero:
        self.filename = fichero.get('filename') or self.filename

    if not self.id:
      self.id = self.server.get_content_id(self.infohash) or self.id

  def stop(self):
    # The watchers go first, whatever the engine answers: with the session already gone or
    # the engine dead, the poller would otherwise outlive the playback and, with it, the
    # whole invocation, because Kodi waits for every thread before letting the script go.
    self._stop_watchers()
    response = self.server.get(self.command_url, method='stop')

    if response.success:
      self.emit('stopped')
    else:
      self.emit('error', response.message)

  @property
  def params(self):
    params = { 'id': self.id, 'url': self.url, 'infohash': self.infohash }
    params = dict(filter(lambda item: item[1] is not None, params.items()))

    return params

  def _start_watchers(self):
    if self.stat_url:
      # Connected before the poller starts, so its first answer cannot go unheard.
      self.stats.connect('updated', self._on_stats_update)
      self.stats.watch(self.stat_url)

  def _stop_watchers(self):
    self.stats.stop()

  def _check_required_args(self, **kwargs):
    values = list(filter(None, kwargs.values()))
    params = "'id' or 'url' or 'infohash'"

    if not any(values):
      banner = '__init__() missing 1 required positional argument'
      raise TypeError('{0}: {1}'.format(banner, params))

    if len(values) > 1:
      banner = '__init__() too many positional arguments, provide only one of'
      raise TypeError('{0}: {1}'.format(banner, params))

  def _parse_stream_params(self, **kwargs):
    sid_args = list(filter(None, kwargs.values()))
    self.pid = hashlib.sha1(sid_args[0].encode('utf-8')).hexdigest()

    self._set_attrs_to_values(kwargs)

  def _on_stats_update(self, **kwargs):
    prev_status = self.status
    self.status = self.stats.status

    self.emit('stats::updated')

    if prev_status != self.status:
      self.emit('status::changed', self.status)

  # get_available_players() and open_in_player() used to live here. Nobody called them and
  # they are no use: both engines return an empty player list on Android, which is the
  # only place where they would have made sense. Checked against AceStream 3.2.22 and
  # AceServe 3.2.14.
