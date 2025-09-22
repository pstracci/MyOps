# C:\Meus Projetos\fixer\modules\siebel\siebel_logic.py

import oracledb
import configparser

import configparser
from modules.common import security # Adicionar este import no topo do arquivo

def get_config(section='database_siebel'): # <-- Valor padrão adicionado
    """Lê a seção do Siebel Pós-Pago do arquivo config.ini e descriptografa a senha."""
    config = configparser.ConfigParser()
    config.read('config.ini')
    if section in config:
        user = config[section].get('user', '')
        encrypted_password = config[section].get('password', '')
        dsn = config[section].get('dsn', '')

        # Descriptografa a senha antes de retornar
        password = security.decrypt_password(encrypted_password)
        
        return user, password, dsn
        
    raise ConnectionError(f"Seção '{section}' não encontrada no 'config.ini'.")

def get_active_sessions():
    """Busca sessões de usuário, incluindo o início da execução, grau de paralelismo e filtrando sessões escravas."""
    user, password, dsn = get_config()
    query = """
        SELECT
            s.inst_id,
            s.sid,
            s.serial#,
            s.username,
            s.status,
            s.osuser,
            s.machine,
            s.program,
            s.logon_time,
            s.sql_address,
            s.sql_hash_value,
            s.prev_sql_addr as prev_sql_address,
            s.prev_hash_value,
            s.sql_exec_start,
            px.degree as parallel_degree
        FROM
            gv$session s
        LEFT JOIN
            gv$px_session px ON (s.sid = px.qcsid AND s.serial# = px.qcserial# AND s.inst_id = px.inst_id)
        WHERE
            s.type = 'USER'
            AND s.username IS NOT NULL
            -- NOVO FILTRO: Exclui as sessões que são "escravas" de queries paralelas.
            -- Uma sessão escrava (px) tem seu SID listado na gv$px_session.
            -- Um coordenador (qcsid) não é listado como um escravo.
            AND s.sid NOT IN (SELECT sid FROM gv$px_session WHERE sid IS NOT NULL AND qcinst_id IS NOT NULL)
        ORDER BY
            s.machine, s.logon_time
    """
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                columns = [desc[0].lower() for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar sessões ativas: {e.args[0].message}")

def get_sql_text(inst_id, sql_address, sql_hash_value, prev_sql_address, prev_hash_value):
    """Busca o sql_fulltext de uma sessão, tentando o SQL atual e depois o anterior."""
    addr_to_use = sql_address if sql_hash_value != 0 else prev_sql_address
    hash_to_use = sql_hash_value if sql_hash_value != 0 else prev_hash_value

    if not addr_to_use or hash_to_use == 0:
        return "-- Nenhum SQL ativo ou recente para esta sessão --"

    user, password, dsn = get_config()
    query = "SELECT sql_fulltext FROM gv$sql WHERE address = :addr AND hash_value = :hash AND inst_id = :inst"
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, addr=addr_to_use, hash=hash_to_use, inst=inst_id)
                result = cursor.fetchone()
                if result and hasattr(result[0], 'read'):
                    return result[0].read()
                return "-- Texto do SQL não encontrado no cache --"
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar texto do SQL: {e.args[0].message}")

def kill_session(sid, serial):
    """Chama a procedure para encerrar uma sessão específica."""
    user, password, dsn = get_config()
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.callproc("SYS.PRC_KILL_SESSION", [str(sid), str(serial)])
                return f"Comando para encerrar a sessão SID={sid}, SERIAL#={serial} foi enviado com sucesso."
    except oracledb.DatabaseError as e:
        error, = e.args
        raise Exception(f"Erro ao executar PRC_KILL_SESSION: {error.message}")