# C:\Meus Projetos\MyOps\modules\contestacao\contestacao_logic.py

import oracledb
from modules.common.security import decrypt_password
import configparser
from datetime import datetime, timedelta

def get_config(db_key):
    """Lê uma seção específica do arquivo config.ini."""
    config = configparser.ConfigParser()
    config.read('config.ini')
    if db_key in config:
        user = config[db_key].get('user', '')
        encrypted_password = config[db_key].get('password', '')
        dsn = config[db_key].get('dsn', '')
        password = decrypt_password(encrypted_password)
        return user, password, dsn
    raise ConnectionError(f"Seção '{db_key}' não encontrada no 'config.ini'.")

def search_contestacoes(db_key, sr=None, msisdn=None, start_date=None, end_date=None, status=None):
    """Busca um resumo das contestações com base nos filtros."""
    user, password, dsn = get_config(db_key)
    params = {}
    query = "SELECT id_, sr, msisdn, invoicenumber, TO_CHAR(createdate, 'YYYY-MM-DD HH24:MI:SS') as createdate, statusname FROM scc_invoicerequest WHERE 1=1"
    
    if sr:
        query += " AND sr = :sr"
        params['sr'] = sr
    if msisdn:
        query += " AND msisdn = :msisdn"
        params['msisdn'] = msisdn
    
    if status:
        query += " AND statusname = :status"
        params['status'] = status

    if start_date:
        query += " AND modifieddate >= :start_date"
        params['start_date'] = start_date
    if end_date:
        end_date_inclusive = end_date + timedelta(days=1)
        query += " AND modifieddate < :end_date"
        params['end_date'] = end_date_inclusive
    
    query += " ORDER BY createdate DESC FETCH FIRST 100 ROWS ONLY"

    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                columns = [desc[0].lower() for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar contestações: {e.args[0].message}")

def search_interfaces(db_key, status=None, hours=None):
    """Busca na tabela de interfaces por status e período em horas."""
    user, password, dsn = get_config(db_key)
    params = {}
    
    status_map = {
        "Sucesso": 1,
        "Nao enviado": 2, # Também pode ser 0
        "Aguardando Retorno": 3,
        "Erro Permanente": 4,
        "Envio Cancelado": 5,
        "Erro Temporario": 6
    }

    query = """
        SELECT /*+ parallel(4) */
            a.id_,
            TO_CHAR(a.createdate, 'YYYY-MM-DD HH24:MI:SS') as createdate,
            TO_CHAR(a.senddate, 'YYYY-MM-DD HH24:MI:SS') as senddate,
            a.errordescription,
            DECODE(a.status, 1, 'Sucesso', 2, 'Nao enviado', 3, 'Aguardando Retorno', 4, 'Erro Permanente', 5, 'Envio Cancelado', 6, 'Erro Temporario', 0, 'Nao enviado') desc_status,
            DECODE(a.type_, 1, 'RMCA', 2, 'OCC de Crédito', 3, 'OCC de Débito', 4, 'Recibo de Arrecadação', 5, 'Devolução em Conta Corrente') type_desc
        FROM 
            scc_invoiceinterface a
        WHERE 1=1
    """
    
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
    """Busca apenas os detalhes do cabeçalho da contestação (muito rápido)."""
    user, password, dsn = get_config(db_key)
    details = {}
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                query = """
                    SELECT r.id_, r.sr, r.msisdn, r.invoicenumber, r.customerid,
                           TO_CHAR(r.createdate, 'YYYY-MM-DD HH24:MI:SS') as createdate,
                           r.statusname, u.login as user_login
                    FROM scc_invoicerequest r
                    LEFT JOIN scc_user u ON r.userid = u.id_
                    WHERE r.id_ = :id
                """
                cursor.execute(query, id=request_id)
                columns = [desc[0].lower() for desc in cursor.description]
                request_data = cursor.fetchone()
                if not request_data: return None
                details['request'] = dict(zip(columns, request_data))
                
                query_audit = """
                    SELECT TO_CHAR(modifieddate, 'YYYY-MM-DD HH24:MI:SS') as modifieddate, statusname
                    FROM scc_invoicerequest_audit
                    WHERE id_ = :id ORDER BY modifieddate DESC
                """
                cursor.execute(query_audit, id=request_id)
                columns_audit = [desc[0].lower() for desc in cursor.description]
                details['history'] = [dict(zip(columns_audit, row)) for row in cursor.fetchall()]
            return details
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar detalhes da requisição: {e.args[0].message}")

def get_analysis_details(db_key, sr):
    """Busca os detalhes da Análise da Fatura usando o SR."""
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
    """Busca os detalhes de Interfaces usando o SR, conforme query fornecida."""
    user, password, dsn = get_config(db_key)
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                query = """
                    SELECT a.*,
                           TO_CHAR(a.senddate, 'YYYY-MM-DD HH24:MI:SS') as senddate,
                           DECODE (a.status, 1, 'Sucesso', 2, 'Nao enviado', 3, 'Aguardando Retorno', 4, 'Erro Permanente', 5, 'Envio Cancelado', 6, 'Erro Temporario', 0, 'Nao enviado') desc_status,
                           DECODE (a.type_, 1, 'RMCA', 2, 'OCC de Crédito', 3, 'OCC de Débito', 4, 'Recibo de Arrecadação', 5, 'Devolução em Conta Corrente') type_desc
                    FROM scc_invoiceinterface a
                    WHERE a.invoiceanalysisid IN (
                        SELECT id_ FROM scc_invoiceanalysis WHERE invoicerequestid IN (
                            SELECT id_ FROM scc_invoicerequest WHERE sr = :sr
                        )
                    )
                """
                cursor.execute(query, sr=sr)
                columns = [desc[0].lower() for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar detalhes de interface: {e.args[0].message}")

def get_adjust_details(db_key, sr):
    """Busca os detalhes de Ajuste Futuro usando o SR, conforme query fornecida."""
    user, password, dsn = get_config(db_key)
    adjust_details = {}
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                query_adjust = """
                    SELECT a.*,
                           DECODE (a.status, 1, 'Processado', 2, 'Em processamento', 3, 'Em processamento', 4, 'Erro no processamento', 5, 'Erro de envio', 6, 'Erro de alçada', 7, 'Solicitação cancelada', 8, 'Processamento cancelado', 9, 'Cancelado usuário', 10, 'Não elegível') as desc_status
                    FROM scc_invoiceadjust a
                    WHERE a.invoicerequestid IN (SELECT id_ FROM scc_invoicerequest WHERE sr = :sr)
                """
                cursor.execute(query_adjust, sr=sr)
                columns = [desc[0].lower() for desc in cursor.description]
                adjust_summary = cursor.fetchone()

                if adjust_summary:
                    adjust_details['adjust_summary'] = dict(zip(columns, adjust_summary))
                    adjust_id = adjust_summary[columns.index('id_')]

                    query_adjust_line = "SELECT * FROM scc_invoiceadjustline WHERE invoiceadjustid = :id"
                    cursor.execute(query_adjust_line, id=adjust_id)
                    line_columns = [desc[0].lower() for desc in cursor.description]
                    adjust_details['adjust_lines'] = [dict(zip(line_columns, row)) for row in cursor.fetchall()]
            return adjust_details
    except oracledb.DatabaseError as e:
        raise Exception(f"Erro ao buscar detalhes do ajuste: {e.args[0].message}")

def descartar_contestacao(db_key, sr):
    """Executa o UPDATE para alterar o status de uma contestação para 'Descartada'."""
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