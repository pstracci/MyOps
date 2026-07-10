# C:\Meus Projetos\MyOps\modules\contestacao\contestacao_logic.py

import oracledb
from modules.common.security import decrypt_password
import configparser
from datetime import datetime, timedelta
import subprocess
import os
import tempfile
import time
import sys
import re

# Mapa de fallback para o status das linhas de ajuste (Conta Certa), usado caso o
# comentário da coluna em all_col_comments não esteja disponível ou não seja parseável.
_ADJUST_STATUS_FALLBACK = {
    1: 'Processado', 2: 'Em processamento', 3: 'Em processamento',
    4: 'Erro no processamento', 5: 'Erro de envio', 6: 'Erro de alçada',
    7: 'Solicitação cancelada', 8: 'Processamento cancelado',
    9: 'Cancelado usuário', 10: 'Não elegível',
}


def _parse_status_comment(comment):
    """Extrai um mapa {numero: descrição} a partir do texto de um comentário de coluna
    (all_col_comments). Aceita separadores '-', ':' ou '=' e delimitadores ',', ';' ou
    quebra de linha. Ex.: "1-Processado, 2-Em processamento, 9-Cancelado usuário"."""
    if not comment:
        return {}
    mapping = {}
    for num, desc in re.findall(r'(\d+)\s*[-=:]\s*([^,;\n]+)', str(comment)):
        desc = desc.strip().rstrip('.').strip()
        if desc:
            mapping[int(num)] = desc
    return mapping


def get_column_status_map(cursor, table_name, column_name):
    """Lê o comentário de uma coluna em all_col_comments e devolve {numero: descrição}.
    Usa o cursor de uma conexão já aberta. Retorna {} se nada for encontrado/parseável."""
    try:
        cursor.execute(
            """
            SELECT comments FROM all_col_comments
            WHERE table_name = :t AND column_name = :c AND comments IS NOT NULL
            ORDER BY owner
            """,
            t=table_name.upper(), c=column_name.upper(),
        )
        for row in cursor.fetchall():
            parsed = _parse_status_comment(row[0])
            if parsed:
                return parsed
    except oracledb.DatabaseError:
        pass
    return {}

# ... (funções existentes, do get_config até get_adjust_details, permanecem inalteradas) ...
def get_config(db_key):
    config = configparser.ConfigParser()
    config.read('config.ini')
    if db_key in config:
        user = config[db_key].get('user', '')
        encrypted_password = config[db_key].get('password', '')
        dsn = config[db_key].get('dsn', '')
        password = decrypt_password(encrypted_password)
        return user, password, dsn
    raise ConnectionError(f"Seção '{db_key}' não encontrada no 'config.ini'.")

