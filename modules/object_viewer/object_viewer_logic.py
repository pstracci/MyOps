# C:\Meus Projetos\fixer\modules\object_viewer\object_viewer_logic.py

import oracledb
import configparser
from modules.common import security # NOVO

# Dicionário que mapeia as chaves do config.ini para nomes amigáveis
DB_TARGETS = {
    'database_siebel': 'Siebel Pós-Pago',
    'database_siebel_pre': 'Siebel Pré-Pago',
    'database_espelho': 'Base Espelho' # ADICIONADO: Nova base de dados para a busca
}

def get_config(section):
    """Lê uma seção específica do arquivo config.ini e descriptografa a senha."""
    config = configparser.ConfigParser()
    config.read('config.ini')
    if section in config:
        # Pega os valores do arquivo de configuração
        user = config[section].get('user', '')
        encrypted_password = config[section].get('password', '')
        # Pega 'dsn' para bancos Oracle ou 'url' para Weblogic, tornando a função universal
        dsn = config[section].get('dsn', config[section].get('url', ''))

        # Descriptografa a senha antes de retorná-la
        password = security.decrypt_password(encrypted_password)
        
        return user, password, dsn
        
    raise ConnectionError(f"Seção '{section}' não encontrada no 'config.ini'.")

def search_objects(object_name):
    """Busca por um objeto em todas as bases de dados alvo."""
    all_results = []
    search_pattern = ('%' + object_name.upper() + '%') if object_name else '%'
    
    for db_key, db_friendly_name in DB_TARGETS.items():
        try:
            user, password, dsn = get_config(db_key)
            
            query = """
                SELECT owner, object_name, object_type, status, created, last_ddl_time
                FROM all_objects
                WHERE object_name LIKE :name AND object_type = 'PACKAGE'
                ORDER BY owner, object_name
            """
            with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, name=search_pattern)
                    columns = [desc[0].lower() for desc in cursor.description]
                    for row in cursor.fetchall():
                        row_dict = dict(zip(columns, row))
                        row_dict['db_key'] = db_key
                        row_dict['db_friendly_name'] = db_friendly_name
                        all_results.append(row_dict)
        except Exception as e:
            # Se uma base estiver offline, registra o erro e continua
            print(f"Erro ao conectar ou buscar em '{db_friendly_name}': {e}")
            all_results.append({
                'owner': 'ERRO',
                'object_name': f"Não foi possível conectar à base '{db_friendly_name}'",
                'is_error': True,
                'db_key': db_key,
                'db_friendly_name': db_friendly_name,
            })
            
    return all_results

def get_object_source(db_key, owner, object_name):
    """Busca o código-fonte (spec e body) de um objeto de banco de dados."""
    full_source_code = ""
    user, password, dsn = get_config(db_key)

    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        # Busca a Package Spec (Header)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT text FROM all_source 
                WHERE owner = :owner AND name = :name AND type = 'PACKAGE' 
                ORDER BY line
            """, owner=owner, name=object_name)
            
            spec_rows = cursor.fetchall()
            if spec_rows:
                full_source_code += f"-- ===================\n-- PACKAGE SPECIFICATION: {owner}.{object_name}\n-- ===================\n\n"
                full_source_code += "".join([row[0] for row in spec_rows])

        # Busca a Package Body
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT text FROM all_source 
                WHERE owner = :owner AND name = :name AND type = 'PACKAGE BODY' 
                ORDER BY line
            """, owner=owner, name=object_name)
            
            body_rows = cursor.fetchall()
            if body_rows:
                full_source_code += f"\n\n-- ===================\n-- PACKAGE BODY: {owner}.{object_name}\n-- ===================\n\n"
                full_source_code += "".join([row[0] for row in body_rows])

    return full_source_code if full_source_code else f"-- Código-fonte para {owner}.{object_name} não encontrado."

def recompile_object(db_key, owner, object_name):
    """Recompila a spec e o body de uma package."""
    user, password, dsn = get_config(db_key)
    messages = []

    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        with connection.cursor() as cursor:
            try:
                # Recompila a Spec
                cursor.execute(f'ALTER PACKAGE "{owner}"."{object_name}" COMPILE')
                messages.append(f"Package '{object_name}' compilada com sucesso.")
            except oracledb.DatabaseError as e:
                messages.append(f"Erro ao compilar Package '{object_name}': {e}")

            try:
                # Recompila o Body
                cursor.execute(f'ALTER PACKAGE "{owner}"."{object_name}" COMPILE BODY')
                messages.append(f"Package Body '{object_name}' compilado com sucesso.")
            except oracledb.DatabaseError as e:
                messages.append(f"Erro ao compilar Package Body '{object_name}': {e}")
                
    return "\n".join(messages)