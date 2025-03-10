################################################################################
#      Copyright (C) 2019 drinfernoo                                           #
#                                                                              #
#  This Program is free software; you can redistribute it and/or modify        #
#  it under the terms of the GNU General Public License as published by        #
#  the Free Software Foundation; either version 2, or (at your option)         #
#  any later version.                                                          #
#                                                                              #
#  This Program is distributed in the hope that it will be useful,             #
#  but WITHOUT ANY WARRANTY; without even the implied warranty of              #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the                #
#  GNU General Public License for more details.                                #
#                                                                              #
#  You should have received a copy of the GNU General Public License           #
#  along with XBMC; see the file COPYING.  If not, write to                    #
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.       #
#  http://www.gnu.org/copyleft/gpl.html                                        #
################################################################################

import xbmc
import xbmcgui
import xbmcvfs

import os
import shutil
try:  # Python 3
    import zipfile
except ImportError:  # Python 2
    from resources.libs import zipfile

from resources.libs.common.config import CONFIG
from resources.libs.common import logging
from resources.libs.common import tools


def import_save_data():
    dialog = xbmcgui.Dialog()

    TEMP = os.path.join(CONFIG.PLUGIN_DATA, 'temp')
    if not os.path.exists(TEMP):
        os.makedirs(TEMP)
    source = dialog.browse(1, '[COLOR {0}]Seleccione la ubicación del archivo SaveData.zip[/COLOR]'.format(CONFIG.COLOR2),
                               'files', '.zip', False, False, CONFIG.HOME)
    if not source.endswith('.zip'):
        logging.log_notify(CONFIG.ADDONTITLE,
                           "[COLOR {0}]Error al Importar Datos![/COLOR]".format(CONFIG.COLOR2))
        return
    source = xbmcvfs.translatePath(source)
    tempfile = xbmcvfs.translatePath(os.path.join(CONFIG.MYBUILDS, 'SaveData.zip'))
    if not tempfile == source:
        goto = xbmcvfs.copy(source, tempfile)

    from resources.libs import extract
    if not extract.all(xbmcvfs.translatePath(tempfile), TEMP):
        logging.log("Error al intentar extraer el archivo zip!")
        logging.log_notify(CONFIG.ADDONTITLE,
                           "[COLOR {0}]Error al Importar Datos![/COLOR]".format(CONFIG.COLOR2))
        return

    trakt = os.path.join(TEMP, 'trakt')
    login = os.path.join(TEMP, 'login')
    debrid = os.path.join(TEMP, 'debrid')
    super = os.path.join(TEMP, 'plugin.program.super.favourites')
    xmls = os.path.join(TEMP, 'xmls')

    x = 0
    overwrite = dialog.yesno(CONFIG.ADDONTITLE,
                                 "[COLOR {0}]Prefieres que sobrescribamos todos los archivos de datos guardados o que te preguntemos por cada archivo que se importe?[/COLOR]".format(CONFIG.COLOR2),
                                 yeslabel="[B][COLOR cyan]Sobrescribir Todo[/COLOR][/B]",
                                 nolabel="[B][COLOR red]No Preguntar[/COLOR][/B]")
    
    if os.path.exists(trakt):
        from resources.libs import traktit

        x += 1
        files = os.listdir(trakt)
        if not os.path.exists(CONFIG.TRAKTFOLD):
            os.makedirs(CONFIG.TRAKTFOLD)
        for item in files:
            old = os.path.join(CONFIG.TRAKTFOLD, item)
            temp = os.path.join(trakt, item)
            if os.path.exists(old):
                if overwrite == 1:
                    os.remove(old)
                else:
                    if not dialog.yesno(CONFIG.ADDONTITLE,
                                            "[COLOR {0}]Quieres reemplazar el archivo [COLOR {1}]{2}[/COLOR] actual?".format(CONFIG.COLOR2, CONFIG.COLOR1, item),
                                            yeslabel="[B][COLOR cyan]Sí Reemplazar[/COLOR][/B]",
                                            nolabel="[B][COLOR red]No, Saltar[/COLOR][/B]"):
                        continue
                    else:
                        os.remove(old)
            shutil.copy(temp, old)
        traktit.import_list('all')
        traktit.trakt_it('restore', 'all')
    if os.path.exists(login):
        from resources.libs import loginit

        x += 1
        files = os.listdir(login)
        if not os.path.exists(CONFIG.LOGINFOLD):
            os.makedirs(CONFIG.LOGINFOLD)
        for item in files:
            old = os.path.join(CONFIG.LOGINFOLD, item)
            temp = os.path.join(login, item)
            if os.path.exists(old):
                if overwrite == 1:
                    os.remove(old)
                else:
                    if not dialog.yesno(CONFIG.ADDONTITLE,
                                            "[COLOR {0}]Quieres reemplazar el archivo [COLOR {1}]{2}[/COLOR] actual?".format(CONFIG.COLOR2, CONFIG.COLOR1, item),
                                            yeslabel="[B][COLOR cyan]Sí Reemplazar[/COLOR][/B]",
                                            nolabel="[B][COLOR red]No, Saltar[/COLOR][/B]"):
                        continue
                    else:
                        os.remove(old)
            shutil.copy(temp, old)
        loginit.import_list('all')
        loginit.login_it('restore', 'all')
    
    if os.path.exists(debrid):
        from resources.libs import debridit

        x += 1
        files = os.listdir(debrid)
        if not os.path.exists(CONFIG.DEBRIDFOLD):
            os.makedirs(CONFIG.DEBRIDFOLD)
        for item in files:
            old = os.path.join(CONFIG.DEBRIDFOLD, item)
            temp = os.path.join(debrid, item)
            if os.path.exists(old):
                if overwrite == 1:
                    os.remove(old)
                else:
                    if not dialog.yesno(CONFIG.ADDONTITLE,
                                            "[COLOR {0}]Quieres reemplazar el archivo [COLOR {1}]{2}[/COLOR] actual?".format(CONFIG.COLOR2, CONFIG.COLOR1, item),
                                            yeslabel="[B][COLOR cyan]Sí Reemplazar[/COLOR][/B]",
                                            nolabel="[B][COLOR red]No, Saltar[/COLOR][/B]"):
                        continue
                    else:
                        os.remove(old)
            shutil.copy(temp, old)
        debridit.import_list('all')
        debridit.debrid_it('restore', 'all')
    if os.path.exists(xmls):
        x += 1
        for item in CONFIG.XMLS:
            old = os.path.join(CONFIG.USERDATA, item)
            new = os.path.join(xmls, item)
            if not os.path.exists(new): continue
            if os.path.exists(old):
                if not overwrite == 1:
                    if not dialog.yesno(CONFIG.ADDONTITLE,
                                            "[COLOR {0}]Quieres reemplazar el archivo [COLOR {1}]{2}[/COLOR] actual?".format(CONFIG.COLOR2, CONFIG.COLOR1, item),
                                            yeslabel="[B][COLOR cyan]Sí Reemplazar[/COLOR][/B]",
                                            nolabel="[B][COLOR red]No, Saltar[/COLOR][/B]"):
                        continue
            os.remove(old)
            shutil.copy(new, old)
    if os.path.exists(super):
        x += 1
        old = os.path.join(CONFIG.ADDON_DATA, 'plugin.program.super.favourites')
        if os.path.exists(old):
            cont = dialog.yesno(CONFIG.ADDONTITLE,
                                    "[COLOR {0}]Quieres reemplazar la carpeta actual [COLOR {1}]Super Favoritos[/COLOR] addon_data por la nueva?".format(CONFIG.COLOR2, CONFIG.COLOR1),
                                    yeslabel="[B][COLOR cyan]Sí Reemplazar[/COLOR][/B]",
                                    nolabel="[B][COLOR red]No, Saltar[/COLOR][/B]")
        else:
            cont = 1
        if cont == 1:
            tools.clean_house(old)
            tools.remove_folder(old)
            xbmcvfs.copy(super, old)
    tools.clean_house(TEMP)
    tools.remove_folder(TEMP)
    if not tempfile == source:
        xbmcvfs.delete(tempfile)
    if x == 0:
        logging.log_notify(CONFIG.ADDONTITLE,
                           "[COLOR {0}]Error al Guardar Datos al Importar[/COLOR]".format(CONFIG.COLOR2))
    else:
        logging.log_notify(CONFIG.ADDONTITLE,
                           "[COLOR {0}]Guardar Importación de Datos Completada[/COLOR]".format(CONFIG.COLOR2))


