import json
import os
import sys
import uuid
import logging
from datetime import datetime

from modules.common.security import encrypt_password, decrypt_password

logger = logging.getLogger(__name__)

VAULT_FILE = "password_vault.json"


def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # modules/password_vault/password_vault_logic.py -> 2 levels up = project root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_vault_path():
    return os.path.join(get_base_path(), VAULT_FILE)


def load_vault():
    """Carrega todas as credenciais do arquivo de cofre."""
    vault_path = get_vault_path()
    if not os.path.exists(vault_path):
        return []
    try:
        with open(vault_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Erro ao carregar password_vault.json: {e}")
        return []


def save_vault(entries):
    """Salva todas as credenciais no arquivo de cofre."""
    vault_path = get_vault_path()
    try:
        with open(vault_path, 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Erro ao salvar password_vault.json: {e}")
        raise


def add_entry(name, entry_type, description, host, port, service_name, username, password):
    """Adiciona uma nova credencial ao cofre."""
    entries = load_vault()
    entry = {
        "id": str(uuid.uuid4()),
        "name": name,
        "type": entry_type,
        "description": description,
        "host": host,
        "port": port,
        "service_name": service_name,
        "username": username,
        "password": encrypt_password(password) if password else "",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    entries.append(entry)
    save_vault(entries)
    logger.info(f"Novo acesso '{name}' adicionado ao cofre.")
    return entry


def update_entry(entry_id, name, entry_type, description, host, port, service_name, username, password):
    """Atualiza uma credencial existente no cofre."""
    entries = load_vault()
    for entry in entries:
        if entry["id"] == entry_id:
            entry["name"] = name
            entry["type"] = entry_type
            entry["description"] = description
            entry["host"] = host
            entry["port"] = port
            entry["service_name"] = service_name
            entry["username"] = username
            if password:
                entry["password"] = encrypt_password(password)
            entry["updated_at"] = datetime.now().isoformat()
            break
    save_vault(entries)
    logger.info(f"Acesso '{name}' (id={entry_id}) atualizado no cofre.")


def delete_entry(entry_id):
    """Remove uma credencial do cofre pelo ID."""
    entries = load_vault()
    before = len(entries)
    entries = [e for e in entries if e["id"] != entry_id]
    save_vault(entries)
    logger.info(f"Acesso id={entry_id} removido do cofre ({before - len(entries)} item).")


def get_decrypted_password(entry):
    """Retorna a senha descriptografada de uma entrada."""
    return decrypt_password(entry.get("password", ""))


def search_entries(query):
    """Filtra credenciais por qualquer campo de texto."""
    entries = load_vault()
    if not query:
        return entries
    q = query.lower()
    results = []
    for entry in entries:
        haystack = " ".join([
            entry.get("name", ""),
            entry.get("type", ""),
            entry.get("description", ""),
            entry.get("host", ""),
            entry.get("username", ""),
            entry.get("service_name", ""),
            entry.get("port", ""),
        ]).lower()
        if q in haystack:
            results.append(entry)
    return results
