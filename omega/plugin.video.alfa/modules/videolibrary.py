# -*- coding: utf-8 -*-

import re
import os
import traceback

from channelselector import get_thumb
from core import filetools
from core import scrapertools
from core import videolibrarytools
from core.item import Item
from core import tmdb
from platformcode import config, logger
from platformcode import platformtools
from lib import generictools


def mainlist(item):
    logger.info()

    itemlist = list()
    itemlist.append(
        Item(
            channel=item.channel,
            action="list_movies",
            title=config.get_localized_string(60509),
            category=config.get_localized_string(70270),
            thumbnail=get_thumb("videolibrary_movie.png"),
        )
    )
    itemlist.append(
        Item(
            channel=item.channel,
            action="list_tvshows",
            title=config.get_localized_string(60600),
            category=config.get_localized_string(70271),
            thumbnail=get_thumb("videolibrary_tvshow.png"),
        )
    )

    return itemlist


def channel_config(item):
    return platformtools.show_channel_settings(
        channelpath=os.path.join(config.get_runtime_path(), "channels", item.channel),
        caption=config.get_localized_string(60598),
    )


def list_movies(item, silent=False):
    logger.info()

    itemlist = []
    dead_list = []
    zombie_list = []
    tmdb_upd = False

    for raiz, subcarpetas, ficheros in filetools.walk(videolibrarytools.MOVIES_PATH):
        for f in ficheros:
            if f.endswith(".nfo"):
                nfo_path = filetools.join(raiz, f)

                # Sincronizamos las películas vistas desde la videoteca de Kodi con la de Alfa
                try:
                    if config.is_xbmc():  # Si es Kodi, lo hacemos
                        from platformcode import xbmc_videolibrary

                        xbmc_videolibrary.mark_content_as_watched_on_alfa(nfo_path)
                except Exception:
                    logger.error(traceback.format_exc())

                head_nfo, new_item = videolibrarytools.read_nfo(nfo_path)
                new_item.module = "videolibrary"

                if not new_item or not isinstance(
                    new_item.library_playcounts, dict
                ):  # Si no ha leído bien el .nfo, pasamos a la siguiente
                    logger.error(".nfo erroneo en " + str(nfo_path))
                    continue

                if len(new_item.library_urls) > 1:
                    multicanal = True
                else:
                    multicanal = False

                ## verifica la existencia de los canales, en caso de no existir el canal se pregunta si se quieren
                ## eliminar los enlaces de dicho canal
                zombie = False
                for canal_org in new_item.library_urls:
                    canal = generictools.verify_channel(canal_org)
                    try:
                        channel_verify = __import__(
                            "channels.%s" % canal, fromlist=["channels.%s" % canal]
                        )
                        logger.debug("El canal %s parece correcto" % channel_verify)
                    except Exception:
                        dead_item = Item(
                            multicanal=multicanal,
                            contentType="movie",
                            dead=canal,
                            path=raiz,
                            nfo=nfo_path,
                            library_urls=new_item.library_urls,
                            infoLabels={"title": new_item.contentTitle},
                        )
                        if (
                            canal not in dead_list
                            and canal not in zombie_list
                            and not new_item.zombie
                        ):
                            if (
                                new_item.emergency_urls
                                and isinstance(new_item.emergency_urls, dict)
                                and new_item.emergency_urls.get(canal_org, False)
                            ):
                                confirm = False
                            else:
                                logger.error(
                                    "Parece que el canal {} ya no existe.".format(
                                        canal.upper()
                                    )
                                )
                                logger.debug(".NFO: %s" % new_item)
                                logger.debug("dead_list: %s" % dead_list)
                                logger.debug("zombie_list: %s" % zombie_list)
                                confirm = platformtools.dialog_yesno(
                                    "Videoteca",
                                    "Parece que el canal [COLOR red]{}[/COLOR] ya no existe.".format(
                                        canal.upper()
                                    ),
                                    "¿Deseas eliminar los enlaces de este canal?",
                                )

                        elif canal in zombie_list or new_item.zombie:
                            confirm = False
                            if not new_item.zombie:
                                nfo_path = filetools.join(raiz, f)
                                zombie = True
                                zombie_item = new_item.clone(zombie=zombie)
                                res = videolibrarytools.write_nfo(
                                    nfo_path, head_nfo, zombie_item
                                )
                                if not res:
                                    logger.error(
                                        "ERROR a escribir el .nfo: %s: %s"
                                        % (nfo_path, zombie_item)
                                    )
                        else:
                            confirm = True

                        if confirm:
                            delete(dead_item)
                            if canal not in dead_list:
                                dead_list.append(canal)
                            continue
                        else:
                            if canal not in zombie_list:
                                zombie_list.append(canal)
                                nfo_path = filetools.join(raiz, f)
                                zombie = True
                                zombie_item = new_item.clone(zombie=zombie)
                                res = videolibrarytools.write_nfo(
                                    nfo_path, head_nfo, zombie_item
                                )
                                if not res:
                                    logger.error(
                                        "ERROR a escribir el .nfo: %s: %s"
                                        % (nfo_path, zombie_item)
                                    )

                if len(dead_list) > 0:
                    for canal in dead_list:
                        if canal in new_item.library_urls:
                            del new_item.library_urls[canal]

                new_item.nfo = nfo_path
                new_item.path = raiz
                new_item.thumbnail = new_item.contentThumbnail
                new_item.unify_extended = True
                new_item.text_color = get_color_from_settings("movie")
                strm_path = new_item.strm_path.replace("\\", "/").rstrip("/")
                if "/" in new_item.path:
                    new_item.strm_path = strm_path

                if not filetools.exists(
                    filetools.join(new_item.path, filetools.basename(strm_path))
                ):
                    # Si se ha eliminado el strm desde la bilbioteca de kodi, no mostrarlo
                    continue

                # Menu contextual: Marcar como visto/no visto
                visto = new_item.library_playcounts.get(os.path.splitext(f)[0], 0)
                new_item.infoLabels["playcount"] = visto
                if visto > 0:
                    texto_visto = config.get_localized_string(60016)
                    contador = 0
                else:
                    texto_visto = config.get_localized_string(60017)
                    contador = 1

                # Menu contextual: Eliminar serie/canal
                num_canales = len(new_item.library_urls)
                if "downloads" in new_item.library_urls:
                    num_canales -= 1
                if num_canales > 1:
                    texto_eliminar = config.get_localized_string(60018)
                else:
                    texto_eliminar = config.get_localized_string(60019)
                texto_reset = "Sobrescribir película"

                new_item.context = [
                    {
                        "title": texto_visto,
                        "action": "mark_content_as_watched",
                        "channel": "videolibrary",
                        "playcount": contador,
                    },
                    {
                        "title": texto_eliminar,
                        "action": "delete",
                        "channel": "videolibrary",
                        "multicanal": multicanal,
                    },
                    {
                        "title": texto_reset,
                        "action": "reset_movie",
                        "channel": "videolibrary",
                        "multicanal": multicanal,
                    },
                ]
                # ,{"title": "Cambiar contenido (PENDIENTE)",
                # "action": "",
                # "channel": "videolibrary"}]
                # logger.debug("new_item: " + new_item.tostring('\n'))

                if new_item.infoLabels["tmdb_id"]:
                    tmdb_upd = True

                itemlist.append(new_item)

    if tmdb_upd:
        # Pasamos a TMDB la lista completa Itemlist para actualizar Thumbnail y Fanart
        tmdb.set_infoLabels(itemlist, True)

        for item_tmdb in itemlist:
            # Actualiza Thumbnail y Fanart
            item_tmdb.infoLabels["thumbnail"] = item_tmdb.infoLabels[
                "thumbnail"
            ].replace("http:", "https:")
            if item_tmdb.infoLabels["thumbnail"]:
                item_tmdb.thumbnail = item_tmdb.infoLabels["thumbnail"]
            item_tmdb.infoLabels["fanart"] = item_tmdb.infoLabels["fanart"].replace(
                "http:", "https:"
            )
            if item_tmdb.infoLabels["fanart"]:
                item_tmdb.fanart = item_tmdb.infoLabels["fanart"]

    if silent is False:
        return sorted(itemlist, key=lambda it: it.title.lower())
    else:
        return


