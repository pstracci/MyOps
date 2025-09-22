# C:\Meus Projetos\MyOps\modules\common\db_utils.py

import oracledb

def test_db_connection(user, password, dsn):
    """
    Tenta estabelecer uma conexão com o banco de dados e a fecha imediatamente.
    Retorna True em caso de sucesso ou levanta uma exceção em caso de falha.
    """
    try:
        oracledb.connect(user=user, password=password, dsn=dsn)
        return True
    except oracledb.DatabaseError as e:
        # Levanta a exceção original para que a UI possa exibir a mensagem de erro específica.
        raise e