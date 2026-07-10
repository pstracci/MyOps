# C:\Meus Projetos\fixer\modules\object_viewer\object_viewer_logic.py

import oracledb
import configparser
from modules.common import security # NOVO

# Dicionário que mapeia as chaves do config.ini para nomes amigáveis (mantido para compatibilidade)
DB_TARGETS = {
    'database_siebel': 'Siebel Pós-Pago',
    'database_siebel_pre': 'Siebel Pré-Pago',
    'database_espelho': 'Base Espelho' # ADICIONADO: Nova base de dados para a busca
}

def get_all_db_connections():
    """Retorna todas as conexões de banco disponíveis no config.ini."""
    config = configparser.ConfigParser()
    config.read('config.ini')
    db_connections = {}
    for section in config.sections():
        if section.startswith('database_'):
            # Cria nome amigável baseado na seção
            friendly_name = section.replace('database_', '').replace('_', ' ').title()
            db_connections[section] = friendly_name
    return db_connections

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

def search_objects(object_name, object_types=None, db_key=None, is_cancelled_callback=None):
    """Busca por um objeto em uma base de dados específica ou em todas.
    
    Args:
        object_name: Nome do objeto para buscar (aceita wildcards)
        object_types: Lista de tipos de objetos para filtrar (ex: ['TABLE', 'PACKAGE'])
                     Se None, busca todos os tipos suportados.
        db_key: Chave específica da conexão (ex: 'database_siebel'). Se None, busca em todas.
        is_cancelled_callback: Função callback opcional para verificar se foi cancelado
    """
    all_results = []
    search_pattern = ('%' + object_name.upper() + '%') if object_name else '%'
    
    # Tipos de objetos suportados
    supported_types = ['PACKAGE', 'PROCEDURE', 'FUNCTION', 'TABLE', 'VIEW', 
                       'INDEX', 'TRIGGER', 'SEQUENCE', 'SYNONYM']
    
    # Se não especificou tipos, busca todos
    if object_types is None or len(object_types) == 0:
        types_filter = supported_types
    else:
        types_filter = [t.upper() for t in object_types if t.upper() in supported_types]
    
    # Define quais bases buscar
    if db_key:
        # Busca apenas na base específica
        all_connections = get_all_db_connections()
        if db_key not in all_connections:
            raise ValueError(f"Conexão '{db_key}' não encontrada no config.ini")
        targets = {db_key: all_connections[db_key]}
    else:
        # Busca em todas as bases (comportamento antigo)
        targets = DB_TARGETS
    
    for target_db_key, db_friendly_name in targets.items():
        # Verifica se foi cancelado
        if is_cancelled_callback and is_cancelled_callback():
            return []
            
        try:
            user, password, dsn = get_config(target_db_key)
            
            # Cria a cláusula IN para os tipos
            types_placeholders = ','.join([f":type{i}" for i in range(len(types_filter))])
            
            # Tenta consulta com user_segments primeiro
            try:
                query = f"""
                    SELECT 
                        o.owner, 
                        o.object_name, 
                        o.object_type, 
                        o.status, 
                        o.created, 
                        o.last_ddl_time,
                        CASE 
                            WHEN o.object_type IN ('TABLE', 'INDEX') THEN 
                                ROUND(NVL(us.bytes, 0) / 1024 / 1024 / 1024, 4)
                            ELSE 0
                        END as size_gb
                    FROM all_objects o
                    LEFT JOIN user_segments us ON 
                        us.segment_name = o.object_name AND 
                        (
                            (o.object_type = 'TABLE' AND us.segment_type = 'TABLE')
                            OR (o.object_type = 'INDEX' AND us.segment_type = 'INDEX')
                        )
                    WHERE o.object_name LIKE :name 
                      AND o.object_type IN ({types_placeholders})
                      AND o.owner NOT IN ('SYS', 'SYSTEM', 'OUTLN', 'DBSNMP', 'APPQOSSYS', 
                                        'WMSYS', 'EXFSYS', 'CTXSYS', 'XDB', 'ANONYMOUS', 
                                        'ORDSYS', 'ORDDATA', 'MDSYS', 'LBACSYS', 'DVSYS', 'DVF')
                    ORDER BY o.object_type, o.owner, o.object_name
                """
                
                with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
                    with connection.cursor() as cursor:
                        # Prepara os parâmetros
                        params = {'name': search_pattern}
                        for i, obj_type in enumerate(types_filter):
                            params[f'type{i}'] = obj_type
                        
                        cursor.execute(query, **params)
                        columns = [desc[0].lower() for desc in cursor.description]
                        for row in cursor.fetchall():
                            row_dict = dict(zip(columns, row))
                            row_dict['db_key'] = target_db_key
                            row_dict['db_friendly_name'] = db_friendly_name
                            all_results.append(row_dict)
                            
            except Exception as segment_error:
                # Fallback: consulta sem user_segments (sem informação de tamanho)
                print(f"Aviso: user_segments não disponível em '{db_friendly_name}', usando consulta simplificada")
                query_simple = f"""
                    SELECT 
                        o.owner, 
                        o.object_name, 
                        o.object_type, 
                        o.status, 
                        o.created, 
                        o.last_ddl_time,
                        0 as size_gb
                    FROM all_objects o
                    WHERE o.object_name LIKE :name 
                      AND o.object_type IN ({types_placeholders})
                      AND o.owner NOT IN ('SYS', 'SYSTEM', 'OUTLN', 'DBSNMP', 'APPQOSSYS', 
                                        'WMSYS', 'EXFSYS', 'CTXSYS', 'XDB', 'ANONYMOUS', 
                                        'ORDSYS', 'ORDDATA', 'MDSYS', 'LBACSYS', 'DVSYS', 'DVF')
                    ORDER BY o.object_type, o.owner, o.object_name
                """
                
                with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
                    with connection.cursor() as cursor:
                        # Prepara os parâmetros
                        params = {'name': search_pattern}
                        for i, obj_type in enumerate(types_filter):
                            params[f'type{i}'] = obj_type
                        
                        cursor.execute(query_simple, **params)
                        columns = [desc[0].lower() for desc in cursor.description]
                        for row in cursor.fetchall():
                            row_dict = dict(zip(columns, row))
                            row_dict['db_key'] = target_db_key
                            row_dict['db_friendly_name'] = db_friendly_name
                            all_results.append(row_dict)
        except Exception as e:
            # Se uma base estiver offline, registra o erro e continua
            print(f"Erro ao conectar ou buscar em '{db_friendly_name}': {e}")
            all_results.append({
                'owner': 'ERRO',
                'object_name': f"Não foi possível conectar à base '{db_friendly_name}'",
                'is_error': True,
                'db_key': target_db_key,
                'db_friendly_name': db_friendly_name,
            })
            
    return all_results