def search_contestacoes(db_key, sr=None, msisdn=None, start_date=None, end_date=None, status=None, invoicenumber=None, customerid=None):
    user, password, dsn = get_config(db_key)
    params = {}
    base_query = "SELECT id_, sr, msisdn, invoicenumber, customerid, TO_CHAR(createdate, 'YYYY-MM-DD HH24:MI:SS') as createdate, statusname FROM scc_invoicerequest WHERE 1=1"
    if sr:
        base_query += " AND sr = :sr"
        params['sr'] = sr
    if msisdn:
        base_query += " AND msisdn = :msisdn"
        params['msisdn'] = msisdn
    if invoicenumber:
        base_query += " AND invoicenumber = :invoicenumber"
        params['invoicenumber'] = invoicenumber
    if customerid:
        base_query += " AND customerid = :customerid"
        params['customerid'] = customerid
    if status:
        base_query += " AND statusname = :status"
        params['status'] = status
    if start_date:
        base_query += " AND modifieddate >= :start_date"
        params['start_date'] = start_date
    if end_date:
        end_date_inclusive = end_date + timedelta(days=1)
        base_query += " AND modifieddate < :end_date"
        params['end_date'] = end_date_inclusive
    query = f"SELECT * FROM ( {base_query} ORDER BY createdate DESC ) WHERE ROWNUM <= 100"
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                columns = [desc[0].lower() for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar contestações: {e.args[0].message}")

def search_interfaces(db_key, status=None, hours=None):
    user, password, dsn = get_config(db_key)
    params = {}
    status_map = {"Sucesso": 1, "Nao enviado": 2, "Aguardando Retorno": 3, "Erro Permanente": 4, "Envio Cancelado": 5, "Erro Temporario": 6}
    query = "SELECT /*+ parallel(4) */ a.id_, TO_CHAR(a.createdate, 'YYYY-MM-DD HH24:MI:SS') as createdate, TO_CHAR(a.senddate, 'YYYY-MM-DD HH24:MI:SS') as senddate, a.errordescription, DECODE(a.status, 1, 'Sucesso', 2, 'Nao enviado', 3, 'Aguardando Retorno', 4, 'Erro Permanente', 5, 'Envio Cancelado', 6, 'Erro Temporario', 0, 'Nao enviado') desc_status, DECODE(a.type_, 1, 'RMCA', 2, 'OCC de Crédito', 3, 'OCC de Débito', 4, 'Recibo de Arrecadação', 5, 'Devolução em Conta Corrente') type_desc FROM scc_invoiceinterface a WHERE 1=1"
    if status and status != "Todos":
        if status == "Nao enviado":
            query += " AND a.status IN (0, 2)"
        else:
            status_code = status_map.get(status)
            if status_code is not None:
                query += " AND a.status = :status_code"
                params['status_code'] = status_code
    if hours and hours > 0:
        query += " AND a.createdate >= SYSDATE - (:hours / 24)"
        params['hours'] = hours
    query += " ORDER BY a.createdate DESC"
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                columns = [desc[0].lower() for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar interfaces: {e.args[0].message}")

def get_request_details(db_key, request_id):
    user, password, dsn = get_config(db_key)
    details = {}
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                query = "SELECT r.id_, r.sr, r.msisdn, r.invoicenumber, r.customerid, TO_CHAR(r.createdate, 'YYYY-MM-DD HH24:MI:SS') as createdate, r.statusname, u.login as user_login FROM scc_invoicerequest r LEFT JOIN scc_user u ON r.userid = u.id_ WHERE r.id_ = :id"
                cursor.execute(query, id=request_id)
                columns = [desc[0].lower() for desc in cursor.description]
                request_data = cursor.fetchone()
                if not request_data: return None
                details['request'] = dict(zip(columns, request_data))
                query_audit = "SELECT TO_CHAR(modifieddate, 'YYYY-MM-DD HH24:MI:SS') as modifieddate, statusname FROM scc_invoicerequest_audit WHERE id_ = :id ORDER BY modifieddate DESC"
                cursor.execute(query_audit, id=request_id)
                columns_audit = [desc[0].lower() for desc in cursor.description]
                details['history'] = [dict(zip(columns_audit, row)) for row in cursor.fetchall()]
            return details
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar detalhes da requisição: {e.args[0].message}")

def get_analysis_details(db_key, sr):
    user, password, dsn = get_config(db_key)
    analysis_details = {}
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            subquery_request_id = "SELECT id_ FROM scc_invoicerequest WHERE sr = :sr"
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT * FROM scc_invoiceanalysis WHERE invoicerequestid IN ({subquery_request_id})", sr=sr)
                columns = [desc[0].lower() for desc in cursor.description]
                analysis_summary = cursor.fetchone()
                if analysis_summary:
                    analysis_id = analysis_summary[columns.index('id_')]
                    analysis_details['analysis_summary'] = dict(zip(columns, analysis_summary))
                    cursor.execute("SELECT l.*, r.name_ as reason_name FROM scc_invoiceanalysisline l LEFT JOIN scc_reason r ON l.reasonid = r.id_ WHERE l.invoiceanalysisid = :id", id=analysis_id)
                    line_columns = [desc[0].lower() for desc in cursor.description]
                    analysis_details['analysis_lines'] = [dict(zip(line_columns, row)) for row in cursor.fetchall()]
            return analysis_details
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar detalhes da análise: {e.args[0].message}")

def get_interface_details(db_key, sr):
    user, password, dsn = get_config(db_key)
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                query = "SELECT a.*, TO_CHAR(a.senddate, 'YYYY-MM-DD HH24:MI:SS') as senddate, DECODE (a.status, 1, 'Sucesso', 2, 'Nao enviado', 3, 'Aguardando Retorno', 4, 'Erro Permanente', 5, 'Envio Cancelado', 6, 'Erro Temporario', 0, 'Nao enviado') desc_status, DECODE (a.type_, 1, 'RMCA', 2, 'OCC de Crédito', 3, 'OCC de Débito', 4, 'Recibo de Arrecadação', 5, 'Devolução em Conta Corrente') type_desc FROM scc_invoiceinterface a WHERE a.invoiceanalysisid IN (SELECT id_ FROM scc_invoiceanalysis WHERE invoicerequestid IN (SELECT id_ FROM scc_invoicerequest WHERE sr = :sr))"
                cursor.execute(query, sr=sr)
                columns = [desc[0].lower() for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar detalhes de interface: {e.args[0].message}")

def get_adjust_details(db_key, sr):
    user, password, dsn = get_config(db_key)
    adjust_details = {}
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                query_adjust = "SELECT a.*, DECODE (a.status, 1, 'Processado', 2, 'Em processamento', 3, 'Em processamento', 4, 'Erro no processamento', 5, 'Erro de envio', 6, 'Erro de alçada', 7, 'Solicitação cancelada', 8, 'Processamento cancelado', 9, 'Cancelado usuário', 10, 'Não elegível') as desc_status FROM scc_invoiceadjust a WHERE a.invoicerequestid IN (SELECT id_ FROM scc_invoicerequest WHERE sr = :sr)"
                cursor.execute(query_adjust, sr=sr)
                columns = [desc[0].lower() for desc in cursor.description]
                adjust_summary = cursor.fetchone()
                if adjust_summary:
                    adjust_details['adjust_summary'] = dict(zip(columns, adjust_summary))
                    adjust_id = adjust_summary[columns.index('id_')]
                    query_adjust_line = "SELECT * FROM scc_invoiceadjustline WHERE invoiceadjustid = :id"
                    cursor.execute(query_adjust_line, id=adjust_id)
                    line_columns = [desc[0].lower() for desc in cursor.description]
                    adjust_lines = [dict(zip(line_columns, row)) for row in cursor.fetchall()]
                    # Resolve a descrição do status da linha a partir do comentário da coluna
                    # (all_col_comments) da tabela SCC_INVOICEADJUSTLINE; usa fallback se vazio.
                    line_status_map = get_column_status_map(
                        cursor, 'SCC_INVOICEADJUSTLINE', 'STATUS'
                    ) or _ADJUST_STATUS_FALLBACK
                    for line in adjust_lines:
                        raw_status = line.get('status')
                        try:
                            status_int = int(raw_status) if raw_status is not None else None
                        except (TypeError, ValueError):
                            status_int = None
                        line['desc_status'] = line_status_map.get(status_int, '')
                    adjust_details['adjust_lines'] = adjust_lines
            return adjust_details
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar detalhes do ajuste: {e.args[0].message}")

def get_contestation_analysis_details(db_key, sr):
    user, password, dsn = get_config(db_key)
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                query = "SELECT INVOICEANALYSISID AS ID_ANALISE, CONTESTATIONVALUE AS Valor_da_Contestacao, ANALYSISVALUE AS Valor_sob_analise, argument as justificativa, LINESTATUSNAME as Status_da_Analise FROM scc_invoiceanalysisline WHERE INVOICEANALYSISID IN (SELECT id_ FROM scc_invoiceanalysis WHERE invoicerequestid IN (SELECT id_ FROM scc_invoicerequest WHERE sr = :sr))"
                cursor.execute(query, sr=sr)
                columns = [desc[0].lower() for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar detalhes da análise da contestação: {e.args[0].message}")

# --- NOVA FUNÇÃO ADICIONADA AQUI ---
def get_contested_invoice_details(db_key, invoicenumber):
    """Busca os itens detalhados de uma fatura contestada."""
    user, password, dsn = get_config(db_key)
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                query = """
                    SELECT 
                        INVOICENUMBER,
                        CUSTOMERID,
                        BILLNUMBER,
                        PAGENUMBER,
                        DESCRIPTION AS ITEM_FATURA,
                        AMOUNT,
                        VALUE AS valor,
                        SHDES AS servico_bscs,
                        ACCOUNTNUMBER AS conta_contabil,
                        LINEGROUP AS seção_De_Fatura
                    FROM scc_invoiceline
                    WHERE INVOICEID IN (
                        SELECT id_
                        FROM scc_invoice
                        WHERE invoicenumber = :invoicenumber AND status = 1
                    )
                    ORDER BY DESCRIPTION DESC
                """
                cursor.execute(query, invoicenumber=invoicenumber)
                columns = [desc[0].lower() for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar itens da fatura contestada: {e.args[0].message}")


def get_alcada_profile_limits(db_key, profile_id):
    """Busca os limites de alçada definidos para o perfil sistêmico em SCC_COMPETENCEBYPROFILE.
    Inclui o teto por contestação (COMPETENCE_MAX_BY_ANALYSIS) e demais alçadas (crédito de
    relacionamento, rede, ressarcimento, bolsões etc.). Filtra por profileid (indexado)."""
    if not profile_id:
        return []
    user, password, dsn = get_config(db_key)
    query = """
        SELECT
            id_,
            code,
            name_,
            customertypeid,
            value,
            TO_CHAR(createdate,   'YYYY-MM-DD HH24:MI:SS') AS createdate,
            TO_CHAR(modifieddate, 'YYYY-MM-DD HH24:MI:SS') AS modifieddate,
            status
        FROM scc_competencebyprofile
        WHERE profileid = :profile_id
        ORDER BY code, customertypeid
    """
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, profile_id=profile_id)
                columns = [desc[0].lower() for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar limites do perfil: {e.args[0].message}")


def get_alcada_audit_history(db_key, balance_id, request_date=None, max_rows=200):
    """Retorna o histórico de auditoria de um saldo de competência específico.
    O filtro por id_ é obrigatório para usar o índice da tabela scc_competencebalance_audit.
    Se request_date for informado, traz apenas revisões com modifieddate <= request_date + 1 dia
    (visão da contestação) para reduzir varredura. Limitado a max_rows."""
    if not balance_id:
        return []
    user, password, dsn = get_config(db_key)
    params = {'balance_id': balance_id, 'max_rows': max_rows}
    extra = ""
    if request_date:
        extra = " AND a.modifieddate <= TO_DATE(:cutoff, 'YYYY-MM-DD HH24:MI:SS') + 1"
        params['cutoff'] = request_date
    query = f"""
        SELECT * FROM (
            SELECT
                a.id_,
                a.rev,
                a.revtype,
                a.code,
                a.balance,
                a.startbalance,
                TO_CHAR(a.startvalidity,  'YYYY-MM-DD HH24:MI:SS') AS startvalidity,
                TO_CHAR(a.finishvalidity, 'YYYY-MM-DD HH24:MI:SS') AS finishvalidity,
                TO_CHAR(a.createdate,     'YYYY-MM-DD HH24:MI:SS') AS createdate,
                TO_CHAR(a.modifieddate,   'YYYY-MM-DD HH24:MI:SS') AS modifieddate
            FROM scc_competencebalance_audit a
            WHERE a.id_ = :balance_id{extra}
            ORDER BY a.rev DESC
        ) WHERE ROWNUM <= :max_rows
    """
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                columns = [desc[0].lower() for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar auditoria do saldo: {e.args[0].message}")


def get_alcada_details(db_key, sr):
    """Análise RETROATIVA de alçada: para o usuário que tratou a contestação, resolve o
    perfil sistêmico que estava vigente NA DATA da contestação (via scc_user_audit, filtro
    indexado por id_), e usa esse profile_id histórico para consultar SCC_COMPETENCEBYPROFILE.
    Também retorna o perfil atual, a timeline de mudanças e o saldo de competência vigente."""
    user, password, dsn = get_config(db_key)
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT u.id_      AS user_id,
                           u.login    AS user_login,
                           u.firstname || ' ' || u.lastname AS user_name,
                           u.profileid AS current_profile_id,
                           r.createdate AS request_date_dt,
                           TO_CHAR(r.createdate, 'YYYY-MM-DD HH24:MI:SS') AS request_date
                    FROM scc_invoicerequest r
                    LEFT JOIN scc_user u ON r.userid = u.id_
                    WHERE r.sr = :sr
                    """,
                    sr=sr,
                )
                base_row = cursor.fetchone()
                if not base_row:
                    return {
                        'user': None, 'balances': [], 'profile_limits': [],
                        'contestation_value': None, 'profile_history': [],
                    }
                base_cols = [d[0].lower() for d in cursor.description]
                base = dict(zip(base_cols, base_row))
                user_id = base.get('user_id')
                request_date_dt = base.get('request_date_dt')
                current_profile_id = base.get('current_profile_id')

                historical_profile_id = current_profile_id
                historical_profile_source = "perfil atual (sem registro anterior em scc_user_audit)"
                historical_modifieddate = None
                historical_rev = None
                if user_id and request_date_dt is not None:
                    cursor.execute(
                        """
                        SELECT * FROM (
                            SELECT rev, revtype, profileid,
                                   TO_CHAR(modifieddate, 'YYYY-MM-DD HH24:MI:SS') AS modifieddate
                            FROM scc_user_audit
                            WHERE id_ = :user_id
                              AND modifieddate <= :request_date_dt
                            ORDER BY rev DESC
                        ) WHERE ROWNUM = 1
                        """,
                        user_id=user_id, request_date_dt=request_date_dt,
                    )
                    h_row = cursor.fetchone()
                    if h_row:
                        h_cols = [d[0].lower() for d in cursor.description]
                        h = dict(zip(h_cols, h_row))
                        historical_profile_id = h.get('profileid')
                        historical_rev = h.get('rev')
                        historical_modifieddate = h.get('modifieddate')
                        historical_profile_source = (
                            f"scc_user_audit rev={historical_rev}, "
                            f"modifieddate={historical_modifieddate}"
                        )

                profiles_map = {}
                profile_ids_to_resolve = {pid for pid in (historical_profile_id, current_profile_id) if pid is not None}
                if profile_ids_to_resolve:
                    placeholders = ", ".join(f":p{i}" for i in range(len(profile_ids_to_resolve)))
                    binds = {f"p{i}": pid for i, pid in enumerate(profile_ids_to_resolve)}
                    cursor.execute(
                        f"SELECT id_, code, name_ FROM scc_profile WHERE id_ IN ({placeholders})",
                        binds,
                    )
                    for r in cursor.fetchall():
                        profiles_map[r[0]] = {'code': r[1], 'name': r[2]}

                def _profile_attr(pid, key):
                    info = profiles_map.get(pid)
                    return info.get(key) if info else None

                user_info = {
                    'user_id':        user_id,
                    'user_login':     base.get('user_login'),
                    'user_name':      base.get('user_name'),
                    'request_date':   base.get('request_date'),
                    'profile_id':     historical_profile_id,
                    'profile_code':   _profile_attr(historical_profile_id, 'code'),
                    'profile_name':   _profile_attr(historical_profile_id, 'name'),
                    'profile_source': historical_profile_source,
                    'profile_rev':    historical_rev,
                    'profile_modifieddate': historical_modifieddate,
                    'current_profile_id':   current_profile_id,
                    'current_profile_code': _profile_attr(current_profile_id, 'code'),
                    'current_profile_name': _profile_attr(current_profile_id, 'name'),
                    'profile_changed': (current_profile_id is not None
                                        and historical_profile_id is not None
                                        and current_profile_id != historical_profile_id),
                }

                balances = []
                if user_id and request_date_dt is not None:
                    cursor.execute(
                        """
                        SELECT cb.id_     AS balance_id,
                               cb.code    AS balance_code,
                               cb.balance AS balance_atual,
                               cb.startbalance AS alcada_periodo,
                               TO_CHAR(cb.startvalidity,  'YYYY-MM-DD HH24:MI:SS') AS startvalidity,
                               TO_CHAR(cb.finishvalidity, 'YYYY-MM-DD HH24:MI:SS') AS finishvalidity,
                               cb.status  AS balance_status
                        FROM scc_competencebalance cb
                        WHERE cb.userid = :user_id
                          AND :request_date_dt BETWEEN cb.startvalidity AND cb.finishvalidity
                        ORDER BY cb.code
                        """,
                        user_id=user_id, request_date_dt=request_date_dt,
                    )
                    bcols = [d[0].lower() for d in cursor.description]
                    balances = [dict(zip(bcols, r)) for r in cursor.fetchall()]

                profile_limits = []
                if historical_profile_id is not None:
                    cursor.execute(
                        """
                        SELECT id_, code, name_, customertypeid, value,
                               TO_CHAR(modifieddate, 'YYYY-MM-DD HH24:MI:SS') AS modifieddate,
                               status
                        FROM scc_competencebyprofile
                        WHERE profileid = :profile_id
                        ORDER BY code, customertypeid
                        """,
                        profile_id=historical_profile_id,
                    )
                    pcols = [d[0].lower() for d in cursor.description]
                    profile_limits = [dict(zip(pcols, r)) for r in cursor.fetchall()]

                contestation_value = None
                try:
                    cursor.execute(
                        """
                        SELECT SUM(NVL(CONTESTATIONVALUE, 0)) AS total_contestado,
                               SUM(NVL(ANALYSISVALUE, 0))      AS total_procedente
                        FROM scc_invoiceanalysisline
                        WHERE INVOICEANALYSISID IN (
                            SELECT id_ FROM scc_invoiceanalysis
                            WHERE invoicerequestid IN (
                                SELECT id_ FROM scc_invoicerequest WHERE sr = :sr
                            )
                        )
                        """,
                        sr=sr,
                    )
                    cv_row = cursor.fetchone()
                    if cv_row:
                        contestation_value = {
                            'total_contestado': cv_row[0],
                            'total_procedente': cv_row[1],
                        }
                except oracledb.DatabaseError:
                    contestation_value = None

                profile_history = []
                if user_id:
                    cursor.execute(
                        """
                        SELECT rev, revtype, profileid,
                               TO_CHAR(modifieddate, 'YYYY-MM-DD HH24:MI:SS') AS modifieddate
                        FROM scc_user_audit
                        WHERE id_ = :user_id
                        ORDER BY modifieddate ASC, rev ASC
                        """,
                        user_id=user_id,
                    )
                    hist_cols = [d[0].lower() for d in cursor.description]
                    history_rows = [dict(zip(hist_cols, r)) for r in cursor.fetchall()]
                    hist_pids = {r.get('profileid') for r in history_rows if r.get('profileid') is not None}
                    pending = hist_pids - set(profiles_map.keys())
                    if pending:
                        placeholders = ", ".join(f":p{i}" for i in range(len(pending)))
                        binds = {f"p{i}": pid for i, pid in enumerate(pending)}
                        cursor.execute(
                            f"SELECT id_, code, name_ FROM scc_profile WHERE id_ IN ({placeholders})",
                            binds,
                        )
                        for r in cursor.fetchall():
                            profiles_map[r[0]] = {'code': r[1], 'name': r[2]}
                    for r in history_rows:
                        pid = r.get('profileid')
                        info = profiles_map.get(pid) or {}
                        r['profile_code'] = info.get('code')
                        r['profile_name'] = info.get('name')
                    profile_history = history_rows

                return {
                    'user':               user_info,
                    'balances':           balances,
                    'profile_limits':     profile_limits,
                    'contestation_value': contestation_value,
                    'profile_history':    profile_history,
                }
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar dados de alçada: {e.args[0].message}")


def descartar_contestacao(db_key, sr):
    user, password, dsn = get_config(db_key)
    query = "UPDATE scc_invoicerequest SET status = 6, statusname = 'Descartada', modifieddate = SYSDATE WHERE sr = :sr"
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, sr=sr)
                connection.commit()
                return f"Contestação SR {sr} descartada com sucesso." if cursor.rowcount > 0 else f"Nenhuma contestação encontrada com a SR {sr}."
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao descartar contestação: {e.args[0].message}")

def _run_remote_command_with_temp_script(host_alias, remote_command):
    temp_log_fd, temp_log_path = tempfile.mkstemp(text=True, suffix='.log')
    os.close(temp_log_fd)
    temp_bat_fd, temp_bat_path = tempfile.mkstemp(text=True, suffix='.bat')
    ssh_command_line = f'ssh -T {host_alias} "{remote_command}" > "{temp_log_path}"'
    batch_script_content = f'''
@echo off
echo Conectando a {host_alias} para buscar o log...
echo Por favor, autentique-se se necessario.
echo Esta janela fechará automaticamente ao concluir.
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
            return (False, "Erro: Esta funcionalidade só é compatível com Windows.")
        command_to_execute = ['cmd.exe', '/c', 'start', f"Busca de Log em {host_alias}", '/wait', temp_bat_path]
        process = subprocess.run(command_to_execute, timeout=300)
        time.sleep(1)
        with open(temp_log_path, 'r', encoding='utf-8', errors='replace') as log_file:
            output = log_file.read()
        return (True, output)
    except subprocess.TimeoutExpired:
        return (False, "Erro: A busca do log demorou mais de 5 minutos (Timeout).")
    except Exception as e:
        return (False, f"Erro ao executar o script temporário: {e}")
    finally:
        if os.path.exists(temp_log_path): os.remove(temp_log_path)
        if os.path.exists(temp_bat_path): os.remove(temp_bat_path)

def fetch_remote_log(sr, msisdn, invoicenumber):
    config = configparser.ConfigParser()
    config.read('config.ini')
    host_alias = config.get('ssh_connections', 'contestacao_host', fallback=None)
    if not host_alias:
        raise ConnectionError("O alias do host SSH ('contestacao_host') não foi encontrado na seção [ssh_connections] do config.ini.")
    remote_script_path = "/appl/scc/sccprod1/pstracci/pesquisa_log.sh"
    if not invoicenumber:
        raise ValueError("O número da fatura é obrigatório para a busca do log, mas não foi encontrado.")
    identifier = invoicenumber
    command_to_run_remotely = f"{remote_script_path} {identifier} 15"
    success, output = _run_remote_command_with_temp_script(host_alias, command_to_run_remotely)
    if not success:
        raise Exception(output)
    return output