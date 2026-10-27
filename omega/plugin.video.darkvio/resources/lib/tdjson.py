# -*- coding: utf-8 -*-
"""Minimal TDLib JSON client for Kodi. Native tdjson is loaded with ctypes."""
import ctypes, ctypes.util, json, os, platform, threading, time, uuid, secrets, shutil
import xbmcaddon, xbmcvfs

ADDON=xbmcaddon.Addon()

def xbmc_log(msg, level=1):
    try:
        import xbmc
        xbmc.log(msg, xbmc.LOGINFO if level == 1 else xbmc.LOGWARNING)
    except Exception:
        pass

class TDJsonError(Exception): pass

class TDJsonClient:
    _DARKVIO_TDLIB_LOADER_BUILD = "fix10-fd-no-null-namespace"

    def __init__(self, base_dir, api_id, api_hash):
        self.base_dir=base_dir; self.api_id=int(api_id); self.api_hash=str(api_hash)
        self.lib=None
        self.client=None; self.stop_event=threading.Event(); self.thread=None
        self.lock=threading.RLock(); self.pending={}; self.auth_state=None
        self._started=False
        self._encryption_sent=False
        self.last_error=None

    def _load_library(self):
        """Load the TDLib JSON runtime for the current Kodi host.

        Kodi on Android reports itself as Linux, so Android detection must be
        explicit.  We detect the ABI from Android system properties first and
        fall back to Python/platform information.  The native runtime is kept
        in the addon profile, which means one DARKVIO ZIP can run on Windows
        x64 and the supported Android ABIs without shipping every large .so
        inside the addon itself.
        """
        import subprocess
        base=xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
        profile=xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
        sysname=platform.system().lower()
        mach=(platform.machine() or '').lower()

        def is_android():
            if 'ANDROID_ROOT' in os.environ or 'ANDROID_DATA' in os.environ:
                return True
            if os.path.exists('/system/bin/app_process') or os.path.exists('/system/bin/linker'):
                return True
            # Kodi Android normally exposes android as the OS name through
            # Java/system properties even when Python reports Linux.
            try:
                if os.path.exists('/system/build.prop'):
                    return True
            except Exception:
                pass
            return False

        def getprop(name):
            try:
                out=subprocess.check_output(['getprop', name], stderr=subprocess.DEVNULL, timeout=2)
                return out.decode('utf-8','ignore').strip()
            except Exception:
                return ''

        def detect_android_abi():
            vals=[]
            for key in ('ro.product.cpu.abilist','ro.product.cpu.abilist32','ro.product.cpu.abi'):
                v=getprop(key)
                if v:
                    vals.extend([x.strip().lower() for x in v.split(',') if x.strip()])
            # Prefer the ABI of the running Kodi/Python process, not merely
            # the device ABI list. A 64-bit Android box may expose both
            # arm64-v8a and armeabi-v7a; a 32-bit Kodi process MUST load the
            # 32-bit library.
            import struct
            process_32bit = (struct.calcsize('P') == 4)
            # A 32-bit Kodi process on an ARM64 device can still report
            # aarch64 from the platform layer. If the process is 32-bit and
            # an ARM ABI is exposed, prefer the 32-bit ABI unconditionally.
            if process_32bit and ('arm' in mach or any(x.startswith('arm') or x == 'armeabi-v7a' for x in vals)):
                preferred=['armeabi-v7a','armv7l','armeabi']
            elif 'aarch64' in mach or 'arm64' in mach:
                preferred=['arm64-v8a','aarch64']
            elif mach in ('armv7l','armv7','arm','arm32') or mach.startswith('armv7'):
                preferred=['armeabi-v7a','armv7l','armeabi']
            elif 'x86_64' in mach or 'amd64' in mach:
                preferred=['x86_64']
            elif mach in ('i686','i386','x86'):
                preferred=['x86']
            else:
                preferred=[]
            for x in preferred:
                if x in vals or x.replace('-','_') in vals:
                    return {'arm64-v8a':'arm64','aarch64':'arm64','armeabi-v7a':'armv7','armv7l':'armv7','armeabi':'armv7','x86_64':'x86_64','x86':'x86'}.get(x,x)
            for x in vals:
                if x in ('arm64-v8a','aarch64'):
                    return 'arm64'
                if x in ('armeabi-v7a','armeabi','armv7l'):
                    return 'armv7'
                if x in ('x86_64','amd64'):
                    return 'x86_64'
                if x in ('x86','i686','i386'):
                    return 'x86'
            if 'aarch64' in mach or 'arm64' in mach: return 'arm64'
            if 'armv7' in mach or mach.startswith('arm'): return 'armv7'
            if 'x86_64' in mach or 'amd64' in mach: return 'x86_64'
            if 'x86' in mach or 'i686' in mach: return 'x86'
            return ''

        android=is_android()
        if android:
            arch=detect_android_abi()
            abi_map={'arm64':'arm64-v8a','armv7':'armeabi-v7a','x86_64':'x86_64','x86':'x86'}
            abi=abi_map.get(arch,arch or 'unknown')
            native_dir=os.path.join(profile,'native','android',abi)
            os.makedirs(native_dir,exist_ok=True)
            names=['libtdjson.so']
            # Search both the new profile location and addon-bundled fallback.
            dirs=[os.path.join(base,'resources','bin','android',abi),
                  os.path.join(base,'resources','bin','android',arch),
                  native_dir,
                  os.path.join(base,'resources','bin')]
            candidates=[os.path.join(d,n) for d in dirs for n in names]
            for pth in candidates:
                if os.path.isfile(pth):
                    # Android's linker namespaces can reject a .so loaded by
                    # absolute path from Kodi's userdata directory.  First try
                    # the Android fd-based loader: it asks bionic to open the
                    # library from an already-open file descriptor instead of
                    # resolving the file through the restricted pathname.
                    if os.path.basename(pth) == 'libtdjson.so':
                        try:
                            lib = self._android_load_fd(pth)
                            if lib is not None:
                                xbmc_log('[DARKVIO][TDLIB] Android ABI=%s TDLib cargada mediante android_dlopen_ext(FD): %s' % (abi,pth))
                                return self._bind(lib)
                        except Exception as e:
                            self._last_android_error = str(e)
                            xbmc_log('[DARKVIO][TDLIB] android_dlopen_ext(FD) fallo: %s' % e, 2)
                    if arch != 'armv7':
                        try:
                            lib=ctypes.CDLL(pth)
                            xbmc_log('[DARKVIO][TDLIB] Android ABI=%s TDLib=%s' % (abi,pth))
                            return self._bind(lib)
                        except Exception as e:
                            self._last_android_error = str(e)
                            xbmc_log('[DARKVIO][TDLIB] Biblioteca Android encontrada pero no carga: %s' % e, 2)
            # ARMv7 is bundled with DARKVIO so this ABI does not depend on
            # downloading a .so into Android shared storage. Other ABIs keep
            # the existing on-demand bootstrap unchanged.
            if arch != 'armv7':
                self._bootstrap_android_tdlib(native_dir, arch)
            for pth in [os.path.join(native_dir,'libtdjson.so')]:
                if os.path.isfile(pth):
                    try:
                        lib=ctypes.CDLL(pth)
                        xbmc_log('[DARKVIO][TDLIB] Android ABI=%s TDLib instalada y cargada' % abi)
                        return self._bind(lib)
                    except Exception as e:
                        raise TDJsonError('TDLib Android %s se descargó pero no pudo cargarse: %s' % (abi,e))
            detail = getattr(self, '_last_android_error', '')
            if detail:
                raise TDJsonError('TDLib Android %s no pudo cargarse: %s' % (abi, detail))
            raise TDJsonError('TDLib Android %s no está disponible; biblioteca ARMv7 no pudo cargarse' % abi)

        if sysname.startswith('win'):
            import struct
            process_32bit = (struct.calcsize('P') == 4)
            arch = 'x86' if process_32bit else 'x86_64'
            native_dir = os.path.join(profile,'native','windows',arch)
            os.makedirs(native_dir, exist_ok=True)
            pth = os.path.join(native_dir,'tdjson.dll')
            if not os.path.isfile(pth):
                self._bootstrap_windows_tdlib(native_dir, arch)
            if os.path.isfile(pth):
                try:
                    lib=ctypes.CDLL(pth)
                    xbmc_log('[DARKVIO][TDLIB] Windows %s TDLib=%s' % (arch,pth))
                    return self._bind(lib)
                except Exception as e:
                    raise TDJsonError('No se pudo cargar TDLib Windows %s: %s' % (arch,e))
            raise TDJsonError('No se pudo instalar TDLib Windows %s' % arch)
        elif sysname.startswith('linux'):
            if 'aarch64' in mach or 'arm64' in mach: arch='arm64'
            elif 'armv7' in mach or mach.startswith('arm'): arch='armv7'
            elif 'x86_64' in mach or 'amd64' in mach: arch='x86_64'
            elif 'x86' in mach or 'i686' in mach: arch='x86'
            else: arch=mach
            names=['libtdjson.so','tdjson.so']
            dirs=[os.path.join(base,'resources','bin','linux',arch),os.path.join(base,'resources','bin')]
        else:
            names=['libtdjson.dylib','tdjson.dylib']; dirs=[os.path.join(base,'resources','bin','macos'),os.path.join(base,'resources','bin')]

        candidates=[os.path.join(d,n) for d in dirs for n in names]
        for pth in candidates:
            if os.path.isfile(pth):
                try:
                    lib=ctypes.CDLL(pth)
                    return self._bind(lib)
                except Exception as e:
                    raise TDJsonError('No se pudo cargar TDLib: %s' % e)
        raise TDJsonError('Falta tdjson nativo para %s/%s' % (sysname,mach))

    def _android_load_fd(self, path):
        """Load ARMv7 TDLib without executing a .so from external storage.

        Android rejects executable mappings from Kodi's addon directory under
        /storage/emulated/0/Android/data/... (segment ... Operation not permitted).
        The robust path is to copy the ELF bytes into a sealed memfd and give
        that FD to android_dlopen_ext. We still use a dedicated regular linker
        namespace for the library's dependencies.
        """
        import os, errno, fcntl, struct

        # Linux/Android memfd constants.
        MFD_CLOEXEC = 0x0001
        MFD_ALLOW_SEALING = 0x0002
        # Newer kernels can explicitly mark a memfd executable. Prefer it when
        # available, but fall back for older Android kernels.
        MFD_EXEC = 0x0010
        F_ADD_SEALS = getattr(fcntl, 'F_ADD_SEALS', 1033)
        F_GET_SEALS = getattr(fcntl, 'F_GET_SEALS', 1034)
        F_SEAL_SEAL = getattr(fcntl, 'F_SEAL_SEAL', 0x0001)
        F_SEAL_SHRINK = getattr(fcntl, 'F_SEAL_SHRINK', 0x0002)
        F_SEAL_GROW = getattr(fcntl, 'F_SEAL_GROW', 0x0004)
        F_SEAL_WRITE = getattr(fcntl, 'F_SEAL_WRITE', 0x0008)
        F_SEAL_FUTURE_WRITE = getattr(fcntl, 'F_SEAL_FUTURE_WRITE', 0x0010)

        def _syscall_memfd(name, flags):
            # Android ARM32: __NR_memfd_create = 385. Keep fallbacks for
            # environments where Python is a different 32-bit architecture.
            import platform
            mach=(platform.machine() or '').lower()
            nr = 385 if ('arm' in mach or mach == '') else 319
            libc = ctypes.CDLL(None)
            syscall = getattr(libc, 'syscall', None)
            if not syscall:
                raise OSError('libc.syscall no disponible')
            syscall.restype = ctypes.c_long
            syscall.argtypes = [ctypes.c_long, ctypes.c_char_p, ctypes.c_uint]
            fd = int(syscall(nr, name, flags))
            if fd < 0:
                e = ctypes.get_errno() or errno.ENOSYS
                raise OSError(e, os.strerror(e))
            return fd

        def _create_memfd():
            errors=[]
            for flags in (MFD_CLOEXEC | MFD_ALLOW_SEALING | MFD_EXEC,
                          MFD_CLOEXEC | MFD_ALLOW_SEALING,
                          MFD_CLOEXEC):
                try:
                    fd=_syscall_memfd(b'darkvio-libtdjson', flags)
                    return fd, flags
                except Exception as e:
                    errors.append('%#x: %s' % (flags,e))
            raise OSError('memfd_create fallo: ' + ' | '.join(errors))

        def _load_libdl():
            candidates = [
                None,
                '/system/lib/libdl.so',
                '/system/lib64/libdl.so',
                '/apex/com.android.runtime/lib/bionic/libdl.so',
                '/apex/com.android.runtime/lib64/bionic/libdl.so',
            ]
            errors=[]
            for item in candidates:
                try:
                    lib = ctypes.CDLL(None) if item is None else ctypes.CDLL(item)
                    xbmc_log('[DARKVIO][TDLIB] libdl accesible: %s' %
                             ('handle del proceso' if item is None else item), 1)
                    return lib
                except Exception as e:
                    errors.append('%s: %s' % ('proceso' if item is None else item, e))
            raise OSError('No se pudo acceder a libdl: ' + ' | '.join(errors))

        libdl = _load_libdl()

        class AndroidDlextInfo(ctypes.Structure):
            _fields_ = [
                ('flags', ctypes.c_uint64),
                ('reserved_addr', ctypes.c_void_p),
                ('reserved_size', ctypes.c_size_t),
                ('relro_fd', ctypes.c_int),
                ('library_fd', ctypes.c_int),
                ('library_fd_offset', ctypes.c_longlong),
                ('library_namespace', ctypes.c_void_p),
            ]

        RTLD_NOW = 0x2
        RTLD_LOCAL = 0x0
        USE_LIBRARY_FD = 0x10
        USE_NAMESPACE = 0x200
        FORCE_LOAD = 0x40
        NAMESPACE_TYPE_REGULAR = 0x0

        def proto(fn, restype, argtypes):
            if not fn:
                return None
            fn.restype = restype
            fn.argtypes = argtypes
            return fn

        loader_dlopen = proto(getattr(libdl, 'android_dlopen_ext', None), ctypes.c_void_p,
                              [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(AndroidDlextInfo)])
        if not loader_dlopen:
            loader_dlopen = proto(getattr(libdl, '__loader_android_dlopen_ext', None), ctypes.c_void_p,
                                  [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(AndroidDlextInfo), ctypes.c_void_p])
            private_dlopen = bool(loader_dlopen)
        else:
            private_dlopen = False

        loader_create_ns = proto(getattr(libdl, 'android_create_namespace', None), ctypes.c_void_p,
                                 [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
                                  ctypes.c_uint64, ctypes.c_char_p, ctypes.c_void_p])
        if not loader_create_ns:
            loader_create_ns = proto(getattr(libdl, '__loader_android_create_namespace', None), ctypes.c_void_p,
                                     [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
                                      ctypes.c_uint64, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p])
            private_create_ns = bool(loader_create_ns)
        else:
            private_create_ns = False

        loader_link_ns = proto(getattr(libdl, 'android_link_namespaces', None), ctypes.c_bool,
                               [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p])
        if not loader_link_ns:
            loader_link_ns = proto(getattr(libdl, '__loader_android_link_namespaces', None), ctypes.c_bool,
                                   [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p])

        dlsym = proto(getattr(libdl, 'dlsym', None), ctypes.c_void_p,
                      [ctypes.c_void_p, ctypes.c_char_p])
        dlerror = proto(getattr(libdl, 'dlerror', None), ctypes.c_char_p, [])

        def err():
            try:
                x = dlerror() if dlerror else None
                return x.decode('utf-8', 'replace') if x else ''
            except Exception:
                return ''

        if not loader_dlopen:
            raise OSError('android_dlopen_ext no está disponible')
        if not loader_create_ns:
            raise OSError('android_create_namespace no está disponible')
        if not loader_link_ns:
            raise OSError('android_link_namespaces no está disponible')
        if not dlsym:
            raise OSError('dlsym no está disponible')

        path = os.path.abspath(path)
        errors=[]
        ns=None
        memfd=-1

        # Dedicated regular namespace. The TDLib dependencies are public NDK
        # libraries, so link just those SONAMEs to the default namespace.
        directory=os.path.dirname(path).encode('utf-8')
        ns_name=('darkvio-tdjson-%x' % id(self)).encode('ascii')
        try:
            if private_create_ns:
                ns=loader_create_ns(ns_name, None, directory, NAMESPACE_TYPE_REGULAR, None, None, None)
            else:
                ns=loader_create_ns(ns_name, None, directory, NAMESPACE_TYPE_REGULAR, None, None)
            if not ns:
                raise OSError(err() or 'android_create_namespace devolvió NULL')
            xbmc_log('[DARKVIO][TDLIB] namespace REGULAR creado', 1)
            core=b'libc.so:libm.so:libdl.so:liblog.so:libz.so:libc++.so'
            if not bool(loader_link_ns(ns, None, core)):
                raise OSError(err() or 'android_link_namespaces fallo')
            xbmc_log('[DARKVIO][TDLIB] enlace namespace->default: OK', 1)
        except Exception as e:
            errors.append('namespace: %s' % e)
            ns=None

        # Read the bundled ELF from external storage, but never ask Android to
        # executable-map that external file. Copy the bytes to a sealed memfd.
        try:
            with open(path, 'rb') as f:
                memfd, memfd_flags = _create_memfd()
                while True:
                    chunk=f.read(1024*1024)
                    if not chunk: break
                    os.write(memfd, chunk)
                # Prevent further modification so Android's W^X checks can map
                # executable pages from the anonymous file backing.
                seals=F_SEAL_SHRINK | F_SEAL_GROW | F_SEAL_WRITE
                try:
                    fcntl.fcntl(memfd, F_ADD_SEALS, seals)
                except Exception as e:
                    xbmc_log('[DARKVIO][TDLIB] No se pudieron aplicar seals completos al memfd: %s' % e, 2)
                xbmc_log('[DARKVIO][TDLIB] TDLib copiada a memfd (flags=%#x)' % memfd_flags, 1)
        except Exception as e:
            raise OSError('memfd TDLib: %s' % e)

        try:
            if not ns:
                raise OSError('no se pudo crear namespace regular')
            ext=AndroidDlextInfo()
            ext.flags=USE_LIBRARY_FD | FORCE_LOAD | USE_NAMESPACE
            ext.reserved_addr=None
            ext.reserved_size=0
            ext.relro_fd=-1
            ext.library_fd=memfd
            ext.library_fd_offset=0
            ext.library_namespace=ns
            try:
                if private_dlopen:
                    handle=loader_dlopen(b'libtdjson.so', RTLD_NOW|RTLD_LOCAL, ctypes.byref(ext), None)
                else:
                    handle=loader_dlopen(b'libtdjson.so', RTLD_NOW|RTLD_LOCAL, ctypes.byref(ext))
            except Exception as e:
                errors.append('memfd-dlopen: %s' % e)
                handle=None
            if handle:
                xbmc_log('[DARKVIO][TDLIB] ARMv7 cargada con MEMFD + namespace REGULAR', 1)
                self._android_namespace=ns
                self._android_memfd=memfd
                return self._bind_from_android_handle(handle, dlsym, 'memfd:libtdjson.so')
            errors.append('memfd-dlopen: ' + (err() or 'sin detalle'))
            raise OSError(' | '.join(errors))
        finally:
            # Keep the memfd open for the lifetime of the loaded library. Some
            # Android releases permit it to be closed, but retaining it avoids
            # any FD-backed mapping lifetime edge cases.
            if memfd >= 0:
                try:
                    import atexit
                    atexit.register(lambda fd=memfd: os.close(fd) if fd >= 0 else None)
                except Exception:
                    pass

    def _bind_from_android_handle(self, handle, dlsym, path):
        symbols = ('td_json_client_create','td_json_client_send','td_json_client_receive',
                   'td_json_client_execute','td_json_client_destroy')
        addresses = {}
        for symbol in symbols:
            addr = dlsym(handle, symbol.encode('ascii'))
            if not addr:
                raise OSError('TDLib cargada pero falta símbolo: %s' % symbol)
            addresses[symbol] = int(addr)
        class _HandleLibrary: pass
        lib = _HandleLibrary()
        lib._darkvio_android_handle = int(handle)
        lib._darkvio_android_path = path
        lib.td_json_client_create = ctypes.CFUNCTYPE(ctypes.c_void_p)(addresses['td_json_client_create'])
        lib.td_json_client_send = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_char_p)(addresses['td_json_client_send'])
        lib.td_json_client_receive = ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p, ctypes.c_double)(addresses['td_json_client_receive'])
        lib.td_json_client_execute = ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p, ctypes.c_char_p)(addresses['td_json_client_execute'])
        lib.td_json_client_destroy = ctypes.CFUNCTYPE(None, ctypes.c_void_p)(addresses['td_json_client_destroy'])
        return lib

    def _bootstrap_windows_tdlib(self, target, arch):
        """Download only the TDLib DLL matching the running Kodi process."""
        import urllib.request, hashlib, xbmc
        assets={
            'x86': ('https://github.com/AlexXanderGrib/prebuilt-tdlib/releases/download/0.1.8.52-18f6c78/tdjson-x32.dll', 'a22c36584b04047ce6754501feb62d587acb082a2d131dd394f291b1a934f4eb'),
            'x86_64': ('https://github.com/AlexXanderGrib/prebuilt-tdlib/releases/download/0.1.8.52-18f6c78/tdjson-x64.dll', '10f78fe90d150a2fdd26ae51c349b8c895eb177b44c41bd85d253f4f779d6f87'),
        }
        url, expected=assets[arch]
        xbmc.log('[DARKVIO][TDLIB] Descargando TDLib Windows %s...' % arch, xbmc.LOGINFO)
        req=urllib.request.Request(url, headers={'User-Agent':'DARKVIO/1.3.0'})
        tmp=os.path.join(target,'tdjson.dll.download')
        try:
            with urllib.request.urlopen(req, timeout=180) as r, open(tmp,'wb') as f:
                shutil.copyfileobj(r,f)
            h=hashlib.sha256()
            with open(tmp,'rb') as f:
                for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
            if h.hexdigest().lower()!=expected.lower():
                raise TDJsonError('La verificación SHA-256 de TDLib Windows ha fallado')
            os.replace(tmp, os.path.join(target,'tdjson.dll'))
        finally:
            try:
                if os.path.exists(tmp): os.remove(tmp)
            except Exception: pass
        xbmc.log('[DARKVIO][TDLIB] TDLib Windows %s instalada en %s' % (arch,target), xbmc.LOGINFO)

    def _bootstrap_android_tdlib(self, target, arch):
        """Install only the TDLib ABI needed by the current Android Kodi process.

        We intentionally do this lazily: entering DARKVIO must never attempt a
        native download. The download happens only when the user chooses
        Telegram > Conectar Telegram. A stable upstream prebuilt release is
        used instead of the old Mithka URL, which can disappear/change.
        """
        import urllib.request, zipfile, io, tarfile
        urls={
            'all':'https://github.com/up9cloud/android-libtdjson/releases/download/v1.8.52/jniLibs.tar.gz',
        }
        url=urls['all']
        import xbmc
        xbmc.log('[DARKVIO][TDLIB] Descargando TDLib Android ABI=%s...' % arch, xbmc.LOGINFO)
        req=urllib.request.Request(url, headers={'User-Agent':'DARKVIO/1.3.0'})
        with urllib.request.urlopen(req, timeout=180) as r:
            blob=r.read()
        os.makedirs(target,exist_ok=True)
        found=False
        # Current up9cloud releases publish jniLibs.tar.gz. Accept either
        # jniLibs/<abi>/libtdjson.so or <abi>/libtdjson.so layouts.
        try:
            with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as tf:
                wanted_abi={'armv7':'armeabi-v7a','arm64':'arm64-v8a','x86':'x86','x86_64':'x86_64'}.get(arch,arch)
                for member in tf.getmembers():
                    if not member.isfile() or os.path.basename(member.name) != 'libtdjson.so':
                        continue
                    parts=[x for x in member.name.split('/') if x]
                    if wanted_abi not in parts:
                        continue
                    src=tf.extractfile(member)
                    if src is None: continue
                    with open(os.path.join(target,'libtdjson.so'),'wb') as dst:
                        shutil.copyfileobj(src,dst)
                    found=True
                    break
        except (tarfile.TarError, EOFError):
            # Keep a compatibility path for zip-based distributions.
            try:
                with zipfile.ZipFile(io.BytesIO(blob),'r') as zf:
                    wanted_abi={'armv7':'armeabi-v7a','arm64':'arm64-v8a','x86':'x86','x86_64':'x86_64'}.get(arch,arch)
                    for name in zf.namelist():
                        parts=[x for x in name.split('/') if x]
                        if name.endswith('/') or os.path.basename(name)!='libtdjson.so' or wanted_abi not in parts:
                            continue
                        with zf.open(name) as src, open(os.path.join(target,'libtdjson.so'),'wb') as dst:
                            shutil.copyfileobj(src,dst)
                        found=True
                        break
            except zipfile.BadZipFile:
                pass
        if not found:
            raise TDJsonError('La distribución TDLib no contiene libtdjson.so para '+str(arch))
        xbmc.log('[DARKVIO][TDLIB] TDLib Android %s instalada en %s' % (arch,target), xbmc.LOGINFO)

    def _bind(self, lib):
        self._create=getattr(lib,'td_json_client_create',None) or getattr(lib,'td_create_client_id',None)
        self._send=getattr(lib,'td_json_client_send',None) or getattr(lib,'td_send',None)
        self._receive=getattr(lib,'td_json_client_receive',None) or getattr(lib,'td_receive',None)
        self._execute=getattr(lib,'td_json_client_execute',None) or getattr(lib,'td_execute',None)
        self._destroy=getattr(lib,'td_json_client_destroy',None) or getattr(lib,'td_destroy',None)
        if not all([self._create,self._send,self._receive]): raise TDJsonError('tdjson no exporta la interfaz JSON esperada')
        self._create.restype=ctypes.c_void_p
        if self._receive: self._receive.restype=ctypes.c_char_p
        if self._send: self._send.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
        if self._receive: self._receive.argtypes=[ctypes.c_void_p,ctypes.c_double]
        if self._execute: self._execute.argtypes=[ctypes.c_void_p,ctypes.c_char_p]; self._execute.restype=ctypes.c_char_p
        if self._destroy: self._destroy.argtypes=[ctypes.c_void_p]
        return lib

    def start(self):
        if self._started: return
        if self.lib is None:
            self.lib=self._load_library()
        self.auth_state=None
        self._encryption_sent=False
        self.last_error=None
        self.client=self._create()
        if not self.client: raise TDJsonError('No se pudo crear el cliente TDLib')
        self._started=True
        self.stop_event.clear(); self.thread=threading.Thread(target=self._reader,name='DARKVIO-TDLib',daemon=True); self.thread.start()
        self._send_obj({'@type':'setLogVerbosityLevel','new_verbosity_level':0})
        self._send_obj({'@type':'setTdlibParameters','use_test_dc':False,'database_directory':os.path.join(self.base_dir,'tdlib'),'files_directory':os.path.join(self.base_dir,'tdlib_files'),'use_file_database':True,'use_chat_info_database':True,'use_message_database':True,'use_secret_chats':False,'api_id':self.api_id,'api_hash':self.api_hash,'system_language_code':'es','device_model':'Kodi DARKVIO','system_version':platform.platform(),'application_version':'DARKVIO 1.4.6','enable_storage_optimizer':True,'use_pfs':False})

    def _send_obj(self,obj):
        raw=json.dumps(obj,separators=(',',':')).encode('utf-8'); self._send(self.client,raw)

    def send(self,obj,timeout=30):
        if not self._started: self.start()
        extra=uuid.uuid4().hex; obj=dict(obj); obj['@extra']=extra
        ev=threading.Event(); holder={}
        with self.lock: self.pending[extra]=(ev,holder)
        self._send_obj(obj)
        if not ev.wait(timeout):
            with self.lock: self.pending.pop(extra,None)
            raise TDJsonError('Tiempo de espera agotado para TDLib: '+obj.get('@type','?'))
        if 'error' in holder: raise TDJsonError(holder['error'].get('message','Error TDLib'))
        return holder.get('data')

    def _reader(self):
        while not self.stop_event.is_set():
            try: raw=self._receive(self.client,1.0)
            except Exception: break
            if not raw: continue
            try: obj=json.loads(raw.decode('utf-8') if isinstance(raw,(bytes,bytearray)) else raw)
            except Exception: continue
            if obj.get('@type')=='updateAuthorizationState':
                st=obj.get('authorization_state',{}).get('@type','')
                self.auth_state=st
                try:
                    import xbmc
                    xbmc.log('[DARKVIO][TDLIB] updateAuthorizationState=%s' % st, xbmc.LOGINFO)
                except Exception: pass
            if obj.get('@type')=='error':
                self.last_error=obj
                try:
                    import xbmc
                    xbmc.log('[DARKVIO][TDLIB] ERROR code=%s message=%s' % (obj.get('code'),obj.get('message')), xbmc.LOGERROR)
                except Exception: pass
            extra=obj.get('@extra')
            if extra:
                with self.lock: pair=self.pending.pop(extra,None)
                if pair:
                    ev,holder=pair
                    if obj.get('@type')=='error': holder['error']=obj
                    else: holder['data']=obj
                    ev.set()

    def _database_key(self):
        path=os.path.join(self.base_dir,'tdlib_database_key.txt')
        try:
            if os.path.isfile(path):
                k=open(path,'r',encoding='ascii').read().strip()
                if k: return k
        except Exception: pass
        k=secrets.token_hex(32)
        try:
            os.makedirs(self.base_dir,exist_ok=True)
            with open(path,'w',encoding='ascii') as f: f.write(k)
        except Exception: pass
        return k

    def _ensure_encryption_key(self):
        if self._encryption_sent or not self.client: return
        if self.auth_state == 'authorizationStateWaitEncryptionKey':
            self._send_obj({'@type':'setDatabaseEncryptionKey','encryption_key':self._database_key()})
            self._encryption_sent=True

    def state(self):
        if not self._started: self.start()
        # TDLib primero pasa por WaitTdlibParameters y, si existe una base
        # de datos, por WaitEncryptionKey. No devolvemos esos estados
        # transitorios inmediatamente: el llamador necesita saber si la
        # sesión acaba en Ready o en WaitPhone/WaitCode.
        deadline=time.time()+8
        while time.time()<deadline:
            self._ensure_encryption_key()
            st=self.auth_state
            if st and st not in (
                'authorizationStateWaitTdlibParameters',
                'authorizationStateWaitEncryptionKey'
            ):
                return st
            time.sleep(.10)
        self._ensure_encryption_key()
        if self.last_error:
            return 'error:%s' % (self.last_error.get('message') or self.last_error.get('code') or 'TDLib error')
        return self.auth_state or ''

    def logout(self):
        return self.send({'@type':'logOut'})

    def close(self):
        # Cerrado seguro: primero detenemos y esperamos al hilo receptor y
        # SOLO después destruimos el cliente nativo. Destruir tdjson mientras
        # el hilo sigue dentro de td_json_client_receive puede provocar un
        # cierre nativo de Kodi, especialmente al terminar una búsqueda.
        self.stop_event.set()
        t = self.thread
        if t and t.is_alive() and t is not threading.current_thread():
            try:
                t.join(timeout=3.5)
            except Exception:
                pass
        client = self.client
        self.client = None
        if client and self._destroy:
            try:
                self._destroy(client)
            except Exception:
                pass
        self._started=False; self.auth_state=None; self.thread=None; self.last_error=None

    def auth_phone(self,phone): return self.send({'@type':'setAuthenticationPhoneNumber','phone_number':phone,'settings':{'@type':'phoneNumberAuthenticationSettings','allow_flash_call':False,'allow_missed_call':False,'is_current_phone_number':False,'allow_sms_retriever_api':False}})
    def auth_code(self,code): return self.send({'@type':'checkAuthenticationCode','code':code})
    def auth_password(self,password): return self.send({'@type':'checkAuthenticationPassword','password':password})
    def chats(self,limit=100):
        r=self.send({'@type':'getChats','chat_list':{'@type':'chatListMain'},'limit':limit})
        return r.get('chat_ids',[])
    def chat(self,chat_id): return self.send({'@type':'getChat','chat_id':int(chat_id)})
    def search_chat_messages(self,chat_id,query,limit=100):
        r=self.send({'@type':'searchChatMessages','chat_id':int(chat_id),'topic_id':None,'query':query,'sender_id':None,'from_message_id':0,'offset':0,'limit':min(100,int(limit)),'filter':None})
        return r.get('messages',[])

    def search_messages(self,query,limit=100):
        # La DLL TDLib distribuida con DARKVIO expone la firma JSON clásica de
        # searchMessages (query/offset_date/offset_chat_id/offset_message_id).
        # Probamos esa firma primero y dejamos una segunda firma compatible
        # como respaldo para otras builds de TDLib.
        lim=min(100,int(limit))
        last=None
        try:
            r=self.send({
                '@type':'searchMessages',
                'query':str(query),
                'offset_date':0,
                'offset_chat_id':0,
                'offset_message_id':0,
                'limit':lim
            })
            return r.get('messages',[])
        except Exception as e:
            last=e
        try:
            r=self.send({
                '@type':'searchMessages',
                'chat_list':None,
                'query':str(query),
                'offset':'',
                'limit':lim,
                'filter':None,
                'chat_type_filter':None,
                'min_date':0,
                'max_date':0
            })
            return r.get('messages',[])
        except Exception:
            raise last
    def get_file(self,file_id): return self.send({'@type':'getFile','file_id':int(file_id)})
    def get_message(self,chat_id,message_id): return self.send({'@type':'getMessage','chat_id':int(chat_id),'message_id':int(message_id)})
    def get_file_persistent(self,persistent_id): return self.send({'@type':'getFilePersistent','persistent_file_id':str(persistent_id)})
    def download(self,file_id,offset=0,limit=0,synchronous=False):
        priority = 32 if ('ANDROID_ROOT' in os.environ or 'ANDROID_DATA' in os.environ or os.path.exists('/system/bin/app_process')) else 16
        r=self.send({'@type':'downloadFile','file_id':int(file_id),'priority':priority,'offset':max(0,int(offset)),'limit':max(0,int(limit)),'synchronous':bool(synchronous)},timeout=3600 if synchronous else 30)
        return r
    def get_file_downloaded_prefix_size(self,file_id,offset=0):
        r=self.send({'@type':'getFileDownloadedPrefixSize','file_id':int(file_id),'offset':max(0,int(offset))},timeout=15)
        return int(r.get('size') or 0)

    def delete_file(self,file_id):
        """Remove the local copy of a file from the TDLib file cache."""
        return self.send({'@type':'deleteFile','file_id':int(file_id)},timeout=30)

