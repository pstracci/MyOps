# C:\Meus Projetos\MyOps\modules\pgu\pgu_logic.py

import oracledb
import configparser
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

# --- Funções do Sistema PGU ---
def search_profile(db_key, profile_id):
    user, password, dsn = get_config(db_key)
    query = """
        SELECT v.profile_id, v.description AS perfil, vfv.FEATURE_ID, vfv.description
        FROM VAR_FEATURE_PROFILE_VENDEDOR fpv
        JOIN VAR_PROFILE_VENDEDOR v ON fpv.var_prof_vend_prof_id = v.profile_id
        JOIN var_feature_vendedor vfv ON vfv.feature_id = fpv.VAR_FEAT_VEND_FEAT_ID
        WHERE v.status = 1 AND vfv.status = 1 AND v.profile_id = :profile_id
        ORDER BY v.description ASC
    """
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, profile_id=profile_id)
                return cursor.fetchall()
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro no banco de dados ao pesquisar perfil: {e.args[0].message}")

def execute_gerenciar_perfil(db_key, perfil, funcionalidades, acao, flg_sargento):
    user, password, dsn = get_config(db_key)
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.callproc("dbms_output.enable")
                cod_retorno = cursor.var(oracledb.NUMBER)
                msg_retorno = cursor.var(str, 255)
                cursor.callproc("GERENCIAR_PERFIL", [perfil, funcionalidades, acao, flg_sargento, cod_retorno, msg_retorno])
                resultado = {"cod_retorno": int(cod_retorno.getvalue() or 0), "msg_retorno": msg_retorno.getvalue()}
                lines_var = cursor.arrayvar(str, 100)
                num_lines_var = cursor.var(int, 100)
                dbms_output_lines = []
                while True:
                    cursor.callproc("dbms_output.get_lines", [lines_var, num_lines_var])
                    num_retrieved = num_lines_var.getvalue()
                    lines = lines_var.getvalue()[:num_retrieved]
                    for line in lines:
                        if line: dbms_output_lines.append(line.strip())
                    if num_retrieved < 100: break
                resultado["dbms_output"] = "\n".join(dbms_output_lines)
                return resultado
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro no banco de dados ao executar procedure de perfil: {e.args[0].message}")

def get_seller_details(db_key, identifier, search_type):
    """Busca todos os detalhes de um único vendedor e retorna como um dicionário."""
    user, password, dsn = get_config(db_key)
    query = "SELECT * FROM VAR_VENDEDOR WHERE "
    query += "UPPER(VENDOR_LOGIN) = UPPER(:identifier)" if search_type == 'login' else "VENDOR_ID = :identifier"
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, identifier=identifier)
                columns = [col[0] for col in cursor.description]
                row = cursor.fetchone()
                if row:
                    return dict(zip(columns, row))
                return None
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro no banco de dados ao pesquisar vendedor: {e.args[0].message}")

def check_cpf_blacklist(db_key, cpf):
    """Verifica se um CPF está na tabela de blacklist."""
    user, password, dsn = get_config(db_key)
    query = "SELECT 1 FROM VAR_CPF_BLACKLIST WHERE CPF = :cpf AND ROWNUM = 1"
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, cpf=cpf)
                return cursor.fetchone() is not None
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro no banco de dados ao checar blacklist: {e.args[0].message}")

def get_seller_pdvs(db_key, vendor_id):
    """Busca todos os PDVs associados a um vendedor."""
    user, password, dsn = get_config(db_key)
    query = """
        SELECT 
            A.VAR_VENDEDOR_VENDOR_ID AS CPF,
            A.VAR_PDV_PDV_ID AS PDV,
            B.NICKNAME,
            B.CLASSIFICATION,
            B.REGIONAL,
            B.OPERATOR,
            B.SEGMENT,
            B.FRAUD_RISK
        FROM VAR_VENDEDOR_PDV A, VAR_PDV B
        WHERE A.VAR_PDV_PDV_ID = B.CUST_CODE
        AND A.VAR_VENDEDOR_VENDOR_ID = :vendor_id
        ORDER BY PDV DESC
    """
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, vendor_id=vendor_id)
                return cursor.fetchall()
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro no banco de dados ao buscar PDVs: {e.args[0].message}")

def execute_delete_seller(db_key, vendor_login):
    user, password, dsn = get_config(db_key)
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.callproc("dbms_output.enable")
                cursor.callproc("deleta_usuario", [vendor_login])
                lines_var = cursor.arrayvar(str, 100)
                num_lines_var = cursor.var(int, 100)
                dbms_output_lines = []
                while True:
                    cursor.callproc("dbms_output.get_lines", [lines_var, num_lines_var])
                    num_retrieved = num_lines_var.getvalue()
                    lines = lines_var.getvalue()[:num_retrieved]
                    for line in lines:
                        if line: dbms_output_lines.append(line.strip())
                    if num_retrieved < 100: break
                return "\n".join(dbms_output_lines)
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro no banco de dados ao executar procedure de deleção: {e.args[0].message}")

# Funções do PdvManagerWidget (não modificadas)
def get_seller_info_for_pdv(db_key, identifier, search_type):
    user, password, dsn = get_config(db_key)
    query = "SELECT VENDOR_ID, NAME FROM VAR_VENDEDOR WHERE "
    query += "UPPER(VENDOR_LOGIN) = UPPER(:identifier)" if search_type == 'login' else "VENDOR_ID = :identifier"
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, identifier=identifier)
                return cursor.fetchone()
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar vendedor: {e.args[0].message}")

def get_assigned_pdvs(db_key, vendor_id):
    user, password, dsn = get_config(db_key)
    query = """
        SELECT vp.CUST_CODE, vp.NICKNAME
        FROM var_vendedor_pdv vvp
        JOIN var_pdv vp ON vvp.VAR_PDV_PDV_ID = vp.CUST_CODE
        WHERE vvp.VAR_VENDEDOR_VENDOR_ID = :vendor_id
        ORDER BY vp.NICKNAME ASC
    """
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, vendor_id=vendor_id)
                return cursor.fetchall()
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar PDVs atribuídos: {e.args[0].message}")

def get_all_available_pdvs(db_key):
    user, password, dsn = get_config(db_key)
    query = "SELECT CUST_CODE, NICKNAME FROM var_pdv ORDER BY NICKNAME ASC"
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchall()
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar todos os PDVs: {e.args[0].message}")

def apply_pdv_changes(db_key, vendor_id, final_pdv_codes):
    user, password, dsn = get_config(db_key)
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM var_vendedor_pdv WHERE VAR_VENDEDOR_VENDOR_ID = :vendor_id", [vendor_id])
                deleted_count = cursor.rowcount
                data_to_insert = [(vendor_id, code) for code in final_pdv_codes]
                inserted_count = 0
                if data_to_insert:
                    cursor.executemany("INSERT INTO var_vendedor_pdv (VAR_VENDEDOR_VENDOR_ID, VAR_PDV_PDV_ID) VALUES (:1, :2)", data_to_insert)
                    inserted_count = cursor.rowcount
                connection.commit()
                return f"Mudanças aplicadas com sucesso!\n- {deleted_count} associação(ões) removida(s).\n- {inserted_count} associação(ões) adicionada(s)."
    except oracledb.DatabaseError as e:
        if 'connection' in locals() and connection.is_healthy():
            connection.rollback()
        raise Exception(f"Erro ao aplicar mudanças de PDV: {e.args[0].message}")