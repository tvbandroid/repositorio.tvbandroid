import json
import re

from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError

# Without a timeout, an unreachable engine (wrong ip_addr, machine powered
# off) freezes the Kodi interface until the OS drops the connection.
DEFAULT_TIMEOUT = 10

# Margin for the probe that identifies the engine. Measured at 0.5 s freshly started, but
# it settles the identity for the whole session and cannot fail just because it is busy.
PLAYLIST_TIMEOUT = 5

# The engine answers with small json. If the configured host is not an engine
# and returns something huge, there is no point in loading it all in memory.
MAX_RESPONSE = 4 * 1024 * 1024


def sanitize_host(host):
  """Normalises whatever the user typed in the IP setting.

  It is free text, so anything can arrive: an uppercase scheme, a trailing
  slash from copy-paste, spaces, a port stuck to the host, or even an int
  (get_setting turns "999" into a number). Without this, some cases blew up
  on import and others left the addon mute with no explanation."""
  host = str(host if host is not None else '').strip()
  host = re.sub(r'^https?://', '', host, flags=re.I)   # scheme
  host = host.split('/')[0]                            # leftover path
  host = host.split(':')[0]                            # port stuck to the host

  # Host names are case-insensitive; lower so that LOCALHOST still counts as local.
  return host.strip().lower() or '127.0.0.1'


def version_tuple(value):
  """Compares versions without distutils, which is gone in Python 3.12."""
  parts = list()

  for chunk in re.split(r'[._-]', str(value or '')):
    match = re.match(r'\d+', chunk)
    parts.append(int(match.group()) if match else 0)

  return tuple(parts) if parts else (0,)


class Response(object):

  def __init__(self, data=None, message=None, error=False):
    self.data    = data
    self.error   = error
    self.success = not bool(error)
    self.message = self._parse_message(message)

  def _parse_message(self, message):
    if message:
      # str(): the error may not be text (dict, int...).
      message = str(message).split(']')[-1]
      # .strip() FIRST: the engine sends "[x] <no such stream>", and removing the
      # angle brackets before the space left a dangling '<' in the message.
      message = message.strip().lstrip('<').rstrip('>').strip()
      # If nothing is left ("]", "<>"), message[0] would raise IndexError.
      if not message:
        return None

      return '%s%s' % (message[0].upper(), message[1:])


class Request(object):

  def __init__(self, host, port=None, scheme='http', timeout=DEFAULT_TIMEOUT):
    self.base    = self._geturl_base(scheme, host, str(port))
    self.timeout = timeout

  def get(self, req_url, **params):
    apiurl = self._geturl(req_url, **params)
    return self._request(apiurl)

  def _geturl(self, path, **params):
    params = dict(map(self._parse_param, params.items()))
    params = urlencode(params)
    apiurl = str(path).replace(self.base, '').strip('/')

    return '{0}/{1}?{2}'.format(self.base, apiurl, params)

  def _request(self, req_url):
    try:
      with urlopen(req_url, timeout=self.timeout) as connection:
        cuerpo = connection.read(MAX_RESPONSE)
    except (IOError, HTTPError, ValueError) as error:
      return self._generate_response({ 'result': None, 'error': str(error) })

    return self._generate_response(self._parse_body(cuerpo))

  def _parse_body(self, cuerpo):
    """Reads the engine's answer, which is not always json.

    With format=json the engine answers json EXCEPT when the content has several media
    files and it has not been told which one: then it returns an M3U list with one #EXTINF
    per file and each one's _idx already in place. That used to fall into _parse_json(),
    come back {} and _generate_response took it for a success with empty data, so playback
    sat waiting for a state that never arrived until it timed out. The user saw an 'engine
    not started' with the engine perfectly alive."""
    data = self._parse_json(cuerpo)
    if data:
      return data

    texto = cuerpo.decode('utf-8', 'replace').lstrip() if isinstance(cuerpo, bytes) else str(cuerpo)

    if texto.startswith('#EXTM3U'):
      return { 'result': { 'playlist': texto } }

    # Neither json nor a list. This used to be a mute success; saying so is the only
    # honest thing.
    return { 'result': None, 'error': 'respuesta no reconocida del motor' }

  def _generate_response(self, output):
    result = output.get('result') or output.get('response')
    error  = output.get('error')

    return Response(data=result, error=bool(error), message=error)

  def _geturl_base(self, scheme, host, port):
    # Built with no heuristics. The previous version only appended the port
    # "if the host did not already end with it", so with host 10.0.0.80 and port
    # 80 it skipped it and the url pointed at the wrong port.
    return '{0}://{1}:{2}'.format(scheme or 'http', sanitize_host(host), port)

  def _get_response_key(self, response, key):
    # data is only a dict when there is a real engine on the other side. If the
    # configured host is something else (a router answering HTML, an empty
    # response, a json that is not an object), _parse_json leaves data as None or
    # as some other type and .get() raised AttributeError outside of any try.
    # Returning None means "no engine here", which is the truth.
    if response.success and isinstance(response.data, dict):
      return response.data.get(key)

  def _parse_json(self, string):
    try:
      data = json.loads(string)
    except (IOError, ValueError):
      return {}

    # The engine always answers with an object. If anything else arrives (a list,
    # a null, a number), whoever uses it calls .get() and would blow up, so it is
    # treated as an invalid response, which is what it is.
    return data if isinstance(data, dict) else {}

  def _parse_param(self, param):
    key, value = param

    if isinstance(value, bool):
      value = int(value)

    return (key, value)


