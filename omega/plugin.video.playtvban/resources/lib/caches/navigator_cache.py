# -*- coding: utf-8 -*-
from caches.base_cache import connect_database
from modules.kodi_utils import get_property, set_property, clear_property
# from modules.kodi_utils import logger

class NavigatorCache:
	root_list = [
	{'name': 'Películas', 'mode': 'navigator.main', 'action': 'MovieList', 'iconImage': 'movies'},
	{'name': 'Series', 'mode': 'navigator.main', 'action': 'TVShowList', 'iconImage': 'tv'},
	{'name': 'Anime', 'mode': 'navigator.main', 'action': 'AnimeList', 'iconImage': 'anime'},
	{'name': 'Personas', 'mode': 'navigator.people', 'iconImage': 'empty_person'},
	{'name': 'Buscar', 'mode': 'navigator.search', 'iconImage': 'search'},
	{'name': 'Descubrir', 'mode': 'navigator.discover', 'iconImage': 'discover'},
	{'name': 'Listas Aleatorias', 'mode': 'navigator.random_lists', 'iconImage': 'random'},
	{'name': 'MIs Listas', 'mode': 'navigator.my_lists', 'iconImage': 'lists'},
	{'name': 'Mis Servicios', 'mode': 'navigator.premium', 'iconImage': 'premium'},
	{'name': 'Favoritos', 'mode': 'navigator.favorites', 'iconImage': 'favorites'},
	{'name': 'Descargas', 'mode': 'navigator.downloads', 'iconImage': 'downloads'},
	{'name': 'Herramientas', 'mode': 'navigator.tools', 'iconImage': 'settings2'}
				]
	movie_list = [
	{'name': 'Tendencias', 'mode': 'build_movie_list', 'action': 'trakt_movies_trending', 'random_support': 'true', 'iconImage': 'trending'},
	{'name': 'Tendencias Recientes', 'mode': 'build_movie_list', 'action': 'trakt_movies_trending_recent', 'random_support': 'true', 'iconImage': 'trending_recent'},
	{'name': 'Popular', 'mode': 'build_movie_list', 'action': 'tmdb_movies_popular', 'random_support': 'true', 'iconImage': 'popular'},
	{'name': 'Popular Hoy', 'mode': 'build_movie_list', 'action': 'tmdb_movies_popular_today', 'random_support': 'true', 'iconImage': 'popular_today'},
	{'name': 'Estrenos', 'mode': 'build_movie_list', 'action': 'tmdb_movies_premieres', 'random_support': 'true', 'iconImage': 'fresh'},
	{'name': 'Últimos Lanzamientos', 'mode': 'build_movie_list', 'action': 'tmdb_movies_latest_releases', 'random_support': 'true', 'iconImage': 'dvd'},
	{'name': 'Más Vistas', 'mode': 'build_movie_list', 'action': 'movies_most_watched', 'random_support': 'true', 'iconImage': 'most_watched'},
	{'name': 'Más Favoritas', 'mode': 'build_movie_list', 'action': 'trakt_movies_most_favorited', 'random_support': 'true', 'iconImage': 'favorites'},
	{'name': 'Top 10 Taquilla', 'mode': 'build_movie_list', 'action': 'trakt_movies_top10_boxoffice', 'iconImage': 'box_office'},
	{'name': 'Taquillazos', 'mode': 'build_movie_list', 'action': 'tmdb_movies_blockbusters', 'random_support': 'true', 'iconImage': 'most_voted'},
	{'name': 'En Cines', 'mode': 'build_movie_list', 'action': 'tmdb_movies_in_theaters', 'random_support': 'true', 'iconImage': 'intheatres'},
	{'name': 'Próximamente', 'mode': 'build_movie_list', 'action': 'tmdb_movies_upcoming', 'random_support': 'true', 'iconImage': 'lists'},
	{'name': 'Ganadoras del Óscar', 'mode': 'build_movie_list', 'action': 'tmdb_movies_oscar_winners', 'random_support': 'true', 'iconImage': 'oscar_winners'},
	{'name': 'Géneros', 'mode': 'navigator.genres', 'menu_type': 'movie', 'random_support': 'true', 'iconImage': 'genres'},
	{'name': 'Proveedores', 'mode': 'navigator.providers', 'menu_type': 'movie', 'random_support': 'true', 'iconImage': 'providers'},
	{'name': 'Idiomas', 'mode': 'navigator.languages', 'menu_type': 'movie', 'random_support': 'true', 'iconImage': 'languages'},
	{'name': 'Años', 'mode': 'navigator.years', 'menu_type': 'movie', 'random_support': 'true', 'iconImage': 'calender'},
	{'name': 'Décadas', 'mode': 'navigator.decades', 'menu_type': 'movie', 'random_support': 'true', 'iconImage': 'calendar_decades'},
	{'name': 'Clasificaciones', 'mode': 'navigator.certifications', 'menu_type': 'movie', 'random_support': 'true', 'iconImage': 'certifications'},
	{'name': 'Porque Viste...', 'iconImage': 'because_you_watched', 'mode': 'navigator.because_you_watched', 'menu_type': 'movie'},
	{'name': 'Vistos', 'mode': 'build_movie_list', 'action': 'watched_movies', 'iconImage': 'watched_1'},
	{'name': 'Vistos Recientemente', 'mode': 'build_movie_list', 'action': 'recent_watched_movies', 'iconImage': 'watched_recent'},
	{'name': 'En Progreso', 'mode': 'build_movie_list', 'action': 'in_progress_movies', 'iconImage': 'player'}
				]
	tvshow_list = [
	{'name': 'Tendencias', 'mode': 'build_tvshow_list', 'action': 'trakt_tv_trending', 'random_support': 'true', 'iconImage': 'trending'},
	{'name': 'Tendencias Recientes', 'mode': 'build_tvshow_list', 'action': 'trakt_tv_trending_recent', 'random_support': 'true', 'iconImage': 'trending_recent'},
	{'name': 'Popular', 'mode': 'build_tvshow_list', 'action': 'tmdb_tv_popular', 'random_support': 'true', 'iconImage': 'popular'},
	{'name': 'Popular Hoy', 'mode': 'build_tvshow_list', 'action': 'tmdb_tv_popular_today', 'random_support': 'true', 'iconImage': 'popular_today'},
	{'name': 'Estrenos', 'mode': 'build_tvshow_list', 'action': 'tmdb_tv_premieres', 'random_support': 'true', 'iconImage': 'fresh'},
	{'name': 'Más Vistas', 'mode': 'build_tvshow_list', 'action': 'tv_most_watched', 'random_support': 'true', 'iconImage': 'most_watched'},
	{'name': 'Más Favoritas', 'mode': 'build_tvshow_list', 'action': 'trakt_tv_most_favorited', 'random_support': 'true', 'iconImage': 'favorites'},
	{'name': 'Se Emiten Hoy', 'mode': 'build_tvshow_list', 'action': 'tmdb_tv_airing_today', 'random_support': 'true', 'iconImage': 'live'},
	{'name': 'En Emisión', 'mode': 'build_tvshow_list', 'action': 'tmdb_tv_on_the_air', 'random_support': 'true', 'iconImage': 'ontheair'},
	{'name': 'Próximamente', 'mode': 'build_tvshow_list', 'action': 'tmdb_tv_upcoming', 'random_support': 'true', 'iconImage': 'lists'},
	{'name': 'Géneros', 'mode': 'navigator.genres', 'menu_type': 'tvshow', 'random_support': 'true', 'iconImage': 'genres'},
	{'name': 'Proveedores', 'mode': 'navigator.providers', 'menu_type': 'tvshow', 'random_support': 'true', 'iconImage': 'providers'},
	{'name': 'Cadenas', 'mode': 'navigator.networks', 'menu_type': 'tvshow', 'random_support': 'true', 'iconImage': 'networks'},
	{'name': 'Idiomas', 'mode': 'navigator.languages', 'menu_type': 'tvshow', 'random_support': 'true', 'iconImage': 'languages'},
	{'name': 'Años', 'mode': 'navigator.years', 'menu_type': 'tvshow', 'random_support': 'true', 'iconImage': 'calender'},
	{'name': 'Décadas', 'mode': 'navigator.decades', 'menu_type': 'tvshow', 'random_support': 'true', 'iconImage': 'calendar_decades'},
	{'name': 'Clasificaciones', 'mode': 'navigator.certifications', 'menu_type': 'tvshow', 'random_support': 'true', 'iconImage': 'certifications'},
	{'name': 'Porque Viste...', 'mode': 'navigator.because_you_watched', 'menu_type': 'tvshow', 'iconImage': 'because_you_watched'},
	{'name': 'Vistas', 'mode': 'build_tvshow_list', 'action': 'watched_tvshows', 'iconImage': 'watched_1'},
	{'name': 'Vistas Recientemente', 'mode': 'build_tvshow_list', 'action': 'recent_watched_tvshows', 'iconImage': 'watched_recent'},
	{'name': 'En Progreso', 'mode': 'build_tvshow_list', 'action': 'in_progress_tvshows', 'iconImage': 'in_progress_tvshow'},
	{'name': 'Episodios Vistos Recientemente', 'mode': 'build_recently_watched_episode', 'iconImage': 'watched_recent'},
	{'name': 'Episodios en Progreso', 'mode': 'build_in_progress_episode', 'iconImage': 'player'},
	{'name': 'Próximos Episodios', 'mode': 'build_next_episode', 'iconImage': 'next_episodes'}
				]
	anime_list = [
	{'name': 'Anime Tendencias', 'mode': 'build_tvshow_list', 'action': 'trakt_anime_trending', 'random_support': 'true', 'iconImage': 'trending'},
	{'name': 'Anime Tendencias Recientes', 'mode': 'build_tvshow_list', 'action': 'trakt_anime_trending_recent', 'random_support': 'true', 'iconImage': 'trending_recent'},
	{'name': 'Anime Popular', 'mode': 'build_tvshow_list', 'action': 'tmdb_anime_popular', 'random_support': 'true', 'iconImage': 'popular'},
	{'name': 'Anime Popular Reciente', 'mode': 'build_tvshow_list', 'action': 'tmdb_anime_popular_recent', 'random_support': 'true', 'iconImage': 'popular_today'},
	{'name': 'Anime Estrenos', 'mode': 'build_tvshow_list', 'action': 'tmdb_anime_premieres', 'random_support': 'true', 'iconImage': 'fresh'},
	{'name': 'Anime Más Vistos', 'mode': 'build_tvshow_list', 'action': 'anime_most_watched', 'random_support': 'true', 'iconImage': 'most_watched'},
	{'name': 'Anime Más Favoritos', 'mode': 'build_tvshow_list', 'action': 'trakt_anime_most_favorited', 'random_support': 'true', 'iconImage': 'favorites'},
	{'name': 'Anime En Emisión', 'mode': 'build_tvshow_list', 'action': 'tmdb_anime_on_the_air', 'random_support': 'true', 'iconImage': 'ontheair'},
	{'name': 'Anime Próximamente', 'mode': 'build_tvshow_list', 'action': 'tmdb_anime_upcoming', 'random_support': 'true', 'iconImage': 'lists'},
	{'name': 'Anime Géneros', 'mode': 'navigator.genres', 'menu_type': 'anime', 'random_support': 'true', 'iconImage': 'genres'},
	{'name': 'Anime Proveedores', 'mode': 'navigator.providers', 'menu_type': 'anime', 'random_support': 'true', 'iconImage': 'providers'},
	{'name': 'Anime Años', 'mode': 'navigator.years', 'menu_type': 'anime', 'random_support': 'true', 'iconImage': 'calender'},
	{'name': 'Anime Décadas', 'mode': 'navigator.decades', 'menu_type': 'anime', 'random_support': 'true', 'iconImage': 'calendar_decades'},
	{'name': 'Anime Clasificaciones', 'mode': 'navigator.certifications', 'menu_type': 'anime', 'random_support': 'true', 'iconImage': 'certifications'},
	{'name': 'Anime Vistos', 'mode': 'build_tvshow_list', 'action': 'watched_tvshows', 'is_anime_list': 'true', 'iconImage': 'watched_1'},
	{'name': 'Anime Vistos Recientemente', 'mode': 'build_tvshow_list', 'action': 'recent_watched_tvshows', 'is_anime_list': 'true', 'iconImage': 'watched_recent'},
	{'name': 'Anime En Progreso', 'mode': 'build_tvshow_list', 'action': 'in_progress_tvshows', 'is_anime_list': 'true', 'iconImage': 'in_progress_tvshow'},
	{'name': 'Anime Episodios Vistos Recientemente', 'mode': 'build_recently_watched_episode', 'is_anime_list': 'true', 'iconImage': 'watched_recent'},
	{'name': 'Anime Episodios En Progreso', 'mode': 'build_in_progress_episode', 'is_anime_list': 'true', 'iconImage': 'player'},
	{'name': 'Anime Próximos Episodios', 'mode': 'build_next_episode', 'iconImage': 'next_episodes', 'is_anime_list': 'true'}
					]

	main_menus = {'RootList': root_list, 'MovieList': movie_list, 'TVShowList': tvshow_list, 'AnimeList': anime_list}
	
	def get_main_lists(self, list_name):
		default_contents = self.get_memory_cache(list_name, 'default')
		if not default_contents:
			default_contents = self.get_list(list_name, 'default')
			if default_contents == None:
				self.rebuild_database()
				return self.get_main_lists(list_name)
			try: edited_contents = self.get_list(list_name, 'edited')
			except: edited_contents = None
		else:
			edited_contents = self.get_memory_cache(list_name, 'edited')
		return default_contents, edited_contents

	def get_list(self, list_name, list_type):
		contents = None
		try:
			dbcon = connect_database('navigator_db')
			contents = eval(dbcon.execute('SELECT list_contents FROM navigator WHERE list_name = ? AND list_type = ?', (list_name, list_type)).fetchone()[0])
			self.set_memory_cache(list_name, list_type, contents)
		except: pass
		return contents

	def set_list(self, list_name, list_type, list_contents):
		dbcon = connect_database('navigator_db')
		dbcon.execute('INSERT OR REPLACE INTO navigator VALUES (?, ?, ?)', (list_name, list_type, repr(list_contents)))
		self.set_memory_cache(list_name, list_type, list_contents)

	def delete_list(self, list_name, list_type):
		dbcon = connect_database('navigator_db')
		dbcon.execute('DELETE FROM navigator WHERE list_name=? and list_type=?', (list_name, list_type))
		self.delete_memory_cache(list_name, list_type)
		dbcon.execute('VACUUM')
	
	def get_memory_cache(self, list_name, list_type):
		try: return eval(get_property(self._get_list_prop(list_type) % list_name))
		except: return None
	
	def set_memory_cache(self, list_name, list_type, list_contents):
		set_property(self._get_list_prop(list_type) % list_name, repr(list_contents))

	def delete_memory_cache(self, list_name, list_type):
		clear_property(self._get_list_prop(list_type) % list_name)

	def get_shortcut_folders(self):
		try:
			dbcon = connect_database('navigator_db')
			folders = dbcon.execute('SELECT list_name, list_contents FROM navigator WHERE list_type = ?', ('shortcut_folder',)).fetchall()
			folders = sorted([(str(i[0]), eval(i[1])) for i in folders], key=lambda s: s[0].lower())
		except: folders = []
		return folders

	def get_shortcut_folder_contents(self, list_name):
		try:
			dbcon = connect_database('navigator_db')
			contents = eval(dbcon.execute('SELECT list_contents FROM navigator WHERE list_name = ? AND list_type = ?', (list_name, 'shortcut_folder')).fetchone()[0])
		except: contents = []
		return contents

	def currently_used_list(self, list_name):
		used_list = None
		try:
			used_list = self.get_memory_cache(list_name, 'edited') or self.get_memory_cache(list_name, 'default') \
						or self.get_list(list_name, 'edited') or self.get_list(list_name, 'default')
		except: pass
		if not used_list:
			try: self.rebuild_database()
			except: pass
			used_list = NavigatorCache.main_menus.get(list_name) or []
		return used_list

	def rebuild_database(self):
		dbcon = connect_database('navigator_db')
		main_items = NavigatorCache.main_menus.items()
		for list_name, list_contents in main_items: self.set_list(list_name, 'default', list_contents)

	def _get_list_prop(self, list_type):
		return {'default': 'playtvban_%s_default', 'edited': 'playtvban_%s_edited', 'shortcut_folder': 'playtvban_%s_shortcut_folder'}[list_type]
	
	def random_movie_lists(self):
		m_list = NavigatorCache.movie_list
		movie_random_converts = {'navigator.genres': 'tmdb_movies_genres', 'navigator.providers': 'tmdb_movies_providers',  'navigator.languages': 'tmdb_movies_languages',
								'navigator.years': 'tmdb_movies_year', 'navigator.decades': 'tmdb_movies_decade', 'navigator.certifications': 'tmdb_movies_certifications'}
		return [dict(i, **{'mode': 'random.build_movie_list', 'action': i.get('action') or movie_random_converts[i['mode']],
							'random': 'true', 'name': 'Películas Aleatorias %s' % i['name'], 'menu_type': 'movie'}) for i in m_list if 'random_support' in i]

	def random_tvshow_lists(self):
		t_list = NavigatorCache.tvshow_list
		tvshow_random_converts = {'navigator.genres': 'tmdb_tv_genres', 'navigator.providers': 'tmdb_tv_providers', 'navigator.networks': 'tmdb_tv_networks',
								'navigator.languages': 'tmdb_tv_languages', 'navigator.years': 'tmdb_tv_year', 'navigator.decades': 'tmdb_tv_decade',
								'navigator.certifications': 'trakt_tv_certifications'}
		return [dict(i, **{'mode': 'random.build_tvshow_list', 'action': i.get('action') or tvshow_random_converts[i['mode']],
							'random': 'true', 'name': 'Series Aleatorias %s' % i['name'], 'menu_type': 'tvshow'}) for i in t_list if 'random_support' in i]

	def random_anime_lists(self):
		a_list = NavigatorCache.anime_list
		anime_random_converts = {'navigator.genres': 'tmdb_anime_genres', 'navigator.providers': 'tmdb_anime_providers', 'navigator.years': 'tmdb_anime_year',
								'navigator.decades': 'tmdb_anime_decade', 'navigator.certifications': 'trakt_anime_certifications'}
		return [dict(i, **{'mode': 'random.build_tvshow_list', 'action': i.get('action') or anime_random_converts[i['mode']],
							'random': 'true', 'name': i['name'].replace('Anime', 'Anime Aleatorio'), 'menu_type': 'tvshow'}) for i in a_list if 'random_support' in i]

	def random_because_you_watched_lists(self):
		return [
			{'mode': 'random.build_movie_list', 'action': 'because_you_watched', 'name': 'Películas Aleatorias Basadas en lo que Has Visto', 'iconImage': 'movies', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'because_you_watched', 'name': 'Series Aleatorias Basadas en lo que Has Visto', 'iconImage': 'tv', 'random': 'true'},
				]

	def random_tmdb_lists(self):
		return [
			{'mode': 'random.build_tmdb_lists_contents', 'list_id': 'watchlist', 'media_type': 'movie', 'name': 'Watchlist Aleatoria de Películas de TMDb', 'iconImage': 'tmdb', 'random': 'true'},
			{'mode': 'random.build_tmdb_lists_contents', 'list_id': 'watchlist', 'media_type': 'tv', 'name': 'Watchlist Aleatoria de Series de TMDb', 'iconImage': 'tmdb', 'random': 'true'},
			{'mode': 'random.build_tmdb_lists_contents', 'list_id': 'favorites', 'media_type': 'movie', 'name': 'Favoritos Aleatorios de Películas de TMDb', 'iconImage': 'tmdb', 'random': 'true'},
			{'mode': 'random.build_tmdb_lists_contents', 'list_id': 'favorites', 'media_type': 'tv', 'name': 'Favoritos Aleatorios de Series de TMDb', 'iconImage': 'tmdb', 'random': 'true'},
			{'mode': 'random.build_tmdb_lists_contents', 'list_id': 'recommendations', 'media_type': 'movie', 'name': 'Recomendaciones Aleatorias de Películas de TMDb',
			'iconImage': 'tmdb', 'random': 'true'},
			{'mode': 'random.build_tmdb_lists_contents', 'list_id': 'recommendations', 'media_type': 'tv', 'name': 'Recomendaciones Aleatorias de Series de TMDb',
			'iconImage': 'tmdb', 'random': 'true'},
			{'mode': 'tmdblist.get_tmdb_lists', 'name': 'Mis Listas de TMDb Mezcladas Aleatoriamente (Todas)', 'iconImage': 'tmdb', 'random': 'true', 'shuffle': 'true'},
			{'mode': 'random.build_tmdb_lists', 'name': 'Mi Lista Aleatoria de TMDb (Individual)', 'iconImage': 'tmdb', 'random': 'true'}
				]

	def random_personal_lists(self):
		return [
			{'mode': 'personal_lists.get_personal_lists', 'name': 'Listas Personales Mezcladas Aleatoriamente (Todas)', 'iconImage': 'lists', 'random': 'true', 'shuffle': 'true'},
			{'mode': 'random.build_personal_lists', 'name': 'Lista Personal Aleatoria', 'iconImage': 'lists', 'random': 'true'}
				]

	def random_trakt_lists_personal(self):
		return [
			{'mode': 'random.build_movie_list', 'action': 'trakt_collection_lists', 'name': 'Colección Aleatoria de Películas de Trakt', 'iconImage': 'movies', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'trakt_collection_lists', 'name': 'Colección Aleatoria de Series de Trakt', 'iconImage': 'tv', 'random': 'true'},
			{'mode': 'random.build_movie_list', 'action': 'trakt_watchlist_lists', 'name': 'Watchlist Aleatoria de Películas de Trakt', 'iconImage': 'movies', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'trakt_watchlist_lists', 'name': 'Watchlist Aleatoria de Series de Trakt', 'iconImage': 'tv', 'random': 'true'},
			{'mode': 'random.build_movie_list', 'action': 'trakt_recommendations', 'new_page': 'movies', 'name': 'Películas Recomendadas Aleatorias de Trakt',
			'iconImage': 'movies', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'trakt_recommendations', 'new_page': 'shows', 'name': 'Series Recomendadas Aleatorias de Trakt',
			'iconImage': 'tv', 'random': 'true'},
			{'mode': 'trakt.list.get_trakt_lists', 'list_type': 'my_lists', 'name': 'Mis Listas de Trakt Mezcladas Aleatoriamente (Todas)',
			'iconImage': 'trakt', 'random': 'true', 'shuffle': 'true'},
			{'mode': 'random.build_trakt_lists', 'list_type': 'my_lists', 'name': 'Mi Lista Aleatoria de Trakt', 'iconImage': 'trakt', 'random': 'true'},
			{'mode': 'trakt.list.get_trakt_lists', 'list_type': 'liked_lists', 'name': 'Listas que me Gustan de Trakt Mezcladas Aleatoriamente (Todas)',
			'iconImage': 'trakt', 'random': 'true', 'shuffle': 'true'},
			{'mode': 'random.build_trakt_lists', 'list_type': 'liked_lists', 'name': 'Lista Aleatoria de Favoritos de Trakt', 'iconImage': 'trakt', 'random': 'true'},
				]

	def random_trakt_lists_public(self):
		return [
			{'mode': 'trakt.list.get_trakt_user_lists', 'list_type': 'trending', 'category_name': 'Listas de Usuarios en Tendencia Aleatorias', 'name': 'Listas de Usuarios en Tendencia Aleatorias (Todas)',
			'iconImage': 'trakt', 'random': 'true', 'shuffle': 'true'},
			{'mode': 'random.build_trakt_lists', 'list_type': 'trending', 'category_name': 'Listas de Usuarios en Tendencia Aleatorias', 'name': 'Lista de Usuarios en Tendencia Aleatoria',
			'iconImage': 'trakt', 'random': 'true'},
			{'mode': 'trakt.list.get_trakt_user_lists', 'list_type': 'popular', 'category_name': 'Listas Populares de Usuarios Aleatorias', 'name': 'Listas Populares de Usuarios Aleatorias (Todas)',
			'iconImage': 'trakt', 'random': 'true', 'shuffle': 'true'},
			{'mode': 'random.build_trakt_lists', 'list_type': 'popular', 'category_name': 'Listas Populares de Usuarios Aleatorias', 'name': 'Lista Popular de Usuarios Aleatoria',
			'iconImage': 'trakt', 'random': 'true'}
				]

	def random_simkl_lists(self):
		return [
			{'mode': 'random.build_movie_list', 'action': 'simkl_plantowatch', 'name': 'Películas Aleatorias Pendientes de Ver de Simkl', 'iconImage': 'simkl', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'simkl_plantowatch', 'name': 'Series Aleatorias Pendientes de Ver de Simkl', 'iconImage': 'simkl', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'simkl_watching', 'name': 'Series Aleatorias en Seguimiento de Simkl', 'iconImage': 'simkl', 'random': 'true'},
			{'mode': 'random.build_movie_list', 'action': 'simkl_completed', 'name': 'Películas Aleatorias Completadas de Simkl', 'iconImage': 'simkl', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'simkl_completed', 'name': 'Series Aleatorias Completadas de Simkl', 'iconImage': 'simkl', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'simkl_hold', 'name': 'Series Aleatorias en Pausa de Simkl', 'iconImage': 'simkl', 'random': 'true'},
			{'mode': 'random.build_movie_list', 'action': 'simkl_dropped', 'name': 'Películas Aleatorias Abandonadas de Simkl', 'iconImage': 'simkl', 'random': 'true'},
			{'mode': 'random.build_tvshow_list', 'action': 'simkl_dropped', 'name': 'Series Aleatorias Abandonadas de Simkl', 'iconImage': 'simkl', 'random': 'true'},
				]

def migrate_my_content_nav_mode():
	"""Rewrite stored menus that still use navigator.my_content to navigator.my_lists."""
	nc = NavigatorCache()
	changed = False
	def _patch(items):
		nonlocal changed
		if not items: return items
		out = []
		for item in items:
			row = dict(item)
			if row.get('mode') == 'navigator.my_content':
				row['mode'] = 'navigator.my_lists'
				changed = True
			out.append(row)
		return out
	try:
		dbcon = connect_database('navigator_db')
		for list_name, list_type, raw in dbcon.execute('SELECT list_name, list_type, list_contents FROM navigator').fetchall():
			try: contents = eval(raw)
			except: continue
			patched = _patch(contents)
			if patched != contents:
				nc.set_list(list_name, list_type, patched)
				changed = True
	except: pass
	if changed:
		for list_name in NavigatorCache.main_menus:
			nc.delete_memory_cache(list_name, 'default')
			nc.delete_memory_cache(list_name, 'edited')
	return changed

navigator_cache = NavigatorCache()