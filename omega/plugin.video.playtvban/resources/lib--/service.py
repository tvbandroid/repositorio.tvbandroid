# -*- coding: utf-8 -*-
from xbmc import Monitor
import os
import json
from time import time
from threading import Thread
from caches.settings_cache import get_setting, sync_settings
from modules import kodi_utils

pause_services_prop = 'playtvban.pause_services'
current_skin_prop = 'playtvban.current_skin'
trakt_service_string = 'Actualización del Servicio TraktMonitor %s - %s'
trakt_success_line_dict = {'success': 'Actualización de Trakt Realizada', 'no account': '(No Autorizado) Actualización de Trakt Realizada'}
update_string = 'Próxima Actualización en %s minutos...'

def _start_daemon(target):
	Thread(target=target, daemon=True).start()

class SetAddonConstants:
	def run(self):
		kodi_utils.logger('Play TVBan', 'Servicio SetAddonConstants Iniciado')
		import random
		new_version = kodi_utils.addon_info('version')
		prev_version = kodi_utils.get_property('playtvban.addon_version')
		if prev_version and prev_version != new_version:
			try:
				from caches.settings_cache import clear_settings_boot_state
				clear_settings_boot_state(clear_deferred=True)
			except: pass
			kodi_utils.clear_addon_xml_sync_version()
			kodi_utils.logger('Play TVBan', 'SetAddonConstants - versión %s -> %s' % (prev_version, new_version))
		icon_choice = get_setting('addon_icon_choice', 'resources/media/addon_icons/icon.png')
		addon_path = kodi_utils.addon_info('path')
		icon_path = kodi_utils.translate_path(os.path.join(addon_path, icon_choice))
		icon_mini = os.path.join(addon_path, 'resources', 'media', 'addon_icons', 'minis', os.path.basename(icon_path))
		addon_items = [
			('playtvban.playback_key', str(random.randint(1000, 10000))),
			('playtvban.addon_version', new_version),
			('playtvban.addon_path', addon_path),
			('playtvban.addon_profile', kodi_utils.translate_path(kodi_utils.addon_info('profile'))),
			('playtvban.addon_icon', icon_path),
			('playtvban.addon_icon_mini', icon_mini),
			('playtvban.addon_fanart', kodi_utils.addon_fanart())
					]
		for item in addon_items: kodi_utils.set_property(*item)
		kodi_utils.clear_property('playtvban.widgets_refresh_scheduled')
		kodi_utils.clear_property('playtvban.language_invoker_ready')
		kodi_utils.clear_property('playtvban.addon_xml_applied')
		kodi_utils.clear_property(kodi_utils.SHUTTING_DOWN_PROP)
		try:
			from modules.utils import _prune_qr_cache
			_prune_qr_cache(kodi_utils.translate_path(kodi_utils.addon_info('profile')))
		except: pass
		return kodi_utils.logger('Play TVBan', 'Servicio SetAddonConstants Finalizado')

class DatabaseMaintenance:
	def run(self):
		kodi_utils.logger('Play TVBan', 'Servicio DatabaseMaintenance Iniciado')
		from caches.base_cache import check_databases_integrity
		check_databases_integrity(silent=True)
		return kodi_utils.logger('Play TVBan', 'Servicio DatabaseMaintenance Finalizado')

class SyncSettings:
	def run(self):
		kodi_utils.logger('Play TVBan', 'Servicio SyncSettings Iniciado')
		from caches.settings_cache import sync_settings, settings_sync_needed
		if not settings_sync_needed():
			return kodi_utils.logger('Play TVBan', 'Servicio SyncSettings Omitido')
		sync_settings({'load_properties': False})
		return kodi_utils.logger('Play TVBan', 'Servicio SyncSettings Finalizado')

class BootstrapSettings:
	def run(self, monitor):
		from caches.settings_cache import (
			bootstrap_settings_needed, bootstrap_settings_properties,
			refresh_widgets_after_db_migration, run_deferred_setup_background_if_needed,
			service_bootstrap_needed, widgets_refresh_after_migration_needed, _properties_loaded,
		)
		if not service_bootstrap_needed():
			return
		kodi_utils.logger('Play TVBan', 'Servicio BootstrapSettings Iniciado')
		try:
			from modules.sources import clear_orphan_nextep_play_stash
			clear_orphan_nextep_play_stash()
		except:
			pass
		if bootstrap_settings_needed() and not _properties_loaded():
			monitor.waitForAbort(2)
		if kodi_utils.service_shutting_down(monitor): return
		try:
			if bootstrap_settings_needed():
				bootstrap_settings_properties()
			if not kodi_utils.service_shutting_down(monitor) and widgets_refresh_after_migration_needed():
				refresh_widgets_after_db_migration()
			run_deferred_setup_background_if_needed()
		except Exception as e:
			kodi_utils.logger('BootstrapSettings', str(e))
		return kodi_utils.logger('Play TVBan', 'Servicio BootstrapSettings Finalizado')