class TDLibManager:
    def __init__(self):
        profile=xbmcvfs.translatePath(ADDON.getAddonInfo('profile') or '')
        self.session=os.path.join(profile,'telegram_session')
        # Migración transparente desde ARVIO: al cambiar el addon ID, Kodi
        # asigna un perfil nuevo. Conservamos la sesión TDLib existente para
        # que el usuario no tenga que volver a introducir el teléfono/código.
        self._migrate_legacy_session(profile)
        os.makedirs(self.session,exist_ok=True)
        self.api_id=ADDON.getSetting('telegram_api_id') or '23905496'
        self.api_hash=ADDON.getSetting('telegram_api_hash') or '1e48b355edfe55f9a4fbf8d3c2324628'
        self.client=TDJsonClient(self.session,self.api_id,self.api_hash)
        self._last_error=''

    def _migrate_legacy_session(self, profile):
        import shutil
        try:
            if os.path.exists(os.path.join(self.session, 'tdlib')):
                return
            old_profile=os.path.join(os.path.dirname(profile), 'plugin.video.arvio')
            old_session=os.path.join(old_profile, 'telegram_session')
            if not os.path.isdir(old_session):
                return
            os.makedirs(self.session, exist_ok=True)
            shutil.copytree(old_session, self.session, dirs_exist_ok=True)
            try:
                import xbmc
                xbmc.log('[DARKVIO][MIGRATION] Sesión Telegram ARVIO -> DARKVIO completada', xbmc.LOGINFO)
            except Exception:
                pass
        except Exception as e:
            try:
                import xbmc
                xbmc.log('[DARKVIO][MIGRATION] No se pudo migrar sesión Telegram: %s' % e, xbmc.LOGWARNING)
            except Exception:
                pass

    def logout_and_reset(self):
        """Cierra TDLib y elimina SOLO la sesión local de Telegram.

        No es necesario borrar __pycache__: ahí solo hay bytecode de Python.
        Lo que hay que limpiar para poder volver a autenticar otra cuenta es la
        base de datos/directorios de sesión de TDLib.
        """
        c=self.client
        try:
            if c:
                try:
                    if not c._started:
                        c.start()
                except Exception:
                    pass
                try:
                    if c.auth_state == 'authorizationStateReady':
                        c.logout()
                except Exception:
                    pass
                deadline=time.time()+25
                while time.time()<deadline:
                    st=c.auth_state
                    if st=='authorizationStateClosed':
                        break
                    time.sleep(0.2)
        finally:
            try:
                if c: c.close()
            except Exception: pass

        # Eliminar completamente la sesión TDLib y su clave. Windows puede
        # mantener algún fichero abierto unos instantes, por eso reintentamos.
        for _ in range(40):
            paths=[os.path.join(self.session,'tdlib'),
                   os.path.join(self.session,'tdlib_files')]
            for path in paths:
                if os.path.isdir(path):
                    try: shutil.rmtree(path,ignore_errors=False)
                    except Exception: pass
                elif os.path.exists(path):
                    try: os.remove(path)
                    except Exception: pass
            key=os.path.join(self.session,'tdlib_database_key.txt')
            try:
                if os.path.isfile(key): os.remove(key)
            except Exception: pass
            if not any(os.path.exists(x) for x in paths) and not os.path.exists(key):
                break
            time.sleep(0.25)

        os.makedirs(self.session,exist_ok=True)
        self.client=TDJsonClient(self.session,self.api_id,self.api_hash)

    def _android_native_path(self):
        """Return the expected profile .so path without downloading anything."""
        try:
            import subprocess, struct
            base=xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
            profile=xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
            mach=(platform.machine() or '').lower()
            vals=[]
            for key in ('ro.product.cpu.abilist32','ro.product.cpu.abilist','ro.product.cpu.abi'):
                try:
                    out=subprocess.check_output(['getprop',key],stderr=subprocess.DEVNULL,timeout=2).decode('utf-8','ignore')
                    vals += [x.strip().lower() for x in out.split(',') if x.strip()]
                except Exception: pass
            if struct.calcsize('P')==4 and any(x in vals for x in ('armeabi-v7a','armeabi','armv7l')):
                abi='armeabi-v7a'; arch='armv7'
            elif 'aarch64' in mach or 'arm64' in mach or 'arm64-v8a' in vals:
                abi='arm64-v8a'; arch='arm64'
            elif 'armv7' in mach or mach.startswith('arm') or any(x in vals for x in ('armeabi-v7a','armeabi')):
                abi='armeabi-v7a'; arch='armv7'
            elif 'x86_64' in mach or 'x86_64' in vals:
                abi='x86_64'; arch='x86_64'
            else:
                abi='x86'; arch='x86'
            candidates=[
                os.path.join(profile,'native','android',abi,'libtdjson.so'),
                os.path.join(base,'resources','bin','android',arch,'libtdjson.so'),
                os.path.join(base,'resources','bin','android',abi,'libtdjson.so'),
            ]
            return arch,abi,next((x for x in candidates if os.path.isfile(x)), '')
        except Exception:
            return '', '', ''

    def native_available(self):
        # IMPORTANT: this method is read-only. It must NEVER download TDLib.
        # Downloads are performed exclusively by ensure_native(), which is
        # called by the explicit Telegram -> Conectar action.
        if 'android' in (platform.system() or '').lower() or os.path.exists('/system/bin/app_process'):
            return bool(self._android_native_path()[2])
        try:
            import struct
            base=xbmcvfs.translatePath(ADDON.getAddonInfo('path') or '')
            profile=xbmcvfs.translatePath(ADDON.getAddonInfo('profile') or '')
            sysname=platform.system().lower(); mach=(platform.machine() or '').lower()
            if sysname.startswith('win'):
                arch='x86' if struct.calcsize('P')==4 else 'x86_64'
                return os.path.isfile(os.path.join(profile,'native','windows',arch,'tdjson.dll'))
            if sysname.startswith('linux'):
                if 'aarch64' in mach or 'arm64' in mach: arch='arm64'
                elif 'armv7' in mach or mach.startswith('arm'): arch='armv7'
                elif 'x86_64' in mach or 'amd64' in mach: arch='x86_64'
                elif 'x86' in mach or 'i686' in mach: arch='x86'
                else: arch=mach
                return os.path.isfile(os.path.join(profile,'native','linux',arch,'libtdjson.so'))
            return False
        except Exception:
            return False

    def ensure_native(self):
        try:
            # Always validate/load the actual native library here. If a
            # previously cached .so is corrupt or belongs to the wrong ABI,
            # _load_library will fall back to installing the correct one.
            if self.client.lib is None:
                self.client.lib=self.client._load_library()
            return True
        except Exception as e:
            self._last_error=str(e)
            return False

    def reset_client(self):
        """Crea un cliente TDLib nuevo después de un cierre/logout.

        TDLib no permite reutilizar de forma fiable un cliente cuyo estado
        terminó en authorizationStateClosed. Esto evita que el botón
        «Conectar Telegram» quede aparentemente inactivo después de
        desconectar una cuenta.
        """
        try:
            self.client.close()
        except Exception:
            pass
        self.client=TDJsonClient(self.session,self.api_id,self.api_hash)

    def available(self):
        return self.native_available()
    def error(self):
        if getattr(self,'_last_error',''): return self._last_error
        if self.native_available(): return ''
        return 'Motor TDLib todavía no instalado para este dispositivo'