def list_tvshows(item):
    logger.info()
    itemlist = []
    dead_list = []
    zombie_list = []

    # Obtenemos todos los tvshow.nfo de la videoteca de SERIES recursivamente
    for raiz, subcarpetas, ficheros in filetools.walk(videolibrarytools.TVSHOWS_PATH):
        for f in ficheros:
            if f == "tvshow.nfo":
                tvshow_path = filetools.join(raiz, f)
                # logger.debug(tvshow_path)

                # Sincronizamos los episodios vistos desde la videoteca de Kodi con la de Alfa
                try:
                    if config.is_xbmc():  # Si es Kodi, lo hacemos
                        from platformcode import xbmc_videolibrary

                        xbmc_videolibrary.mark_content_as_watched_on_alfa(tvshow_path)
                except Exception:
                    logger.error(traceback.format_exc())

                head_nfo, item_tvshow = videolibrarytools.read_nfo(tvshow_path)
                item_tvshow.module = "videolibrary"

                if (
                    not item_tvshow
                ):  # Si no ha leído bien el .nfo, pasamos a la siguiente
                    logger.error(".nfo erroneo en " + str(tvshow_path))
                    continue

                if len(item_tvshow.library_urls) > 1:
                    multicanal = True
                else:
                    multicanal = False

                # Si hay una inconsistencia en "mediatype", se arregla.  Afecta al menú contextual
                if item_tvshow.infoLabels.get("mediatype", "") != "tvshow":
                    item_tvshow.infoLabels["mediatype"] = "tvshow"
                    res = videolibrarytools.write_nfo(
                        tvshow_path, head_nfo, item_tvshow
                    )
                    if not res:
                        logger.error(
                            "ERROR a escribir el .nfo: %s: %s"
                            % (tvshow_path, item_tvshow)
                        )

                ## verifica la existencia de los canales, en caso de no existir el canal se pregunta si se quieren
                ## eliminar los enlaces de dicho canal
                zombie = False
                for canal_org in item_tvshow.library_urls:
                    canal = generictools.verify_channel(canal_org)
                    try:
                        channel_verify = __import__(
                            "channels.%s" % canal, fromlist=["channels.%s" % canal]
                        )
                        logger.debug("El canal %s parece correcto" % channel_verify)
                    except Exception:
                        dead_item = Item(
                            multicanal=multicanal,
                            contentType="tvshow",
                            dead=canal,
                            path=raiz,
                            nfo=tvshow_path,
                            library_urls=item_tvshow.library_urls,
                            infoLabels={"title": item_tvshow.contentTitle},
                        )
                        if (
                            canal not in dead_list
                            and canal not in zombie_list
                            and not item_tvshow.zombie
                        ):
                            if (
                                item_tvshow.emergency_urls
                                and isinstance(item_tvshow.emergency_urls, dict)
                                and item_tvshow.emergency_urls.get(canal_org, False)
                            ):
                                confirm = False
                                item_tvshow.active = 0
                            else:
                                logger.error(
                                    "Parece que el canal {} ya no existe.".format(
                                        canal.upper()
                                    )
                                )
                                logger.debug(".NFO: %s" % item_tvshow)
                                logger.debug("dead_list: %s" % dead_list)
                                logger.debug("zombie_list: %s" % zombie_list)
                                confirm = platformtools.dialog_yesno(
                                    "Videoteca",
                                    "Parece que el canal [COLOR red]{}[/COLOR] ya no existe.".format(
                                        canal.upper()
                                    ),
                                    "¿Deseas eliminar los enlaces de este canal?",
                                )

                        elif canal in zombie_list or item_tvshow.zombie:
                            confirm = False
                            if not item_tvshow.zombie:
                                tvshow_path = filetools.join(raiz, f)
                                zombie = True
                                zombie_item = item_tvshow.clone(zombie=zombie)
                                res = videolibrarytools.write_nfo(
                                    tvshow_path, head_nfo, zombie_item
                                )
                                if not res:
                                    logger.error(
                                        "ERROR a escribir el .nfo: %s: %s"
                                        % (tvshow_path, zombie_item)
                                    )
                        else:
                            confirm = True

                        if confirm:
                            delete(dead_item)
                            if canal not in dead_list:
                                dead_list.append(canal)
                            continue
                        else:
                            if canal not in zombie_list:
                                zombie_list.append(canal)
                                tvshow_path = filetools.join(raiz, f)
                                zombie = True
                                zombie_item = item_tvshow.clone(zombie=zombie)
                                res = videolibrarytools.write_nfo(
                                    tvshow_path, head_nfo, zombie_item
                                )
                                if not res:
                                    logger.error(
                                        "ERROR a escribir el .nfo: %s: %s"
                                        % (tvshow_path, zombie_item)
                                    )

                if len(dead_list) > 0:
                    for canal in dead_list:
                        if canal in item_tvshow.library_urls:
                            del item_tvshow.library_urls[canal]

                ### continua la carga de los elementos de la videoteca

                try:  # A veces da errores aleatorios, por no encontrar el .nfo.  Probablemente problemas de timing
                    item_tvshow.title = item_tvshow.contentTitle
                    item_tvshow.path = raiz
                    item_tvshow.nfo = tvshow_path
                    # Menu contextual: Marcar como visto/no visto
                    if item_tvshow.library_playcounts:
                        visto = item_tvshow.library_playcounts.get(
                            item_tvshow.contentTitle, 0
                        )
                    else:
                        item_tvshow, visto = verify_playcount_series(item_tvshow, raiz)
                        visto = int(visto)
                        if config.is_xbmc():  # Si es Kodi, lo hacemos
                            from platformcode import xbmc_videolibrary

                            xbmc_videolibrary.mark_content_as_watched_on_alfa(
                                tvshow_path
                            )
                    item_tvshow.infoLabels["playcount"] = visto
                    if visto > 0:
                        texto_visto = config.get_localized_string(60020)
                        contador = 0
                    else:
                        texto_visto = config.get_localized_string(60021)
                        contador = 1

                except Exception:
                    logger.error("No encuentra: " + str(tvshow_path))
                    logger.error(traceback.format_exc())
                    continue

                # Menu contextual: Buscar automáticamente nuevos episodios o no
                item_tvshow.unify_extended = True
                if item_tvshow.active and int(item_tvshow.active) > 0:
                    texto_update = config.get_localized_string(60022)
                    value = 0
                    item_tvshow.text_color = get_color_from_settings("tvshow_color")
                else:
                    texto_update = config.get_localized_string(60023)
                    value = 1
                    item_tvshow.text_color = get_color_from_settings("no_update_color")

                # Menu contextual: Eliminar serie/canal
                num_canales = len(item_tvshow.library_urls)
                if "downloads" in item_tvshow.library_urls:
                    num_canales -= 1
                if num_canales > 1:
                    texto_eliminar = config.get_localized_string(60024)
                else:
                    texto_eliminar = config.get_localized_string(60025)
                texto_reset = "Sobrescribir serie"

                item_tvshow.context = [
                    {
                        "title": texto_visto,
                        "action": "mark_content_as_watched",
                        "channel": "videolibrary",
                        "playcount": contador,
                    },
                    {
                        "title": texto_update,
                        "action": "mark_tvshow_as_updatable",
                        "channel": "videolibrary",
                        "active": value,
                    },
                    {
                        "title": texto_eliminar,
                        "action": "delete",
                        "channel": "videolibrary",
                        "multicanal": multicanal,
                    },
                    {
                        "title": texto_reset,
                        "action": "reset_serie",
                        "channel": "videolibrary",
                        "multicanal": multicanal,
                    },
                    {
                        "title": config.get_localized_string(70269),
                        "action": "update_tvshow",
                        "channel": "videolibrary",
                    },
                ]
                # ,{"title": "Cambiar contenido (PENDIENTE)",
                # "action": "",
                # "channel": "videolibrary"}]

                # logger.debug("item_tvshow:\n" + item_tvshow.tostring('\n'))

                # Actualiza Thumbnail y Fanart desde InfoLabels
                if item_tvshow.infoLabels["tmdb_id"]:
                    item_tvshow.infoLabels["thumbnail"] = item_tvshow.infoLabels[
                        "thumbnail"
                    ].replace("http:", "https:")
                    if item_tvshow.infoLabels["thumbnail"]:
                        item_tvshow.thumbnail = item_tvshow.infoLabels["thumbnail"]
                    item_tvshow.infoLabels["fanart"] = item_tvshow.infoLabels[
                        "fanart"
                    ].replace("http:", "https:")
                    if item_tvshow.infoLabels["fanart"]:
                        item_tvshow.fanart = item_tvshow.infoLabels["fanart"]

                ## verifica la existencia de los canales ##
                if len(item_tvshow.library_urls) > 0:
                    itemlist.append(item_tvshow)

    if itemlist:
        itemlist = sorted(itemlist, key=lambda it: it.title.lower())

        itemlist.append(
            Item(
                channel=item.channel,
                action="update_videolibrary",
                thumbnail=item.thumbnail,
                title=config.get_localized_string(60026),
                folder=False,
            )
        )

    return itemlist


