# C:\Meus Projetos\MyOps\modules\change_manager\change_manager_logic.py

import json
import os
import shutil
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'changes')
DATA_FILE = os.path.join(DATA_DIR, 'changes.json')
FILES_DIR = os.path.join(DATA_DIR, 'files')

STATUS_OPTIONS = ["Planejada", "Em Aprovacao", "Aprovada", "Em Execucao", "Concluida", "Cancelada", "Rollback"]


def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(FILES_DIR, exist_ok=True)


def _load_all():
    _ensure_dirs()
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Erro ao ler arquivo de changes: {e}")
        return []


def _save_all(changes):
    _ensure_dirs()
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(changes, f, ensure_ascii=False, indent=2)


def get_all_changes():
    return _load_all()


def search_changes(query):
    query = query.lower().strip()
    if not query:
        return _load_all()
    results = []
    for c in _load_all():
        searchable = f"{c.get('number','')} {c.get('name','')} {c.get('description','')} {c.get('responsible','')} {c.get('status','')}".lower()
        if query in searchable:
            results.append(c)
    return results


def get_change_by_id(change_id):
    for c in _load_all():
        if c['id'] == change_id:
            return c
    return None


def _next_id(changes):
    if not changes:
        return 1
    return max(c['id'] for c in changes) + 1


def save_change(change_data, change_id=None):
    changes = _load_all()
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    if change_id is not None:
        for i, c in enumerate(changes):
            if c['id'] == change_id:
                change_data['id'] = change_id
                change_data['created_at'] = c.get('created_at', now)
                change_data['updated_at'] = now
                change_data['files'] = c.get('files', [])
                changes[i] = change_data
                break
    else:
        change_data['id'] = _next_id(changes)
        change_data['created_at'] = now
        change_data['updated_at'] = now
        change_data['files'] = []
        changes.append(change_data)
        change_id = change_data['id']

    _save_all(changes)
    return change_id


def delete_change(change_id):
    changes = _load_all()
    change = next((c for c in changes if c['id'] == change_id), None)
    if not change:
        return

    change_files_dir = os.path.join(FILES_DIR, str(change_id))
    if os.path.isdir(change_files_dir):
        shutil.rmtree(change_files_dir, ignore_errors=True)

    changes = [c for c in changes if c['id'] != change_id]
    _save_all(changes)


def add_files_to_change(change_id, file_paths):
    _ensure_dirs()
    change_files_dir = os.path.join(FILES_DIR, str(change_id))
    os.makedirs(change_files_dir, exist_ok=True)

    changes = _load_all()
    for i, c in enumerate(changes):
        if c['id'] == change_id:
            existing_files = c.get('files', [])
            for src in file_paths:
                filename = os.path.basename(src)
                dest = os.path.join(change_files_dir, filename)
                counter = 1
                base, ext = os.path.splitext(filename)
                while os.path.exists(dest):
                    filename = f"{base}_{counter}{ext}"
                    dest = os.path.join(change_files_dir, filename)
                    counter += 1
                shutil.copy2(src, dest)
                existing_files.append({
                    'name': filename,
                    'original_path': src,
                    'added_at': datetime.now().strftime('%Y-%m-%d %H:%M')
                })
            changes[i]['files'] = existing_files
            changes[i]['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
            break
    _save_all(changes)


def remove_file_from_change(change_id, filename):
    changes = _load_all()
    change_files_dir = os.path.join(FILES_DIR, str(change_id))

    for i, c in enumerate(changes):
        if c['id'] == change_id:
            file_path = os.path.join(change_files_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            changes[i]['files'] = [f for f in c.get('files', []) if f['name'] != filename]
            changes[i]['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
            break
    _save_all(changes)


def get_file_path(change_id, filename):
    return os.path.join(FILES_DIR, str(change_id), filename)


def get_change_files_dir(change_id):
    return os.path.join(FILES_DIR, str(change_id))
