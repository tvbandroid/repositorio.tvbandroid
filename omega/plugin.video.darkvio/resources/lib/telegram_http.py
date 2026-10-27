# -*- coding: utf-8 -*-
"""HTTP/HTTPS-style local streaming bridge for Telegram files.

Kodi receives a normal HTTP URL on 127.0.0.1. The proxy asks TDLib for the
requested byte ranges and serves them as they become locally available.
It does not expose Telegram credentials or remote Telegram URLs.
"""
import os, threading, time, mimetypes, socket, socketserver, shutil, hashlib

from urllib.parse import urlparse, parse_qs, quote
import xbmc

IS_WINDOWS = (os.name == 'nt')

# Platform profiles. Both paths now use ONE active TDLib window at a time.
# Windows keeps the larger fix12-style window, but no longer queues a second
# 96 MB request before the first one is consumed. Android keeps the stable
# single-window model from fix13, with a larger window to reduce stalls on
# higher-bitrate Telegram videos.
if IS_WINDOWS:
    CHUNK = 4 * 1024 * 1024
    PREFETCH = 64 * 1024 * 1024
    DOWNLOAD_WINDOW = 128 * 1024 * 1024
    WAIT = 900.0
    RETRY_429 = 5
else:
    # Android: 48 MB window. Queue the next non-overlapping range before
    # the current window is consumed, so the buffer can refill aggressively.
    CHUNK = 1 * 1024 * 1024
    PREFETCH = 48 * 1024 * 1024
    DOWNLOAD_WINDOW = 48 * 1024 * 1024
    WAIT = 300.0
    RETRY_429 = 4
RETRY_429_DELAYS = (1.0, 2.0, 4.0, 8.0, 12.0)


class _Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 64

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._active_gets = 0
        self._active_lock = threading.RLock()

    def active_gets(self):
        with self._active_lock:
            return self._active_gets

    def inc_get(self):
        with self._active_lock:
            self._active_gets += 1

    def dec_get(self):
        with self._active_lock:
            self._active_gets = max(0, self._active_gets - 1)


