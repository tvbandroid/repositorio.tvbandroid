# -*- coding: utf-8 -*-
import sys
from caches.navigator_cache import navigator_cache as nc
from caches.settings_cache import get_setting, set_setting
from modules import kodi_utils as k, settings as s
# logger = k.logger

class Navigator:
	def __init__(self, params):
		self.params = params
		self.params_get = self.params.get
		self.category_name = self.params_get('name', 'Play TVBan')
		self.list_name = self.params_get('action', 'RootList')
		self.is_external = k.external()
		self.make_listitem = lambda: k.make_listitem(False)
		self.build_url = k.build_url
		self.add_item = k.add_item
		self.get_icon = k.get_icon
		self.fanart = k.get_addon_fanart()
		self.run_plugin = 'RunPlugin(%s)'

	def main(self):
		def _process():
			for count, item in enumerate(browse_list):
				try:
					folder_params = dict(item)
					url = k.build_folder_url(folder_params)
					cm_items = []
					if can_move:
						cm_items.append(('[B]Mover[/B]', self.run_plugin % self.build_url({'mode': 'menu_editor.move', 'active_list': self.list_name, 'position': count})))
					cm_items.extend([
					('[B]Eliminar[/B]', self.run_plugin % self.build_url({'mode': 'menu_editor.remove', 'active_list': self.list_name, 'position': count})),
					('[B]Añadir Contenido[/B]', self.run_plugin % self.build_url({'mode': 'menu_editor.add', 'active_list': self.list_name, 'position': count})),
					('[B]Restaurar Menú[/B]', self.run_plugin % self.build_url({'mode': 'menu_editor.restore', 'active_list': self.list_name, 'position': count})),
					('[B]Buscar Nuevos Elementos del Menú[/B]', self.run_plugin % self.build_url({'mode': 'menu_editor.update', 'active_list': self.list_name, 'position': count})),
					('[B]Recargar Menú[/B]', self.run_plugin % self.build_url({'mode': 'menu_editor.reload', 'active_list': self.list_name, 'position': count})),
					('[B]Explorar Elementos Eliminados[/B]', self.run_plugin % self.build_url({'mode': 'menu_editor.browse', 'active_list': self.list_name, 'position': count})),
					('[B]Añadir a la Carpeta de Accesos Directos[/B]', self.run_plugin % self.build_url({'mode': 'menu_editor.shortcut_folder_add_known', 'url': url}))])
					icon = k.resolve_list_icon(item.get('iconImage', ''))
					item['iconImage'] = icon
					listitem = self.make_listitem()
					listitem.setLabel(item.get('name', ''))
					listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, 'fanart': self.fanart, 'banner': icon, 'landscape': icon})
					info_tag = listitem.getVideoInfoTag(True)
					info_tag.setPlot(' ')
					if not self.is_external: listitem.addContextMenuItems(cm_items)
					yield ((url, listitem, True), count)
				except: pass
		if self.params_get('full_list', 'false') == 'true': browse_list = nc.get_main_lists(self.list_name)[0]
		else: browse_list = nc.currently_used_list(self.list_name)
		if not browse_list:
			browse_list = list(nc.main_menus.get(self.list_name, []))
		can_move = len(browse_list) > 1
		results = sorted(list(_process()), key=lambda k: k[1])
		if not results and browse_list:
			k.logger('Play TVBan', 'Construcción del menú vacía para %s (se esperaban %s elementos)' % (self.list_name, len(browse_list)))
		handle = int(sys.argv[1])
		if results:
			k.add_items(handle, [i[0] for i in results])
		if not self.is_external:
			if self.list_name == 'RootList':
				folder_path = k.folder_path()
				if folder_path: k.set_property('playtvban.exit_params', k.sanitize_folder_url(folder_path))
			else:
				k.set_property('playtvban.exit_params', k.build_folder_url({'mode': 'navigator.main', 'action': 'RootList'}))
		self.end_directory(cache_to_disc=bool(results), skip_view_mode=(self.list_name == 'RootList'))

	def discover(self):
		self.add({'mode': 'navigator.discover_contents', 'media_type': 'movie'}, 'Películas', 'movies')
		self.add({'mode': 'navigator.discover_contents', 'media_type': 'tvshow'}, 'Series', 'tv')
		self._set_submenu_exit_params()
		self.end_directory()

	def premium(self):
		if s.authorized_debrid_check('ad'): self.add({'mode': 'navigator.alldebrid'}, 'All Debrid', 'alldebrid')
		if s.easynews_authorized(): self.add({'mode': 'navigator.easynews'}, 'EasyNews', 'easynews')
		if s.nzb_indexer_active(): self.add({'mode': 'navigator.nzb_indexers'}, 'NZB Indexers', 'search')
		if s.authorized_debrid_check('oc'): self.add({'mode': 'navigator.offcloud'}, 'Offcloud', 'offcloud')
		if s.authorized_debrid_check('pm'): self.add({'mode': 'navigator.premiumize'}, 'Premiumize', 'premiumize')
		if s.authorized_debrid_check('rd'): self.add({'mode': 'navigator.real_debrid'}, 'Real Debrid', 'realdebrid')
		if s.authorized_debrid_check('tb'): self.add({'mode': 'navigator.torbox'}, 'TorBox', 'torbox')
		self.end_directory()

	def easynews(self):
		self.add({'mode': 'navigator.search_history', 'action': 'easynews_video'}, 'Buscar vídeos', 'search')
		self.add({'mode': 'navigator.search_history', 'action': 'easynews_image'}, 'Buscar imágenes', 'search')
		self.add({'mode': 'easynews.account_info', 'isFolder': 'false'}, 'Información de la cuenta', 'easynews')
		self.end_directory()

	def nzb_indexers(self):
		from caches.settings_cache import get_setting
		self.add({'mode': 'navigator.search_history', 'action': 'nzb_search'}, 'Buscar en todos los indexadores', 'search')
		for slot in (1, 2, 3):
			if get_setting('playtvban.nzb%d.enabled' % slot, 'false') != 'true': continue
			label = get_setting('playtvban.nzb%d.label' % slot) or 'Indexador NZB %d' % slot
			self.add({'mode': 'nzb.test_connection', 'slot': str(slot), 'isFolder': 'false'}, 'Probar conexión: %s' % label, 'settings')
		self.end_directory()

	def real_debrid(self):
		self.add({'mode': 'real_debrid.rd_cloud'}, 'Almacenamiento en la nube', 'realdebrid')
		self.add({'mode': 'real_debrid.rd_downloads'}, 'Historial', 'realdebrid')
		self.add({'mode': 'real_debrid.rd_account_info', 'isFolder': 'false'}, 'Información de la cuenta', 'realdebrid')
		self.end_directory()

	def premiumize(self):
		self.add({'mode': 'premiumize.pm_cloud'}, 'Almacenamiento en la nube', 'premiumize')
		self.add({'mode': 'premiumize.pm_transfers'}, 'Historial', 'premiumize')
		self.add({'mode': 'premiumize.pm_account_info', 'isFolder': 'false'}, 'Información de la cuenta', 'premiumize')
		self.end_directory()

	def alldebrid(self):
		self.add({'mode': 'alldebrid.ad_cloud'}, 'Almacenamiento en la nube', 'alldebrid')
		self.add({'mode': 'alldebrid.ad_downloads'}, 'Historial', 'alldebrid')
		self.add({'mode': 'alldebrid.ad_saved_links'}, 'Enlaces guardados', 'alldebrid')
		self.add({'mode': 'alldebrid.ad_account_info', 'isFolder': 'false'}, 'Información de la cuenta', 'alldebrid')
		self.end_directory()

	def offcloud(self):
		self.add({'mode': 'offcloud.oc_cloud'}, 'Almacenamiento en la nube', 'offcloud')
		self.add({'mode': 'offcloud.oc_history'}, 'Historial', 'offcloud')
		self.add({'mode': 'offcloud.oc_account_info', 'isFolder': 'false'}, 'Información de la cuenta', 'offcloud')
		self.end_directory()

	def torbox(self):
		self.add({'mode': 'torbox.tb_cloud'}, 'Almacenamiento en la nube', 'torbox')
		self.add({'mode': 'torbox.tb_history'}, 'Historial', 'torbox')
		self.add({'mode': 'torbox.send_webdl', 'isFolder': 'false'}, 'Enviar URL a WebDL', 'torbox')
		self.add({'mode': 'torbox.tb_account_info', 'isFolder': 'false'}, 'Información de la cuenta', 'torbox')
		self.end_directory()

	def favorites(self):
		self.add({'mode': 'build_movie_list', 'action': 'favorites_movies', 'name': 'Películas'}, 'Películas', 'movies')
		self.add({'mode': 'build_tvshow_list', 'action': 'favorites_tvshows', 'name': 'Series'}, 'Series', 'tv'),
		self.add({'mode': 'build_tvshow_list', 'action': 'favorites_anime', 'is_anime_list': 'true', 'name': 'Anime'}, 'Anime', 'anime'),
		self.add({'mode': 'favorite_people', 'isFolder': 'false', 'name': 'Personas'}, 'Personas', 'empty_person')
		self._set_submenu_exit_params()
		self.end_directory()

	def my_content(self):
		return self.my_lists()

	def my_lists(self):
		if s.mdblist_user_active():
			self._safe_add({'mode': 'navigator.mdblist_lists'}, 'Listas MDBList', 'mdblist')
		if s.simkl_user_active():
			self._safe_add(self._simkl_lists_menu(), 'Listas Simkl', 'simkl')
		if s.trakt_user_active(): self._safe_add({'mode': 'navigator.trakt_lists_personal'}, 'Listas Trakt', 'trakt')
		self._safe_add({'mode': 'navigator.trakt_lists_public'}, 'Listas Públicas Trakt', 'trakt')
		if s.tmdblist_user_active(): self._safe_add({'mode': 'navigator.tmdb_lists_personal'}, 'Listas TMDb', 'tmdb')
		self._safe_add({'mode': 'personal_lists.get_personal_lists'}, 'Listas Personales', 'lists')
		self._safe_add({'mode': 'navigator.discover_contents', 'media_type': 'movie', 'show_new': 'false'}, 'Descubrir Listas (Películas)', 'movies')
		self._safe_add({'mode': 'navigator.discover_contents', 'media_type': 'tvshow', 'show_new': 'false'}, 'Descubrir Listas (Series)', 'tv')
		self._set_submenu_exit_params()
		self.end_directory()

	def tmdb_lists_personal(self):
		self.add({'mode': 'navigator.tmdb_watchlists'}, 'Ver Más Tarde', 'tmdb')
		self.add({'mode': 'navigator.tmdb_favorites'}, 'Favoritos', 'tmdb')
		self.add({'mode': 'navigator.tmdb_recommendations'}, 'Recomendaciones', 'tmdb')
		self.add({'mode': 'tmdblist.get_tmdb_lists'}, 'Mis Listas', 'tmdb')
		self._set_exit_params({'mode': 'navigator.my_lists'})
		self.end_directory()

	def tmdb_watchlists(self):
		self.category_name = 'Ver Más Tarde'
		self.add({'mode': 'tmdblist.build_tmdb_list', 'list_id': 'watchlist', 'media_type': 'movie', 'list_name': 'Movie Watchlist'}, 'Ver Más Tarde de Películas', 'tmdb')
		self.add({'mode': 'tmdblist.build_tmdb_list', 'list_id': 'watchlist', 'media_type': 'tv', 'list_name': 'TV Show Watchlist'}, 'Ver Más Tarde de Series', 'tmdb')
		self._set_exit_params({'mode': 'navigator.tmdb_lists_personal'})
		self.end_directory()

	def tmdb_favorites(self):
		self.category_name = 'Favoritos'
		self.add({'mode': 'tmdblist.build_tmdb_list', 'list_id': 'favorites', 'media_type': 'movie', 'list_name': 'Movie Favorites'}, 'Películas Favoritas', 'tmdb')
		self.add({'mode': 'tmdblist.build_tmdb_list', 'list_id': 'favorites', 'media_type': 'tv', 'list_name': 'TV Show Favorites'}, 'Series Favoritas', 'tmdb')
		self._set_exit_params({'mode': 'navigator.tmdb_lists_personal'})
		self.end_directory()

	def tmdb_recommendations(self):
		self.category_name = 'Recomendaciones'
		self.add({'mode': 'tmdblist.build_tmdb_list', 'list_id': 'recommendations', 'media_type': 'movie', 'list_name': 'Movie Recommendations'}, 'Recomendaciones de Películas', 'tmdb')
		self.add({'mode': 'tmdblist.build_tmdb_list', 'list_id': 'recommendations', 'media_type': 'tv', 'list_name': 'TV Show Recommendations'}, 'Recomendaciones de Series', 'tmdb')
		self._set_exit_params({'mode': 'navigator.tmdb_lists_personal'})
		self.end_directory()

	def trakt_lists_personal(self):
		self.add({'mode': 'navigator.trakt_collections'}, 'Colección', 'trakt')
		self.add({'mode': 'navigator.trakt_watchlists'}, 'Ver Más Tarde', 'trakt')
		self.add({'mode': 'trakt.list.get_trakt_lists', 'list_type': 'my_lists', 'category_name': 'My Lists'}, 'Mis Listas', 'trakt')
		self.add({'mode': 'trakt.list.get_trakt_lists', 'list_type': 'liked_lists', 'category_name': 'Liked Lists'}, 'Listas que me Gustan', 'trakt')
		self.add({'mode': 'navigator.trakt_favorites', 'category_name': 'Favorites'}, 'Favoritos', 'trakt')
		self.add({'mode': 'navigator.trakt_recommendations', 'category_name': 'Recommended'}, 'Recomendados', 'trakt')
		self.add({'mode': 'build_my_calendar'}, 'Calendario', 'trakt')
		if s.trakt_user_active(): self.add({'mode': 'navigator.search_history', 'action': 'trakt_my_lists'}, 'Buscar Mis Listas de Trakt', 'search')
		self._set_exit_params({'mode': 'navigator.my_lists'})
		self.end_directory()

	def trakt_lists_public(self):
		self.add({'mode': 'trakt.list.get_trakt_user_lists', 'list_type': 'trending', 'category_name': 'Trending User Lists'}, 'Listas de Usuarios en Tendencia', 'trakt')
		self.add({'mode': 'trakt.list.get_trakt_user_lists', 'list_type': 'popular', 'category_name': 'Popular User Lists'}, 'Listas de Usuarios Populares', 'trakt')
		self.add({'mode': 'navigator.search_history', 'action': 'trakt_lists'}, 'Buscar Listas de Usuarios', 'search')
		self._set_exit_params({'mode': 'navigator.my_lists'})
		self.end_directory()

	def random_lists(self):
		self.add({'mode': 'navigator.build_random_lists', 'menu_type': 'movie'}, 'Listas Aleatorias de Películas', 'movies')
		self.add({'mode': 'navigator.build_random_lists', 'menu_type': 'tvshow'}, 'Listas Aleatorias de Series', 'tv')
		self.add({'mode': 'navigator.build_random_lists', 'menu_type': 'anime'}, 'Listas Aleatorias de Anime', 'anime')
		self.add({'mode': 'navigator.build_random_lists', 'menu_type': 'because_you_watched'}, 'Aleatorio Porque Has Visto', 'because_you_watched')
		if s.tmdblist_user_active(): self.add({'mode': 'navigator.build_random_lists', 'menu_type': 'tmdb_lists'}, 'Listas Aleatorias de TMDb', 'tmdb')
		self.add({'mode': 'navigator.build_random_lists', 'menu_type': 'personal_lists'}, 'Listas Personales Aleatorias', 'lists')
		if s.simkl_user_active(): self.add({'mode': 'navigator.build_random_lists', 'menu_type': 'simkl_lists'}, 'Listas Aleatorias de Simkl', 'simkl')
		if s.trakt_user_active():
			self.add({'mode': 'navigator.build_random_lists', 'menu_type': 'trakt_personal'}, 'Listas Aleatorias de Trakt (Personales)', 'trakt')
			self.add({'mode': 'navigator.build_random_lists', 'menu_type': 'trakt_public'}, 'Listas Aleatorias de Trakt (Públicas)', 'trakt')
		self._set_submenu_exit_params()
		self.end_directory()

	def _simkl_lists_menu(self):
		return {'mode': 'navigator.simkl_lists'}

	def _simkl_list_link(self, list_mode, action, category_name):
		return {'mode': list_mode, 'action': action, 'category_name': category_name}

	def simkl_lists(self):
		"""Listas planas de estados (diseño v1.3.4) — enlaces directos a cada lista de Películas/Series."""
		self.category_name = 'Listas de Simkl'
		for url_params, label in (
			(self._simkl_list_link('build_movie_list', 'simkl_plantowatch', 'Películas Pendientes por Ver'), 'Películas Pendientes por Ver'),
			(self._simkl_list_link('build_tvshow_list', 'simkl_plantowatch', 'Series Pendientes por Ver'), 'Series Pendientes por Ver'),
			(self._simkl_list_link('build_movie_list', 'simkl_watching', 'Películas en Reproducción'), 'Películas en Reproducción'),
			(self._simkl_list_link('build_tvshow_list', 'simkl_watching', 'Series en Reproducción'), 'Series en Reproducción'),
			(self._simkl_list_link('build_movie_list', 'simkl_completed', 'Películas Completadas'), 'Películas Completadas'),
			(self._simkl_list_link('build_tvshow_list', 'simkl_completed', 'Series Completadas'), 'Series Completadas'),
			(self._simkl_list_link('build_movie_list', 'simkl_hold', 'Películas en Pausa'), 'Películas en Pausa'),
			(self._simkl_list_link('build_tvshow_list', 'simkl_hold', 'Series en Pausa'), 'Series en Pausa'),
			(self._simkl_list_link('build_movie_list', 'simkl_dropped', 'Películas Abandonadas'), 'Películas Abandonadas'),
			(self._simkl_list_link('build_tvshow_list', 'simkl_dropped', 'Series Abandonadas'), 'Series Abandonadas'),
		):
			self._safe_add(url_params, label, 'simkl')
		self._safe_add({'mode': 'navigator.search_history', 'action': 'simkl_lists'}, 'Buscar Mis Listas de Simkl', 'search')
		self.end_directory()

	def simkl_watchlists(self):
		self.category_name = 'Pendientes por Ver'
		self._safe_add(self._simkl_list_link('build_movie_list', 'simkl_plantowatch', 'Películas Pendientes por Ver'), 'Películas', 'simkl')
		self._safe_add(self._simkl_list_link('build_tvshow_list', 'simkl_plantowatch', 'Series Pendientes por Ver'), 'Series', 'simkl')
		self.end_directory()

	def simkl_completed(self):
		self.category_name = 'Completadas'
		self._safe_add(self._simkl_list_link('build_movie_list', 'simkl_completed', 'Películas Completadas'), 'Películas', 'simkl')
		self._safe_add(self._simkl_list_link('build_tvshow_list', 'simkl_completed', 'Series Completadas'), 'Series', 'simkl')
		self.end_directory()

	def simkl_watching(self):
		self.category_name = 'En Reproducción'
		self._safe_add(self._simkl_list_link('build_movie_list', 'simkl_watching', 'Películas en Reproducción'), 'Películas', 'simkl')
		self._safe_add(self._simkl_list_link('build_tvshow_list', 'simkl_watching', 'Series en Reproducción'), 'Series', 'simkl')
		self.end_directory()

	def simkl_hold(self):
		self.category_name = 'En Pausa'
		self._safe_add(self._simkl_list_link('build_movie_list', 'simkl_hold', 'Películas en Pausa'), 'Películas', 'simkl')
		self._safe_add(self._simkl_list_link('build_tvshow_list', 'simkl_hold', 'Series en Pausa'), 'Series', 'simkl')
		self.end_directory()

	def simkl_dropped(self):
		self.category_name = 'Abandonadas'
		self._safe_add(self._simkl_list_link('build_movie_list', 'simkl_dropped', 'Películas Abandonadas'), 'Películas', 'simkl')
		self._safe_add(self._simkl_list_link('build_tvshow_list', 'simkl_dropped', 'Series Abandonadas'), 'Series', 'simkl')
		self.end_directory()

	def mdblist_lists(self):
		self.category_name = 'Listas de MDBList'
		self._safe_add({'mode': 'build_movie_list', 'action': 'mdblist_watchlist', 'category_name': 'Lista de Seguimiento de Películas'}, 'Lista de Seguimiento de Películas', 'mdblist')
		self._safe_add({'mode': 'build_tvshow_list', 'action': 'mdblist_watchlist', 'category_name': 'Lista de Seguimiento de Series'}, 'Lista de Seguimiento de Series', 'mdblist')
		self._safe_add({'mode': 'build_movie_list', 'action': 'mdblist_collection', 'category_name': 'Biblioteca de Películas'}, 'Biblioteca de Películas', 'mdblist')
		self._safe_add({'mode': 'build_tvshow_list', 'action': 'mdblist_collection', 'category_name': 'Biblioteca de Series'}, 'Biblioteca de Series', 'mdblist')
		self._safe_add({'mode': 'build_tvshow_list', 'action': 'mdblist_droplist', 'category_name': 'Series Abandonadas'}, 'Series Abandonadas', 'mdblist')
		self._safe_add({'mode': 'mdblist.get_mdbl_lists', 'name': 'Mis Listas'}, 'Mis Listas', 'mdblist')
		self._safe_add({'mode': 'mdblist.get_mdbl_liked_lists', 'name': 'Listas de Películas que me Gustan', 'media_type': 'movie'}, 'Listas de Películas que me Gustan', 'mdblist')
		self._safe_add({'mode': 'mdblist.get_mdbl_liked_lists', 'name': 'Listas de Series que me Gustan', 'media_type': 'tvshow'}, 'Listas de Series que me Gustan', 'mdblist')
		self._safe_add({'mode': 'mdblist.get_mdbl_top_lists', 'name': 'MDBLists Populares'}, 'MDBLists Populares', 'mdblist')
		self._set_exit_params({'mode': 'navigator.my_lists'})
		self.end_directory()

	def trakt_collections(self):
		self.category_name = 'Colección'
		self.add({'mode': 'build_movie_list', 'action': 'trakt_collection', 'category_name': 'Colección de Películas'}, 'Colección de Películas', 'trakt')
		self.add({'mode': 'build_tvshow_list', 'action': 'trakt_collection', 'category_name': 'Colección de Series'}, 'Colección de Series', 'trakt')
		self.add({'mode': 'build_movie_list', 'action': 'trakt_collection_lists', 'new_page': 'recent', 'category_name': 'Películas Agregadas Recientemente'}, 'Películas Agregadas Recientemente', 'trakt')
		self.add({'mode': 'build_tvshow_list', 'action': 'trakt_collection_lists', 'new_page': 'recent', 'category_name': 'Series Agregadas Recientemente'},
					'Series Agregadas Recientemente', 'trakt')
		self.add({'mode': 'build_my_calendar', 'recently_aired': 'true'}, 'Episodios Emitidos Recientemente', 'trakt')
		self._set_exit_params({'mode': 'navigator.trakt_lists_personal'})
		self.end_directory()

	def trakt_watchlists(self):
		self.category_name = 'Lista de Seguimiento'
		self.add({'mode': 'build_movie_list', 'action': 'trakt_watchlist', 'category_name': 'Lista de Seguimiento de Películas'}, 'Lista de Seguimiento de Películas', 'trakt')
		self.add({'mode': 'build_tvshow_list', 'action': 'trakt_watchlist', 'category_name': 'Lista de Seguimiento de Series'}, 'Lista de Seguimiento de Series', 'trakt')
		self.add({'mode': 'build_movie_list', 'action': 'trakt_watchlist_lists', 'new_page': 'recent', 'category_name': 'Películas Agregadas Recientemente'}, 'Películas Agregadas Recientemente', 'trakt')
		self.add({'mode': 'build_tvshow_list', 'action': 'trakt_watchlist_lists', 'new_page': 'recent', 'category_name': 'Series Agregadas Recientemente'},
					'Series Agregadas Recientemente', 'trakt')
		self._set_exit_params({'mode': 'navigator.trakt_lists_personal'})
		self.end_directory()

	def trakt_recommendations(self):
		self.category_name = 'Recomendado'
		self.add({'mode': 'build_movie_list', 'action': 'trakt_recommendations', 'category_name': 'Películas Recomendadas'}, 'Películas Recomendadas', 'trakt')
		self.add({'mode': 'build_tvshow_list', 'action': 'trakt_recommendations', 'category_name': 'Series Recomendadas'}, 'Series Recomendadas', 'trakt')
		self._set_exit_params({'mode': 'navigator.trakt_lists_personal'})
		self.end_directory()

	def trakt_favorites(self):
		self.category_name = 'Favoritos'
		self.add({'mode': 'build_movie_list', 'action': 'trakt_favorites', 'category_name': 'Películas Favoritas'}, 'Películas', 'trakt')
		self.add({'mode': 'build_tvshow_list', 'action': 'trakt_favorites', 'category_name': 'Series Favoritas'}, 'Series', 'trakt')
		self._set_exit_params({'mode': 'navigator.trakt_lists_personal'})
		self.end_directory()

	def people(self):
		self.add({'mode': 'build_tmdb_people', 'action': 'popular', 'isFolder': 'false', 'name': 'Populares'}, 'Populares', 'popular')
		self.add({'mode': 'build_tmdb_people', 'action': 'day', 'isFolder': 'false', 'name': 'Tendencias'}, 'Tendencias', 'trending')
		self.add({'mode': 'build_tmdb_people', 'action': 'week', 'isFolder': 'false', 'name': 'Tendencias de Esta Semana'}, 'Tendencias de Esta Semana', 'trending_recent')
		self.end_directory()

	def search(self):
		self.add({'mode': 'navigator.search_history', 'action': 'movie', 'name': 'Historial de Búsqueda de Películas'}, 'Buscar Películas', 'movies')
		self.add({'mode': 'navigator.search_history', 'action': 'tvshow', 'name': 'Historial de Búsqueda de Series'}, 'Buscar Series', 'tv')
		self.add({'mode': 'navigator.search_history', 'action': 'anime', 'name': 'Historial de Búsqueda de Anime'}, 'Buscar Anime', 'anime')
		self.add({'mode': 'navigator.search_history', 'action': 'tvshow_anime', 'name': 'Historial de Búsqueda de Series y Anime'}, 'Buscar Series y Anime', 'tv_anime')
		self.add({'mode': 'navigator.search_history', 'action': 'people', 'name': 'Historial de Búsqueda de Personas'}, 'Buscar Personas', 'people')
		self.add({'mode': 'navigator.search_history', 'action': 'tmdb_keyword_movie', 'name': 'Historial de Búsqueda de Palabras Clave (Películas)'}, 'Buscar Palabras Clave (Películas)', 'tmdb')
		self.add({'mode': 'navigator.search_history', 'action': 'tmdb_keyword_tvshow', 'name': 'Historial de Búsqueda de Palabras Clave (Series)'}, 'Buscar Palabras Clave (Series)', 'tmdb')
		self.add({'mode': 'navigator.search_history', 'action': 'trakt_lists'}, 'Buscar Listas de Usuarios de Trakt', 'trakt')
		if s.easynews_authorized():
			self.add({'mode': 'navigator.search_history', 'action': 'easynews_video'}, 'Buscar Videos de EasyNews', 'easynews')
			self.add({'mode': 'navigator.search_history', 'action': 'easynews_image'}, 'Buscar Imágenes de EasyNews', 'easynews')
		if s.nzb_indexer_active(): self.add({'mode': 'navigator.search_history', 'action': 'nzb_search'}, 'Buscar los indexadores NZB', 'search')
		self.end_directory()

	def downloads(self):
		self.add({'mode': 'downloader.manager', 'name': 'Administrador de Descargas', 'isFolder': 'false'}, 'Administrador de Descargas', 'downloads')
		self.add({'mode': 'downloader.viewer', 'folder_type': 'movie', 'name': 'Películas'}, 'Películas', 'movies')
		self.add({'mode': 'downloader.viewer', 'folder_type': 'episode', 'name': 'Series'}, 'Series', 'tv')
		self.add({'mode': 'downloader.viewer', 'folder_type': 'premium', 'name': 'Archivos Premium'}, 'Archivos Premium', 'premium')
		self.add({'mode': 'browser_image', 'folder_path': s.download_directory('image'), 'isFolder': 'false'}, 'Imágenes', 'people')
		self.end_directory()

	def tools(self):
		self.add({'mode': 'open_settings', 'isFolder': 'false'}, 'Configuración', 'settings')
		if s.configured_external_scraper_slots():
			self.add({'mode': 'open_external_scraper_settings', 'isFolder': 'false'}, s.external_scraper_settings_tools_label(), 'settings')
		self.add({'mode': 'navigator.tips'}, 'Consejos de Uso', 'settings2')
		if get_setting('playtvban.use_viewtypes', 'true') == 'true' and not get_setting('playtvban.manual_viewtypes', 'false') == 'true':
			self.add({'mode': 'navigator.set_view_modes'}, 'Configurar Vistas', 'settings2')
		self.add({'mode': 'navigator.changelog_utils'}, 'Registro de Cambios y Utilidades de Registro', 'settings2')
		self.add({'mode': 'build_next_episode_manager'}, 'Administrador del Progreso de Series', 'settings2')
		self.add({'mode': 'navigator.shortcut_folders'}, 'Administrador de Carpetas de Accesos Directos', 'settings2')
		self.add({'mode': 'navigator.import_export'}, 'Importar y Exportar', 'settings2')
		self.add({'mode': 'navigator.maintenance'}, 'Mantenimiento de Base de Datos y Caché', 'settings2')
		self.add({'mode': 'language_invoker_choice', 'isFolder': 'false'}, 'Alternar Invocador de Idioma (¡¡AVANZADO!!)', 'settings2')
		self.end_directory()

	def import_export(self):
		self.add({'mode': 'settings_backup.import_settings', 'isFolder': 'false'}, 'Importar Configuración de Play TVBan', 'settings')
		self.add({'mode': 'settings_backup.export_settings', 'isFolder': 'false'}, 'Exportar Configuración de Play TVBan', 'settings')
		self.add({'mode': 'local_backup.import_data', 'isFolder': 'false'}, 'Importar Favoritos e Historial de Play TVBan', 'folder')
		self.add({'mode': 'local_backup.export_data', 'isFolder': 'false'}, 'Exportar Favoritos e Historial de Play TVBan', 'folder')
		self.add({'mode': 'kodi_favorites.import_favorites', 'isFolder': 'false'}, 'Importar Favoritos de Kodi', 'favorites')
		self.add({'mode': 'kodi_favorites.export_favorites', 'isFolder': 'false'}, 'Exportar Favoritos de Kodi', 'favorites')
		self.end_directory()

	def maintenance(self):
		self.add({'mode': 'check_databases_integrity_cache', 'isFolder': 'false'}, 'Comprobar Bases de Datos Dañadas', 'settings')
		self.add({'mode': 'clean_databases_cache', 'isFolder': 'false'}, 'Limpiar Bases de Datos', 'settings')
		self.add({'mode': 'sync_settings', 'silent': 'false', 'isFolder': 'false'}, 'Reconstruir la Caché de Configuración', 'settings')
		self.add({'mode': 'clear_all_cache', 'isFolder': 'false'}, 'Borrar Toda la Caché (Excepto Favoritos)', 'settings')
		self.add({'mode': 'clear_favorites_choice', 'isFolder': 'false'}, 'Borrar Caché de Favoritos', 'settings')
		self.add({'mode': 'search.clear_search', 'isFolder': 'false'}, 'Borrar Caché del Historial de Búsquedas', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'ai_functions', 'isFolder': 'false'}, 'Borrar Caché de Datos de IA', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'list', 'isFolder': 'false'}, 'Borrar Caché de Listas', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'main', 'isFolder': 'false'}, 'Borrar Caché Principal', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'meta', 'isFolder': 'false'}, 'Borrar Caché de Metadatos', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'tmdb_list', 'isFolder': 'false'}, 'Borrar Caché de Listas Personales de TMDb', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'imdb', 'isFolder': 'false'}, 'Borrar Caché de IMDb', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'mdblist', 'isFolder': 'false'}, 'Borrar Caché de MDBList', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'simkl', 'isFolder': 'false'}, 'Borrar Caché de Simkl', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'trakt', 'isFolder': 'false'}, 'Borrar Caché de Trakt', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'subtitles', 'isFolder': 'false'}, 'Borrar Caché de Subtítulos', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'easynews_scrape', 'isFolder': 'false'}, 'Borrar Caché de Scrape de EasyNews', 'settings')
		self.add({'mode': 'search.clear_easynews_search_history', 'isFolder': 'false'}, 'Borrar Historial de Búsquedas de EasyNews', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'external_scrapers', 'isFolder': 'false'}, 'Borrar Caché de Scrapers Externos', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'internal_scrapers', 'isFolder': 'false'}, 'Borrar Caché de Scrapers Internos', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'ad_cloud', 'isFolder': 'false'}, 'Borrar Caché de All Debrid', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'oc_cloud', 'isFolder': 'false'}, 'Borrar Caché de Offcloud', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'pm_cloud', 'isFolder': 'false'}, 'Borrar Caché de Premiumize', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'rd_cloud', 'isFolder': 'false'}, 'Borrar Caché de Real Debrid', 'settings')
		self.add({'mode': 'clear_cache', 'cache': 'tb_cloud', 'isFolder': 'false'}, 'Borrar Caché de TorBox', 'settings')
		self.end_directory()

	def set_view_modes(self):
		self.add({'mode': 'navigator.choose_view', 'view_type': 'view.main', 'content': 'files', 'name': 'menus'}, 'Configurar Menús', 'folder')
		self.add({'mode': 'navigator.choose_view', 'view_type': 'view.movies', 'content': 'movies'}, 'Configurar Películas', 'movies')
		self.add({'mode': 'navigator.choose_view', 'view_type': 'view.tvshows', 'content': 'tvshows'}, 'Configurar Series', 'tv')
		self.add({'mode': 'navigator.choose_view', 'view_type': 'view.seasons', 'content': 'seasons'}, 'Configurar Temporadas', 'ontheair')
		self.add({'mode': 'navigator.choose_view', 'view_type': 'view.episodes', 'content': 'episodes'}, 'Configurar Episodios (mostrar temporadas)', 'next_episodes')
		self.add({'mode': 'navigator.choose_view', 'view_type': 'view.episodes_single', 'content': 'episodes', 'name': 'episode lists'}, 'Configurar Listas de Episodios (Próximos Episodios, etc.)', 'calender')
		self.add({'mode': 'navigator.choose_view', 'view_type': 'view.premium', 'content': 'files', 'name': 'premium files'}, 'Configurar Archivos Premium', 'premium')
		self.end_directory()

	def changelog_utils(self):
		log_loc, old_log_loc = k.translate_path('special://logpath/kodi.log'), k.translate_path('special://logpath/kodi.old.log')
		playtvban_clogpath = k.translate_path('special://home/addons/plugin.video.playtvban/resources/text/changelog.txt')
		self.add({'mode': 'show_text', 'heading': 'Registro de Cambios', 'file': playtvban_clogpath, 'font_size': 'large', 'isFolder': 'false'}, 'Registro de Cambios', 'lists')
		self.add({'mode': 'show_text', 'heading': 'Visor del Registro de Kodi', 'file': log_loc, 'kodi_log': 'true', 'isFolder': 'false'}, 'Visor del Registro de Kodi', 'lists')
		self.add({'mode': 'show_text', 'heading': 'Visor del Registro de Kodi (Anterior)', 'file': old_log_loc, 'kodi_log': 'true', 'isFolder': 'false'}, 'Visor del Registro de Kodi (Anterior)', 'lists')
		self.add({'mode': 'upload_logfile', 'isFolder': 'false'}, 'Subir Registro de Kodi a Pastebin', 'lists')
		self.end_directory()

	def certifications(self):
		menu_type = self.params_get('menu_type')
		if menu_type == 'movie': from modules.meta_lists import movie_certifications as function
		else: from modules.meta_lists import tvshow_certifications as function
		menu_type = self.params_get('menu_type')
		if menu_type == 'movie': mode, action = 'build_movie_list', 'tmdb_movies_certifications'
		else:
			mode = 'build_tvshow_list'
			if menu_type == 'tvshow': action = 'trakt_tv_certifications'
			else: action = 'trakt_anime_certifications'
		for i in function(): self.add({'mode': mode, 'action': action, 'key_id': i['id'], 'name': i['name']}, i['name'], 'certifications')
		self._set_submenu_exit_params(menu_type)
		self.end_directory()

	def languages(self):
		from modules.meta_lists import languages as function
		menu_type = self.params_get('menu_type')
		if menu_type == 'movie': mode, action = 'build_movie_list', 'tmdb_movies_languages'
		else: mode, action = 'build_tvshow_list', 'tmdb_tv_languages'
		for i in function(): self.add({'mode': mode, 'action': action, 'key_id': i['id'], 'name': i['name']}, i['name'], 'languages')
		self._set_submenu_exit_params(menu_type)
		self.end_directory()

	def years(self):
		menu_type = self.params_get('menu_type')
		if menu_type == 'movie':
			from modules.meta_lists import years_movies as function
			mode, action = 'build_movie_list', 'tmdb_movies_year'
		else:
			mode = 'build_tvshow_list'
			if menu_type == 'tvshow':
				from modules.meta_lists import years_tvshows as function
				action = 'tmdb_tv_year'
			else:
				from modules.meta_lists import years_anime as function
				action = 'tmdb_anime_year'
		for i in function(): self.add({'mode': mode, 'action': action, 'key_id': i['id'], 'name': i['name']}, i['name'], 'calender')
		self._set_submenu_exit_params(menu_type)
		self.end_directory()

	def decades(self):
		menu_type = self.params_get('menu_type')
		if menu_type == 'movie':
			from modules.meta_lists import decades_movies as function
			mode, action = 'build_movie_list', 'tmdb_movies_decade'
		else:
			mode = 'build_tvshow_list'
			if menu_type == 'tvshow':
				from modules.meta_lists import decades_tvshows as function
				action = 'tmdb_tv_decade'
			else:
				from modules.meta_lists import decades_anime as function
				action = 'tmdb_anime_decade'
		for i in function(): self.add({'mode': mode, 'action': action, 'key_id': i['id'], 'name': i['name']}, i['name'], 'calendar_decades')
		self._set_submenu_exit_params(menu_type)
		self.end_directory()

	def networks(self):
		menu_type = self.params_get('menu_type')
		if menu_type == 'movie': return
		from modules.meta_lists import networks
		for i in sorted(networks(), key=lambda k: k['name']): self.add({'mode': 'build_tvshow_list', 'action': 'tmdb_tv_networks', 'key_id': i['id'], 'name': i['name']}, i['name'],
																		self.get_icon(i['logo'], 'network_icons'), original_image=True)
		self._set_submenu_exit_params(menu_type)
		self.end_directory()

	def providers(self):
		menu_type = self.params_get('menu_type')
		tmdb_img = 'https://image.tmdb.org/t/p/original/%s'
		if menu_type == 'movie':
			from modules.meta_lists import watch_providers_movies as function
			mode, action = 'build_movie_list', 'tmdb_movies_providers'
		else:
			from modules.meta_lists import watch_providers_tvshows as function
			mode = 'build_tvshow_list'
			if menu_type == 'tvshow': action = 'tmdb_tv_providers'
			else: action = 'tmdb_anime_providers'
		for i in function(): self.add({'mode': mode, 'action': action, 'key_id': i['id'], 'name': i['name']}, i['name'], tmdb_img % i['logo'], original_image=True)
		self._set_submenu_exit_params(menu_type)
		self.end_directory()

	def genres(self):
		menu_type = self.params_get('menu_type')
		if menu_type == 'movie':
			from modules.meta_lists import movie_genres as function
			mode, action = 'build_movie_list', 'tmdb_movies_genres'
		else:
			mode = 'build_tvshow_list'
			if menu_type == 'tvshow':
				from modules.meta_lists import tvshow_genres as function
				action = 'tmdb_tv_genres'
			else:
				from modules.meta_lists import anime_genres as function
				action = 'tmdb_anime_genres'
		for i in function(): self.add({'mode': mode, 'action': action, 'key_id': i['id'], 'name': i['name']}, i['name'], i['icon'])
		self._set_submenu_exit_params(menu_type)
		self.end_directory()

	def search_history(self):
		from urllib.parse import unquote
		from caches.main_cache import main_cache
		search_mode_dict = {
		'movie': ('movie_queries', {'mode': 'search.get_key_id', 'media_type': 'movie', 'isFolder': 'false'}),
		'tvshow': ('tvshow_queries', {'mode': 'search.get_key_id', 'media_type': 'tv_show', 'isFolder': 'false'}),
		'anime': ('anime_queries', {'mode': 'search.get_key_id', 'media_type': 'anime', 'isFolder': 'false'}),
		'tvshow_anime': ('tvshow_anime_queries', {'mode': 'search.get_key_id', 'media_type': 'tvshow_anime', 'isFolder': 'false'}),
		'people': ('people_queries', {'mode': 'search.get_key_id', 'search_type': 'people', 'isFolder': 'false'}),
		'tmdb_keyword_movie': ('keyword_tmdb_movie_queries', {'mode': 'search.get_key_id', 'search_type': 'tmdb_keyword', 'media_type': 'movie', 'isFolder': 'false'}),
		'tmdb_keyword_tvshow': ('keyword_tmdb_tvshow_queries', {'mode': 'search.get_key_id', 'search_type': 'tmdb_keyword', 'media_type': 'tvshow', 'isFolder': 'false'}),
		'easynews_video': ('easynews_video_queries', {'mode': 'search.get_key_id', 'search_type': 'easynews_video', 'isFolder': 'false'}),
		'easynews_image': ('easynews_image_queries', {'mode': 'search.get_key_id', 'search_type': 'easynews_image', 'isFolder': 'false'}),
		'nzb_search': ('nzb_queries', {'mode': 'search.get_key_id', 'search_type': 'nzb_search', 'isFolder': 'false'}),
		'trakt_lists': ('trakt_list_queries', {'mode': 'search.get_key_id', 'search_type': 'trakt_lists', 'isFolder': 'false'}),
		'trakt_my_lists': ('trakt_my_list_queries', {'mode': 'search.get_key_id', 'search_type': 'trakt_my_lists', 'isFolder': 'false'}),
		'simkl_lists': ('simkl_list_queries', {'mode': 'search.get_key_id', 'search_type': 'simkl_lists', 'isFolder': 'false'})}
		setting_id, action_dict = search_mode_dict[self.list_name]
		url_params = dict(action_dict)
		data = main_cache.get(setting_id) or []
		self.add(action_dict, '[B]NUEVA BÚSQUEDA...[/B]', 'new')
		for i in data:
			try:
				key_id = unquote(i)
				url_params['key_id'] = key_id
				url_params['setting_id'] = setting_id
				cm_items = [('[B]Eliminar del historial[/B]', 'RunPlugin(%s)' % self.build_url({'mode': 'search.remove', 'setting_id':setting_id, 'key_id': key_id})),
							('[B]Borrar todo el historial[/B]', 'RunPlugin(%s)' % self.build_url({'mode': 'search.clear_all', 'setting_id':setting_id, 'refresh': 'true'}))]
				self.add(url_params, key_id, 'calender', cm_items=cm_items)
			except: pass
		self.category_name = self.params_get('name') or 'Historial'
		self.end_directory(cache_to_disc=False)

	def keyword_results(self):
		from apis.tmdb_api import tmdb_keywords_by_query
		media_type, key_id = self.params_get('media_type'), self.params_get('key_id') or self.params_get('query')
		try: page_no = int(self.params_get('new_page', '1'))
		except: page_no = self.params_get('new_page')
		mode = 'build_movie_list' if media_type == 'movie' else 'build_tvshow_list'
		action = 'tmdb_movie_keyword_results' if media_type == 'movie' else 'tmdb_tv_keyword_results'
		data = tmdb_keywords_by_query(key_id, page_no)
		results = data['results']
		for item in results:
			name = item['name'].upper()
			self.add({'mode': mode, 'action': action, 'key_id': item['id'], 'iconImage': 'tmdb', 'category_name': name}, name, iconImage='tmdb')
		if data['total_pages'] > page_no:
			new_page = {'mode': 'navigator.keyword_results', 'key_id': key_id, 'category_name': self.category_name, 'new_page': str(data['page'] + 1)}
			self.add(new_page, 'Página Siguiente (%s) >>' % new_page['new_page'], 'nextpage', False)
		self.category_name = 'Resultados de búsqueda para %s' % key_id.upper()
		self.end_directory()

	def choose_view(self):
		handle = int(sys.argv[1])
		view_type = self.params.get('view_type', 'view.main')
		if view_type in ('view.main', 'view.premium'):
			content = k.MENU_FOLDER_CONTENT
		else:
			content = self.params.get('content', 'files')
		name = self.params.get('name') or content or 'menus'
		self.add({'mode': 'navigator.set_view', 'view_type': view_type, 'name': name, 'isFolder': 'false'}, 'Set view and then click here', 'settings')
		k.set_content(handle, content)
		k.end_directory(handle)
		k.set_view_mode(view_type, content, False)

	def set_view(self):
		view_type = self.params.get('view_type', 'view.main')
		label = (self.params.get('name') or view_type.replace('view.', '').replace('_', ' ')).upper()
		view_id = str(k.current_window_object().getFocusId())
		set_setting(view_type, view_id)
		if view_type == 'view.episodes':
			from caches.settings_cache import default_setting_values
			episodes_single_default = (default_setting_values('view.episodes_single') or {}).get('setting_default', '55')
			if str(get_setting('playtvban.view.episodes_single', episodes_single_default)) == str(episodes_single_default):
				set_setting('view.episodes_single', view_id)
		k.notification('%s: %s' % (label, k.get_infolabel('Container.Viewmode').upper()), time=500)

	def shortcut_folders(self):
		folders = nc.get_shortcut_folders()
		if folders:
			for i in folders:
				name = i[0]
				convert_sr = '[B]Quitar Aleatorio[/B]' if '[COLOR khaki][RANDOM][/COLOR]' in name else '[B]Convertir en Aleatorio[/B]'
				cm_items = [('[B]Renombrar[/B]', self.run_plugin % self.build_url({'mode': 'menu_editor.shortcut_folder_rename'})),
							('[B]Eliminar Carpeta[/B]' , self.run_plugin % self.build_url({'mode': 'menu_editor.shortcut_folder_delete'})),
							('[B]Crear Nueva Carpeta[/B]' , self.run_plugin % self.build_url({'mode': 'menu_editor.shortcut_folder_make'})),
							(convert_sr , self.run_plugin % self.build_url({'mode': 'menu_editor.shortcut_folder_convert', 'name': name}))]
				self.add({'mode': 'navigator.build_shortcut_folder_contents', 'name': name, 'iconImage': 'folder'}, name, 'folder', cm_items=cm_items)
		else: self.add({'mode': 'menu_editor.shortcut_folder_make', 'isFolder': 'false'}, '[I]Crear Nueva Carpeta...[/I]', 'new')
		self.category_name = 'Carpetas de Accesos Directos'
		self.end_directory()

	def build_shortcut_folder_contents(self):
		list_name = self.params_get('name')
		if not list_name:
			k.notification('No se encontró la carpeta de accesos directos.', 2500)
			return self.end_directory()
		is_random = '[COLOR khaki][RANDOM][/COLOR]' in list_name
		contents = nc.get_shortcut_folder_contents(list_name)
		if not contents and not is_random:
			random_name = '%s [COLOR khaki][RANDOM][/COLOR]' % list_name
			contents = nc.get_shortcut_folder_contents(random_name)
			if contents:
				list_name, is_random = random_name, True
		folder_icon = self.get_icon('folder')
		if is_random:
			from indexers.random_lists import random_shortcut_folders
			return random_shortcut_folders(list_name.replace(' [COLOR khaki][RANDOM][/COLOR]', ''), contents)
		if contents:
			can_move = len(contents) > 1
			for count, item in enumerate(contents):
				item_get = item.get
				iconImage = item_get('iconImage', None)
				if iconImage:
					if iconImage.startswith('http') and 'raw.githubusercontent.com' not in iconImage:
						icon, original_image = iconImage, True
					else:
						icon, original_image = k.resolve_list_icon(iconImage), False
				else: icon, original_image = folder_icon, False
				cm_items = []
				if can_move:
					cm_items.append(('[B]Mover[/B]', self.run_plugin % self.build_url({'mode': 'menu_editor.shortcut_folder_edit', 'active_list': list_name, 'position': count, 'action': 'move'})))
				cm_items.extend([
				('[B]Eliminar[/B]' , self.run_plugin % self.build_url({'mode': 'menu_editor.shortcut_folder_edit', 'active_list': list_name, 'position': count, 'action': 'remove'})),
				('[B]Agregar Contenido[/B]' , self.run_plugin % self.build_url({'mode': 'menu_editor.shortcut_folder_add', 'name': list_name})),
				('[B]Renombrar[/B]' , self.run_plugin % self.build_url({'mode': 'menu_editor.shortcut_folder_edit', 'active_list': list_name, 'position': count, 'action': 'rename'})),
				('[B]Borrar Todo[/B]' , self.run_plugin % self.build_url({'mode': 'menu_editor.shortcut_folder_edit', 'active_list': list_name, 'position': count, 'action': 'clear'}))])
				self.add(item, item_get('name'), icon, original_image, cm_items=cm_items)
		elif is_random: pass
		else: self.add({'mode': 'menu_editor.shortcut_folder_add', 'name': list_name, 'isFolder': 'false'}, '[I]Agregar Contenido...[/I]', 'new')
		self.end_directory()

	def discover_contents(self):
		from caches.discover_cache import discover_cache
		action, media_type = self.params_get('action', ''), self.params_get('media_type')
		if not action:
			if self.params_get('show_new', 'true') == 'true':
				self.add({'mode': 'discover_choice', 'media_type': media_type, 'isFolder': 'false'}, '[I]CREAR NUEVA LISTA DISCOVER...[/I]', 'new')
			results = discover_cache.get_all(media_type)
			if media_type == 'movie': mode, action = 'build_movie_list', 'tmdb_movies_discover'
			else: mode, action = 'build_tvshow_list', 'tmdb_tv_discover'
			for item in results:
				name, data = item['id'], item['data']
				cm_items = [('[B]ELIMINAR DEL HISTORIAL[/B]', 'RunPlugin(%s)' % self.build_url({'mode': 'navigator.discover_contents', 'action':'delete_one', 'name': name})),
							('[B]BORRAR TODO EL HISTORIAL[/B]', 'RunPlugin(%s)' % self.build_url({'mode': 'navigator.discover_contents', 'action':'clear_cache',
								'media_type': media_type}))]
				if '[random]' in data:
					self.add({'mode': 'random.%s' % mode, 'action': action, 'name': name, 'url': data, 'new_page': 'random', 'random': 'true'},
								name, 'discover', cm_items=cm_items)
				else: self.add({'mode': mode, 'action': action, 'name': name, 'url': data}, name, 'discover', cm_items=cm_items)
			self.end_directory()
		else:
			if action == 'delete_one': discover_cache.delete_one(self.params_get('name'))
			elif action == 'clear_cache': discover_cache.clear_cache(media_type)
			k.container_refresh()

	def exit_media_menu(self):
		params = k.get_property('playtvban.exit_params')
		if not params: return
		params = k.sanitize_folder_url(params)
		k.container_refresh_input(params)

	def _set_submenu_exit_params(self, menu_type=None):
		if self.is_external: return
		parent = {'movie': 'MovieList', 'tvshow': 'TVShowList', 'anime': 'AnimeList'}
		if menu_type in parent:
			k.set_property('playtvban.exit_params', k.build_folder_url({'mode': 'navigator.main', 'action': parent[menu_type]}))
		else:
			k.set_property('playtvban.exit_params', k.build_folder_url({'mode': 'navigator.main', 'action': 'RootList'}))

	def _set_exit_params(self, parent_params):
		if self.is_external: return
		k.set_property('playtvban.exit_params', k.build_folder_url(parent_params))

	def tips(self):
		tips_location = 'special://home/addons/plugin.video.playtvban/resources/text/tips'
		files = sorted(k.list_dirs(tips_location)[1])
		tips_location += '/%s'
		tips_list = []
		tips_append = tips_list.append
		for item in files:
			tip = item.replace('.txt', '')[4:]
			if '!!HELP!!' in tip: tip, sort_order = tip.replace('!!HELP!!', '[COLOR crimson][B]¡¡AYUDA!![/B][/COLOR] '), 0
			elif '!!NEW!!' in tip: tip, sort_order = tip.replace('!!NEW!!', '[COLOR chartreuse][B]¡¡NUEVO!![/B][/COLOR] '), 1
			elif '!!SPOTLIGHT!!' in tip: tip, sort_order = tip.replace('!!SPOTLIGHT!!', '[COLOR orange][B]¡DESTACADO![/B][/COLOR] '), 2
			else: sort_order = 3
			params = {'mode': 'show_text', 'heading': tip, 'file': k.translate_path(tips_location % item), 'font_size': 'large', 'isFolder': 'false'}
			tips_append((params, tip, sort_order))
		item_list = sorted(tips_list, key=lambda x: x[2])
		for c, i in enumerate(item_list, 1): self.add(i[0], '[B]%02d. [/B]%s' % (c, i[1]), 'information')
		self.end_directory()

	def because_you_watched(self):
		from modules.watched_status import get_recently_watched
		from modules.episode_tools import single_last_watched_episodes
		recommend_type = s.recommend_service()
		menu_type = self.params_get('menu_type')
		action_dict = {'movie':
		{'mode': 'build_movie_list', 'action': {0: 'tmdb_movies_recommendations', 1: 'imdb_more_like_this', 2: 'ai_similar', 3: 'trakt_movies_related'}, 'media_type': 'movie'},
						'tvshow':
		{'mode': 'build_tvshow_list', 'action': {0: 'tmdb_tv_recommendations', 1: 'imdb_more_like_this', 2: 'ai_similar', 3: 'trakt_tv_related'}, 'media_type': 'episode'}}
		action_params = action_dict[menu_type]
		mode, action, media_type = action_params['mode'], action_params['action'][recommend_type], action_params['media_type']
		recently_watched = get_recently_watched(media_type)
		if media_type == 'episode': recently_watched = single_last_watched_episodes(recently_watched)
		for item in recently_watched:
			if media_type == 'movie':
				name = item['title']
				key_id = item['media_id'] if recommend_type in (0, 1, 3) else 'movie|%s' % item['media_id']
			else:
				name = '%s - %sx%s' % (item['title'], str(item['season']), str(item['episode']))
				key_id = item['media_ids']['tmdb'] if recommend_type in (0, 1, 3) else 'tvshow|%s' % item['media_ids']['tmdb']
			params = {'mode': mode, 'action': action, 'key_id': key_id, 'name': 'Porque Viste %s' % name}
			if recommend_type == 1: params['get_imdb'] = 'true'
			self.add(params, name, 'because_you_watched')
		self.end_directory()

	def build_random_lists(self):
		random_list_dict = {
		'movie': ('Listas Aleatorias de Películas', nc.random_movie_lists),
		'tvshow': ('Listas Aleatorias de Series', nc.random_tvshow_lists),
		'anime': ('Listas Aleatorias de Anime', nc.random_anime_lists),
		'because_you_watched': ('Listas Aleatorias de Porque Viste', nc.random_because_you_watched_lists),
		'tmdb_lists': ('Listas Aleatorias de TMDb', nc.random_tmdb_lists),
		'personal_lists': ('Listas Personales Aleatorias', nc.random_personal_lists),
		'trakt_personal': ('Listas Aleatorias de Trakt (Personales)', nc.random_trakt_lists_personal),
		'trakt_public': ('Listas Aleatorias de Trakt (Públicas)', nc.random_trakt_lists_public),
		'simkl_lists': ('Listas Aleatorias de Simkl', nc.random_simkl_lists)}
		self.category_name, function = random_list_dict[self.params_get('menu_type')]
		func = function()
		for item in func: self.add(item, item['name'], item['iconImage'])
		self.end_directory()

	def _safe_add(self, url_params, list_name, iconImage='folder', original_image=False, cm_items=[]):
		try: self.add(url_params, list_name, iconImage, original_image, cm_items)
		except Exception as e: k.logger('Play TVBan', 'Error al agregar mis listas [%s]: %s' % (list_name, e))

	def add(self, url_params, list_name, iconImage='folder', original_image=False, cm_items=[]):
		isFolder = url_params.get('isFolder', 'true') == 'true'
		try:
			if original_image: icon = iconImage
			else: icon = k.resolve_list_icon(iconImage)
		except: icon = k.get_icon('folder')
		folder_params = dict(url_params)
		folder_params.pop('isFolder', None)
		url = k.build_folder_url(folder_params) if isFolder else k.build_url(folder_params)
		listitem = self.make_listitem()
		listitem.setLabel(list_name)
		listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, 'fanart': self.fanart, 'banner': icon, 'landscape': icon})
		info_tag = listitem.getVideoInfoTag(True)
		info_tag.setPlot(' ')
		if not self.is_external:
			if isFolder:
				shortcut_params = dict(url_params)
				shortcut_params.update({'iconImage': iconImage, 'name': list_name})
				folder_item = ('[B]Añadir a Carpeta de Accesos Directos[/B]', self.run_plugin % self.build_url({'mode': 'menu_editor.shortcut_folder_add_known', 'url': self.build_url(shortcut_params)}))
				if cm_items: cm_items.append(folder_item)
				else: cm_items = [folder_item]
			listitem.addContextMenuItems(cm_items)
		self.add_item(int(sys.argv[1]), url, listitem, isFolder)

	def end_directory(self, cache_to_disc=True, update_listing=False, skip_view_mode=False):
		handle = int(sys.argv[1])
		k.set_content(handle, k.MENU_FOLDER_CONTENT)
		k.set_category(handle, self.category_name)
		k.end_directory(handle, updateListing=update_listing, cacheToDisc=cache_to_disc)
		if not skip_view_mode:
			k.set_view_mode('view.main', k.MENU_FOLDER_CONTENT)