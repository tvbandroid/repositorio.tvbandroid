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

import os

from resources.libs.common import directory
from resources.libs.common.config import CONFIG


class MainMenu:

    def get_listing(self):
        from resources.libs import check
        from resources.libs.common import logging
        from resources.libs.common import tools

        errors = int(logging.error_checking(count=True))
        errorsfound = str(errors) + ' Error(es) Encontrado' if errors > 0 else '[COLOR gold]Nada Encontrado[/COLOR]'

        if CONFIG.AUTOUPDATE == 'Yes':
            response = tools.open_url(CONFIG.BUILDFILE, check=True)

            if response:
                ver = check.check_wizard('version')
                if ver:
                    if ver > CONFIG.ADDON_VERSION:
                        directory.add_file(
                            '{0}[/COLOR] [v{1}] [COLOR red][B][ACTUALIZACION v{2}][/B][/COLOR]'.format(CONFIG.ADDONTITLE,
                                                                                        CONFIG.ADDON_VERSION, ver),
                            {'mode': 'wizardupdate'}, themeit=CONFIG.THEME2)
                    else:
                        directory.add_file('{0} [v{1}]'.format(CONFIG.ADDONTITLE, CONFIG.ADDON_VERSION),
                                           themeit=CONFIG.THEME2)
            else:
                directory.add_file('{0} [v{1}]'.format(CONFIG.ADDONTITLE, CONFIG.ADDON_VERSION),
                                   themeit=CONFIG.THEME2)
        else:
            directory.add_file('{0} [v{1}]'.format(CONFIG.ADDONTITLE, CONFIG.ADDON_VERSION), themeit=CONFIG.THEME2)
        if len(CONFIG.BUILDNAME) > 0:
            version = check.check_build(CONFIG.BUILDNAME, 'version')
            build = '[B][COLOR yellowgreen]{0}[/COLOR] [COLOR khaki] - v{1}[/COLOR][/B]'.format(CONFIG.BUILDNAME, CONFIG.BUILDVERSION)
            if version > CONFIG.BUILDVERSION:
                build = '{0} [COLOR red][B][ACTUALIZACION v{1}][/B][/COLOR]'.format(build, version)
            directory.add_dir(build, {'mode': 'viewbuild', 'name': CONFIG.BUILDNAME}, themeit=CONFIG.THEME4)

            from resources.libs.gui.build_menu import BuildMenu
            themefile = BuildMenu().theme_count(CONFIG.BUILDNAME)
            if themefile:
                directory.add_file('[COLOR indianred]Ninguno[/COLOR]' if CONFIG.BUILDTHEME == "" else CONFIG.BUILDTHEME, {'mode': 'theme', 'name': CONFIG.BUILDNAME},
                                   themeit=CONFIG.THEME5)
        else:
            directory.add_dir('[COLOR indianred]Ninguno[/COLOR]', {'mode': 'builds'}, themeit=CONFIG.THEME4)
        directory.add_separator()
        directory.add_dir('[B][COLOR orange]BUILDS[COLOR azure] - [COLOR orange]PARCHES:[COLOR azure] TVBAN [COLOR cyan]MATNEXOM[/COLOR][/B]', {'mode': 'builds'}, icon=CONFIG.ICONBUILDS, themeit=CONFIG.THEME1)
        directory.add_dir('[B]Mantenimiento[/B]', {'mode': 'maint'}, icon=CONFIG.ICONMAINT, themeit=CONFIG.THEME1)
        if (tools.platform() == 'android' or CONFIG.DEVELOPER == 'true'):
            directory.add_dir('[B]Instalador de [COLOR yellowgreen]APKs[/COLOR][/B]', {'mode': 'apk'}, icon=CONFIG.ICONAPK, themeit=CONFIG.THEME1)
        if tools.open_url(CONFIG.ADDONFILE, check=True) or os.path.exists(os.path.join(CONFIG.ADDON_PATH, 'resources', 'text', 'addons.json')):
            directory.add_dir('[B]Instalador de Addon[/B]', {'mode': 'addons'}, icon=CONFIG.ICONADDONS, themeit=CONFIG.THEME1)
        if tools.open_url(CONFIG.YOUTUBEFILE, check=True) and not CONFIG.YOUTUBETITLE == '':
            directory.add_dir(CONFIG.YOUTUBETITLE, {'mode': 'youtube'}, icon=CONFIG.ICONYOUTUBE, themeit=CONFIG.THEME1)
        directory.add_dir('[B]Guardar Datos[/B]', {'mode': 'savedata'}, icon=CONFIG.ICONSAVE, themeit=CONFIG.THEME1)
        if CONFIG.HIDECONTACT == 'No':
            directory.add_file('[B]Contacto[/B]', {'mode': 'contact'}, icon=CONFIG.ICONCONTACT, themeit=CONFIG.THEME1)
        directory.add_separator()
        directory.add_file('[B]Cargar Archivo de Registro[/B]', {'mode': 'uploadlog'}, icon=CONFIG.ICONMAINT, themeit=CONFIG.THEME1)
        directory.add_file('[B]Ver Errores en el Registro:[/B] [COLOR teal]{0}[/COLOR]'.format(errorsfound), {'mode': 'viewerrorlog'}, icon=CONFIG.ICONMAINT,
                           themeit=CONFIG.THEME1)
        if errors > 0:
            directory.add_file('[B]Ver el Ultimo Error en el Registro[/B]', {'mode': 'viewerrorlast'}, icon=CONFIG.ICONMAINT, themeit=CONFIG.THEME1)
        directory.add_separator()
        directory.add_file('[B]Ajustes[/B]', {'mode': 'settings', 'name': CONFIG.ADDON_ID}, icon=CONFIG.ICONSETTINGS, themeit=CONFIG.THEME1)
        if CONFIG.DEVELOPER == 'true':
            directory.add_dir('[B]Menú de Desarrollador[/B]', {'mode': 'developer'}, icon=CONFIG.ADDON_ICON, themeit=CONFIG.THEME1)
