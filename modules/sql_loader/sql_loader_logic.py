# C:\Meus Projetos\MyOps\modules\sql_loader\sql_loader_logic.py

import configparser
import oracledb
import os
import subprocess
import time
import re
from datetime import datetime
from modules.common import security
import pandas as pd

def init_thick_mode():
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')
        client_path = config.get('general', 'instant_client_path', fallback=None)
        if client_path and os.path.isdir(client_path):
            oracledb.init_oracle_client(lib_dir=client_path)
    except Exception as e:
        print(f"Aviso: Não foi possível (re)inicializar o modo Thick. Erro: {e}")

def get_config(section):
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

def get_table_columns(db_key, schema, table_name):
    init_thick_mode()
    user, password, dsn = get_config(db_key)
    sane_schema = re.sub(r'[^A-Z0-9_]', '', schema.upper())
    sane_table_name = re.sub(r'[^A-Z0-9_$#]', '', table_name.upper())
    if sane_schema != schema.upper() or sane_table_name != table_name.upper():
        raise ValueError("Nome de schema ou tabela contém caracteres inválidos.")
    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        with connection.cursor() as cursor:
            query = f"SELECT column_name, data_type FROM all_tab_columns WHERE owner = '{sane_schema}' AND table_name = '{sane_table_name}' ORDER BY column_id"
            cursor.execute(query)
            columns = cursor.fetchall()
            if not columns:
                raise ValueError(f"Tabela '{schema}.{table_name}' não encontrada ou não possui colunas.")
            return columns

def infer_column_types(file_path, delimiter):
    """
    Analisa uma amostra do arquivo para inferir os tipos de dados Oracle (VARCHAR2, NUMBER, DATE).
    Retorna uma lista de tuplas (column_name, oracle_type, date_format).
    """
    try:
        df = pd.read_csv(file_path, sep=delimiter, nrows=1000, encoding='latin-1', keep_default_na=False, engine='python')
        
        column_types = []
        for col in df.columns:
            sane_col_name = re.sub(r'[^A-Z0-9_]', '', str(col).upper().replace(" ", "_"))
            if not sane_col_name:
                sane_col_name = f"COLUNA_{len(column_types) + 1}"

            col_data = df[col].dropna().astype(str)
            if col_data.empty:
                column_types.append((sane_col_name, "VARCHAR2(255)", None))
                continue

            # Tenta converter para numérico (aceita inteiros e decimais com vírgula ou ponto)
            if col_data.str.match(r'^-?\d+([.,]\d+)?$').all():
                column_types.append((sane_col_name, "NUMBER", None))
                continue

            # Tenta converter para data (testa formatos comuns)
            date_format_map = {
                'DD/MM/YYYY HH24:MI:SS': r'^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$',
                'DD/MM/YYYY': r'^\d{2}/\d{2}/\d{4}$',
                'YYYY-MM-DD HH24:MI:SS': r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$',
                'YYYY-MM-DD': r'^\d{4}-\d{2}-\d{2}$',
            }
            
            detected_format = None
            for fmt, pattern in date_format_map.items():
                if col_data.str.match(pattern).all():
                    detected_format = fmt
                    break
            
            if detected_format:
                column_types.append((sane_col_name, "DATE", detected_format))
                continue

            # Se não for número nem data, assume VARCHAR2
            max_len = col_data.str.len().max()
            varchar_len = 4000 if max_len > 2000 else 1000 if max_len > 255 else 255
            column_types.append((sane_col_name, f"VARCHAR2({varchar_len})", None))

        return column_types
    except Exception as e:
        raise RuntimeError(f"Falha ao analisar o arquivo para inferir tipos de dados: {e}")

def create_temporary_table(db_key, schema, columns):
    """
    Cria uma nova tabela temporária no banco de dados com base nas colunas inferidas.
    Retorna o nome da tabela criada.
    """
    init_thick_mode()
    user, password, dsn = get_config(db_key)
    
    timestamp = datetime.now().strftime('%d%m%Y_%H%M%S')
    table_name = f"PM_TMP_SQLLOADER_{timestamp}"
    
    column_definitions = ", ".join([f'"{col[0]}" {col[1]}' for col in columns])
    
    create_sql = f'CREATE TABLE "{schema.upper()}"."{table_name}" ({column_definitions})'
    
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(create_sql)
        return table_name
    except Exception as e:
        raise RuntimeError(f"Falha ao criar tabela temporária: {e}\nSQL: {create_sql}")

