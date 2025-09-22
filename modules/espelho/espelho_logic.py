import oracledb
import configparser
import requests # Importa a nova biblioteca
import json     # Para tratar possíveis erros de JSON

from modules.common import security # NOVO

def get_config(section='database_espelho'): # <-- O valor padrão foi adicionado aqui
    """Lê a seção do Espelho do config.ini e descriptografa a senha."""
    config = configparser.ConfigParser()
    config.read('config.ini')
    if section in config:
        # Pega os valores do arquivo de configuração
        user = config[section].get('user', '')
        encrypted_password = config[section].get('password', '')
        # Pega 'dsn' para bancos Oracle ou 'url' para Weblogic, tornando a função universal
        dsn = config[section].get('dsn', config[section].get('url', ''))

        # Descriptografa a senha antes de retorná-la
        password = security.decrypt_password(encrypted_password)
        
        return user, password, dsn
        
    raise ConnectionError(f"Seção '{section}' não encontrada no 'config.ini'.")

# --- Funções do Sistema Base Espelho ---

def _get_customer_profile(schema, identifier, search_type):
    # ... (código desta função não foi alterado)
    user, password, dsn = get_config()
    query = f"""
        SELECT row_id, cust_stat_cd, x_tipo_cliente, alias_name, name, x_data_nascimento,
               x_sexo, main_ph_num, x_doc_type, x_doc_num, x_doc_orgao, x_doc_uf_emissao,
               x_doc_emissao, x_doc_validade, loc, x_nome_mae, main_email_addr, created,
               last_upd, cust_stat_cd, x_port_out, DIVN_TYPE_CD, PR_MGR_POSTN_ID
        FROM {schema}.s_org_ext
    """
    if search_type == 'cpf':
        query += " WHERE name = :identifier"
    elif search_type == 'row_id':
        query += " WHERE row_id = :identifier"
    
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, identifier=identifier)
                columns = [desc[0] for desc in cursor.description]
                row = cursor.fetchone()
                return dict(zip(columns, row)) if row else None
    except oracledb.DatabaseError as e:
        error, = e.args
        raise Exception(f"Erro ao buscar perfil do cliente em {schema}: {error.message}")

def _get_customer_assets(schema, gsm):
    # ... (código desta função não foi alterado)
    user, password, dsn = get_config()
    asset_num_col = 'asset_num' if schema == 'ssblpre001' else 'serial_num'
    if schema == 'ssblpre001':
        query = f"""
            SELECT a.row_id, p.part_num, p.name, a.serial_num, c.name as cpf, a.status_cd,
                   a.type_cd, p.paymnt_type_cd, p.CATEGORY_CD, a.created, a.last_upd,
                   a.last_upd_by, a.integration_id, c.row_id as customer_row_id
            FROM {schema}.s_asset a, {schema}.s_prod_int p, {schema}.s_org_ext c
            WHERE 1 = 1 AND (c.row_id = a.bill_accnt_id OR c.row_id = a.owner_accnt_id)
              AND a.prod_id = p.row_id
              AND a.status_cd <> 'Cancelado'
              AND a.root_asset_id IN (
                  SELECT root_asset_id FROM {schema}.s_asset
                  WHERE {asset_num_col} = :identifier AND status_cd <> 'Cancelado'
              )
            ORDER BY a.root_asset_id, a.status_cd, p.part_num
        """
    else:
        query = f"""
            SELECT a.row_id, p.part_num, p.name, a.serial_num, c.name as cpf, a.status_cd,
                   a.type_cd, p.paymnt_type_cd, p.CATEGORY_CD, a.created, a.last_upd,
                   a.last_upd_by, a.integration_id, a.x_integ_id, a.x_fiber_customer_id,
                   c.row_id as customer_row_id
            FROM {schema}.s_asset a, {schema}.s_prod_int p, {schema}.s_org_ext c
            WHERE 1 = 1 AND (c.row_id = a.bill_accnt_id OR c.row_id = a.owner_accnt_id)
              AND a.prod_id = p.row_id
              AND a.status_cd <> 'Cancelado'
              AND a.root_asset_id IN (
                  SELECT root_asset_id FROM {schema}.s_asset
                  WHERE {asset_num_col} = :identifier AND status_cd <> 'Cancelado'
              )
            ORDER BY a.root_asset_id, a.status_cd, p.part_num
        """
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, identifier=gsm)
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows] if rows else []
    except oracledb.DatabaseError as e:
        error, = e.args
        raise Exception(f"Erro ao buscar assets do cliente em {schema}: {error.message}")

def find_customer_and_determine_type(gsm):
    # ... (código desta função não foi alterado)
    pre_assets = _get_customer_assets('ssblpre001', gsm)
    pos_assets = _get_customer_assets('ssblpos001', gsm)
    assets_data = []
    customer_type = None
    schema_to_use = None
    if pos_assets:
        customer_type = "PÓS-PAGO"
        assets_data = pos_assets
        schema_to_use = 'ssblpos001'
        if pre_assets:
            customer_type = "HÍBRIDO (PÓS-PAGO E PRÉ-PAGO)"
    elif pre_assets:
        customer_type = "PRÉ-PAGO"
        assets_data = pre_assets
        schema_to_use = 'ssblpre001'
    else:
        return None
    customer_cpf = assets_data[0]['CPF']
    profile_data = _get_customer_profile(schema_to_use, customer_cpf, 'cpf')
    history_data = {}
    if customer_type in ["PÓS-PAGO", "HÍBRIDO (PÓS-PAGO E PRÉ-PAGO)"]:
        customer_id = get_customer_id_for_renotify(gsm)
        history_data['client'] = get_history_client(customer_cpf)
        history_data['asset'] = get_history_asset(gsm)
        if customer_id:
            history_data['billing'] = get_history_billing_profile(customer_id)
        else:
            history_data['billing'] = []
    return {
        "profile": profile_data,
        "assets": assets_data,
        "type": customer_type,
        "history": history_data
    }

