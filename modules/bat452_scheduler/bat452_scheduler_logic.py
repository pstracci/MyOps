# C:\Meus Projetos\MyOps\modules\bat452_scheduler\bat452_scheduler_logic.py

import csv
import oracledb
import getpass
import os
import re
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

def preview_file(file_path):
    try:
        data_to_return, headers = [], []
        try:
            with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                reader = csv.reader(f, delimiter='|')
                headers = next(reader)
                for _, row in zip(range(100), reader):
                    data_to_return.append([field.strip() for field in row])
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                reader = csv.reader(f, delimiter='|')
                headers = next(reader)
                for _, row in zip(range(100), reader):
                    data_to_return.append([field.strip() for field in row])
        return data_to_return, headers
    except Exception as e:
        return [[f"Erro ao ler o arquivo: {e}"], ["Erro"]]

def get_scheduled_jobs(db_section_key):
    try:
        conn_details = get_db_config(db_section_key)
        with oracledb.connect(**conn_details) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SCHEDULE_ID, REQ_ID, STATUS, 
                       TO_CHAR(SCHEDULE_TIMESTAMP, 'DD/MM/YYYY HH24:MI:SS'), 
                       TO_CHAR(PROCESS_TIMESTAMP, 'DD/MM/YYYY HH24:MI:SS'), 
                       FILE_NAME, USER_WHO_SCHEDULED, ERROR_MESSAGE 
                FROM ACC_PM_BAT452_SCHEDULE 
                ORDER BY SCHEDULE_ID DESC
            """)
            return True, cursor.fetchall()
    except Exception as e:
        return False, str(e)

def schedule_job(db_section_key, req_id, data_to_load, file_name):
    good_rows = []
    bad_rows_count = 0
    
    for row in data_to_load:
        if len(row) < 3:
            bad_rows_count += 1
            continue
        cleaned_row = [str(field).strip() if field is not None else None for field in row]
        cpf_original = cleaned_row[2]
        cpf_cleaned = re.sub(r'\D', '', cpf_original)
        if len(cpf_cleaned) == 11:
            cleaned_row[2] = cpf_cleaned
            good_rows.append(cleaned_row)
        else:
            bad_rows_count += 1

    if not good_rows:
        return False, "Nenhum registro válido encontrado no arquivo. Verifique os CPFs."

    try:
        conn_details = get_db_config(db_section_key)
        with oracledb.connect(**conn_details) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ACC_PM_BAT452_SCHEDULE WHERE STATUS = 'PENDING'")
            if cursor.fetchone()[0] > 0:
                return False, "Já existe um processamento pendente na fila."

            cursor.execute("TRUNCATE TABLE ACC_SBL_TIR577967_LDR_TABLE")
            
            prepared_data = [tuple(row[:9]) + (None,) * (9 - len(row)) for row in good_rows]
            cursor.executemany("""
                INSERT INTO ACC_SBL_TIR577967_LDR_TABLE (
                    MSISDN, CO_ID, CPF, ACAO, MOTIVO_STATUS, MOTIVO1, 
                    MOTIVO2, MOTIVO3, STATUS_SR
                ) VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9)
            """, prepared_data)

            user = getpass.getuser()
            cursor.execute("""
                INSERT INTO ACC_PM_BAT452_SCHEDULE (REQ_ID, FILE_NAME, USER_WHO_SCHEDULED)
                VALUES (:req_id, :file_name, :p_user)
            """, req_id=req_id, file_name=file_name, p_user=user)
            conn.commit()
            
            success_message = f"{len(good_rows)} registros válidos foram carregados e agendados para a REQ {req_id}."
            if bad_rows_count > 0:
                success_message += f"\n\nAtenção: {bad_rows_count} registros foram ignorados por CPF/CNPJ inválido."
            return True, success_message

    except oracledb.DatabaseError as e:
        error_obj, = e.args
        return False, f"Erro de Banco de Dados: {error_obj.code} - {error_obj.message}"
    except Exception as e:
        return False, f"Um erro inesperado ocorreu: {e}"

# --- INÍCIO DA NOVA FUNÇÃO ---
def get_final_asset_status(db_section_key, req_id):
    """
    Busca os MSISDNs de uma execução e consulta seu status final na S_ASSET.
    """
    try:
        conn_details = get_db_config(db_section_key)
        with oracledb.connect(**conn_details) as conn:
            cursor = conn.cursor()

            # 1. Encontra o EXEC_ID correspondente à REQ_ID
            cursor.execute("SELECT EXEC_ID FROM ACC_SBL_TIR577967_EXEC WHERE REQ_ID = :req_id", req_id=req_id)
            result = cursor.fetchone()
            if not result:
                return False, f"Nenhum EXEC_ID encontrado para a REQ {req_id}. O processo pode não ter iniciado."
            exec_id = result[0]

            # 2. Busca todos os MSISDNs processados naquela execução
            cursor.execute("SELECT MSISDN FROM ACC_SBL_TIR577967_CTRL WHERE EXEC_ID = :exec_id", exec_id=exec_id)
            msisdn_list = [row[0] for row in cursor.fetchall()]
            
            if not msisdn_list:
                return False, f"Nenhum MSISDN encontrado na tabela de controle para o EXEC_ID {exec_id}."

            # 3. Consulta o status final de todos os MSISDNs na S_ASSET
            # A forma como o oracledb lida com a cláusula IN é passando um tuple/lista diretamente
            sql_query = """
                SELECT TO_CHAR(created, 'DD/MM/YYYY HH24:MI:SS'), 
                       TO_CHAR(last_upd, 'DD/MM/YYYY HH24:MI:SS'), 
                       serial_num, status_cd, last_upd_by 
                FROM s_Asset 
                WHERE serial_num IN ({})
            """.format(','.join([':'+str(i+1) for i in range(len(msisdn_list))]))
            
            cursor.execute(sql_query, msisdn_list)
            
            return True, cursor.fetchall()

    except Exception as e:
        return False, str(e)
# --- FIM DA NOVA FUNÇÃO ---