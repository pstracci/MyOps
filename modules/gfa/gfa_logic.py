# C:\Meus Projetos\MyOps\modules\gfa\gfa_logic.py (Versão Revertida - Terminal Externo)
import subprocess
import os
import tempfile
import time
import sys

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