def get_customer_id_for_renotify(gsm):
    # ... (código desta função não foi alterado)
    user, password, dsn = get_config()
    query = """
        SELECT prof.name 
        FROM ssblpos001.S_INV_PROF prof
        WHERE prof.row_id IN (
            SELECT asset.bill_profile_id 
            FROM ssblpos001.s_asset asset 
            WHERE asset.serial_num = :gsm 
              AND asset.status_cd <> 'Cancelado' 
              AND ROWNUM = 1
        )
    """
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, gsm=gsm)
                result = cursor.fetchone()
                return result[0] if result else None
    except oracledb.DatabaseError as e:
        error, = e.args
        raise Exception(f"Erro ao buscar Customer ID para renotificação: {error.message}")

def execute_renotify_procedure(serial_num, cpf, customer_id):
    # ... (código desta função não foi alterado)
    user, password, dsn = get_config()
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.callproc("dbms_output.enable")
                return_code_var = cursor.var(str, 100)
                return_msg_var = cursor.var(str, 500)
                params = [serial_num, cpf, customer_id, return_code_var, return_msg_var]
                cursor.callproc("PRC_RENOTIFICA_POS", params)
                resultado = {
                    "return_code": return_code_var.getvalue(),
                    "return_msg": return_msg_var.getvalue()
                }
                chunk_size = 100
                lines_var = cursor.arrayvar(str, chunk_size)
                num_lines_var = cursor.var(int)
                num_lines_var.setvalue(0, chunk_size)
                dbms_output_lines = []
                while True:
                    cursor.callproc("dbms_output.get_lines", [lines_var, num_lines_var])
                    num_retrieved = num_lines_var.getvalue()
                    lines = lines_var.getvalue()[:num_retrieved]
                    for line in lines:
                        if line:
                            dbms_output_lines.append(line.strip())
                    if num_retrieved < chunk_size:
                        break
                resultado["dbms_output"] = "\n".join(dbms_output_lines)
                return resultado
    except oracledb.DatabaseError as e:
        error_obj, = e.args
        raise Exception(f"Erro ao executar a procedure PRC_RENOTIFICA_POS: {error_obj.message.strip()}")

def get_history_client(cpf):
    # ... (código desta função não foi alterado)
    user, password, dsn = get_config()
    query = """
        SELECT entry_date, document, name, main_ph_num 
        FROM (
            SELECT * FROM ACC_SIEBEXTRACT_STG_CLIENT_POS 
            WHERE document = :cpf 
            ORDER BY entry_date DESC
        )
        WHERE ROWNUM <= 10
    """
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, cpf=cpf)
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
    except oracledb.DatabaseError as e:
        error, = e.args
        raise Exception(f"Erro ao buscar histórico do cliente: {error.message}")

def get_history_asset(gsm):
    # ... (código desta função não foi alterado)
    user, password, dsn = get_config()
    query = """
        SELECT entry_date, cpf, msisdn, customer_id, tipo_contrato, motivo_status, codigo_plano 
        FROM (
            SELECT * FROM ACC_SIEBEXTRACT_STG_ASSET_POS 
            WHERE msisdn = :gsm AND status <> 'Cancelado' 
            ORDER BY entry_date DESC
        )
        WHERE ROWNUM <= 10
    """
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, gsm=gsm)
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
    except oracledb.DatabaseError as e:
        error, = e.args
        raise Exception(f"Erro ao buscar histórico de assets: {error.message}")

def get_history_billing_profile(customer_id):
    # ... (código desta função não foi alterado)
    user, password, dsn = get_config()
    query = """
        SELECT entry_date, document, cust_code, tipo_fatura, dia_vencimento, metodo_pagamento, customer_adi 
        FROM (
            SELECT * FROM ACC_SIEBEXTRACT_STG_BP_POS 
            WHERE billing_profile_id = :customer_id 
            ORDER BY entry_date DESC
        )
        WHERE ROWNUM <= 10
    """
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, customer_id=customer_id)
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
    except oracledb.DatabaseError as e:
        error, = e.args
        raise Exception(f"Erro ao buscar histórico de faturamento: {error.message}")

# --- NOVA Função para buscar dados do IMDB ---
def get_imdb_data(gsm):
    """Faz uma requisição HTTP para a API do IMDB e retorna o JSON."""
    url = f"http://10.161.0.20:10010/profile/contract/full/{gsm}"
    try:
        # Timeout de 10 segundos para evitar que a aplicação congele indefinidamente
        response = requests.get(url, timeout=10)
        # Lança um erro para respostas como 404 ou 500
        response.raise_for_status()
        # Converte a resposta em um dicionário Python
        return response.json()
    except requests.exceptions.Timeout:
        raise Exception(f"Tempo de conexão esgotado ao tentar acessar a API do IMDB.")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"Erro HTTP ao acessar a API do IMDB: {e.response.status_code} {e.response.reason}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Erro de conexão com a API do IMDB: {e}")
    except json.JSONDecodeError:
        raise Exception("A resposta da API do IMDB não é um JSON válido.")