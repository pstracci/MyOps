# C:\Meus Projetos\MyOps\modules\bat509\bat509_logic.py

import oracledb
import configparser
from datetime import datetime
from modules.common import security # Adicionado import de segurança

def get_config(section='database_siebel'): # <-- CORREÇÃO APLICADA AQUI
    """Lê a seção do Siebel Pós-Pago do config.ini e descriptografa a senha."""
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

def mark_orders_for_extraction(order_numbers: list):
    """
    Processa uma lista de ordens, inserindo-as na tabela ACC_SBL_MARC_BAT509
    para forçar sua re-extração, mimetizando o processo BAT801.
    """
    user, password, dsn = get_config()
    
    report = {'success': [], 'already_marked': [], 'not_found': [], 'errors': []}
    src_file = f"BAT801_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    execution_id = int(datetime.now().timestamp())

    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        with connection.cursor() as cursor:
            for order_num in order_numbers:
                order_num = order_num.strip()
                if not order_num:
                    continue
                
                try:
                    # 1. Verifica se a ordem existe e obtém seu ROW_ID
                    cursor.execute("SELECT ROW_ID FROM SIEBEL.S_ORDER WHERE ORDER_NUM = :order_num", order_num=order_num)
                    order_row = cursor.fetchone()
                    
                    if not order_row:
                        report['not_found'].append(order_num)
                        continue
                    
                    order_row_id = order_row[0]

                    # 2. Verifica se a ordem já está marcada e pendente
                    cursor.execute("""
                        SELECT 1 FROM SIEBEL.ACC_SBL_MARC_BAT509
                        WHERE ROW_ID = :row_id AND DATA_EXTRACAO IS NULL
                    """, row_id=order_row_id)
                    
                    if cursor.fetchone():
                        report['already_marked'].append(order_num)
                        continue

                    # 3. Executa o INSERT ... SELECT mimetizando o BAT801
                    insert_query = """
                    INSERT INTO SIEBEL.ACC_SBL_MARC_BAT509 (
                        ID, CREATED, LAST_UPD, CREATED_BY, LAST_UPD_BY, SRC_FILE,
                        PROJETO, SERVICE_ID, ROW_ID, DATA_EXTRACAO, NOME_EXTRACAO
                    )
                    SELECT
                        :exec_id,
                        TO_CHAR(SO.CREATED, 'DD-MM-YYYY HH24:MI:SS'),
                        TO_CHAR(SYSDATE, 'DD-MM-YYYY HH24:MI:SS'),
                        '0-1', -- Usuário padrão de sistema (CREATED_BY)
                        '0-1', -- Usuário padrão de sistema (LAST_UPD_BY)
                        :src_file,
                        'Marcacao para extracao da BAT509',
                        SOI.X_SERVICE_ID,
                        SO.ROW_ID,
                        NULL,
                        NULL
                    FROM
                        SIEBEL.S_ORDER SO
                    LEFT JOIN
                        SIEBEL.S_ORDER_ITEM SOI ON SO.ROW_ID = SOI.ORDER_ID AND SOI.ROW_ID = SOI.ROOT_ORDER_ITEM_ID
                    WHERE
                        SO.ORDER_NUM = :order_num
                    AND ROWNUM = 1
                    """
                    
                    cursor.execute(insert_query, exec_id=execution_id, src_file=src_file, order_num=order_num)
                    
                    if cursor.rowcount > 0:
                        report['success'].append(order_num)
                    else:
                        raise RuntimeError("A query de SELECT interna para o INSERT não retornou dados.")

                except Exception as e:
                    report['errors'].append(f"{order_num}: {e}")

        connection.commit()

    # Monta uma mensagem de relatório final
    summary = []
    if report['success']:
        summary.append(f"Ordens marcadas com sucesso: {', '.join(report['success'])}")
    if report['already_marked']:
        summary.append(f"Ordens que já estavam marcadas: {', '.join(report['already_marked'])}")
    if report['not_found']:
        summary.append(f"Ordens não encontradas: {', '.join(report['not_found'])}")
    if report['errors']:
        summary.append(f"Erros: {'; '.join(report['errors'])}")
        
    final_report = "\n".join(summary)
    if report['success']:
        final_report += f"\n\nID de Execução deste lote: {execution_id}"
        
    return final_report