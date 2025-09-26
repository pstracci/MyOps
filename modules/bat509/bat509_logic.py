# C:\Meus Projetos\MyOps\modules\bat509\bat509_logic.py

import oracledb
import configparser
import logging
from datetime import datetime
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

def force_extraction(order_numbers: list, db_section_name: str):
    """
    Processa uma lista de ordens, inserindo-as na tabela ACC_SBL_MARC_BAT509
    para forçar sua re-extração. O nome da função está correto.
    """
    try:
        user, password, dsn = get_config(db_section_name)
    except ConnectionError as e:
        logging.error(f"Erro ao obter configuração para BAT509: {e}")
        return False, str(e)

    report = {'success': [], 'already_marked': [], 'not_found': [], 'errors': []}
    src_file = f"BAT801_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    execution_id = int(datetime.now().timestamp())

    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                for order_num in order_numbers:
                    order_num = order_num.strip()
                    if not order_num:
                        continue
                    
                    try:
                        cursor.execute("SELECT ROW_ID FROM SIEBEL.S_ORDER WHERE ORDER_NUM = :order_num", order_num=order_num)
                        order_row = cursor.fetchone()
                        
                        if not order_row:
                            report['not_found'].append(order_num)
                            continue
                        
                        order_row_id = order_row[0]

                        cursor.execute("""
                            SELECT 1 FROM SIEBEL.ACC_SBL_MARC_BAT509
                            WHERE ROW_ID = :row_id AND DATA_EXTRACAO IS NULL
                        """, row_id=order_row_id)
                        
                        if cursor.fetchone():
                            report['already_marked'].append(order_num)
                            continue

                        insert_query = """
                        INSERT INTO SIEBEL.ACC_SBL_MARC_BAT509 (
                            ID, CREATED, LAST_UPD, CREATED_BY, LAST_UPD_BY, SRC_FILE,
                            PROJETO, SERVICE_ID, ROW_ID, DATA_EXTRACAO, NOME_EXTRACAO
                        )
                        SELECT
                            :exec_id,
                            TO_CHAR(SO.CREATED, 'DD-MM-YYYY HH24:MI:SS'),
                            TO_CHAR(SYSDATE, 'DD-MM-YYYY HH24:MI:SS'),
                            '0-1', '0-1', :src_file,
                            'Marcacao para extracao da BAT509',
                            SOI.X_SERVICE_ID, SO.ROW_ID, NULL, NULL
                        FROM SIEBEL.S_ORDER SO
                        LEFT JOIN SIEBEL.S_ORDER_ITEM SOI ON SO.ROW_ID = SOI.ORDER_ID AND SOI.ROW_ID = SOI.ROOT_ORDER_ITEM_ID
                        WHERE SO.ORDER_NUM = :order_num AND ROWNUM = 1
                        """
                        
                        cursor.execute(insert_query, exec_id=execution_id, src_file=src_file, order_num=order_num)
                        
                        if cursor.rowcount > 0:
                            report['success'].append(order_num)
                        else:
                            raise RuntimeError("A query de INSERT...SELECT não inseriu registros.")

                    except Exception as e:
                        logging.error(f"Erro processando ordem {order_num} no BAT509: {e}", exc_info=True)
                        report['errors'].append(f"{order_num}: {e}")

            connection.commit()
    
    except oracledb.DatabaseError as db_err:
        logging.error(f"Erro de banco de dados no BAT509: {db_err}", exc_info=True)
        return False, f"Erro de Banco de Dados: {db_err}"
    except Exception as general_err:
        logging.error(f"Erro inesperado no BAT509: {general_err}", exc_info=True)
        return False, f"Erro inesperado: {general_err}"

    summary = []
    has_success = bool(report['success'])
    if report['success']:
        summary.append(f"Ordens marcadas com sucesso: {', '.join(report['success'])}")
    if report['already_marked']:
        summary.append(f"Ordens que já estavam marcadas/pendentes: {', '.join(report['already_marked'])}")
    if report['not_found']:
        summary.append(f"Ordens não encontradas: {', '.join(report['not_found'])}")
    if report['errors']:
        summary.append(f"Erros: {'; '.join(report['errors'])}")
        
    final_report = "\n".join(summary)
    if has_success:
        final_report += f"\n\nID de Execução deste lote: {execution_id}"
        
    return has_success or not final_report, final_report if final_report else "Nenhuma ordem processada."