def get_object_source(db_key, owner, object_name, object_type):
    """Busca o código-fonte, DDL ou DESCRIBE de um objeto de banco de dados.
    
    Args:
        db_key: Chave da conexão no config.ini
        owner: Schema owner do objeto
        object_name: Nome do objeto
        object_type: Tipo do objeto (PACKAGE, TABLE, PROCEDURE, etc.)
    """
    user, password, dsn = get_config(db_key)
    
    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        # Para objetos com código-fonte (PACKAGE, PROCEDURE, FUNCTION, TRIGGER, VIEW)
        if object_type in ['PACKAGE', 'PROCEDURE', 'FUNCTION', 'TRIGGER', 'TYPE']:
            return _get_source_code(connection, owner, object_name, object_type)
        
        # Para VIEW, retorna o DDL
        elif object_type == 'VIEW':
            return _get_view_ddl(connection, owner, object_name)
        
        # Para TABLE, retorna DESCRIBE + DDL
        elif object_type == 'TABLE':
            return _get_table_info(connection, owner, object_name)
        
        # Para INDEX, retorna informações e DDL
        elif object_type == 'INDEX':
            return _get_index_info(connection, owner, object_name)
        
        # Para SEQUENCE, retorna informações
        elif object_type == 'SEQUENCE':
            return _get_sequence_info(connection, owner, object_name)
        
        # Para SYNONYM, retorna informações
        elif object_type == 'SYNONYM':
            return _get_synonym_info(connection, owner, object_name)
        
        else:
            return f"-- Tipo de objeto '{object_type}' não suportado para visualização detalhada."


