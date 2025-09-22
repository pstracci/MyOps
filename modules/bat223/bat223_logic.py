# C:\Meus Projetos\MyOps\modules\bat223\bat223_logic.py

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

# --- ALTERAÇÃO: A função agora recebe 'db_section_name' como argumento ---
def force_bat223_extraction(environment, msisdn_list, db_section_name):
    """
    Executa o processo completo para forçar a extração da BAT223 para uma lista de MSISDNs.
    """
    # A lógica para definir tabelas e colunas com base no ambiente (Pós/Pré) permanece
    if environment == 'pre':
        temp_table = 'SIEBEL.PM_TMP_ACESSOS_BAT223_PRE'
        stage_table = 'SIEBEL.PM_TMP_ACESSOS_BAT223_f1' # Usaremos um nome único para evitar conflitos
        asset_column = 'a.asset_num'
    elif environment == 'pos':
        temp_table = 'SIEBEL.PM_TMP_ACESSOS_BAT223_POS'
        stage_table = 'SIEBEL.PM_TMP_ACESSOS_BAT223_f1'
        asset_column = 'a.serial_num'
    else:
        raise ValueError("Ambiente inválido selecionado.")

    # A chave do banco de dados agora é fornecida pelo usuário
    user, password, dsn = get_config(db_section_name)
    logs = []

    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        with connection.cursor() as cursor:
            try:
                # 1. Truncar a tabela temporária
                logs.append(f"Iniciando TRUNCATE na tabela {temp_table}...")
                cursor.execute(f"TRUNCATE TABLE {temp_table}")
                logs.append("Tabela truncada com sucesso.")

                # 2. Inserir os MSISDNs
                logs.append(f"Inserindo {len(msisdn_list)} MSISDNs...")
                data_to_insert = [(msisdn,) for msisdn in msisdn_list]
                cursor.executemany(f"INSERT INTO {temp_table} (CONTRATOACESSO) VALUES (:1)", data_to_insert)
                logs.append(f"{cursor.rowcount} registros inseridos com sucesso.")
                connection.commit()

                # 3. Dropar a tabela stage se ela existir
                try:
                    logs.append(f"Verificando e dropando tabela stage antiga ({stage_table})...")
                    cursor.execute(f"DROP TABLE {stage_table}")
                    logs.append("Tabela stage antiga dropada.")
                except oracledb.DatabaseError as e:
                    # ORA-00942: table or view does not exist - esperado se a tabela não existe
                    if 'ORA-00942' in str(e):
                        logs.append("Tabela stage não existia, continuando.")
                    else:
                        raise # Relança outros erros de drop

                # 4. Criar a tabela stage
                create_stage_sql = f"""
                CREATE TABLE {stage_table} AS
                    SELECT b.row_id,
                           b.created,
                           b.last_upd,
                           b.name AS cpf,
                           a.ROW_ID row_id_sa,
                           a.CREATED created_sa,
                           a.LAST_UPD last_upd_sa,
                           {asset_column} AS gsm_number,
                           a.OWNER_ACCNT_ID
                    FROM SIEBEL.S_ASSET a, SIEBEL.S_ORG_EXT b, {temp_table} c
                    WHERE a.{asset_column.split('.')[1]} = c.CONTRATOACESSO
                      AND a.OWNER_ACCNT_ID = b.row_id
                      AND a.status_cd <> 'Cancelado'
                """
                logs.append(f"Criando tabela stage {stage_table}...")
                cursor.execute(create_stage_sql)
                logs.append(f"{cursor.rowcount} registros criados na tabela stage.")
                connection.commit()

                # 5. Executar o bloco anônimo
                plsql_block = f"""
                DECLARE
                    v_count NUMBER := 0;
                BEGIN
                    FOR rec IN (SELECT * FROM {stage_table})
                    LOOP
                        UPDATE SIEBEL.S_ORG_EXT
                           SET LAST_UPD = SYSDATE, LAST_UPD_BY = '1-0'
                         WHERE ROW_ID = rec.row_id;

                        UPDATE SIEBEL.S_ASSET
                           SET LAST_UPD = SYSDATE, LAST_UPD_BY = '1-0'
                         WHERE ROW_ID = rec.row_id_sa;

                        v_count := v_count + 1;
                        IF (v_count >= 1000)
                        THEN
                            COMMIT;
                            v_count := 0;
                        END IF;
                    END LOOP;
                    COMMIT;
                END;
                """
                logs.append("Executando bloco anônimo para atualizar S_ASSET e S_ORG_EXT...")
                cursor.execute(plsql_block)
                logs.append("Bloco anônimo executado com sucesso.")

                # 6. Limpeza final
                logs.append(f"Dropando tabela stage final ({stage_table})...")
                cursor.execute(f"DROP TABLE {stage_table}")
                logs.append("Limpeza concluída.")
                connection.commit()

            except Exception as e:
                logs.append(f"ERRO: Ocorreu um erro durante o processo: {e}")
                connection.rollback()
                raise e

    return "\n".join(logs)