_custom_windows_thread_started = False

def start_custom_windows_prepare(monitor):
	global _custom_windows_thread_started
	if _custom_windows_thread_started: return
	_custom_windows_thread_started = True
	_start_daemon(lambda: CustomWindowsPrepare().run(monitor))

def run_deferred_service_setup():
	global _custom_windows_thread_started
	kodi_utils.logger('Play TVBan', 'Configuración Diferida del Servicio Iniciada')
	try:
		from windows.base_window import ExtrasUtils
		ExtrasUtils().run()
	except Exception as e: kodi_utils.logger('DeferredServiceSetup', 'ExtrasUtils: %s' % e)
	return kodi_utils.logger('Play TVBan', 'Configuración Diferida del Servicio Finalizada')

class CustomWindowsPrepare:
	def run(self, monitor):
		kodi_utils.logger('Play TVBan', 'Servicio CustomWindowsPrepare Iniciado')
		from windows.base_window import FontUtils
		player = kodi_utils.kodi_player()
		wait_for_abort, is_playing = monitor.waitForAbort, player.isPlayingVideo
		kodi_utils.clear_property(current_skin_prop)
		font_utils = FontUtils()
		while not monitor.abortRequested():
			font_utils.execute_custom_fonts()
			wait_for_abort(20)
		try: del player
		except: pass
		return kodi_utils.logger('Play TVBan', 'Servicio CustomWindowsPrepare Finalizado')

class TraktMonitor:
	def run(self, monitor):
		kodi_utils.logger('Play TVBan', 'Servicio TraktMonitor Iniciado')
		from apis.trakt_api import trakt_sync_activities
		from modules.settings import trakt_user_active, trakt_sync_interval
		player = kodi_utils.kodi_player()
		wait_for_abort, is_playing = monitor.waitForAbort, player.isPlayingVideo
		wait_for_abort(45)
		while not monitor.abortRequested():
			while is_playing() or kodi_utils.get_property(pause_services_prop) == 'true': wait_for_abort(10)
			wait_time = 1800
			try:
				from caches.settings_cache import sync_kodi_profile_context
				sync_kodi_profile_context()
				sync_interval, wait_time = trakt_sync_interval()
				next_update_string = update_string % sync_interval
				if trakt_user_active(): status = trakt_sync_activities()
				else: status = 'no_auth'
				if status == 'failed':
					kodi_utils.logger('Play TVBan', trakt_service_string % ('Falló. Error de Trakt', next_update_string))
				elif status == 'no_auth':
					kodi_utils.logger('Play TVBan', trakt_service_string % ('No Ejecutado. No Hay una Cuenta Trakt Activa', next_update_string))
				else:
					if status in ('success', 'no account'):
						kodi_utils.logger('Play TVBan', trakt_service_string % ('Correcto. %s' % trakt_success_line_dict[status], next_update_string))
					else:
						kodi_utils.logger('Play TVBan', trakt_service_string % ('Correcto. No Se Requieren Cambios', next_update_string))
					if status == 'success' and get_setting('playtvban.trakt.refresh_widgets', 'false') == 'true' and not kodi_utils.service_shutting_down(monitor):
						if not kodi_utils.playback_widget_refresh_recent():
							kodi_utils.run_plugin({'mode': 'kodi_refresh'})
			except Exception as e:
				kodi_utils.logger('Play TVBan', trakt_service_string % ('Falló', 'Ocurrió el siguiente Error: %s' % str(e)))
			wait_for_abort(wait_time)
		try: del player
		except: pass
		return kodi_utils.logger('Play TVBan', 'Servicio TraktMonitor Finalizado')

