# C:\Meus Projetos\MyOps\modules\gfa\gfa_logic.py (Versão Revertida - Terminal Externo)
import subprocess
import os
import tempfile
import time
import sys
import configparser
import oracledb
from modules.common import security


def get_config(section):
    """Lê uma seção específica do arquivo config.ini e descriptografa a senha."""
    config = configparser.ConfigParser()
    config.read('config.ini')
    if section in config:
        user = config[section].get('user', '')
        encrypted_password = config[section].get('password', '')
        dsn = config[section].get('dsn', config[section].get('url', ''))
        password = security.decrypt_password(encrypted_password)
        return user, password, dsn
    raise ConnectionError(f"Seção '{section}' não encontrada no 'config.ini'.")


def get_all_db_connections():
    config = configparser.ConfigParser()
    config.read('config.ini')
    db_connections = {}
    for section in config.sections():
        if section.startswith('database_'):
            db_connections[section] = section.replace('database_', '').replace('_', ' ').title()
    return db_connections


def release_pdv_for_update(db_key, pdv_code):
    """
    Executa SGFA001.PRC_FIX_LOJA para o PDV informado, liberando-o para
    atualização, e retorna a saída do DBMS_OUTPUT gerada pela procedure.
    """
    pdv_code = (pdv_code or "").strip()
    if not pdv_code:
        raise ValueError("Informe o código do PDV.")

    user, password, dsn = get_config(db_key)
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.callproc("dbms_output.enable")
                cursor.callproc("SGFA001.PRC_FIX_LOJA", [pdv_code])
                connection.commit()

                lines_var = cursor.arrayvar(str, 100)
                num_lines_var = cursor.var(int, 100)
                dbms_output_lines = []
                while True:
                    cursor.callproc("dbms_output.get_lines", [lines_var, num_lines_var])
                    num_retrieved = num_lines_var.getvalue()
                    lines = lines_var.getvalue()[:num_retrieved]
                    for line in lines:
                        if line:
                            dbms_output_lines.append(line.strip())
                    if num_retrieved < 100:
                        break
                return "\n".join(dbms_output_lines)
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro no banco de dados ao liberar o PDV: {e.args[0].message}")

def run_health_check_with_temp_script(host_alias):
    """
    Cria e executa um script .bat temporário em uma nova janela de terminal.
    """
    command_to_run_remotely = "/appl/bea/PRODUCAO/MONITORACAO/PM_HEALTH/get_detailed_health_log.sh"

    temp_log_fd, temp_log_path = tempfile.mkstemp(text=True, suffix='.log')
    os.close(temp_log_fd)

    temp_bat_fd, temp_bat_path = tempfile.mkstemp(text=True, suffix='.bat')
    
    ssh_command_line = f'ssh -T {host_alias} "{command_to_run_remotely}" > "{temp_log_path}"'
    
    batch_script_content = f'''
@echo off
echo Conectando a {host_alias} e executando script de coleta...
echo Por favor, autentique-se. Esta janela fechará automaticamente.
echo.

{ssh_command_line}

if %errorlevel% neq 0 (
    echo.
    echo Ocorreu um erro na conexao ou execucao remota.
    pause
)
exit
'''
    with os.fdopen(temp_bat_fd, 'w') as bat_file:
        bat_file.write(batch_script_content)
    
    try:
        if sys.platform != "win32":
            return (False, "Erro: Esta funcionalidade so e compativel com Windows.")

        command_to_execute = [
            'cmd.exe', '/c', 'start', f"Autenticacao SSH para {host_alias}", '/wait', temp_bat_path
        ]
        
        process = subprocess.run(
            command_to_execute,
            timeout=300
        )
        
        time.sleep(1)
        with open(temp_log_path, 'r', encoding='utf-8', errors='replace') as log_file:
            output = log_file.read()

        if "ERRO|" in output:
             return (False, f"O script remoto reportou um erro: {output}")

        return (True, output)
        
    except subprocess.TimeoutExpired:
        return (False, "Erro: O processo de autenticacao e execucao demorou mais de 5 minutos (Timeout).")
    except Exception as e:
        return (False, f"Erro ao executar o script temporario: {e}")
    finally:
        if os.path.exists(temp_log_path):
            os.remove(temp_log_path)
        if os.path.exists(temp_bat_path):
            os.remove(temp_bat_path)