# C:\Meus Projetos\MyOps\modules\siebel_relation\siebel_relation_logic.py

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

def get_relationships(db_section_name, src_table, dest_table):
    """
    Consulta a tabela de relacionamentos do Siebel (exp_relationship_table).
    Retorna os cabeçalhos e as linhas de dados.
    """
    if not src_table or not dest_table:
        raise ValueError("Os nomes da tabela de origem e destino são obrigatórios.")

    user, password, dsn = get_config(db_section_name)
    
    # Prepara a consulta SQL
    sql_query = """
        SELECT 
            SRC_TBL_NAME, 
            SRC_COL_NAME, 
            DEST_COL_NAME, 
            DEST_TBL_NAME 
        FROM exp_relationship_table 
        WHERE 
            SRC_TBL_NAME = :src_tbl 
        AND DEST_TBL_NAME = :dest_tbl
    """
    
    # Prepara os parâmetros, convertendo para maiúsculas
    params = {
        'src_tbl': src_table.upper().strip(),
        'dest_tbl': dest_table.upper().strip()
    }

    headers = ["Tabela de Origem", "Coluna de Origem (FK)", "Coluna de Destino (PK)", "Tabela de Destino"]
    data = []

    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql_query, params)
            rows = cursor.fetchall()
            if rows:
                data = [list(row) for row in rows]
    
    return headers, data