def get_seasons(item):
    logger.info()
    # logger.debug("item:\n" + item.tostring('\n'))
    itemlist = []
    dict_temp = {}
    tmdb_upd = False

    raiz, carpetas_series, ficheros = next(filetools.walk(item.path))

    # Menu contextual: Releer tvshow.nfo
    head_nfo, item_nfo = videolibrarytools.read_nfo(item.nfo)

    if config.get_setting("videolibrary_merge_seasons") == 2:  # Siempre
        return get_episodes(item)

    for f in ficheros:
        if f.endswith(".json"):
            season = f.split("x")[0]
            dict_temp[season] = config.get_localized_string(60027) % season

    if (
        config.get_setting("videolibrary_merge_seasons") == 1 and len(dict_temp) == 1
    ):  # Sólo si hay una temporada
        return get_episodes(item)
    else:
        # En ocasiones llega informacion del episodio en el item, lo que confunde a tmdb
        # y crea una lista de episodios en vez de temporadas, borremosla
        if "episode" in item.infoLabels:
            del item.infoLabels["episode"]

        # TODO mostrar los episodios de la unica temporada "no vista", en vez de mostrar el Item "temporada X" previo
        # si está marcado "ocultar los vistos" en el skin, se ejecutaria esto
        #     se comprueba cada temporada en dict_temp si está visto.
        #          si hay una sola temporada y no_pile_on_seasons == 1, se devuelve get(episodios)
        #          si está todo visto, hacemos como actualmente <-- el else no se hace nada.. CREO
        # if config.get_setting("videolibrary_merge_seasons") == 1 and len(dict_temp_Visible) == 1:  # Sólo si hay una temporada

        # Creamos un item por cada temporada
        for season, title in list(dict_temp.items()):
            new_item = item.clone(
                action="get_episodes",
                title=title,
                contentSeason=season,
                filtrar_season=True,
            )

            # Menu contextual: Marcar la temporada como vista o no
            visto = item_nfo.library_playcounts.get("season %s" % season, 0)
            new_item.infoLabels["playcount"] = visto
            if visto > 0:
                texto = config.get_localized_string(60028)
                value = 0
            else:
                texto = config.get_localized_string(60029)
                value = 1
            new_item.context = [
                {
                    "title": texto,
                    "action": "mark_season_as_watched",
                    "channel": "videolibrary",
                    "playcount": value,
                }
            ]

            if new_item.infoLabels["tmdb_id"]:
                tmdb_upd = True

            # logger.debug("new_item:\n" + new_item.tostring('\n'))
            itemlist.append(new_item)

        if len(itemlist) > 1:
            itemlist = sorted(itemlist, key=lambda it: int(it.contentSeason))

        if config.get_setting("videolibrary_show_all_seasons_entry"):
            new_item = item.clone(
                action="get_episodes", title=config.get_localized_string(60030)
            )
            new_item.infoLabels["playcount"] = 0
            itemlist.insert(0, new_item)

    if tmdb_upd:
        # Pasamos a TMDB la lista completa Itemlist para actualizar Thumbnail y Fanart
        tmdb.set_infoLabels(itemlist, True)

        for item_tmdb in itemlist:
            # Actualiza Thumbnail y Fanart
            item_tmdb.infoLabels["thumbnail"] = item_tmdb.infoLabels[
                "thumbnail"
            ].replace("http:", "https:")
            item_tmdb.infoLabels["poster_path"] = item_tmdb.infoLabels[
                "poster_path"
            ].replace("http:", "https:")
            if item_tmdb.infoLabels["poster_path"]:
                item_tmdb.thumbnail = item_tmdb.infoLabels["poster_path"]
            item_tmdb.infoLabels["fanart"] = item_tmdb.infoLabels["fanart"].replace(
                "http:", "https:"
            )
            if item_tmdb.infoLabels["fanart"]:
                item_tmdb.fanart = item_tmdb.infoLabels["fanart"]

    return itemlist