def _get_source_code(connection, owner, object_name, object_type):
    """Obtém o código-fonte de objetos PL/SQL."""
    full_source_code = ""
    
    with connection.cursor() as cursor:
        # Para PACKAGE, busca SPEC e BODY
        if object_type == 'PACKAGE':
            # Package Spec
            cursor.execute("""
                SELECT text FROM all_source 
                WHERE owner = :owner AND name = :name AND type = 'PACKAGE' 
                ORDER BY line
            """, owner=owner, name=object_name)
            
            spec_rows = cursor.fetchall()
            if spec_rows:
                full_source_code += f"-- ===================\n-- PACKAGE SPECIFICATION: {owner}.{object_name}\n-- ===================\n\n"
                full_source_code += "".join([row[0] for row in spec_rows])

            # Package Body
            cursor.execute("""
                SELECT text FROM all_source 
                WHERE owner = :owner AND name = :name AND type = 'PACKAGE BODY' 
                ORDER BY line
            """, owner=owner, name=object_name)
            
            body_rows = cursor.fetchall()
            if body_rows:
                full_source_code += f"\n\n-- ===================\n-- PACKAGE BODY: {owner}.{object_name}\n-- ===================\n\n"
                full_source_code += "".join([row[0] for row in body_rows])
        
        else:
            # Para PROCEDURE, FUNCTION, TRIGGER, TYPE
            cursor.execute("""
                SELECT text FROM all_source 
                WHERE owner = :owner AND name = :name AND type = :type
                ORDER BY line
            """, owner=owner, name=object_name, type=object_type)
            
            rows = cursor.fetchall()
            if rows:
                full_source_code += f"-- ===================\n-- {object_type}: {owner}.{object_name}\n-- ===================\n\n"
                full_source_code += "".join([row[0] for row in rows])
    
    return full_source_code if full_source_code else f"-- Código-fonte para {owner}.{object_name} não encontrado."