class SimklMonitor:
	def run(self, monitor):
		kodi_utils.logger('Play TVBan', 'Servicio SimklMonitor Iniciado')
		from apis.simkl_api import simkl_sync_activities
		from modules.settings import simkl_user_active, simkl_sync_interval
		player = kodi_utils.kodi_player()
		wait_for_abort, is_playing = monitor.waitForAbort, player.isPlayingVideo
		wait_for_abort(45)
		while not monitor.abortRequested():
			while is_playing() or kodi_utils.get_property(pause_services_prop) == 'true': wait_for_abort(10)
			wait_time = 1800
			try:
				from caches.settings_cache import sync_kodi_profile_context
				sync_kodi_profile_context()
				sync_interval, wait_time = simkl_sync_interval()
				next_update_string = 'Sincronización de Simkl finalizada - Próxima sincronización en %s minutos' % sync_interval
				if simkl_user_active():
					status = simkl_sync_activities()
				else:
					status = 'no_auth'
				if status == 'failed':
					kodi_utils.logger('Play TVBan', 'Falló la Sincronización de Simkl')
				elif status == 'no_auth':
					kodi_utils.logger('Play TVBan', 'La Sincronización de Simkl No Se Ejecutó - No Hay Cuenta')
				else:
					kodi_utils.logger('Play TVBan', 'Sincronización de Simkl %s - %s' % ('CORRECTA' if status == 'success' else 'Sin Cambios', next_update_string))
				if status == 'success' and get_setting('playtvban.simkl.refresh_widgets', 'false') == 'true' and not kodi_utils.service_shutting_down(monitor):
					if not kodi_utils.playback_widget_refresh_recent():
						kodi_utils.run_plugin({'mode': 'kodi_refresh'})
			except Exception as e:
				kodi_utils.logger('Play TVBan', 'Falló la Sincronización de Simkl: %s' % str(e))
			wait_for_abort(wait_time)
		try: del player
		except: pass
		return kodi_utils.logger('Play TVBan', 'Servicio SimklMonitor Finalizado')

class MdblistMonitor:
	def run(self, monitor):
		kodi_utils.logger('Play TVBan', 'Servicio MDBListMonitor Iniciado')
		from apis.mdblist_api import mdblist_sync_activities
		from modules.settings import mdblist_user_active, mdblist_sync_interval
		player = kodi_utils.kodi_player()
		wait_for_abort, is_playing = monitor.waitForAbort, player.isPlayingVideo
		wait_for_abort(60)
		while not monitor.abortRequested():
			while is_playing() or kodi_utils.get_property(pause_services_prop) == 'true': wait_for_abort(10)
			wait_time = 1800
			try:
				from caches.settings_cache import sync_kodi_profile_context
				sync_kodi_profile_context()
				sync_interval, wait_time = mdblist_sync_interval()
				next_update_string = 'Sincronización de MDBList finalizada - Próxima sincronización en %s minutos' % sync_interval
				if mdblist_user_active(): status = mdblist_sync_activities()
				else: status = 'no_auth'
				if status == 'failed': kodi_utils.logger('Play TVBan', 'Falló la sincronización de MDBList')
				elif status == 'no_auth': kodi_utils.logger('Play TVBan', 'La sincronización de MDBList no se ejecutó - No hay cuenta')
				else: kodi_utils.logger('Play TVBan', 'Sincronización de MDBList %s - %s' % ('CORRECTA' if status == 'success' else 'Sin cambios', next_update_string))
				if status == 'success' and get_setting('playtvban.mdblist.refresh_widgets', 'false') == 'true' and not kodi_utils.service_shutting_down(monitor):
					if not kodi_utils.playback_widget_refresh_recent(): kodi_utils.run_plugin({'mode': 'kodi_refresh'})
			except Exception as e: kodi_utils.logger('Play TVBan', 'Falló la sincronización de MDBList: %s' % str(e))
			wait_for_abort(wait_time)
		try: del player
		except: pass
		return kodi_utils.logger('Play TVBan', 'Servicio MDBListMonitor Finalizado')

class WidgetRefresher:
	def run(self, monitor):
		kodi_utils.logger('Play TVBan', 'Servicio WidgetRefresher Iniciado')
		from time import time
		player = kodi_utils.kodi_player()
		wait_for_abort, self.is_playing = monitor.waitForAbort, player.isPlayingVideo
		wait_for_abort(10)
		self.set_next_refresh(time())
		while not monitor.abortRequested():
			try:
				wait_for_abort(10)
				if kodi_utils.service_shutting_down(monitor): continue
				offset = int(get_setting('playtvban.widget_refresh_timer', '60'))
				if offset != self.offset:
					self.set_next_refresh(time())
					continue
				if self.condition_check(): continue
				if self.next_refresh < time():
					kodi_utils.logger('Play TVBan', 'Servicio WidgetRefresher - Widgets Actualizados')
					kodi_utils.refresh_widgets()
					self.set_next_refresh(time())
			except: pass
		try: del player
		except: pass
		return kodi_utils.logger('Play TVBan', 'Servicio WidgetRefresher Finalizado')

	def condition_check(self):
		if not self.external(): return True

		if self.next_refresh == None or self.is_playing() or kodi_utils.get_property(pause_services_prop) == 'true': return True
		if kodi_utils.get_property('playtvban.window_loaded') == 'true': return True 
		try:
			window_stack = json.loads(kodi_utils.get_property('playtvban.window_stack'))
			if window_stack or window_stack == []: return True
		except: pass
		return False

	def set_next_refresh(self, _time):
		self.offset = int(get_setting('playtvban.widget_refresh_timer', '60'))
		if self.offset: self.next_refresh = _time + (self.offset*60)
		else: self.next_refresh = None

	def external(self):
		return 'plugin' not in kodi_utils.get_infolabel('Container.PluginName')