def parse_port(value):
  """The port as an int, or None if it is not one."""
  try:
    port = int(value)
  except (TypeError, ValueError):
    return None

  return port if 0 < port < 65536 else None


class Server(Request):
  def __init__(self, host, port=6878, scheme='http', timeout=DEFAULT_TIMEOUT):
    # The port comes from a free-text setting. It is sanitised BEFORE building the
    # base url, so that the url and ping() talk about the same port. Otherwise an
    # invalid port made ping() report "engine alive" while every request failed.
    # Besides, int() over garbage blew up the addon import.
    self._port = parse_port(port) or 6878
    self._host = sanitize_host(host)
    self._scheme = scheme or 'http'

    Request.__init__(self, self._host, self._port, self._scheme, timeout)

    self._version = None

  def cambiar_puerto(self, port):
    """Points at another port of the same host. False if the port is not one.

    For an engine found on a port other than the configured one. The Server is built once
    and shared by every module, so it is retargeted in place instead of rebuilt; the cached
    version goes with the old port."""
    port = parse_port(port)
    if port is None:
      return False

    self._port = port
    self.base = self._geturl_base(self._scheme, self._host, str(port))
    self._version = None
    return True

  def ping(self, timeout=2):
    """Cheap TCP connection probe, so the menu does not block for 10 seconds
    when the engine sits on a remote ip that is switched off. It does not
    replace available; it only tells whether the port answers."""
    import socket

    try:
      with socket.create_connection((self._host, self._port), timeout=timeout):
        return True
    except Exception:
      return False

  def http_status(self, path, timeout=2):
    """HTTP code of an engine route, or None if it does not answer.

    get() is no good here: it reads the body and what is needed is the code. A plain 404
    and an error json can only be told apart this way."""
    url = f"{self.base}/{str(path).lstrip('/')}"

    try:
      with urlopen(url, timeout=timeout) as connection:
        return connection.getcode()
    except HTTPError as error:
      return error.code
    except Exception:
      return None

  def get_text(self, path, timeout=None):
    """Raw body of an engine route, or None if it does not answer or does not give 200.

    For /pl.m3u, which is not json. get() would turn it into an unrecognised response
    error, which is right for the rest of the API but not for this."""
    url = f"{self.base}/{str(path).lstrip('/')}"

    try:
      with urlopen(url, timeout=timeout or self.timeout) as connection:
        if connection.getcode() != 200:
          return None
        return connection.read(MAX_RESPONSE).decode('utf-8', 'replace')
    except Exception:
      return None

  def playlist_status(self, timeout=PLAYLIST_TIMEOUT):
    """True if the engine serves /pl.m3u, False if it says no, None if it could not tell.

    AceServe publishes its list there and the AceStream engine answers 500, so this is the
    only thing that tells the two apart: their version numbers overlap (3.2.14 against
    3.2.22) and are no use.

    The three states are not a whim. The caller caches the verdict for the whole Kodi
    session, and an unlucky probe while the engine is busy broadcasting would leave the
    engine misidentified until a restart. A network failure has to be able to say 'I do
    not know' instead of 'no'. Measured at 0.5 s with the engine freshly started; the
    PLAYLIST_TIMEOUT margin is for a slow device or one that is serving video."""
    code = self.http_status('pl.m3u', timeout)

    return None if code is None else code == 200

  def getservice(self, **params):
    return self.get('webui/api/service', format='json', **params)

  def getversion(self):
    return self.getservice(method='get_version')

  def getserver(self, **params):
    return self.get('server/api', **params)

  def getstatus(self):
    return self.getserver(method='get_status')

  def getnetwork(self):
    return self.getserver(method='get_network_connection_status')

  def get_content_id(self, infohash):
    """content_id matching an infohash, or None.

    The engine caches it, so the first time costs half a second and the rest are instant.
    It is a transformation, not a search: it returns something even for a made-up
    infohash, which means it is no use for checking that the content exists."""
    response = self.getserver(method='get_content_id', infohash=infohash)
    return self._get_response_key(response, 'content_id')

  def buscar(self, query='', page=0, page_size=200):
    """One page of the engine's own catalogue.

    It goes to /search and not to /server/api?method=search: the first asks for no token
    and the official app and AceServe serve it alike, checked against both."""
    return self.get('search', query=query, page=page, page_size=page_size)

  def getstream(self, **params):
    is_hls = params.pop('hls', False)
    apiurl = 'manifest.m3u8' if is_hls else 'getstream'

    version = self.version
    if version and version_tuple(version) < (3, 1, 29):
      params['sid'] = params.pop('pid')

    return self.get('ace/{0}'.format(apiurl), format='json', **params)

  def invalidate(self):
    """Forgets the cached version. Mandatory after stopping the engine."""
    self._version = None

  @property
  def host(self):
    # Already sanitised. Anyone building a url by hand must take it from here and
    # not re-read the setting, or it ends up pointing elsewhere than the addon.
    return self._host

  @property
  def port(self):
    return self._port

  @property
  def version(self):
    # Only a positive answer is cached. While the engine stays silent we must keep
    # asking (the startup loops wait for it to show up).
    if not self._version:
      response = self.getversion()
      version = self._get_response_key(response, 'version')
      # str(): whoever uses it joins it to text (detect_engine), and a service that is not an
      # engine may answer a number.
      self._version = str(version) if version else None

    return self._version

  @property
  def available(self):
    return bool(self.version)