def get_episodes(item):
    logger.info()
    # logger.debug("item:\n" + item.tostring('\n'))
    itemlist = []
    tmdb_upd = False

    # Obtenemos los archivos de los episodios
    raiz, carpetas_series, ficheros = next(filetools.walk(item.path))

    # Menu contextual: Releer tvshow.nfo
    head_nfo, item_nfo = videolibrarytools.read_nfo(item.nfo)

    # Crear un item en la lista para cada strm encontrado
    for i in ficheros:
        if i.endswith(".strm"):
            season_episode = scrapertools.get_season_and_episode(i)
            if not season_episode:
                # El fichero no incluye el numero de temporada y episodio
                continue
            season, episode = season_episode.split("x")
            # Si hay q filtrar por temporada, ignoramos los capitulos de otras temporadas
            if item.filtrar_season and int(season) != int(item.contentSeason):
                continue

            # Obtener los datos del season_episode.nfo
            nfo_path = filetools.join(raiz, i).replace(".strm", ".nfo")
            head_nfo, epi = videolibrarytools.read_nfo(nfo_path)
            epi.module = "videolibrary"

            # Fijar el titulo del capitulo si es posible
            if epi.contentTitle:
                title_episodie = epi.contentTitle.strip()
            else:
                title_episodie = config.get_localized_string(60031) % (
                    epi.contentSeason,
                    str(epi.contentEpisodeNumber).zfill(2),
                )

            epi.contentTitle = "%sx%s" % (
                epi.contentSeason,
                str(epi.contentEpisodeNumber).zfill(2),
            )
            epi.title = "%sx%s - %s" % (
                epi.contentSeason,
                str(epi.contentEpisodeNumber).zfill(2),
                title_episodie,
            )

            if item_nfo.library_filter_show:
                epi.library_filter_show = item_nfo.library_filter_show

            # Menu contextual: Marcar episodio como visto o no
            visto = item_nfo.library_playcounts.get(season_episode, 0)
            epi.infoLabels["playcount"] = visto
            if visto > 0:
                texto = config.get_localized_string(60032)
                value = 0
            else:
                texto = config.get_localized_string(60033)
                value = 1
            epi.context = [
                {
                    "title": texto,
                    "action": "mark_content_as_watched",
                    "channel": "videolibrary",
                    "playcount": value,
                    "nfo": item.nfo,
                }
            ]

            if epi.infoLabels["tmdb_id"]:
                tmdb_upd = True

            # logger.debug("epi:\n" + epi.tostring('\n'))
            itemlist.append(epi)

    if tmdb_upd:
        # Pasamos a TMDB la lista completa Itemlist para actualizar Thumbnail y Fanart
        tmdb.set_infoLabels(itemlist, True)

        for item_tmdb in itemlist:
            # Actualiza Thumbnail y Fanart
            item_tmdb.infoLabels["thumbnail"] = item_tmdb.infoLabels[
                "thumbnail"
            ].replace("http:", "https:")
            item_tmdb.infoLabels["poster_path"] = item_tmdb.infoLabels[
                "poster_path"
            ].replace("http:", "https:")
            if item_tmdb.infoLabels["poster_path"]:
                item_tmdb.thumbnail = item_tmdb.infoLabels["poster_path"]
            item_tmdb.infoLabels["fanart"] = item_tmdb.infoLabels["fanart"].replace(
                "http:", "https:"
            )
            if item_tmdb.infoLabels["fanart"]:
                item_tmdb.fanart = item_tmdb.infoLabels["fanart"]
            item_tmdb.contentTitle = "%sx%s" % (
                item_tmdb.contentSeason,
                str(item_tmdb.contentEpisodeNumber).zfill(2),
            )

    return sorted(
        itemlist, key=lambda it: (int(it.contentSeason), int(it.contentEpisodeNumber))
    )


