# C:\Meus Projetos\fixer\modules\common\security.py

import keyring
from base64 import b64encode, b64decode
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import json

# Identificadores para o nosso app no cofre de credenciais do SO
SERVICE_NAME = "FixerApp"
KEY_USERNAME = "encryption_key"

def get_encryption_key():
    """
    Busca a chave de criptografia no cofre do SO.
    Se não existir, cria uma nova e a armazena.
    """
    key = keyring.get_password(SERVICE_NAME, KEY_USERNAME)
    if key is None:
        # Gera uma chave forte de 32 bytes (AES-256)
        new_key = get_random_bytes(32)
        # Armazena a chave como uma string base64
        keyring.set_password(SERVICE_NAME, KEY_USERNAME, b64encode(new_key).decode('utf-8'))
        return new_key
    
    # Decodifica a chave de base64 para bytes
    return b64decode(key.encode('utf-8'))

def encrypt_password(password: str) -> str:
    """Criptografa a senha usando AES-GCM e retorna em base64."""
    if not password:
        return ""
    key = get_encryption_key()
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(password.encode('utf-8'))
    
    # Junta nonce, tag e ciphertext para armazenamento
    encrypted_data = {
        'nonce': b64encode(cipher.nonce).decode('utf-8'),
        'tag': b64encode(tag).decode('utf-8'),
        'ciphertext': b64encode(ciphertext).decode('utf-8')
    }
    return b64encode(json.dumps(encrypted_data).encode('utf-8')).decode('utf-8')

def decrypt_password(encrypted_b64: str) -> str:
    """Descriptografa uma senha que foi armazenada em base64."""
    if not encrypted_b64:
        return ""
    key = get_encryption_key()
    try:
        encrypted_data = json.loads(b64decode(encrypted_b64).decode('utf-8'))
        nonce = b64decode(encrypted_data['nonce'])
        tag = b64decode(encrypted_data['tag'])
        ciphertext = b64decode(encrypted_data['ciphertext'])
        
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        decrypted_password = cipher.decrypt_and_verify(ciphertext, tag)
        return decrypted_password.decode('utf-8')
    except (ValueError, KeyError, TypeError):
        # Se a senha no config.ini não estiver criptografada, retorna ela mesma.
        # Útil para a transição de senhas antigas.
        print("Aviso: Tentando descriptografar uma senha que não parece estar criptografada. Retornando em texto plano.")
        return encrypted_b64