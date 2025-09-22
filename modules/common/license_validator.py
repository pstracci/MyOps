# C:\Meus Projetos\MyOps\modules\common\license_validator.py

import hmac
import hashlib
import datetime
import os

# IMPORTANTE: Esta chave secreta DEVE ser exatamente a mesma do seu gerador de licenças.
SECRET_KEY = "MyOps_Super_Secret_Key_For_HMAC_2024_XYZ"

def check_license():
    """
    Verifica a validade do arquivo de licença 'license.key'.

    Retorna:
        tuple[bool, str]: (True, "Mensagem de sucesso") se a licença for válida.
                          (False, "Mensagem de erro") se for inválida, expirada ou inexistente.
    """
    license_file = 'license.key'

    # 1. Verifica se o arquivo de licença existe
    if not os.path.exists(license_file):
        return (False, "Arquivo de licença 'license.key' não encontrado. Por favor, coloque o arquivo de licença na mesma pasta do executável.")

    try:
        with open(license_file, 'r') as f:
            license_content = f.read().strip()
    except IOError as e:
        return (False, f"Não foi possível ler o arquivo de licença: {e}")

    # 2. Verifica se o formato do conteúdo é válido (data::assinatura)
    parts = license_content.split('::')
    if len(parts) != 2:
        return (False, "Licença corrompida ou em formato inválido.")
    
    expiry_date_str, stored_signature = parts

    # 3. Recalcula a assinatura e a compara com a assinatura armazenada
    # Isso impede que o usuário simplesmente altere a data no arquivo.
    expected_signature = hmac.new(
        key=SECRET_KEY.encode('utf-8'),
        msg=expiry_date_str.encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(stored_signature, expected_signature):
        return (False, "Assinatura da licença é inválida. O arquivo pode ter sido adulterado.")

    # 4. Se a assinatura for válida, verifica se a data de expiração já passou
    try:
        expiry_date = datetime.datetime.strptime(expiry_date_str, '%Y-%m-%d')
        if datetime.datetime.now() > expiry_date:
            return (False, f"Sua licença expirou em {expiry_date_str}. Por favor, renove sua licença.")
    except ValueError:
        return (False, "O formato da data na licença é inválido.")

    # 5. Se tudo estiver correto, a licença é válida
    return (True, f"Licença válida até {expiry_date_str}.")