def generate_control_file(file_path, table_name, schema, delimiter, columns, load_method):
    temp_dir = os.path.join(os.getcwd(), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    file_base = f"sqlldr_{int(time.time())}_{os.getpid()}"
    ctl_path = os.path.join(temp_dir, f"{file_base}.ctl")
    
    data_file_path_quoted = f'"{file_path}"'
    bad_file_path_quoted = f'"{os.path.join(temp_dir, f"{file_base}.bad")}"'
    discard_file_path_quoted = f'"{os.path.join(temp_dir, f"{file_base}.dsc")}"'
    
    load_option = "TRUNCATE" if load_method == "Truncar" else "APPEND"
    
    column_definitions = []
    for col_name, col_type, date_mask in columns:
        if col_type == "DATE" and date_mask:
            column_definitions.append(f'"{col_name}" DATE "{date_mask}"')
        else:
            column_definitions.append(f'"{col_name}"')
    column_list = ",\n".join(column_definitions)
    
    ctl_content = f"""
OPTIONS (SKIP=0, ERRORS=99999, BINDSIZE=512000, ROWS=10000, DIRECT=YES)
LOAD DATA
INFILE {data_file_path_quoted}
BADFILE {bad_file_path_quoted}
DISCARDFILE {discard_file_path_quoted}
{load_option}
INTO TABLE "{schema.upper()}"."{table_name.upper()}"
FIELDS TERMINATED BY '{delimiter}'
TRAILING NULLCOLS
(
{column_list}
)
"""
    with open(ctl_path, 'w', encoding='utf-8') as f:
        f.write(ctl_content)
    return ctl_path

def run_sql_loader(db_key, ctl_path):
    config = configparser.ConfigParser()
    config.read('config.ini')
    instant_client_path = config.get('general', 'instant_client_path', fallback='')
    if not instant_client_path:
        raise ValueError("Caminho do Oracle Instant Client não está configurado.")
    
    sqlldr_exe = os.path.join(instant_client_path, 'sqlldr.exe')
    if not os.path.exists(sqlldr_exe):
        raise FileNotFoundError(f"Executável do SQL*Loader não encontrado em: {sqlldr_exe}")

    user, password, dsn = get_config(db_key)
    
    base_path = os.path.dirname(ctl_path)
    base_filename = os.path.splitext(os.path.basename(ctl_path))[0]
    log_path = os.path.join(base_path, f"{base_filename}.log")
    
    command = [
        sqlldr_exe,
        f"userid={user}/{password}@{dsn}",
        f'control="{ctl_path}"',
        f'log="{log_path}"'
    ]
    
    env = os.environ.copy()
    env['NLS_LANG'] = '.UTF8' # Garante a codificação correta
    env['PATH'] = instant_client_path + os.pathsep + env.get('PATH', '')

    result_log, bad_file_content, exit_code = "", "", -1
    
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=False, encoding='latin-1', env=env)
        exit_code = process.returncode
        
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='latin-1') as f:
                result_log = f.read()
        
        if not result_log and exit_code != 0:
            result_log = (f"O processo SQL*Loader falhou com o código de saída: {exit_code}\n"
                          f"Saída de Erro Padrão (stderr):\n{process.stderr}\n\n"
                          f"Saída Padrão (stdout):\n{process.stdout}")

        bad_path = os.path.join(base_path, f"{base_filename}.bad")
        if os.path.exists(bad_path):
            with open(bad_path, 'r', encoding='latin-1') as f:
                bad_file_content = f.read()
    finally:
        for f_path in [ctl_path, log_path, bad_path, ctl_path.replace('.ctl', '.dsc')]:
            if os.path.exists(f_path):
                try:
                    os.remove(f_path)
                except OSError:
                    pass

    return result_log, bad_file_content, exit_code