class AutoStart:
	def run(self, monitor):
		kodi_utils.logger('Play TVBan', 'Servicio AutoStart Iniciado')
		from modules.settings import auto_start_playtvban
		if auto_start_playtvban() and not kodi_utils.service_shutting_down(monitor):
			try:
				from caches.settings_cache import ensure_settings_properties_loaded
				ensure_settings_properties_loaded()
			except Exception as e:
				kodi_utils.logger('AutoStart', 'bootstrap: %s' % e)
			kodi_utils.run_addon()
		return kodi_utils.logger('Play TVBan', 'Servicio AutoStart Finalizado')

class AddonXMLCheck:
	def run(self):
		kodi_utils.logger('Play TVBan', 'Servicio AddonXMLCheck Iniciado')
		try: kodi_utils.reuse_language_invoker_check()
		except Exception as e: kodi_utils.logger('AddonXMLCheck', str(e))
		return kodi_utils.logger('Play TVBan', 'Servicio AddonXMLCheck Finalizado')

class RedLightMonitor(Monitor):
	def __init__ (self):
		Monitor.__init__(self)
		self.startServices()

	def startServices(self):
		try: SetAddonConstants().run()
		except Exception as e: kodi_utils.logger('SetAddonConstants', str(e))
		try: DatabaseMaintenance().run()
		except Exception as e: kodi_utils.logger('DatabaseMaintenance', str(e))
		try: SyncSettings().run()
		except Exception as e: kodi_utils.logger('SyncSettings', str(e))
		try: AddonXMLCheck().run()
		except Exception as e: kodi_utils.logger('AddonXMLCheck', str(e))
		try:
			from caches.settings_cache import service_bootstrap_needed
			if service_bootstrap_needed():
				_start_daemon(lambda: BootstrapSettings().run(self))
		except Exception as e: kodi_utils.logger('BootstrapSettings', str(e))
		start_custom_windows_prepare(self)
		_start_daemon(lambda: TraktMonitor().run(self))
		_start_daemon(lambda: SimklMonitor().run(self))
		_start_daemon(lambda: MdblistMonitor().run(self))
		_start_daemon(lambda: WidgetRefresher().run(self))
		try: AutoStart().run(self)
		except Exception as e: kodi_utils.logger('AutoStart', str(e))

	def onNotification(self, sender, method, data):
		if method in ('GUI.OnScreensaverActivated', 'System.OnSleep'):
			kodi_utils.set_property(pause_services_prop, 'true')
			kodi_utils.logger('OnNotificationActions', 'PAUSANDO los servicios de Play TVBan debido a que el dispositivo entró en suspensión')
		elif method in ('GUI.OnScreensaverDeactivated', 'System.OnWake'):
			kodi_utils.clear_property(pause_services_prop)
			kodi_utils.logger('OnNotificationActions', 'REANUDANDO los servicios de Play TVBan debido a que el dispositivo salió de suspensión')
		elif method in ('Addon.OnDisabled', 'Addon.OnUninstalled'):
			try:
				info = json.loads(data)
				if info.get('id') == 'plugin.video.playtvban':
					kodi_utils.prepare_service_shutdown()
					kodi_utils.logger('Play TVBan', 'Apagado del servicio - complemento deshabilitado para actualización o desinstalación')
			except: pass

if __name__ == '__main__':
	# ----- Inicio del parche de sincronización de inicio de AM Lite Trakt -----
	def wait_for_am_trakt(timeout=120, max_age=180):
		import time
		import xbmc
		import xbmcaddon

		if not xbmc.getCondVisibility('System.HasAddon(script.module.acctmgr)'):
			return False

		waited = 0
		while waited < timeout:
			try:
				am = xbmcaddon.Addon('script.module.acctmgr')
				ready = am.getSetting('am_trakt_ready')
				last_prepare = am.getSetting('am_last_prepare')
				if ready == 'true' and last_prepare:
					age = int(time.time()) - int(last_prepare)
					if 0 <= age <= max_age:
						return True
			except Exception:
				pass
			xbmc.sleep(1000)
			waited += 1
		return False

	def _am_trakt_startup():
		try:
			wait_for_am_trakt()
		except Exception:
			pass

	Thread(target=_am_trakt_startup, daemon=True).start()
	# ----- Fin del parche de sincronización de inicio de AM Lite Trakt -----
	kodi_utils.logger('Play TVBan', 'Servicio Principal del Monitor Iniciado')
	RedLightMonitor().waitForAbort()
	kodi_utils.logger('Play TVBan', 'Servicio Principal del Monitor Finalizado')