def export_save_data():
    from resources.libs import debridit
    from resources.libs import loginit
    from resources.libs import traktit

    dialog = xbmcgui.Dialog()

    dir = ['debrid', 'login', 'trakt']
    keepx = [CONFIG.KEEPADVANCED, CONFIG.KEEPSOURCES, CONFIG.KEEPFAVS, CONFIG.KEEPPROFILES, CONFIG.KEEPPLAYERCORE, CONFIG.KEEPGUISETTINGS]
    traktit.trakt_it('update', 'all')
    loginit.login_it('update', 'all')
    debridit.debrid_it('update', 'all')
    source = dialog.browse(3, '[COLOR {0}]Seleccione dónde desea exportar el archivo zip SaveData.[/COLOR]'.format(CONFIG.COLOR2),
                               'files', '', False, True, CONFIG.HOME)
    source = xbmcvfs.translatePath(source)
    tempzip = os.path.join(source, 'SaveData.zip')
    superfold = os.path.join(CONFIG.ADDON_DATA, 'plugin.program.super.favourites')
    zipf = zipfile.ZipFile(tempzip, mode='w', allowZip64=True)
    for fold in dir:
        path = os.path.join(CONFIG.PLUGIN_DATA, fold)
        if os.path.exists(path):
            files = os.listdir(path)
            for file in files:
                fn = os.path.join(path, file)
                zipf.write(fn, os.path.join(fold, file), zipfile.ZIP_DEFLATED)
    if CONFIG.KEEPSUPER == 'true' and os.path.exists(superfold):
        for base, dirs, files in os.walk(superfold):
            for file in files:
                fn = os.path.join(base, file)
                zipf.write(fn, fn[len(CONFIG.ADDON_DATA):], zipfile.ZIP_DEFLATED)
    for item in CONFIG.XMLS:
        if keepx[CONFIG.XMLS.index(item)] == 'true' and os.path.exists(os.path.join(CONFIG.USERDATA, item)):
            zipf.write(os.path.join(CONFIG.USERDATA, item), os.path.join('xmls', item), zipfile.ZIP_DEFLATED)
    zipf.close()
    
    dialog.ok(CONFIG.ADDONTITLE,
                  "[COLOR {0}]Se ha realizado una copia de seguridad de los datos guardados en:[/COLOR]".format(CONFIG.COLOR2)
                  +'\n'+"[COLOR {0}]{1}[/COLOR]".format(CONFIG.COLOR1, os.path.join(source, 'SaveData.zip')))
