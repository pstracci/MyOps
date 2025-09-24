# modules/gfa/gfa_logic.py (Versão com Paramiko)
import paramiko

def run_health_check_with_paramiko(host_alias, password):
    """
    Conecta-se a um servidor via SSH usando Paramiko, executa um comando e retorna a saída.
    """
    # Mapeamento de alias para detalhes da conexão.
    # Isso elimina a necessidade do arquivo C:\Users\...\.ssh\config
    HOSTS = {
        "gfa-prod": {
            "hostname": "snevlxa106",
            "username": "system"
            # A senha é fornecida dinamicamente
        }
    }

    if host_alias not in HOSTS:
        return (False, f"O alias '{host_alias}' nao esta configurado no dicionario HOSTS.")

    host_info = HOSTS[host_alias]
    
    # Comando a ser executado no servidor remoto
    command = "/appl/bea/PRODUCAO/MONITORACAO/PM_HEALTH/get_detailed_health_log.sh"

    try:
        # 1. Cria o cliente SSH
        client = paramiko.SSHClient()
        # Adiciona automaticamente a chave do host (menos seguro, mas mais fácil para distribuição interna)
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # 2. Conecta ao servidor
        client.connect(
            hostname=host_info["hostname"],
            username=host_info["username"],
            password=password,
            timeout=20 # Timeout de 20 segundos para a conexão
        )

        # 3. Executa o comando
        stdin, stdout, stderr = client.exec_command(command, timeout=300) # Timeout de 5 minutos para o comando

        # 4. Lê a saída e os erros
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()

        if error:
            # Se houver algo no 'stderr', consideramos um erro
            return (False, f"Erro na execucao remota: {error}")
        
        return (True, output)

    except paramiko.AuthenticationException:
        return (False, "Falha na autenticacao. Verifique a senha.")
    except paramiko.SSHException as e:
        return (False, f"Erro no SSH: {e}")
    except Exception as e:
        return (False, f"Um erro inesperado ocorreu: {e}")
    finally:
        # 5. Garante que a conexão seja sempre fechada
        if 'client' in locals() and client.get_transport() is not None:
            client.close()