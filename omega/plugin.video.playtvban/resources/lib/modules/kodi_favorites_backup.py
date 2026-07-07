# -*- coding: utf-8 -*-
import json
import os
import shutil
from datetime import datetime
from xml.etree import ElementTree as ET
from modules import kodi_utils, settings
from modules.import_export_utils import offer_save_export_directory, pick_export_folder
_KODI_FAVORITES_FILENAMES = ('Favourites.xml', 'favourites.xml')

BACKUP_MASK = '.xml'


def _kodi_favorites_path():
	profile = kodi_utils.translate_path('special://profile/')
	for name in _KODI_FAVORITES_FILENAMES:
		path = os.path.join(profile, name)
		if os.path.isfile(path):
			return path
	return os.path.join(profile, 'Favourites.xml')


def _pick_import_file():
	path = kodi_utils.browse_file(BACKUP_MASK, settings.import_export_directory_setting(), heading='Choose Kodi favorites backup', force_defaultt=True)
	if not path:
		return None
	tpath = kodi_utils.translate_path(path)
	if not os.path.isfile(tpath):
		return None
	if not tpath.lower().endswith('.xml'):
		kodi_utils.ok_dialog(heading='Import Kodi favorites', text='Please choose a Kodi favorites backup (.xml).')
		return None
	return tpath


def _parse_favorites_file(path):
	try:
		tree = ET.parse(path)
	except Exception as e:
		raise ValueError('Invalid XML (%s)' % e)
	root = tree.getroot()
	if root.tag.lower() != 'favourites':
		raise ValueError('This file is not a Kodi favorites backup (expected a favourites root element).')
	items = []
	for node in root.findall('favourite'):
		action = (node.text or '').strip()
		if not action:
			continue
		items.append({
			'name': node.get('name') or '',
			'thumb': node.get('thumb') or '',
			'action': action,
		})
	return items


def _write_favorites_file(path, items):
	root = ET.Element('favourites')
	for item in items:
		node = ET.SubElement(root, 'favourite')
		if item.get('name'):
			node.set('name', item['name'])
		if item.get('thumb'):
			node.set('thumb', item['thumb'])
		node.text = item.get('action') or ''
	tree = ET.ElementTree(root)
	kodi_utils.make_directory(os.path.dirname(path))
	with open(path, 'wb') as handle:
		tree.write(handle, encoding='utf-8', xml_declaration=True)


def _compat_note():
	return '[COLOR yellow]Los favoritos de Kodi normalmente solo funcionan con el complemento que los creó.[/COLOR]'


def export_favorites(params):
	src = _kodi_favorites_path()
	if not os.path.isfile(src):
		return kodi_utils.ok_dialog(heading='Exportar favoritos de Kodi', text='No se encontró el archivo de favoritos de Kodi en este perfil.')
	try:
		items = _parse_favorites_file(src)
	except Exception as e:
		return kodi_utils.ok_dialog(heading='Error al exportar', text='No se pudieron leer los favoritos de Kodi.[CR][CR]%s' % e)
	if not items:
		return kodi_utils.ok_dialog(heading='Exportar favoritos de Kodi', text='El archivo de favoritos de Kodi está vacío.')
	folder = pick_export_folder(heading='Elegir carpeta de exportación')
	if not folder:
		return
	filename = 'kodi-favorites-%s.xml' % datetime.now().strftime('%Y%m%d-%H%M%S')
	dest = os.path.join(folder, filename)
	count = len(items)
	preview_lines = [
		'[B]%s[/B]' % filename,
		'%s favorito(s) de Kodi.' % count,
		'',
		_compat_note(),
	]
	if not kodi_utils.confirm_dialog(heading='Exportar favoritos de Kodi', text='[CR]'.join(preview_lines), ok_label='Exportar', cancel_label='Cancelar', default_control=10, scroll=True):
		return
	try:
		kodi_utils.make_directory(folder)
		shutil.copy2(src, dest)
	except Exception as e:
		return kodi_utils.ok_dialog(heading='Error al exportar', text=str(e))
	summary = 'Se exportaron %s favorito(s) de Kodi a %s' % (count, filename)
	kodi_utils.ok_dialog(heading='Exportación completada', text=summary, scroll=True)
	kodi_utils.notification(summary, 6500)
	offer_save_export_directory(folder)