def findvideos(item):
    from modules import autoplay

    logger.info()
    # logger.debug("item:\n" + item.tostring('\n'))

    itemlist = []
    list_canales = {}
    item_local = None

    # Desactiva autoplay
    autoplay.set_status(False)

    if not item.contentTitle or not item.strm_path:
        logger.debug("No se pueden buscar videos por falta de parametros")
        return []

    # content_title = [c for c in item.contentTitle.strip().lower() if c not in ":*?<>|\/"]
    content_title = "".join(
        c for c in item.contentTitle.strip().lower() if c not in ":*?<>|\/"
    )

    if item.contentType == "movie":
        item.strm_path = filetools.join(videolibrarytools.MOVIES_PATH, item.strm_path)
        path_dir = filetools.dirname(item.strm_path)
        item.nfo = filetools.join(path_dir, filetools.basename(path_dir) + ".nfo")
    else:
        item.strm_path = filetools.join(videolibrarytools.TVSHOWS_PATH, item.strm_path)
        path_dir = filetools.dirname(item.strm_path)
        item.nfo = filetools.join(path_dir, "tvshow.nfo")
    head_nfo, it = videolibrarytools.read_nfo(item.nfo)

    for fd in filetools.listdir(path_dir):
        if fd.endswith(".json"):
            contenido, nom_canal = fd[:-6].split("[")
            if (
                contenido.startswith(content_title) or item.contentType == "movie"
            ) and nom_canal not in list(list_canales.keys()):
                list_canales[nom_canal] = filetools.join(path_dir, fd)

    num_canales = len(list_canales)

    if "downloads" in list_canales:
        json_path = list_canales["downloads"]
        item_json = Item().fromjson(filetools.read(json_path))
        item_json.contentChannel = "local"

        # Redirige a nuevo dominio en caso de cambio
        if (
            it.library_urls.get(item_json.channel, "")
            and config.BTDIGG_URL not in it.library_urls[item_json.channel]
        ):
            if config.BTDIGG_URL in item_json.url:
                item_json.url = it.library_urls[item_json.channel]
            if config.BTDIGG_URL in item_json.url_tvshow:
                item_json.url_tvshow = it.library_urls[item_json.channel]
        item_json = videolibrarytools.redirect_url(item_json)

        # Soporte para rutas relativas en descargas
        if filetools.is_relative(item_json.url):
            if scrapertools.find_single_match(item_json.url, ":(.+?):"):
                from servers import torrent

                special = scrapertools.find_single_match(
                    item_json.url, ":(.+?):"
                ).upper()
                if "downloads" in special.lower():
                    from modules import downloads

                    item_json.url = filetools.join(
                        downloads.DOWNLOAD_PATH,
                        (re.sub("(?is):(.+?):\s?", "", item_json.url)),
                    )
                elif "videolibrary" in special.lower():
                    item_json.url = filetools.join(
                        config.get_videolibrary_path(),
                        (re.sub("(?is):(.+?):\s?", "", item_json.url)),
                    )
                elif torrent.torrent_dirs().get(special):
                    torrent_dir = torrent.torrent_dirs()[special]
                    item_json.url = filetools.join(
                        torrent_dir, (re.sub("(?is):(.+?):\s?", "", item_json.url))
                    )
            else:
                item_json.url = filetools.join(
                    videolibrarytools.VIDEOLIBRARY_PATH, item_json.url
                )

        del list_canales["downloads"]

        # Comprobar q el video no haya sido borrado
        if filetools.exists(item_json.url):
            item_local = item_json.clone(action="play")
            itemlist.append(item_local)
        else:
            num_canales -= 1

    filtro_canal = ""
    if num_canales > 1 and config.get_setting("videolibrary_ask_playback_channel"):
        opciones = [
            config.get_localized_string(70089) % k.capitalize()
            for k in list(list_canales.keys())
        ]
        opciones.insert(0, config.get_localized_string(70083))
        if item_local:
            opciones.append(item_local.title)

        index = platformtools.dialog_select(
            config.get_localized_string(30163), opciones
        )
        if index < 0:
            return []

        elif item_local and index == len(opciones) - 1:
            filtro_canal = "downloads"
            platformtools.play_video(item_local)

        elif index > 0:
            filtro_canal = (
                opciones[index].replace(config.get_localized_string(70078), "").strip()
            )
            itemlist = []

    for nom_canal, json_path in list(list_canales.items()):
        if filtro_canal and filtro_canal != nom_canal.capitalize():
            continue

        item_canal = Item()
        item_canal.channel = nom_canal

        # Importamos el canal de la parte seleccionada
        channel = None
        for nom_canal, folder in [[nom_canal, "channels"], ["url", "modules"]]:
            try:
                channel = __import__(
                    "%s.%s" % (folder, nom_canal),
                    fromlist=["%s.%s" % (folder, nom_canal)],
                )
            except ImportError:
                pass
            if channel:
                break

        item_json = Item().fromjson(filetools.read(json_path))
        item_json.nfo = item.nfo
        if "trailertools" in item_json.channel:
            continue

        # Redirige a nuevo dominio en caso de cambio
        if (
            it.library_urls.get(item_json.channel, "")
            and config.BTDIGG_URL not in it.library_urls[item_json.channel]
        ):
            if config.BTDIGG_URL in item_json.url:
                item_json.url = it.library_urls[item_json.channel]
            if config.BTDIGG_URL in item_json.url_tvshow:
                item_json.url_tvshow = it.library_urls[item_json.channel]
        item_json = videolibrarytools.redirect_url(item_json)

        if nom_canal == "url" and not item_json.emergency_urls:
            platformtools.dialog_notification(
                item_canal.action.capitalize(),
                "Canal %s no existe" % item_canal.channel.upper(),
            )
            return []
        if nom_canal == "url" and item_json.emergency_urls:
            item_canal.channel = nom_canal

        # Obtener la información actualizada del vídeo.  En una segunda lectura de TMDB da más información que en la primera
        try:
            generictools.format_tmdb_id(item_json)  # Normaliza el formato de los IDs
            if item_json.infoLabels["tmdb_id"]:
                config.set_setting("tmdb_cache_read", False)
                tmdb.set_infoLabels_item(item_json, seekTmdb=True)
                config.set_setting("tmdb_cache_read", True)

                item_json.infoLabels["thumbnail"] = item_json.infoLabels[
                    "thumbnail"
                ].replace("http:", "https:")
                if item.contentType == "movie":
                    if item_json.infoLabels["thumbnail"]:
                        item_json.thumbnail = item_json.infoLabels["thumbnail"]
                else:
                    item_json.infoLabels["poster_path"] = item_json.infoLabels[
                        "poster_path"
                    ].replace("http:", "https:")
                    if item_json.infoLabels["poster_path"]:
                        item_json.thumbnail = item_json.infoLabels["poster_path"]
                item_json.infoLabels["fanart"] = item_json.infoLabels["fanart"].replace(
                    "http:", "https:"
                )
                if item_json.infoLabels["fanart"]:
                    item_json.fanart = item_json.infoLabels["fanart"]
        except Exception:
            logger.error(traceback.format_exc())

        list_servers = []
        try:
            # FILTERTOOLS
            if item_json.contentType != "movie":
                from modules import filtertools

                filtertools.get_season_search(item_json)
            # si el canal tiene filtro se le pasa el nombre que tiene guardado para que filtre correctamente.
            if "list_language" in item_json:
                # si se viene desde la videoteca del addon
                if "library_filter_show" in item:
                    item_json.show = item.library_filter_show.get(nom_canal, "")

            # Ejecutamos find_videos, del canal o común
            item_json.contentChannel = "videolibrary"
            if hasattr(channel, "findvideos"):
                from core import servertools

                if item_json.videolibray_emergency_urls:
                    del item_json.videolibray_emergency_urls
                list_servers = getattr(channel, "findvideos")(item_json)
                list_servers = servertools.filter_servers(list_servers)
            elif item_json.action == "play":
                autoplay.set_status(True)
                item_json.contentChannel = item_json.channel
                item_json.channel = "videolibrary"
                platformtools.play_video(item_json)
                return ""
            else:
                from core import servertools

                list_servers = servertools.find_video_items(item_json)
        except Exception as ex:
            logger.error(
                "Ha fallado la funcion findvideos para el canal %s" % nom_canal
            )
            template = "An exception of type %s occured. Arguments:\n%r"
            message = template % (type(ex).__name__, ex.args)
            logger.error(message)
            logger.error(traceback.format_exc())

        # Cambiarle el titulo a los servers añadiendoles el nombre del canal delante y
        # las infoLabels y las imagenes del item si el server no tiene
        y = -1
        z_torrent_url = ""
        for x, server in enumerate(list_servers):
            # if not server.action:  # Ignorar/PERMITIR las etiquetas
            #    continue
            if server.action == "add_pelicula_to_library":
                continue
            server.contentChannel = server.channel
            server.channel = "videolibrary"
            server.nfo = item.nfo
            server.strm_path = item.strm_path

            # Para downloads de Torrents desde ventana flotante (sin context menu)
            if server.contentChannel == "downloads" and not server.sub_action:
                y = x
            if (
                server.server == "torrent"
                and server.contentChannel != "downloads"
                and not z_torrent_url
            ):
                z_torrent_url = server.url
            if server.contentChannel == "downloads":
                server.channel = server.contentChannel

            #### Compatibilidad con Kodi 18: evita que se quede la ruedecedita dando vueltas en enlaces Directos
            if server.action == "play":
                server.folder = False

            # Se añade el nombre del canal si se desea
            if config.get_setting("videolibrary_remove_channel_name") == 0:
                server.title = "%s: %s" % (nom_canal.capitalize(), server.title)

            # server.infoLabels = item_json.infoLabels
            if not server.thumbnail:
                server.thumbnail = item.thumbnail

            # logger.debug("server:\n%s" % server.tostring('\n'))
            itemlist.append(server)

        # Pego la url del primer torrent en el pseudo-context "Descargar"
        if y >= 0:
            itemlist[y].url = z_torrent_url

    # return sorted(itemlist, key=lambda it: it.title.lower())
    autoplay.play_multi_channel(item, itemlist)
    from inspect import stack
    from modules import nextep

    if nextep.check(item) and stack()[1][3] == "run":
        nextep.videolibrary(item)
    return itemlist


