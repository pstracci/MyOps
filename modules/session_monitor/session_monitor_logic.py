# C:\Meus Projetos\MyOps\modules\session_monitor\session_monitor_logic.py

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
        dsn = config[section].get('dsn', '')
        password = security.decrypt_password(encrypted_password)
        return user, password, dsn
    raise ConnectionError(f"Seção '{section}' não encontrada no 'config.ini'.")

def get_all_db_connections():
    """Lê o config.ini e retorna um dicionário de conexões de banco de dados."""
    config = configparser.ConfigParser()
    config.read('config.ini')
    db_connections = {}
    for section in config.sections():
        if section.startswith('database_'):
            friendly_name = section.replace('database_', '').replace('_', ' ').title()
            db_connections[section] = friendly_name
    return db_connections

def get_active_sessions(db_key):
    """Busca sessões, incluindo SQL_ID para o plano e filtrando sessões paralelas escravas."""
    user, password, dsn = get_config(db_key)
    query = """
        SELECT
            s.inst_id, s.sid, s.serial#, s.username, s.status, s.osuser,
            s.machine, s.program, s.logon_time, s.sql_address, s.sql_hash_value,
            s.prev_sql_addr as prev_sql_address, s.prev_hash_value,
            s.sql_exec_start, px.degree as parallel_degree,
            s.sql_id, s.sql_child_number, s.prev_sql_id
        FROM
            gv$session s
        LEFT JOIN
            gv$px_session px ON (s.sid = px.qcsid AND s.serial# = px.qcserial# AND s.inst_id = px.inst_id)
        WHERE
            s.type = 'USER' AND s.username IS NOT NULL
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

def get_sql_text(db_key, inst_id, sql_address, sql_hash_value, prev_sql_address, prev_hash_value):
    """Busca o sql_fulltext de uma sessão, tentando o SQL atual e depois o anterior."""
    addr_to_use = sql_address if sql_hash_value != 0 else prev_sql_address
    hash_to_use = sql_hash_value if sql_hash_value != 0 else prev_hash_value
    if not addr_to_use or hash_to_use == 0:
        return "-- Nenhum SQL ativo ou recente para esta sessão --"
    user, password, dsn = get_config(db_key)
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

def get_execution_plan(db_key, sql_id, child_number, prev_sql_id, plan_format='TYPICAL'):
    """Busca o plano de execução de uma query usando DBMS_XPLAN."""
    sql_id_to_use = sql_id or prev_sql_id
    child_to_use = child_number if sql_id else 0

    if not sql_id_to_use:
        return "-- SQL ID não disponível para gerar o plano de execução --"

    user, password, dsn = get_config(db_key)
    query = "SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(:sql_id, :child, :format))"
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, sql_id=sql_id_to_use, child=child_to_use, format=plan_format)
                plan_rows = cursor.fetchall()
                return "\n".join([row[0].rstrip() for row in plan_rows])
    except oracledb.DatabaseError as e:
        return f"-- Erro ao buscar plano de execução --\n{e.args[0].message}"

def kill_session(db_key, sid, serial):
    """Chama a procedure para encerrar uma sessão específica."""
    user, password, dsn = get_config(db_key)
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.callproc("SYS.PRC_KILL_SESSION", [str(sid), str(serial)])
                return f"Comando para encerrar a sessão SID={sid}, SERIAL#={serial} foi enviado com sucesso."
    except oracledb.DatabaseError as e:
        error, = e.args
        raise Exception(f"Erro ao executar PRC_KILL_SESSION: {error.message}")

def get_single_session_details(db_key, inst_id, sid, serial):
    """Busca os detalhes completos de uma única sessão."""
    user, password, dsn = get_config(db_key)
    query = """
        SELECT
            s.inst_id, s.sid, s.serial#, s.username, s.status, s.osuser,
            s.machine, s.program, s.logon_time, s.sql_address, s.sql_hash_value,
            s.prev_sql_addr as prev_sql_address, s.prev_hash_value,
            s.sql_exec_start, px.degree as parallel_degree,
            s.sql_id, s.sql_child_number, s.prev_sql_id
        FROM
            gv$session s
        LEFT JOIN
            gv$px_session px ON (s.sid = px.qcsid AND s.serial# = px.qcserial# AND s.inst_id = px.inst_id)
        WHERE
            s.sid = :sid AND s.serial# = :serial AND s.inst_id = :inst_id
    """
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, sid=sid, serial=serial, inst_id=inst_id)
                columns = [desc[0].lower() for desc in cursor.description]
                row = cursor.fetchone()
                return dict(zip(columns, row)) if row else None
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar detalhes da sessão: {e.args[0].message}")

def get_long_ops_for_session(db_key, inst_id, sid, serial):
    """Busca o progresso de operações longas para uma sessão específica."""
    user, password, dsn = get_config(db_key)
    query = """
        SELECT
            opname,
            target,
            sofar,
            totalwork,
            units,
            start_time,
            last_update_time,
            elapsed_seconds,
            time_remaining
        FROM
            gv$session_longops
        WHERE
            inst_id = :inst_id
            AND sid = :sid
            AND serial# = :serial
            AND totalwork > 0
            AND sofar != totalwork
        ORDER BY
            start_time DESC
    """
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, inst_id=inst_id, sid=sid, serial=serial)
                columns = [desc[0].lower() for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar long ops: {e.args[0].message}")

def get_session_wait_events(db_key, inst_id, sid):
    """Busca os eventos de espera para uma sessão específica, ordenados por tempo."""
    user, password, dsn = get_config(db_key)
    query = """
        SELECT
            event,
            wait_class,
            total_waits,
            time_waited_micro
        FROM
            gv$session_event
        WHERE
            sid = :sid
            AND inst_id = :inst_id
            AND wait_class != 'Idle'
        ORDER BY
            time_waited_micro DESC
    """
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, sid=sid, inst_id=inst_id)
                columns = [desc[0].lower() for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar eventos de espera: {e.args[0].message}")

# --- NOVA FUNÇÃO ---
def get_session_time_model(db_key, inst_id, sid):
    """Busca as estatísticas de tempo do modelo de tempo da sessão, incluindo DB CPU."""
    user, password, dsn = get_config(db_key)
    # A view gv$sess_time_model fornece estatísticas detalhadas sobre onde a sessão
    # gastou seu tempo, incluindo o tempo de CPU. O valor é em microssegundos.
    query = """
        SELECT
            stat_name,
            value
        FROM
            gv$sess_time_model
        WHERE
            sid = :sid
            AND inst_id = :inst_id
            AND stat_name IN ('DB CPU', 'DB time')
    """
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, sid=sid, inst_id=inst_id)
                return {row[0]: row[1] for row in cursor.fetchall()}
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar o time model da sessão: {e.args[0].message}")