def import_favorites(params):
	path = _pick_import_file()
	if not path:
		return
	try:
		import_items = _parse_favorites_file(path)
	except Exception as e:
		return kodi_utils.ok_dialog(heading='Error al importar', text='No se pudo leer ese archivo.[CR][CR]%s' % e)
	if not import_items:
		return kodi_utils.ok_dialog(heading='Importar favoritos de Kodi', text='Ese archivo no contiene favoritos de Kodi.')
	dest = _kodi_favorites_path()
	local_items = []
	if os.path.isfile(dest):
		try:
			local_items = _parse_favorites_file(dest)
		except:
			local_items = []
	file_count = len(import_items)
	local_count = len(local_items)
	empty_dest = local_count == 0
	preview_lines = [
		'[B]%s[/B]' % os.path.basename(path),
		'Respaldo: %s favorito(s).' % file_count,
		'Este dispositivo: %s favorito(s).' % local_count,
		'',
		_compat_note(),
	]
	if not kodi_utils.confirm_dialog(
		heading='Importar favoritos de Kodi',
		text='[CR]'.join(preview_lines),
		ok_label='Importar' if empty_dest else 'Continuar',
		cancel_label='Cancelar',
		default_control=10,
		scroll=True,
	):
		return
	if empty_dest:
		mode = 'merge'
	else:
		mode_choices = [
			('Combinar — agregar desde el respaldo y conservar los favoritos existentes', 'merge'),
			('Reemplazar — eliminar los favoritos locales e importar el respaldo', 'replace'),
		]
		list_items = [{'line1': i[0]} for i in mode_choices]
		kwargs = {'items': json.dumps(list_items), 'heading': 'Modo de importación', 'narrow_window': 'true'}
		mode = kodi_utils.select_dialog([i[1] for i in mode_choices], **kwargs)
		if not mode:
			return
		rules = _import_rules_text(mode)
		if not kodi_utils.confirm_dialog(heading='Importar %s' % mode, text=rules, ok_label='Importar', cancel_label='Cancelar', default_control=10, scroll=True):
			return
		if mode == 'replace':
			if not kodi_utils.confirm_dialog(heading='¿Reemplazar datos locales?', text=_replace_warning(local_count), ok_label='Reemplazar', cancel_label='Cancelar', default_control=10):
				return
	try:
		if mode == 'merge':
			merged = _merge_favorites(local_items, import_items)
			_write_favorites_file(dest, merged)
			added = len(merged) - len(local_items)
			summary = 'Importación completada — %s favorito(s) en total (%s agregados)' % (len(merged), max(added, 0))
		else:
			if os.path.isfile(dest):
				backup = dest + '.playtvban.bak'
				shutil.copy2(dest, backup)
			shutil.copy2(path, dest)
			summary = 'Importación completada — %s favorito(s) importados (reemplazo)' % file_count
	except Exception as e:
		return kodi_utils.ok_dialog(heading='Error al importar', text=str(e))
	kodi_utils.ok_dialog(
		heading='Importación completada',
		text='%s[CR][CR][COLOR yellow]Reinicia Kodi si el menú de Favoritos no se actualiza.[/COLOR]' % summary,
		scroll=True,
	)
	kodi_utils.notification('Importación completada', 6500)


def _import_rules_text(mode):
	if mode == 'merge':
		return 'Favoritos de Kodi: agregar desde el respaldo y conservar los favoritos existentes.'
	return 'Favoritos de Kodi: reemplazar todos los favoritos de este dispositivo.[CR]Antes de importar se guarda una copia de los favoritos actuales.'


def _replace_warning(local_count):
	return (
		'Esto reemplazará %s favorito(s) de este dispositivo con los del respaldo.[CR]'
		'Antes de importar se guardará una copia de los favoritos actuales en Favourites.xml.playtvban.bak.'
	) % local_count


def _merge_favorites(local_items, import_items):
	seen = set(i['action'] for i in local_items)
	merged = list(local_items)
	for item in import_items:
		if item['action'] in seen:
			continue
		merged.append(item)
		seen.add(item['action'])
	return merged