def play(item):
    logger.info()
    # logger.debug("item:\n" + item.tostring('\n'))

    module_type = "modules" if item.contentChannel in ["downloads"] else "channels"
    if item.contentChannel != "local" and item.channel_recovery != "url":
        channel = __import__(
            "%s.%s" % (module_type, item.contentChannel),
            fromlist=["%s.%s" % (module_type, item.contentChannel)],
        )
        if hasattr(channel, "play"):
            itemlist = getattr(channel, "play")(item)

        else:
            itemlist = [item.clone()]
    else:
        itemlist = [item.clone(url=item.url, server=item.server or "local")]

    if not itemlist:
        return []
    # Para enlaces directo en formato lista
    if isinstance(itemlist[0], list):
        item.video_urls = itemlist
        itemlist = [item]

    # Esto es necesario por si el play del canal elimina los datos
    for v in itemlist:
        if isinstance(v, Item):
            v.nfo = item.nfo
            v.strm_path = item.strm_path
            v.infoLabels = item.infoLabels
            if item.contentTitle:
                v.title = item.contentTitle
            else:
                if item.contentType == "episode":
                    v.title = (
                        config.get_localized_string(60036) % item.contentEpisodeNumber
                    )
            v.thumbnail = item.thumbnail
            v.contentThumbnail = item.thumbnail
            v.contentChannel = item.contentChannel
            if (
                item.action == "save_download"
                and item.channel == "downloads"
                and item.from_channel
            ):
                v.contentAction = "videolibrary"

    return itemlist


def update_videolibrary(item):
    logger.info()

    # Actualizar las series activas sobreescribiendo
    import videolibrary_service

    videolibrary_service.check_for_update(overwrite=True)

    # Eliminar las carpetas de peliculas que no contengan archivo strm
    for raiz, subcarpetas, ficheros in filetools.walk(videolibrarytools.MOVIES_PATH):
        strm = False
        for f in ficheros:
            if f.endswith(".strm"):
                strm = True
                break

        if ficheros and not strm:
            logger.debug("Borrando carpeta de pelicula eliminada: %s" % raiz)
            filetools.rmdirtree(raiz)


# metodos de menu contextual
def update_tvshow(item):
    logger.info()
    # logger.debug("item:\n" + item.tostring('\n'))

    heading = config.get_localized_string(60037)
    p_dialog = platformtools.dialog_progress_bg(
        config.get_localized_string(20000), heading
    )
    p_dialog.update(0, heading, item.contentSerieName)

    # Si viene de canales torrent con Series vinculadas a la Videoteca, se usa el .nfo de la serie para la actualización
    if item.video_path:
        path = filetools.join(
            config.get_videolibrary_path(),
            config.get_setting("folder_tvshows"),
            item.video_path,
            "tvshow.nfo",
        )
        head_nfo, it = videolibrarytools.read_nfo(path)
        it.nfo = path
        it.path = filetools.join(
            config.get_videolibrary_path(),
            config.get_setting("folder_tvshows"),
            it.path,
        )
        if item.season_search:
            it.season_search = item.season_search
    else:
        it = item.clone()
    it.from_action = "update_tvshow"
    tmdb.set_infoLabels_item(it, seekTmdb=True)

    import videolibrary_service

    if (
        videolibrary_service.update(it.path, p_dialog, 1, 1, it, False)
        and config.is_xbmc()
    ):
        from platformcode import xbmc_videolibrary

        xbmc_videolibrary.update(folder=filetools.basename(it.path))

    p_dialog.close()

    for channel, url in list(it.library_urls.items()):
        channel_f = generictools.verify_channel(channel)
        if config.get_setting("auto_download_new", channel_f):
            from modules import downloads

            downloads.download_auto(it)
            break


def verify_playcount_series(item, path):
    logger.info()

    """
    Este método revisa y repara el PlayCount de una serie que se haya desincronizado de la lista real de episodios en su carpeta.  Las entradas de episodios, temporadas o serie que falten, son creado con la marca de "no visto".  Posteriormente se envia a verificar los contadores de Temporadas y Serie
    
    En el retorno envía de estado de True si se actualizado o False si no, normalmente por error.  Con este estado, el caller puede actualizar el estado de la opción "verify_playcount" en "videolibrary.py".  La intención de este método es la de dar una pasada que repare todos los errores y luego desactivarse.  Se puede volver a activar en el menú de Videoteca de Alfa.
    
    """
    # logger.debug("item:\n" + item.tostring('\n'))

    # Si no ha hecho nunca la verificación, lo forzamos
    estado = config.get_setting("videolibrary_verify_playcount")
    if not estado or estado is False:
        estado = True  # Si no ha hecho nunca la verificación, lo forzamos
    else:
        estado = False

    if item.contentType == "movie":  # Esto es solo para Series
        return (item, False)
    if filetools.exists(path):
        nfo_path = filetools.join(path, "tvshow.nfo")
        head_nfo, it = videolibrarytools.read_nfo(
            nfo_path
        )  # Obtenemos el .nfo de la Serie
        if (
            not hasattr(it, "library_playcounts") or not it.library_playcounts
        ):  # Si el .nfo no tiene library_playcounts se lo creamos
            logger.error("** %s: No tiene PlayCount" % it.title)
            it.library_playcounts = {}

        # Obtenemos los archivos de los episodios
        raiz, carpetas_series, ficheros = next(filetools.walk(path))
        # Crear un item en la lista para cada strm encontrado
        estado_update = False
        for i in ficheros:
            if i.endswith(".strm"):
                season_episode = scrapertools.get_season_and_episode(i)
                if not season_episode:
                    # El fichero no incluye el numero de temporada y episodio
                    continue
                season, episode = season_episode.split("x")
                if (
                    season_episode not in it.library_playcounts
                ):  # No está incluido el episodio
                    it.library_playcounts.update(
                        {season_episode: 0}
                    )  # actualizamos el playCount del .nfo
                    estado_update = True  # Marcamos que hemos actualizado algo

                if (
                    "season %s" % season not in it.library_playcounts
                ):  # No está incluida la Temporada
                    it.library_playcounts.update(
                        {"season %s" % season: 0}
                    )  # actualizamos el playCount del .nfo
                    estado_update = True  # Marcamos que hemos actualizado algo

                if (
                    it.contentSerieName not in it.library_playcounts
                ):  # No está incluida la Serie
                    it.library_playcounts.update(
                        {item.contentSerieName: 0}
                    )  # actualizamos el playCount del .nfo
                    estado_update = True  # Marcamos que hemos actualizado algo

        if estado_update:
            logger.error(
                "** Estado de actualización de %s: %s / PlayCount: %s"
                % (it.title, str(estado), str(it.library_playcounts))
            )
            estado = estado_update

        # se comprueba que si todos los episodios de una temporada están marcados, se marque tb la temporada
        for key, value in it.library_playcounts.items():
            if key.startswith("season"):
                season = scrapertools.find_single_match(
                    key, "season (\d+)"
                )  # Obtenemos en núm. de Temporada
                it = check_season_playcount(it, season)
        # Guardamos los cambios en item.nfo
        if videolibrarytools.write_nfo(nfo_path, head_nfo, it):
            return (it, estado)
    return (item, False)


