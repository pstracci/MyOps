# C:\Meus Projetos\MyOps\modules\top_sql\top_sql_logic.py

import oracledb
from modules.session_monitor.session_monitor_logic import get_config

class TopSqlLogic:
    def __init__(self, db_key):
        self.db_key = db_key
        self.user, self.password, self.dsn = get_config(self.db_key)

    def take_snapshot(self):
        """
        Executa a query na gv$sql uma vez e retorna os dados brutos,
        formatados em um dicionário para acesso rápido por sql_id.
        """
        query = """
            SELECT
                sql_id,
                cpu_time,
                elapsed_time,
                executions,
                disk_reads,
                rows_processed,
                parsing_schema_name,
                substr(sql_text, 1, 1000) as sql_text_snippet
            FROM
               v$sql
            WHERE
                executions > 0 AND parsing_schema_name NOT IN ('SYS', 'SYSTEM')
        """
        try:
            with oracledb.connect(user=self.user, password=self.password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    columns = [desc[0].lower() for desc in cursor.description]
                    snapshot_dict = {row[0]: dict(zip(columns, row)) for row in cursor.fetchall()}
                    return snapshot_dict
        except oracledb.DatabaseError as e:
            raise Exception(f"Erro de banco de dados ao fazer snapshot da gv$sql: {e.args[0].message}")