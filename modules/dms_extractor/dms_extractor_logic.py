# C:\Meus Projetos\MyOps\modules\dms_extractor\dms_extractor_logic.py

import subprocess
import os
import tempfile
import time
import sys
from datetime import datetime
import oracledb
import configparser
from modules.common import security

def get_db_config(section):
    config = configparser.ConfigParser()
    config.read('config.ini')
    if section in config:
        user = config[section].get('user', '')
        encrypted_password = config[section].get('password', '')
        dsn = config[section].get('dsn', '')
        password = security.decrypt_password(encrypted_password)
        return {'user': user, 'password': password, 'dsn': dsn}
    raise ConnectionError(f"Seção '{section}' não encontrada no 'config.ini'.")

def get_all_db_connections():
    config = configparser.ConfigParser()
    config.read('config.ini')
    db_connections = {}
    for section in config.sections():
        if section.startswith('database_'):
            display_name = section.replace('database_', '').replace('_', ' ').title()
            db_connections[section] = display_name
    return db_connections

def get_id_custcode_map_from_siebel(siebel_db_key, search_list, search_field):
    if not siebel_db_key:
        return False, "A conexão com o banco de dados Siebel não foi fornecida."
    if not search_list:
        return True, {}

    query = f"""
        SELECT CUSTOMER_ID, CUSTCODE 
        FROM customer_all@SBL_BSCS 
        WHERE {search_field} IN ({{placeholders}})
          AND PAYMNTRESP = 'X'
    """
    
    placeholders = [f':val_{i}' for i in range(len(search_list))]
    query = query.format(placeholders=', '.join(placeholders))
    params = {f'val_{i}': val for i, val in enumerate(search_list)}
    
    try:
        conn_details = get_db_config(siebel_db_key)
        id_custcode_map = {}
        with oracledb.connect(**conn_details) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            for row in cursor:
                customer_id = str(row[0])
                custcode = str(row[1])
                id_custcode_map[customer_id] = custcode
            return True, id_custcode_map
    except Exception as e:
        return False, f"Erro ao consultar dados no Siebel: {e}"

def get_invoices_for_customer_ids(db_section_key, customer_ids, due_date_str_prefix=None):
    if not customer_ids:
        return True, []

    base_query = """
        SELECT /*+ INDEX (A, IDX_ODM_PAGINAFATURA_01)*/
            DISTINCT a.customeridfatura, a.datavencimentofatura, 
            TO_CHAR(TO_DATE(a.datavencimentofatura, 'YYYYMMDD'), 'DD/MM/YYYY') AS VENCIMENTO_FORMATADO,
            a.nufatura,
            (SELECT MAX(numpagina) FROM ODM_PAGINAFATURA fat
             WHERE FAT.customeridfatura = a.customeridfatura AND fat.datavencimentofatura = a.datavencimentofatura) qtd_paginas
        FROM ODM_PAGINAFATURA a, ODM_DOCUMENT b, ODM_CONTENTOBJECT c, ODMM_NONINDEXEDSTORE d
        WHERE a.id = b.id AND b.contentobject = c.id
              AND contenttype = 1 AND c.content = d.id
    """
    
    placeholders = [f':id_{i}' for i in range(len(customer_ids))]
    in_clause = ', '.join(placeholders)
    base_query += f" AND a.customeridfatura IN ({in_clause})"
    params = {f'id_{i}': cid for i, cid in enumerate(customer_ids)}

    if due_date_str_prefix:
        base_query += " AND a.datavencimentofatura LIKE :due_date || '%'"
        params["due_date"] = due_date_str_prefix
        
    try:
        conn_details = get_db_config(db_section_key)
        with oracledb.connect(**conn_details) as conn:
            cursor = conn.cursor()
            cursor.execute(base_query, params)
            columns = [desc[0].lower() for desc in cursor.description]
            return True, [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        return False, f"Erro ao consultar faturas: {e}"

def get_available_invoices(db_section_key, siebel_db_key, search_type, search_values_raw, due_date_str_prefix=None):
    search_values = [line.strip() for line in search_values_raw.splitlines() if line.strip()]
    if not search_values:
        return True, []

    search_field = 'CUSTCODE' if search_type == 'custcode' else 'CUSTOMER_ID'
    success, id_custcode_map = get_id_custcode_map_from_siebel(siebel_db_key, search_values, search_field)
    
    if not success:
        return False, id_custcode_map

    customer_ids_to_search = list(id_custcode_map.keys())
    if not customer_ids_to_search:
        return True, []

    success, invoices = get_invoices_for_customer_ids(db_section_key, customer_ids_to_search, due_date_str_prefix)

    if not success:
        return False, invoices

    for invoice in invoices:
        # --- INÍCIO DA CORREÇÃO ---
        # Converte o customer_id do DMS para string ANTES de procurar no mapa
        customer_id = str(invoice.get('customeridfatura'))
        # --- FIM DA CORREÇÃO ---
        invoice['custcode'] = id_custcode_map.get(customer_id, 'N/A')

    return True, invoices

def run_remote_extraction(invoices_to_process):
    # (Esta função permanece inalterada)
    if not invoices_to_process:
        return (False, "Nenhuma fatura selecionada para processar.")
    first_customer_id = invoices_to_process[0]['customeridfatura']
    file_content = ""
    for inv in invoices_to_process:
        file_content += f"{inv['customeridfatura']}|{inv['datavencimentofatura']}\n"
    temp_dir = tempfile.gettempdir()
    timestamp = datetime.now().strftime('%d%m%Y')
    remote_filename = f"cli_{first_customer_id}_{timestamp}.txt"
    remote_input_path = f"/dms/scripts/RESSARCIMENTO_PDF/input/{remote_filename}"
    local_content_path = os.path.join(temp_dir, remote_filename)
    with open(local_content_path, 'w', encoding='utf-8') as f:
        f.write(file_content)
    ssh_alias = "dms-prod" 
    script_user = "system"
    script_pass = "dmstimprd01"
    command_to_run_remotely = (
        f". /dms/scripts/bin/env.sh && "
        f"nohup /dms/scripts/bin/ressarcimentoPdf_teste.sh {script_user} {script_pass} {remote_input_path} 1 > "
        f"/dms/scripts/RESSARCIMENTO_PDF/log/nohup_{remote_filename.replace('.txt', '.log')} 2>&1 &"
    )
    local_content_path_for_scp = local_content_path.replace("\\", "/")
    batch_script_content = f'''
@echo off
echo 1. Copiando arquivo de entrada para o servidor via SCP...
scp "{local_content_path_for_scp}" {ssh_alias}:{remote_input_path}
echo.
echo 2. Executando script de extração no servidor (assíncrono)...
ssh -T {ssh_alias} "{command_to_run_remotely}"
echo.
echo 3. Processo iniciado no servidor. Esta janela fechará em 5 segundos.
timeout /t 5 > nul
exit
'''
    temp_bat_fd, temp_bat_path = tempfile.mkstemp(text=True, suffix='.bat')
    with os.fdopen(temp_bat_fd, 'w') as bat_file:
        bat_file.write(batch_script_content)
    try:
        if sys.platform != "win32":
            return (False, "Esta funcionalidade só é compatível com Windows.")
        subprocess.Popen(
            ['cmd.exe', '/c', 'start', f"Extracao de Fatura DMS - {first_customer_id}", temp_bat_path],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return (True, "Processo de extração iniciado no servidor.")
    except Exception as e:
        return (False, f"Erro ao iniciar o processo remoto: {e}")