def mark_content_as_watched2(item):
    logger.info()
    # logger.debug("item:\n" + item.tostring('\n'))

    video_path = ""
    if item.video_path:
        FOLDER = (
            config.get_setting("folder_movies")
            if item.contentType == "movie"
            else config.get_setting("folder_tvshows")
        )
        video_path = filetools.join(
            config.get_videolibrary_path(), FOLDER, item.video_path
        )
        if item.contentType in ["movie", "tvshow"]:
            item.path = video_path
        if item.contentType == "episode":
            item.strm_path = filetools.join(
                video_path,
                "%sx%s.strm"
                % (item.contentSeason, str(item.contentEpisodeNumber).zfill(2)),
            )
        video_path = filetools.join(
            video_path,
            "%s.nfo" % item.video_path if item.contentType == "movie" else "tvshow.nfo",
        )

    item.nfo = item.nfo or video_path
    if filetools.exists(item.nfo):
        head_nfo, it = videolibrarytools.read_nfo(item.nfo)
        name_file = ""
        if item.contentType == "movie" or item.contentType == "tvshow":
            name_file = os.path.splitext(filetools.basename(item.nfo))[0]

            if name_file != "tvshow":
                it.library_playcounts.update({name_file: item.playcount})

        if (
            item.contentType == "episode"
            or item.contentType == "list"
            or name_file == "tvshow"
        ):
            # elif item.contentType == 'episode':
            name_file = os.path.splitext(filetools.basename(item.strm_path))[0]
            num_season = name_file[0]
            item.__setattr__("contentType", "episode")
            item.__setattr__("contentSeason", num_season)
            # logger.debug(name_file)

        else:
            name_file = item.contentTitle
        # logger.debug(name_file)

        if not hasattr(it, "library_playcounts"):
            it.library_playcounts = {}
        it.library_playcounts.update({name_file: item.playcount})

        # se comprueba que si todos los episodios de una temporada están marcados, se marque tb la temporada
        if item.contentType != "movie":
            it = check_season_playcount(it, item.contentSeason)
            # logger.debug(it)

        # Guardamos los cambios en item.nfo
        if videolibrarytools.write_nfo(item.nfo, head_nfo, it):
            item.infoLabels["playcount"] = item.playcount
            # logger.debug(item.playcount)

            # if  item.contentType == 'episodesss':
            # Actualizar toda la serie
            # new_item = item.clone(contentSeason=-1)
            # mark_season_as_watched(new_item)

            if config.is_xbmc():
                from platformcode.xbmc_videolibrary import (
                    mark_content_as_watched_on_kodi,
                )

                mark_content_as_watched_on_kodi(item, item.playcount)
                # logger.debug(item)

            platformtools.itemlist_refresh()


def mark_content_as_watched(item):
    logger.info()
    # logger.debug("item:\n" + item.tostring('\n'))

    if filetools.exists(item.nfo):
        head_nfo, it = videolibrarytools.read_nfo(item.nfo)

        if item.contentType == "movie":
            name_file = os.path.splitext(filetools.basename(item.nfo))[0]
        elif item.contentType == "episode":
            name_file = "%sx%s" % (
                item.contentSeason,
                str(item.contentEpisodeNumber).zfill(2),
            )
        else:
            name_file = item.contentTitle

        if not hasattr(it, "library_playcounts"):
            it.library_playcounts = {}
        it.library_playcounts.update({name_file: item.playcount})

        # se comprueba que si todos los episodios de una temporada están marcados, se marque tb la temporada
        if item.contentType != "movie":
            it = check_season_playcount(it, item.contentSeason)

        # Guardamos los cambios en item.nfo
        if videolibrarytools.write_nfo(item.nfo, head_nfo, it):
            item.infoLabels["playcount"] = item.playcount

            if item.contentType == "tvshow" and item.type != "episode":
                # Actualizar toda la serie
                new_item = item.clone(contentSeason=-1)
                mark_season_as_watched(new_item)

            if config.is_xbmc():  # and item.contentType == 'episode':
                from platformcode.xbmc_videolibrary import (
                    mark_content_as_watched_on_kodi,
                )

                mark_content_as_watched_on_kodi(item, item.playcount)

            platformtools.itemlist_refresh()


def mark_video_as_watched(item):
    logger.info()
    # logger.debug("item:\n" + item.tostring('\n'))

    if config.is_xbmc():
        # Actualizamos la BBDD de Kodi
        from platformcode.xbmc_videolibrary import mark_season_as_watched_on_kodi

        mark_season_as_watched_on_kodi(item, item.playcount)

    platformtools.itemlist_refresh()