def _get_table_info(connection, owner, table_name):
    """Obtém informações detalhadas de uma tabela (DESCRIBE + constraints + indexes)."""
    output = []
    output.append(f"-- ===================\n-- TABLE: {owner}.{table_name}\n-- ===================\n")
    
    with connection.cursor() as cursor:
        # DESCRIBE - Colunas
        cursor.execute("""
            SELECT column_name, data_type, data_length, data_precision, data_scale, 
                   nullable, data_default
            FROM all_tab_columns
            WHERE owner = :owner AND table_name = :table_name
            ORDER BY column_id
        """, owner=owner, table_name=table_name)
        
        output.append("\n-- COLUNAS:\n")
        output.append(f"{'COLUMN_NAME':<30} {'DATA_TYPE':<20} {'NULLABLE':<10} DEFAULT\n")
        output.append("-" * 100 + "\n")
        
        for row in cursor.fetchall():
            col_name, data_type, data_len, data_prec, data_scale, nullable, default = row
            
            # Formata o tipo de dado
            if data_type in ['VARCHAR2', 'CHAR', 'NVARCHAR2', 'NCHAR']:
                type_str = f"{data_type}({data_len})"
            elif data_type == 'NUMBER':
                if data_prec:
                    type_str = f"NUMBER({data_prec},{data_scale or 0})"
                else:
                    type_str = "NUMBER"
            else:
                type_str = data_type
            
            null_str = "NULL" if nullable == 'Y' else "NOT NULL"
            default_str = str(default)[:30] if default else ""
            
            output.append(f"{col_name:<30} {type_str:<20} {null_str:<10} {default_str}\n")
        
        # Primary Key
        cursor.execute("""
            SELECT constraint_name, column_name
            FROM all_cons_columns
            WHERE owner = :owner AND table_name = :table_name
              AND constraint_name IN (
                  SELECT constraint_name FROM all_constraints
                  WHERE owner = :owner AND table_name = :table_name
                    AND constraint_type = 'P'
              )
            ORDER BY position
        """, owner=owner, table_name=table_name)
        
        pk_rows = cursor.fetchall()
        if pk_rows:
            output.append(f"\n-- PRIMARY KEY: {pk_rows[0][0]}\n")
            output.append("   Colunas: " + ", ".join([row[1] for row in pk_rows]) + "\n")
        
        # Foreign Keys
        cursor.execute("""
            SELECT c.constraint_name, c.r_constraint_name, 
                   listagg(cc.column_name, ', ') WITHIN GROUP (ORDER BY cc.position) as columns
            FROM all_constraints c
            JOIN all_cons_columns cc ON c.constraint_name = cc.constraint_name 
                                     AND c.owner = cc.owner
            WHERE c.owner = :owner AND c.table_name = :table_name
              AND c.constraint_type = 'R'
            GROUP BY c.constraint_name, c.r_constraint_name
        """, owner=owner, table_name=table_name)
        
        fk_rows = cursor.fetchall()
        if fk_rows:
            output.append("\n-- FOREIGN KEYS:\n")
            for fk_name, ref_constraint, columns in fk_rows:
                output.append(f"   {fk_name}: ({columns}) -> {ref_constraint}\n")
        
        # Indexes
        try:
            cursor.execute("""
                SELECT i.index_name, i.uniqueness, 
                       listagg(ic.column_name, ', ') WITHIN GROUP (ORDER BY ic.column_position) as columns
                FROM all_indexes i
                JOIN all_ind_columns ic ON i.index_name = ic.index_name AND i.owner = ic.index_owner
                WHERE i.table_owner = :owner AND i.table_name = :table_name
                GROUP BY i.index_name, i.uniqueness
                ORDER BY i.index_name
            """, owner=owner, table_name=table_name)
            
            idx_rows = cursor.fetchall()
            if idx_rows:
                output.append("\n-- INDEXES:\n")
                for idx_name, uniqueness, columns in idx_rows:
                    unique_str = "UNIQUE" if uniqueness == 'UNIQUE' else "NON-UNIQUE"
                    output.append(f"   {idx_name} ({unique_str}): {columns}\n")
        except Exception as e:
            # Fallback: consulta simplificada sem uniqueness
            try:
                cursor.execute("""
                    SELECT index_name, 
                           listagg(column_name, ', ') WITHIN GROUP (ORDER BY column_position) as columns
                    FROM all_ind_columns
                    WHERE table_owner = :owner AND table_name = :table_name
                    GROUP BY index_name
                    ORDER BY index_name
                """, owner=owner, table_name=table_name)
                
                idx_rows = cursor.fetchall()
                if idx_rows:
                    output.append("\n-- INDEXES:\n")
                    for idx_name, columns in idx_rows:
                        output.append(f"   {idx_name}: {columns}\n")
            except Exception as e2:
                output.append(f"\n-- ERRO ao consultar índices: {e2}\n")
    
    return "".join(output)