class _Handler(socketserver.StreamRequestHandler):
    """Minimal HTTP/1.0 server tailored to Kodi's localhost curl client.

    Kodi's Stat/seek path is extremely sensitive to a stalled HEAD connection.
    Using a tiny raw HTTP parser avoids BaseHTTPRequestHandler buffering and
    makes HEAD/GET acceptance deterministic. Every request is one connection.
    """
    timeout = 120.0

    def setup(self):
        super().setup()
        try:
            self.connection.settimeout(self.timeout)
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except Exception:
            pass

    def _log(self, msg, level=xbmc.LOGDEBUG):
        try: xbmc.log('[DARKVIO][TELEGRAM][HTTP] ' + msg, level)
        except Exception: pass

    def _send(self, code, reason, headers=None, body=b''):
        lines=['HTTP/1.0 %d %s' % (int(code), reason)]
        for k,v in (headers or {}).items():
            lines.append('%s: %s' % (k, v))
        lines.append('Connection: close')
        lines.append('X-DARKVIO-Stream: 1')
        raw=('\r\n'.join(lines)+'\r\n\r\n').encode('iso-8859-1')
        self.wfile.write(raw)
        self.wfile.flush()
        if body:
            self.wfile.write(body)
            self.wfile.flush()

    def _parse_request(self):
        line=self.rfile.readline(65536)
        if not line:
            return None
        try:
            text=line.decode('iso-8859-1').strip()
            method,path,version=text.split(None,2)
        except Exception:
            return None
        headers={}
        while True:
            line=self.rfile.readline(65536)
            if not line or line in (b'\r\n', b'\n'):
                break
            try:
                k,v=line.decode('iso-8859-1').split(':',1)
                headers[k.strip().lower()]=v.strip()
            except Exception:
                continue
        return method.upper(),path,version,headers

    def _meta(self,path):
        parts=path.split('?',1)
        clean=parts[0]
        qs=parse_qs(parts[1] if len(parts)>1 else '')
        # The visible URL id is deliberately unique per playback. The real
        # TDLib file id is carried separately in ?fid= so Kodi never sees the
        # same /telegram/1241 path for every movie.
        try:
            fid=int(qs.get('fid',['0'])[0] or 0)
        except Exception:
            fid=0
        if not fid:
            try: fid=int(clean.rstrip('/').split('/')[-1])
            except Exception: return None
        name=qs.get('name',['video'])[0]
        persistent_id=qs.get('pid',[''])[0]
        try: size=int(qs.get('size',['0'])[0] or 0)
        except Exception: size=0
        stream_id=clean.rstrip('/').split('/')[-1]
        return fid,name,size,persistent_id,stream_id

    def _serve(self,method,path,headers):
        if path.startswith('/__darkvio_health'):
            self._send(200,'OK',{'Content-Type':'text/plain; charset=utf-8','Content-Length':'2'}, b'OK' if method != 'HEAD' else b'')
            return
        meta=self._meta(path)
        if not meta:
            self._send(404,'Not Found',{'Content-Length':'0'})
            return
        fid,name,total,persistent_id,stream_id=meta
        ctype=mimetypes.guess_type(name)[0] or ('video/x-matroska' if name.lower().endswith('.mkv') else 'video/mp4')
        # Kodi llama a Stat/HEAD inmediatamente despues de recibir la URL.
        # Nunca debemos consultar TDLib antes de responder a HEAD: una llamada
        # nativa lenta puede hacer que CCurlFile espere ~20s y deje Kodi con la
        # rueda azul. La URL ya contiene el tamano real en reproducciones DARKVIO.
        if method == 'HEAD' and total > 0:
            self._log('HEAD recibido file=%s size=%s' % (fid, total), xbmc.LOGINFO)
            self._send(200,'OK',{
                'Content-Type':ctype,
                'Accept-Ranges':'bytes',
                'Content-Length':str(total),
                'Cache-Control':'no-store, no-cache, must-revalidate',
            })
            return
        if total<=0:
            total=_get_total_size(fid,persistent_id)
        if total<=0:
            self._send(404,'Not Found',{'Content-Length':'0'})
            return
        if method == 'HEAD':
            self._log('HEAD recibido tras consulta TDLib file=%s size=%s' % (fid, total), xbmc.LOGINFO)
            self._send(200,'OK',{
                'Content-Type':ctype,
                'Accept-Ranges':'bytes',
                'Content-Length':str(total),
                'Cache-Control':'no-store, no-cache, must-revalidate',
            })
            return
        if method != 'GET':
            self._send(405,'Method Not Allowed',{'Allow':'GET, HEAD','Content-Length':'0'})
            return

        start,end=0,total-1
        rh=headers.get('range','')
        if rh.startswith('bytes='):
            spec=rh[6:].split(',',1)[0].strip()
            try:
                a,b=(spec.split('-',1)+[''])[:2]
                if a=='':
                    n=int(b)
                    if n<=0: raise ValueError()
                    start=max(0,total-n); end=total-1
                else:
                    start=int(a); end=int(b) if b else total-1
                    if start<0 or start>=total: raise ValueError()
                    end=min(end,total-1)
                    if end<start: raise ValueError()
            except Exception:
                self._send(416,'Range Not Satisfiable',{'Content-Range':'bytes */%d' % total,'Content-Length':'0'})
                return
        length=end-start+1
        self._log('GET recibido file=%s range=%s-%s len=%s' % (fid,start,end,length), xbmc.LOGINFO)
        # Warm up a small initial playback buffer on both platforms before
        # allowing Kodi to decode. This avoids the 10-18s startup starvation
        # seen on Windows while keeping the startup buffer modest.
        if length > 0:
            try:
                warm_window=min(DOWNLOAD_WINDOW, total-start)
                _request_range_retry(fid, start, warm_window, persistent_id)
                warm_target=min((64 if IS_WINDOWS else 48) * 1024 * 1024, warm_window)
                warm_path, warm_ready=_wait_local(
                    fid, start, start + warm_target, persistent_id
                )
                if warm_ready < start + warm_target:
                    self._log(
                        'buffer inicial insuficiente file=%s ready=%s target=%s'
                        % (fid, warm_ready, start + warm_target),
                        xbmc.LOGWARNING
                    )
                    self._send(
                        503, 'Service Unavailable',
                        {'Content-Length':'0', 'Retry-After':'1'}
                    )
                    return
                self._log(
                    'buffer inicial listo file=%s (%d MB)'
                    % (fid, warm_target // (1024 * 1024)),
                    xbmc.LOGINFO
                )
            except Exception as e:
                self._log('buffer inicial: %s' % e, xbmc.LOGWARNING)
                self._send(
                    503, 'Service Unavailable',
                    {'Content-Length':'0', 'Retry-After':'1'}
                )
                return

        status=206 if rh else 200
        out_headers={
            'Content-Type':ctype,
            'Accept-Ranges':'bytes',
            'Content-Length':str(length),
            'Cache-Control':'no-store, no-cache, must-revalidate',
        }
        if status == 206:
            out_headers['Content-Range']='bytes %d-%d/%d' % (start,end,total)
        self._send(status,'Partial Content' if status==206 else 'OK',out_headers)
        sent=0; pos=start
        try:
            active_start=None; active_end=None; next_requested=False
            local_path=''
            while sent<length:
                want=min(CHUNK,length-sent)
                if active_end is None or pos >= active_end:
                    active_start=pos
                    window=min(DOWNLOAD_WINDOW,total-pos)
                    active_end=pos+window
                    _request_range_retry(fid,pos,window,persistent_id)
                    next_requested=False
                    self._log('ventana TDLib activa %s-%s (%d MB, modo=%s)' % (
                        active_start,active_end-1,window//(1024*1024),
                        'WINDOWS-SEQUENTIAL' if IS_WINDOWS else 'ANDROID-EARLY-REFILL'), xbmc.LOGINFO)
                local_path,ready=_wait_local(fid,pos,pos+want,persistent_id)
                # Android schedules the following, non-overlapping range as soon
                # as ~60% of this window is available, while the white buffer
                # still has room to stay ahead of playback. Windows unchanged.
                if (not IS_WINDOWS and not next_requested and active_end < total
                        and ready >= active_start + int((active_end-active_start)*0.60)):
                    next_start=active_end
                    next_window=min(DOWNLOAD_WINDOW,total-next_start)
                    try:
                        _request_range_retry(fid,next_start,next_window,persistent_id)
                        next_requested=True
                        self._log('Android refill anticipado: siguiente ventana desde %s (%d MB)' %
                                  (next_start,next_window//(1024*1024)), xbmc.LOGINFO)
                    except Exception as e:
                        self._log('Android refill anticipado aplazado: %s' % e, xbmc.LOGWARNING)
                if not local_path:
                    raise IOError('TDLib no devolvió ruta local')

                # Las ventanas son contiguas y no se solapan. En Android la
                # siguiente puede estar ya programada antes de consumir la actual.
                available=max(0,ready-pos)
                if available<=0:
                    continue
                take=min(available,length-sent)
                take=min(take,max(0,active_end-pos))
                if take<=0:
                    continue
                with open(local_path,'rb') as f:
                    f.seek(pos)
                    data=f.read(take)
                if not data:
                    raise IOError('Lectura vacía')
                self.wfile.write(data); self.wfile.flush()
                got=len(data); sent+=got; pos+=got
                if got<take:
                    break
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            self._log('cliente cerro/interrumpio file=%s range=%s-%s enviado=%s' % (fid,start,end,sent), xbmc.LOGDEBUG)
        except Exception as e:
            self._log('GET file=%s error=%s enviado=%s' % (fid,e,sent), xbmc.LOGWARNING)

    def handle(self):
        try:
            req=self._parse_request()
            if not req:
                return
            method,path,version,headers=req
            self._log('REQUEST %s %s' % (method, path), xbmc.LOGINFO)
            counted = (method == 'GET')
            if counted:
                try: self.server.inc_get()
                except Exception: pass
            try:
                self._serve(method,path,headers)
            finally:
                if counted:
                    try:
                        self.server.dec_get()
                        self._log('GET finalizado; activos=%d' % self.server.active_gets(), xbmc.LOGINFO)
                    except Exception: pass
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            pass
        except Exception as e:
            self._log('request error: %s' % e, xbmc.LOGWARNING)

_download_state = {}
_download_state_lock = threading.RLock()
# TDLib permite solo una descarga concurrente por archivo. Todas las llamadas
# nativas pasan por este lock para impedir carreras entre HEAD/GET/seek.
_tdlib_io_lock = threading.RLock()


def _range_covered(ranges, start, end):
    for a,b in ranges:
        if a <= start and b >= end:
            return True
        if a > start:
            break
    return False


def _request_range_retry(fid, offset, limit, persistent_id=''):
    """Request exactly one sequential TDLib download window.

    The Android and Windows implementations intentionally share the same
    serialized native call now. The only platform-specific difference is the
    window size. This prevents Windows from queueing two overlapping ranges
    for the same Telegram file.
    """
    key=(int(fid), str(persistent_id or ''))
    start=int(offset or 0)
    end=start+max(0,int(limit or 0))-1
    if end < start:
        return True
    with _tdlib_io_lock:
        with _download_state_lock:
            state=_download_state.setdefault(key, {'ranges': [], 'last_error': None})
            if _range_covered(state['ranges'], start, end):
                return True
        last=None
        for attempt in range(RETRY_429):
            try:
                result=_request_range(fid,start,limit,persistent_id)
                with _download_state_lock:
                    st=_download_state.setdefault(key, {'ranges': [], 'last_error': None})
                    ranges=list(st.get('ranges', [])); ranges.append((start,end)); ranges.sort()
                    merged=[]
                    for a,b in ranges:
                        if not merged or a > merged[-1][1]+1:
                            merged.append([a,b])
                        else:
                            merged[-1][1]=max(merged[-1][1],b)
                    st['ranges']=[tuple(x) for x in merged]
                    st['last_error']=None
                return result
            except Exception as e:
                last=e
                txt=str(e).lower()
                if '429' not in txt and 'too many' not in txt and 'rate' not in txt:
                    with _download_state_lock:
                        st=_download_state.get(key)
                        if st: st['last_error']=str(e)
                    raise
                delay=RETRY_429_DELAYS[min(attempt,len(RETRY_429_DELAYS)-1)]
                try:
                    xbmc.log('[DARKVIO][TELEGRAM][HTTP] 429; reintento %d/%d en %.1fs' % (attempt+1,RETRY_429,delay), xbmc.LOGWARNING)
                except Exception:
                    pass
                time.sleep(delay)
        with _download_state_lock:
            st=_download_state.get(key)
            if st: st['last_error']=str(last)
        if last:
            raise last
        return None


def _cleanup_tdlib_media(session):
    """Delete Telegram media cached by TDLib after playback ends.

    TDLib may place streamed video under tdlib_files/videos instead of
    tdlib_files/temp. DARKVIO serves the video through its local HTTP bridge,
    so these media files are no longer needed after the player exits. Cleanup
    is performed only after the HTTP server has released active GET requests.
    """
    if not session:
        return 0
    root=os.path.join(session, 'tdlib_files')
    media_dirs=(os.path.join(root, 'temp'), os.path.join(root, 'videos'))
    removed=0
    for media_dir in media_dirs:
        try:
            os.makedirs(media_dir, exist_ok=True)
        except Exception:
            pass
        for attempt in range(8):
            try:
                names=os.listdir(media_dir)
            except Exception:
                names=[]
            if not names:
                break
            for name in names:
                path=os.path.join(media_dir, name)
                try:
                    if os.path.isdir(path) and not os.path.islink(path):
                        shutil.rmtree(path, ignore_errors=False)
                    else:
                        os.remove(path)
                    removed += 1
                except Exception:
                    pass
            time.sleep(0.35)
    if removed:
        try:
            xbmc.log('[DARKVIO][TELEGRAM][CLEANUP] Eliminados %d elementos de tdlib_files/temp y tdlib_files/videos' % removed, xbmc.LOGINFO)
        except Exception:
            pass
    return removed

# Compatibility name used by older code paths.
def _cleanup_tdlib_temp(session):
    return _cleanup_tdlib_media(session)

class TelegramHTTPServer:
    """Persistent local HTTP server for one Telegram playback session.

    The resolver deliberately closes its TDLib client after listing sources so
    another Kodi plugin invocation can safely use the same TDLib database.
    Playback therefore gets its OWN TDLib client, owned by this server, and
    keeps it alive for the complete HTTP stream.
    """
    def __init__(self):
        self._server=None
        self._thread=None
        self._watcher=None
        self._bridge=None
        self._lock=threading.RLock()
        self._stopping=False
        self._generation=0
        self._session=''

    def start(self):
        with self._lock:
            if self._server:
                return
            self._stopping=False
            # Resolver y reproducción usan EXACTAMENTE el mismo bloqueo y la
            # misma carpeta de sesión real de TDLib. Primero tomamos el bloqueo
            # y solo después creamos el cliente nativo, evitando una carrera en
            # la que dos procesos abran td.binlog a la vez.
            from .telegram_bridge import TelegramBridge
            from .telegram_process_lock import TDLibProcessLock
            probe=TelegramBridge()
            session=probe.m.session
            self._session=session
            self._process_lock=TDLibProcessLock(os.path.join(session,'tdlib.process.lock'), 5.0)
            if not self._process_lock.acquire():
                try: probe.close()
                except Exception: pass
                self._process_lock=None
                raise RuntimeError('Otra instancia está usando la sesión de Telegram')
            # Limpiar restos de reproducciones anteriores antes de reutilizar
            # la carpeta de archivos temporales. No toca tdlib ni la cuenta.
            _cleanup_tdlib_temp(session)
            # probe has not started TDLib yet; it only loaded the native library.
            self._bridge=probe
            state=self._bridge.auth_state()
            if state != 'ready':
                self.stop()
                raise RuntimeError('Telegram no está autorizado (estado %s)' % state)

            # IMPORTANT: the HTTP server must survive after the plugin route
            # returns. A daemon thread would be killed when the plugin process
            # exits, which is exactly the symptom of playback starting and then
            # stopping a few seconds later.
            for port in range(38990,39061):
                try:
                    self._server=_Server(('127.0.0.1',port),_Handler)
                    self._server.timeout=2.0
                    self._server.darkvio_owner=self
                    break
                except OSError:
                    self._server=None
            if not self._server:
                self.stop()
                raise OSError('No hay puerto HTTP local disponible para Telegram')
            self._thread=threading.Thread(target=self._server.serve_forever,name='DARKVIO-TelegramHTTP',daemon=True)
            self._thread.start()
            # Yield briefly so the listening socket is accepting before the
            # control request returns the URL to Kodi.
            time.sleep(0.05)
            # La vigilancia de reproducción se inicia por sesión desde url().
            # Esto evita que el watcher de una película anterior pueda cerrar
            # un servidor que ya está siendo reutilizado por una nueva fuente.
            xbmc.log('[DARKVIO][TELEGRAM][HTTP] servidor local en 127.0.0.1:%d (HTTP/1.0, Range, modo=%s, ventanas=%dMB)' % (self.port(), 'WINDOWS-COMPAT' if IS_WINDOWS else 'ANDROID-SEQUENTIAL', DOWNLOAD_WINDOW//(1024*1024)), xbmc.LOGINFO)

    def port(self):
        with self._lock:
            if not self._server:
                raise RuntimeError('Servidor HTTP de reproducción no está iniciado')
            return int(self._server.server_address[1])

    def bridge(self):
        with self._lock:
            if self._bridge is None:
                raise RuntimeError('TDLib de reproducción no está disponible')
            return self._bridge

    def url(self,file_id,name='video',size=0,persistent_id='',chat_id=0,message_id=0):
        self.start()
        with self._lock:
            self._generation += 1
            generation = self._generation
        port=self.port()
        current_id=int(file_id)
        current_pid=str(persistent_id or '')
        # Los file_id de TDLib son propios de una instancia. Si la fuente se
        # obtuvo en otro proceso, recuperamos el archivo desde chat+mensaje
        # en el cliente TDLib de reproducción y usamos su file_id actual.
        if chat_id and message_id:
            f=self._bridge.file_from_message(int(chat_id),int(message_id)) or {}
            current_id=int(f.get('id') or current_id)
            current_pid=str(f.get('persistent_id') or current_pid)
            if f.get('size'):
                size=int(f.get('size'))
        extra='&pid=%s' % quote(current_pid,safe='') if current_pid else ''
        # Kodi 21 puede conservar un punto de reanudación para una URL HTTP
        # local aunque el contenido sea una reproducción nueva.  Un identificador
        # único por sesión evita que Telegram herede el resume point de una
        # reproducción anterior del mismo archivo.
        session_id='%d-%d-%d' % (generation, int(time.time() * 1000), os.getpid())
        # Unique Kodi-facing stream id. Telegram's TDLib file id (for example
        # 1241) is NOT suitable as the URL identity because different movies
        # can arrive with the same logical file id after a TDLib/session change.
        # The title/message/size/session are folded into a stable per-playback
        # token so Kodi treats every selected movie as a new item.
        stream_seed='%s|%s|%s|%s|%s|%s' % (session_id, current_id, name or '', size or 0, chat_id or 0, message_id or 0)
        stream_id=hashlib.sha1(stream_seed.encode('utf-8','replace')).hexdigest()[:20]
        # Solicitar la primera ventana antes de entregar la URL evita que
        # Kodi llegue a un objeto TDLib sin descarga iniciada. La llamada es
        # corta (downloadFile solo programa la descarga); el GET hace la espera
        # real por el prefijo descargado.
        # Cada URL representa una nueva sesión. El watcher asociado a una
        # reproducción anterior queda invalidado y ya no puede llamar a stop()
        # sobre esta reproducción nueva.
        self._watcher=threading.Thread(target=self._watch_playback, args=(generation,), name='DARKVIO-TelegramWatch-%d' % generation, daemon=True)
        self._watcher.start()
        return 'http://127.0.0.1:%d/telegram/%s?fid=%d&name=%s&size=%d%s&sid=%s&start=0' % (port,stream_id,current_id,quote(name or 'video'),int(size or 0),extra,quote(session_id,safe=''))

    def stop(self):
        # Esta función puede ser llamada desde el hilo de control del servicio
        # mientras Kodi acaba de cerrar el reproductor. shutdown() de
        # socketserver puede esperar al bucle serve_forever y, si se ejecuta
        # aquí, puede contribuir a la rueda azul. Desacoplamos toda la limpieza
        # pesada a un hilo daemon y dejamos el estado lógico cerrado de forma
        # inmediata.
        with self._lock:
            if self._stopping and self._server is None:
                return
            self._stopping=True
            self._generation += 1
            srv=self._server
            self._server=None
            th=self._thread
            self._thread=None
            br=self._bridge
            self._bridge=None
            lock=getattr(self,'_process_lock',None)
            self._process_lock=None
            session=self._session
            self._session=''
        worker=threading.Thread(
            target=self._finish_stop,
            args=(srv,th,br,lock,session),
            name='DARKVIO-TelegramStop',
            daemon=True
        )
        worker.start()

    def _finish_stop(self,srv,th,br,lock,session):
        try:
            if srv:
                # Do not destroy TDLib/local files while Kodi still has an
                # outstanding HTTP GET. A manual STOP can leave curl closing
                # asynchronously; waiting briefly here prevents the
                # 'No such file or directory' race and the blue-wheel hang.
                deadline = time.time() + 5.0
                while time.time() < deadline:
                    try:
                        active = srv.active_gets()
                    except Exception:
                        active = 0
                    if active <= 0:
                        break
                    xbmc.log('[DARKVIO][TELEGRAM][HTTP] esperando GET activos=%d antes de cerrar' % active, xbmc.LOGINFO)
                    time.sleep(0.10)
                try: srv.shutdown()
                except Exception: pass
                try: srv.server_close()
                except Exception: pass
            if th and th.is_alive() and th is not threading.current_thread():
                try: th.join(timeout=0.25)
                except Exception: pass
            if br:
                try: br.close()
                except Exception: pass
            if lock:
                try: lock.close()
                except Exception: pass
            _cleanup_tdlib_temp(session)
            with _download_state_lock:
                _download_state.clear()
            xbmc.log('[DARKVIO][TELEGRAM][HTTP] servidor detenido, TDLib liberado y temporales limpiados', xbmc.LOGINFO)
        finally:
            with self._lock:
                self._stopping=False

    def _watch_playback(self, generation):
        # Allow a short window for Kodi to actually attach the player after
        # Player.play(). If it never starts, release TDLib instead of leaving
        # td.binlog locked forever.
        player=xbmc.Player()
        deadline=time.time()+30
        started=False
        while time.time()<deadline and not self._stopping:
            with self._lock:
                if generation != self._generation:
                    return
            try:
                if player.isPlaying():
                    started=True
                    break
            except Exception:
                pass
            time.sleep(.25)
        if not started:
            with self._lock:
                if generation != self._generation:
                    return
            self.stop()
            return
        # Keep the TDLib client alive for the complete HTTP playback.
        while not self._stopping:
            with self._lock:
                if generation != self._generation:
                    return
            try:
                if not player.isPlaying():
                    break
            except Exception:
                break
            time.sleep(1.0)
        # Give Kodi a moment to finish outstanding HTTP reads before closing
        # TDLib and releasing the database lock.
        time.sleep(.5)
        with self._lock:
            if generation != self._generation:
                return
        self.stop()

server=TelegramHTTPServer()

def _bridge():
    """Return the playback TDLib bridge owned by the HTTP server."""
    return server.bridge()

def _get_total_size(fid,persistent_id=''):
    try:
        with _tdlib_io_lock:
            x=_bridge().file_info(fid,persistent_id) or {}
        return int(x.get('size') or 0)
    except Exception as e:
        xbmc.log('[DARKVIO][TELEGRAM][HTTP] get_file %s: %s' % (fid,e), xbmc.LOGWARNING)
        return 0

def _request_range(fid,offset,limit,persistent_id=''):
    try:
        with _tdlib_io_lock:
            return _bridge().request_download(fid,offset,limit,persistent_id)
    except Exception as e:
        xbmc.log('[DARKVIO][TELEGRAM][HTTP] request_download %s: %s' % (fid,e), xbmc.LOGWARNING)
        # Do not swallow rate-limit/transient errors: the retry layer needs
        # the exception to decide whether to retry without restarting TDLib.
        raise

def _wait_local(fid,offset,needed=None,persistent_id=''):
    """Wait until the requested byte position is actually readable."""
    if needed is None:
        needed=offset
        offset=0
    deadline=time.time()+WAIT
    path=''
    while time.time()<deadline:
        try:
            with _tdlib_io_lock:
                x=_bridge().file_info(fid,persistent_id) or {}
                loc=x.get('local') or {}
                path=loc.get('path') or path
                if loc.get('is_downloading_completed'):
                    total=int(x.get('size') or 0)
                    if path and total>=needed:
                        return path,total
                try:
                    prefix=_bridge().downloaded_prefix(fid,offset)
                except Exception:
                    dl_offset=int(loc.get('download_offset') or 0)
                    dl_prefix=int(loc.get('downloaded_prefix_size') or 0)
                    prefix=(dl_offset+dl_prefix-offset) if dl_offset<=offset else 0
                if path and prefix>=needed-offset:
                    return path,needed
        except Exception:
            pass
        time.sleep(0.10 if IS_WINDOWS else 0.15)
    return path,0

