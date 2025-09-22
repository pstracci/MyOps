# C:\Meus Projetos\fixer\modules\gfa\gfa_logic.py

import configparser
import requests # Usaremos a biblioteca requests
import json

GFA_CONFIG_KEY = 'weblogic_gfa'

def get_config():
    """Lê a seção GFA do arquivo config.ini."""
    config = configparser.ConfigParser()
    config.read('config.ini')
    if GFA_CONFIG_KEY in config:
        return config[GFA_CONFIG_KEY]
    raise ConnectionError(f"Seção '{GFA_CONFIG_KEY}' não encontrada no 'config.ini'.")

def get_gfa_status():
    """Busca o status dos servidores GFA via API REST."""
    config = get_config()
    base_url = config['url']
    user = config['user']
    password = config['password']
    
    # O "endpoint" da API para servidores em tempo de execução
    api_url = f"{base_url}/management/weblogic/latest/serverRuntimes"
    
    headers = {
        "Accept": "application/json"
    }
    
    try:
        # Faz a chamada GET para a API com autenticação
        response = requests.get(api_url, auth=(user, password), headers=headers, timeout=30)
        response.raise_for_status() # Lança um erro se a resposta for 4xx ou 5xx
        
        data = response.json()
        all_servers = []

        if 'items' not in data:
            return []

        for server in data['items']:
            # A API retorna o Health State em um formato complexo, extraímos o estado principal
            health_state_raw = server.get('healthState', {})
            health = f"{health_state_raw.get('state', 'UNKNOWN')} ({health_state_raw.get('subsystem', 'N/A')})"
            
            server_data = {
                'name': server['name'],
                'state': server['state'],
                'health': health,
                'is_ok': "RUNNING" in server['state'] and "OK" in health
            }
            all_servers.append(server_data)
            
        return all_servers

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Erro de conexão ou comunicação com a API do WebLogic: {e}")

def restart_gfa_server(server_name):
    """Envia um comando de restart para um servidor via API REST."""
    config = get_config()
    base_url = config['url']
    user = config['user']
    password = config['password']
    
    # O endpoint para operações de ciclo de vida (start, shutdown)
    api_url_shutdown = f"{base_url}/management/weblogic/latest/serverRuntimes/{server_name}/shutdown"
    api_url_start = f"{base_url}/management/weblogic/latest/serverRuntimes/{server_name}/start"
    
    headers = { "Accept": "application/json" }
    
    try:
        # 1. Envia o comando POST para desligar (shutdown)
        print(f"Enviando comando SHUTDOWN para {server_name}...")
        shutdown_response = requests.post(api_url_shutdown, auth=(user, password), headers=headers, timeout=30)
        shutdown_response.raise_for_status()
        
        # 2. Envia o comando POST para iniciar (start)
        print(f"Enviando comando START para {server_name}...")
        start_response = requests.post(api_url_start, auth=(user, password), headers=headers, timeout=30)
        start_response.raise_for_status()

        return f"Comandos de restart para o servidor '{server_name}' enviados com sucesso.\n\nMonitore o status do servidor para confirmar a reinicialização."

    except requests.exceptions.RequestException as e:
        error_details = e.response.json() if e.response else str(e)
        raise RuntimeError(f"Erro ao enviar comando de restart via API:\n{json.dumps(error_details, indent=2)}")