def _get_index_info(connection, owner, index_name):
    """Obtém informações de um índice."""
    output = []
    output.append(f"-- ===================\n-- INDEX: {owner}.{index_name}\n-- ===================\n")
    
    with connection.cursor() as cursor:
        try:
            cursor.execute("""
                SELECT i.table_owner, i.table_name, i.uniqueness, i.index_type,
                       listagg(ic.column_name, ', ') WITHIN GROUP (ORDER BY ic.column_position) as columns
                FROM all_indexes i
                JOIN all_ind_columns ic ON i.index_name = ic.index_name AND i.owner = ic.index_owner
                WHERE i.owner = :owner AND i.index_name = :index_name
                GROUP BY i.table_owner, i.table_name, i.uniqueness, i.index_type
            """, owner=owner, index_name=index_name)
            
            row = cursor.fetchone()
            if row:
                table_owner, table_name, uniqueness, index_type, columns = row
                output.append(f"\nTabela: {table_owner}.{table_name}\n")
                output.append(f"Tipo: {index_type}\n")
                output.append(f"Unique: {uniqueness}\n")
                output.append(f"Colunas: {columns}\n")
        except Exception as e:
            # Fallback: consulta simplificada
            try:
                cursor.execute("""
                    SELECT listagg(column_name, ', ') WITHIN GROUP (ORDER BY column_position) as columns
                    FROM all_ind_columns
                    WHERE index_owner = :owner AND index_name = :index_name
                """, owner=owner, index_name=index_name)
                
                row = cursor.fetchone()
                if row and row[0]:
                    output.append(f"\nColunas: {row[0]}\n")
                else:
                    output.append("\nNenhuma informação de coluna encontrada.\n")
            except Exception as e2:
                output.append(f"\nErro ao consultar índice: {e2}\n")
    
    return "".join(output)


def _get_view_ddl(connection, owner, view_name):
    """Obtém o DDL de uma VIEW."""
    output = []
    output.append(f"-- ===================\n-- VIEW: {owner}.{view_name}\n-- ===================\n\n")
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT text FROM all_views
            WHERE owner = :owner AND view_name = :view_name
        """, owner=owner, view_name=view_name)
        
        row = cursor.fetchone()
        if row:
            output.append(f"CREATE OR REPLACE VIEW {owner}.{view_name} AS\n")
            output.append(row[0])
            output.append(";\n")
    
    return "".join(output)


def _get_sequence_info(connection, owner, sequence_name):
    """Obtém informações de uma SEQUENCE."""
    output = []
    output.append(f"-- ===================\n-- SEQUENCE: {owner}.{sequence_name}\n-- ===================\n\n")
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT min_value, max_value, increment_by, cycle_flag, 
                   order_flag, cache_size, last_number
            FROM all_sequences
            WHERE sequence_owner = :owner AND sequence_name = :sequence_name
        """, owner=owner, sequence_name=sequence_name)
        
        row = cursor.fetchone()
        if row:
            min_val, max_val, increment, cycle, order, cache, last_num = row
            output.append(f"Valor Mínimo: {min_val}\n")
            output.append(f"Valor Máximo: {max_val}\n")
            output.append(f"Incremento: {increment}\n")
            output.append(f"Cycle: {cycle}\n")
            output.append(f"Order: {order}\n")
            output.append(f"Cache: {cache}\n")
            output.append(f"Último Número: {last_num}\n")
    
    return "".join(output)