def mark_season_as_watched(item):
    logger.info()
    # logger.debug("item:\n" + item.tostring('\n'))

    # Obtener el diccionario de episodios marcados
    f = filetools.join(item.path, "tvshow.nfo")
    head_nfo, it = videolibrarytools.read_nfo(f)
    if not hasattr(it, "library_playcounts"):
        it.library_playcounts = {}

    # Obtenemos los archivos de los episodios
    raiz, carpetas_series, ficheros = next(filetools.walk(item.path))

    # Marcamos cada uno de los episodios encontrados de esta temporada
    episodios_marcados = 0
    for i in ficheros:
        if i.endswith(".strm"):
            season_episode = scrapertools.get_season_and_episode(i)
            if not season_episode:
                # El fichero no incluye el numero de temporada y episodio
                continue
            season, episode = season_episode.split("x")

            if int(item.contentSeason) == -1 or int(season) == int(item.contentSeason):
                name_file = os.path.splitext(filetools.basename(i))[0]
                it.library_playcounts[name_file] = item.playcount
                episodios_marcados += 1

    if episodios_marcados:
        if int(item.contentSeason) == -1:
            # Añadimos todas las temporadas al diccionario item.library_playcounts
            for k in list(it.library_playcounts.keys()):
                if k.startswith("season"):
                    it.library_playcounts[k] = item.playcount
        else:
            # Añadimos la temporada al diccionario item.library_playcounts
            it.library_playcounts["season %s" % item.contentSeason] = item.playcount

            # se comprueba que si todas las temporadas están vistas, se marque la serie como vista
            it = check_tvshow_playcount(it, item.contentSeason)

        # Guardamos los cambios en tvshow.nfo
        videolibrarytools.write_nfo(f, head_nfo, it)
        item.infoLabels["playcount"] = item.playcount

        if config.is_xbmc():
            # Actualizamos la BBDD de Kodi
            from platformcode.xbmc_videolibrary import mark_season_as_watched_on_kodi

            mark_season_as_watched_on_kodi(item, item.playcount)

    platformtools.itemlist_refresh()


def mark_tvshow_as_updatable(item):
    logger.info()
    head_nfo, it = videolibrarytools.read_nfo(item.nfo)
    it.active = item.active
    videolibrarytools.write_nfo(item.nfo, head_nfo, it)

    platformtools.itemlist_refresh()


def delete(item):
    def delete_all(_item):
        for file in filetools.listdir(_item.path):
            if (
                file.endswith(".strm")
                or file.endswith(".nfo")
                or file.endswith(".json")
                or file.endswith(".torrent")
            ):
                filetools.remove(filetools.join(_item.path, file))
        raiz, carpeta_serie, ficheros = next(filetools.walk(_item.path))
        if ficheros == []:
            filetools.rmdir(_item.path)

        if config.is_xbmc():
            import xbmc

            # esperamos 3 segundos para dar tiempo a borrar los ficheros
            xbmc.sleep(3000)
            # TODO mirar por qué no funciona al limpiar en la videoteca de Kodi al añadirle un path
            # limpiamos la videoteca de Kodi
            from platformcode import xbmc_videolibrary

            xbmc_videolibrary.clean()

        logger.info("Eliminados todos los enlaces")
        platformtools.itemlist_refresh()

    # logger.info(item.contentTitle)
    # logger.debug(item.tostring('\n'))
    config.cache_reset(label="alfa_videolab_series_list")

    if item.contentType == "movie":
        heading = config.get_localized_string(70084)
    else:
        heading = config.get_localized_string(70085)
    if item.multicanal:
        # Obtener listado de canales
        msg_txt = ""
        if item.dead == "":
            opciones = [
                config.get_localized_string(70086) % k.capitalize()
                for k in list(item.library_urls.keys())
                if k != "downloads"
            ]
            opciones.insert(0, heading)

            index = platformtools.dialog_select(
                config.get_localized_string(30163), opciones
            )

            if index == 0:
                # Seleccionado Eliminar pelicula/serie
                delete_all(item)
                msg_txt = config.get_localized_string(80783) % item.contentTitle

            elif index > 0:
                # Seleccionado Eliminar canal X
                canal = (
                    opciones[index]
                    .replace(config.get_localized_string(70079), "")
                    .lower()
                )
            else:
                return
        else:
            canal = item.dead

        num_enlaces = 0
        for fd in filetools.listdir(item.path):
            if fd.endswith(canal + "].json") or scrapertools.find_single_match(
                fd, "%s]_\d+.torrent" % canal
            ):
                if filetools.remove(filetools.join(item.path, fd)):
                    num_enlaces += 1

        if num_enlaces > 0:
            # Actualizar .nfo
            head_nfo, item_nfo = videolibrarytools.read_nfo(item.nfo)
            del item_nfo.library_urls[canal]
            if item_nfo.emergency_urls and item_nfo.emergency_urls.get(canal, False):
                del item_nfo.emergency_urls[canal]
            videolibrarytools.write_nfo(item.nfo, head_nfo, item_nfo)

        if not msg_txt:
            msg_txt = config.get_localized_string(70087) % (num_enlaces, canal)
        logger.info(msg_txt)
        platformtools.dialog_notification(heading, msg_txt)
        platformtools.itemlist_refresh()

    else:
        if platformtools.dialog_yesno(
            heading, config.get_localized_string(70088) % item.infoLabels["title"]
        ):
            delete_all(item)


def reset_movie(item):
    logger.info()

    if item.nfo:
        config.cache_reset(label="alfa_videolab_series_list")
        videolibrarytools.reset_movie(item.nfo)
    else:
        logger.error("Error al crear de nuevo la película. No .nfo")


def reset_serie(item):
    logger.info()

    if item.nfo:
        config.cache_reset(label="alfa_videolab_series_list")
        videolibrarytools.reset_serie(item.nfo)
    else:
        logger.error("Error al crear de nuevo la serie. No .nfo")


def check_season_playcount(item, season):
    logger.info()

    if season:
        episodios_temporada = 0
        episodios_vistos_temporada = 0
        for key, value in item.library_playcounts.items():
            if key.startswith("%sx" % season):
                episodios_temporada += 1
                if value > 0:
                    episodios_vistos_temporada += 1

        if episodios_temporada == episodios_vistos_temporada:
            # se comprueba que si todas las temporadas están vistas, se marque la serie como vista
            item.library_playcounts.update({"season %s" % season: 1})
        else:
            # se comprueba que si todas las temporadas están vistas, se marque la serie como vista
            item.library_playcounts.update({"season %s" % season: 0})

    return check_tvshow_playcount(item, season)


def check_tvshow_playcount(item, season):
    logger.info()
    if season:
        temporadas_serie = 0
        temporadas_vistas_serie = 0
        for key, value in item.library_playcounts.items():
            # if key.startswith("season %s" % season):
            if key.startswith("season"):
                temporadas_serie += 1
                if value > 0:
                    temporadas_vistas_serie += 1
                    # logger.debug(temporadas_serie)

        if temporadas_serie == temporadas_vistas_serie:
            item.library_playcounts.update({item.title: 1})
        else:
            item.library_playcounts.update({item.title: 0})

    else:
        playcount = item.library_playcounts.get(item.title, 0)
        item.library_playcounts.update({item.title: playcount})

    return item


def get_color_from_settings(label, default="white"):
    color = config.get_setting(label)
    if not color:
        return default

    color = scrapertools.find_single_match(color, "\](\w+)\[")

    return color or default
