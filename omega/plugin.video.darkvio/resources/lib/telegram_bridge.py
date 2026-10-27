# -*- coding: utf-8 -*-
"""Telegram propio de DARKVIO mediante TDLib JSON + ctypes. Sesión separada."""
from .tdjson import TDLibManager, TDJsonError
class BridgeError(Exception): pass
class TelegramBridge:
    def __init__(self): self.m=TDLibManager()
    def available(self): return self.m.available()
    def ensure_native(self): return self.m.ensure_native()
    def native_available(self): return self.m.native_available()
    def error(self): return self.m.error()
    def close(self):
        try: self.m.client.close()
        except Exception: pass
    def reset(self):
        try: self.m.reset_client()
        except Exception as e: raise BridgeError(str(e))
    def _c(self):
        try:self.m.client.start(); return self.m.client
        except Exception as e: raise BridgeError(str(e))
    def auth_state(self):
        if not self.m.native_available():
            return "unavailable"
        c=self._c(); s=c.state();
        try:
            import xbmc
            xbmc.log('[DARKVIO][TELEGRAM] TDLib raw_state=%r error=%r' % (s, getattr(c,'last_error',None)), xbmc.LOGINFO)
        except Exception:
            pass
        mp = {
            'authorizationStateWaitPhoneNumber':'wait_phone',
            'authorizationStateWaitCode':'wait_code',
            'authorizationStateWaitPassword':'wait_password',
            'authorizationStateReady':'ready',
            'authorizationStateLoggingOut':'logging_out',
            'authorizationStateClosing':'closing',
            'authorizationStateClosed':'closed',
            'authorizationStateWaitTdlibParameters':'initializing',
            'authorizationStateWaitEncryptionKey':'wait_encryption_key'
        }
        return mp.get(s, s)
    def submit_phone(self,phone):
        try:return self._c().auth_phone(phone)
        except Exception as e: raise BridgeError(str(e))
    def submit_code(self,code):
        try:return self._c().auth_code(code)
        except Exception as e: raise BridgeError(str(e))
    def submit_password(self,password):
        try:return self._c().auth_password(password)
        except Exception as e: raise BridgeError(str(e))
    def logout(self):
        try:
            self.m.logout_and_reset()
            return True
        except Exception as e:
            raise BridgeError(str(e))
    def chats(self):
        c=self._c(); out=[]
        for cid in c.chats(100):
            try:
                x=c.chat(cid); out.append({'id':cid,'title':x.get('title','')})
            except Exception: pass
        return out
    def search(self,query,limit=100,chat_id=None):
        c=self._c()
        try:
            import xbmc
            xbmc.log('[DARKVIO][TELEGRAM] Buscando globalmente: %r' % query, xbmc.LOGINFO)
        except Exception:
            pass
        msgs=c.search_messages(query,limit) if chat_id is None else c.search_chat_messages(int(chat_id),query,limit); out=[]
        for m in msgs:
            content=m.get('content',{}); typ=content.get('@type',''); f=None; name=''; size=0
            caption=''
            cap=content.get('caption') or {}
            if isinstance(cap,dict):
                caption=(cap.get('text') or '').strip()
            if typ=='messageVideo':
                v=content.get('video',{}) or {}; f=v.get('video',{}) or {}; name=v.get('file_name','') or 'video'; size=f.get('size',0) if isinstance(f,dict) else 0
            elif typ=='messageDocument':
                d=content.get('document',{}) or {}; f=d.get('document',{}) or {}; name=d.get('file_name','') or 'document'; size=f.get('size',0) if isinstance(f,dict) else 0
                mime=str(d.get('mime_type') or '').lower()
                ext=name.lower().rsplit('.',1)[-1] if '.' in name else ''
                video_ext={'mkv','mp4','avi','mov','wmv','m4v','ts','m2ts','webm','mpg','mpeg','flv','3gp'}
                # Telegram solo aporta archivos de vídeo reproducibles; se
                # excluyen explícitamente ZIP/RAR y cualquier documento no vídeo.
                if ext in {'zip','rar','7z','tar','gz','bz2'} or (mime and not mime.startswith('video/')) or (not mime and ext not in video_ext):
                    continue
            else: continue
            fid=f.get('id') if isinstance(f,dict) else None
            persistent_id=f.get('persistent_id','') if isinstance(f,dict) else ''
            if fid is None: continue
            try: ch=c.chat(m.get('chat_id',0)); title=ch.get('title','')
            except Exception:title=''
            out.append({'file_id':fid,'persistent_id':persistent_id,'chat_id':m.get('chat_id'), 'chat_title':title,'message_id':m.get('id'),'filename':name,'file_name':name,'size':size,'file_size':size,'caption':caption,'content_type':typ})
        return out[:limit]
    def file_info(self,file_id=None,persistent_id=None):
        c=self._c()
        if persistent_id:
            return c.get_file_persistent(str(persistent_id))
        return c.get_file(int(file_id))

    def file_from_message(self,chat_id,message_id):
        c=self._c()
        msg=c.get_message(int(chat_id),int(message_id)) or {}
        content=msg.get('content') or {}
        typ=content.get('@type','')
        obj=None
        if typ=='messageVideo':
            obj=(content.get('video') or {}).get('video') or {}
        elif typ=='messageDocument':
            obj=(content.get('document') or {}).get('document') or {}
        elif typ=='messageAnimation':
            obj=(content.get('animation') or {}).get('animation') or {}
        fid=obj.get('id') if isinstance(obj,dict) else None
        if not fid:
            raise BridgeError('El mensaje de Telegram ya no contiene el archivo multimedia')
        return obj

    def request_download(self,file_id,offset=0,limit=0,persistent_id=None):
        try:
            c=self._c()
            current_id=int(file_id)
            if persistent_id:
                f=c.get_file_persistent(str(persistent_id)) or {}
                current_id=int(f.get('id') or current_id)
            return c.download(current_id,offset,limit,False)
        except Exception as e:
            raise BridgeError(str(e))

    def downloaded_prefix(self,file_id,offset=0):
        c=self._c()
        return c.get_file_downloaded_prefix_size(int(file_id),int(offset))

    def delete_cached_file(self,file_id,persistent_id=None):
        """Delete only the local TDLib cache for a Telegram file."""
        try:
            c=self._c()
            current_id=int(file_id)
            if persistent_id:
                f=c.get_file_persistent(str(persistent_id)) or {}
                current_id=int(f.get('id') or current_id)
            return c.delete_file(current_id)
        except Exception as e:
            raise BridgeError(str(e))

    def stream_url(self,file_id,name='',size=0,persistent_id='',chat_id=0,message_id=0):
        from .telegram_http import server
        return server.url(int(file_id), name or 'video', int(size or 0), persistent_id, int(chat_id or 0), int(message_id or 0))
bridge=TelegramBridge()