def _get_synonym_info(connection, owner, synonym_name):
    """Obtém informações de um SYNONYM."""
    output = []
    output.append(f"-- ===================\n-- SYNONYM: {owner}.{synonym_name}\n-- ===================\n\n")
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT table_owner, table_name, db_link
            FROM all_synonyms
            WHERE owner = :owner AND synonym_name = :synonym_name
        """, owner=owner, synonym_name=synonym_name)
        
        row = cursor.fetchone()
        if row:
            table_owner, table_name, db_link = row
            output.append(f"Aponta para: {table_owner}.{table_name}")
            if db_link:
                output.append(f"@{db_link}")
            output.append("\n")
    
    return "".join(output)

def recompile_object(db_key, owner, object_name, object_type):
    """Recompila um objeto PL/SQL (PACKAGE, PROCEDURE, FUNCTION, TRIGGER, VIEW)."""
    user, password, dsn = get_config(db_key)
    messages = []

    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        with connection.cursor() as cursor:
            try:
                if object_type == 'PACKAGE':
                    # Recompila a Spec
                    cursor.execute(f'ALTER PACKAGE "{owner}"."{object_name}" COMPILE')
                    messages.append(f"Package '{object_name}' compilada com sucesso.")
                    
                    # Recompila o Body
                    try:
                        cursor.execute(f'ALTER PACKAGE "{owner}"."{object_name}" COMPILE BODY')
                        messages.append(f"Package Body '{object_name}' compilado com sucesso.")
                    except oracledb.DatabaseError as e:
                        messages.append(f"Aviso ao compilar Package Body '{object_name}': {e}")
                
                elif object_type == 'PROCEDURE':
                    cursor.execute(f'ALTER PROCEDURE "{owner}"."{object_name}" COMPILE')
                    messages.append(f"Procedure '{object_name}' compilada com sucesso.")
                
                elif object_type == 'FUNCTION':
                    cursor.execute(f'ALTER FUNCTION "{owner}"."{object_name}" COMPILE')
                    messages.append(f"Function '{object_name}' compilada com sucesso.")
                
                elif object_type == 'TRIGGER':
                    cursor.execute(f'ALTER TRIGGER "{owner}"."{object_name}" COMPILE')
                    messages.append(f"Trigger '{object_name}' compilado com sucesso.")
                
                elif object_type == 'VIEW':
                    cursor.execute(f'ALTER VIEW "{owner}"."{object_name}" COMPILE')
                    messages.append(f"View '{object_name}' compilada com sucesso.")
                
                else:
                    messages.append(f"Tipo de objeto '{object_type}' não suporta recompilação.")
                    
            except oracledb.DatabaseError as e:
                messages.append(f"Erro ao compilar {object_type} '{object_name}': {e}")
                
    return "\n".join(messages)

def drop_object(db_key, owner, object_name, object_type):
    """Exclui um objeto do banco de dados usando a sintaxe apropriada para cada tipo.
    
    Args:
        db_key: Chave da conexão no config.ini
        owner: Schema owner do objeto
        object_name: Nome do objeto
        object_type: Tipo do objeto (PACKAGE, TABLE, PROCEDURE, etc.)
    
    Returns:
        str: Mensagem de sucesso ou erro
    """
    user, password, dsn = get_config(db_key)
    
    # Monta o comando DROP apropriado para cada tipo
    drop_commands = {
        'TABLE': f'DROP TABLE "{owner}"."{object_name}" CASCADE CONSTRAINTS',
        'VIEW': f'DROP VIEW "{owner}"."{object_name}"',
        'INDEX': f'DROP INDEX "{owner}"."{object_name}"',
        'SEQUENCE': f'DROP SEQUENCE "{owner}"."{object_name}"',
        'SYNONYM': f'DROP SYNONYM "{owner}"."{object_name}"',
        'PACKAGE': f'DROP PACKAGE "{owner}"."{object_name}"',
        'PROCEDURE': f'DROP PROCEDURE "{owner}"."{object_name}"',
        'FUNCTION': f'DROP FUNCTION "{owner}"."{object_name}"',
        'TRIGGER': f'DROP TRIGGER "{owner}"."{object_name}"',
        'TYPE': f'DROP TYPE "{owner}"."{object_name}" FORCE',
    }
    
    if object_type not in drop_commands:
        return f"Tipo de objeto '{object_type}' não suportado para exclusão."
    
    drop_sql = drop_commands[object_type]
    
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(drop_sql)
                connection.commit()
                return f"Objeto {object_type} '{owner}.{object_name}' excluído com sucesso."
    except oracledb.DatabaseError as e:
        error_obj, = e.args
        return f"Erro ao excluir {object_type} '{owner}.{object_name}':\n{error_obj.message}"