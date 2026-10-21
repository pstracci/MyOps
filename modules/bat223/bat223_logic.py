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

def _batches(items, size=999):
    """Divide uma lista em lotes de até `size` elementos (limite do IN do Oracle)."""
    for i in range(0, len(items), size):
        yield items[i:i + size]

def _get_accnt_ids(cursor, cpf_batch):
    """Resolve CPFs → OWNER_ACCNT_IDs via S_ORG_EXT.NAME (CPF no Siebel TIM).
    NAME é 2ª coluna dos índices M15/M16/M2 (flag low-cardinality na frente) → index
    skip scan resolve sem full scan. Sem filtro de flag para não descartar contas."""
    ph = ', '.join([f':{i + 1}' for i in range(len(cpf_batch))])
    cursor.execute(
        f"SELECT ROW_ID FROM SIEBEL.S_ORG_EXT WHERE NAME IN ({ph})",
        cpf_batch
    )
    return [row[0] for row in cursor.fetchall()]


def preview_bat223_by_cpf(cpf_list, db_section_name):
    """
    Consulta prévia sem alterar dados.
    Retorna dict: {'movel': N, 'bl': N, 'total': N}

    - MOVEL: assets ROOT (ROW_ID = ROOT_ASSET_ID) com PROD_ID '1-2VL6D' ou '1-1SGIOKK'
    - BL   : SUB_ACESSO (PAR_ASSET_ID = ROOT_ASSET_ID) com PROD_ID '1-6RE2' ou '1-6REC'

    Usa dois passos para evitar JOIN lento S_ASSET × S_ORG_EXT:
      1) TAX_IDEN_NUM → ROW_ID em S_ORG_EXT (rápido, poucos CPFs)
      2) OWNER_ACCNT_ID → S_ASSET (FK indexada)
    """
    user, password, dsn = get_config(db_section_name)
    movel_count = 0
    bl_count = 0

    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        with connection.cursor() as cursor:
            cursor.callTimeout = 30000  # 30 s por statement

            for cpf_batch in _batches(cpf_list):
                accnt_ids = _get_accnt_ids(cursor, cpf_batch)
                if not accnt_ids:
                    continue

                for accnt_batch in _batches(accnt_ids):
                    ph = ', '.join([f':{i + 1}' for i in range(len(accnt_batch))])

                    cursor.execute(f"""
                        SELECT COUNT(SA.ROW_ID)
                        FROM SIEBEL.S_ASSET SA
                        WHERE SA.OWNER_ACCNT_ID IN ({ph})
                          AND SA.PROD_ID IN ('1-2VL6D', '1-1SGIOKK')
                          AND SA.ROW_ID = SA.ROOT_ASSET_ID
                    """, accnt_batch)
                    movel_count += cursor.fetchone()[0]

                    cursor.execute(f"""
                        SELECT COUNT(SA.ROW_ID)
                        FROM SIEBEL.S_ASSET SA
                        WHERE SA.OWNER_ACCNT_ID IN ({ph})
                          AND SA.PROD_ID IN ('1-6RE2', '1-6REC')
                          AND SA.PAR_ASSET_ID = SA.ROOT_ASSET_ID
                    """, accnt_batch)
                    bl_count += cursor.fetchone()[0]

    return {'movel': movel_count, 'bl': bl_count, 'total': movel_count + bl_count}


def force_bat223_extraction_by_cpf(cpf_list, db_section_name):
    """
    Força a extração BAT223 para uma lista de CPFs, atualizando LAST_UPD dos assets:
      - MOVEL: ROOT asset (ROW_ID = ROOT_ASSET_ID, PROD_ID '1-2VL6D'/'1-1SGIOKK')
      - BL   : SUB_ACESSO (PAR_ASSET_ID = ROOT_ASSET_ID, PROD_ID '1-6RE2'/'1-6REC')

    Retorna string de log detalhado.
    """
    STAGE_MOVEL = 'SIEBEL.PM_TMP_BAT223_MOVEL_STAGE'
    STAGE_BL    = 'SIEBEL.PM_TMP_BAT223_BL_STAGE'

    user, password, dsn = get_config(db_section_name)
    logs = []

    def drop_if_exists(cursor, table):
        try:
            cursor.execute(f"DROP TABLE {table}")
        except oracledb.DatabaseError as e:
            if 'ORA-00942' not in str(e):
                raise

    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        with connection.cursor() as cursor:
            cursor.callTimeout = 60000  # 60 s por statement (UPDATE pode ser mais lento)
            try:
                # ── 0. Resolver CPFs → OWNER_ACCNT_IDs ─────────────────────
                logs.append(f"Resolvendo {len(cpf_list)} CPF(s) para OWNER_ACCNT_ID...")
                all_accnt_ids = []
                for cpf_batch in _batches(cpf_list):
                    all_accnt_ids.extend(_get_accnt_ids(cursor, cpf_batch))
                logs.append(f"  → {len(all_accnt_ids)} conta(s) encontrada(s).")

                # ── 1. Stage MOVEL ──────────────────────────────────────────
                logs.append(f"Criando stage MOVEL ({STAGE_MOVEL})...")
                drop_if_exists(cursor, STAGE_MOVEL)
                cursor.execute(f"CREATE TABLE {STAGE_MOVEL} (ASSET_ROW_ID VARCHAR2(30))")

                for accnt_batch in _batches(all_accnt_ids):
                    ph = ', '.join([f':{i + 1}' for i in range(len(accnt_batch))])
                    cursor.execute(f"""
                        INSERT INTO {STAGE_MOVEL} (ASSET_ROW_ID)
                        SELECT SA.ROW_ID
                        FROM SIEBEL.S_ASSET SA
                        WHERE SA.OWNER_ACCNT_ID IN ({ph})
                          AND SA.PROD_ID IN ('1-2VL6D', '1-1SGIOKK')
                          AND SA.ROW_ID = SA.ROOT_ASSET_ID
                    """, accnt_batch)
                connection.commit()

                cursor.execute(f"SELECT COUNT(*) FROM {STAGE_MOVEL}")
                movel_total = cursor.fetchone()[0]
                logs.append(f"  → {movel_total} contratos MOVEL identificados.")

                # ── 2. Stage BL ─────────────────────────────────────────────
                logs.append(f"Criando stage BL ({STAGE_BL})...")
                drop_if_exists(cursor, STAGE_BL)
                cursor.execute(f"CREATE TABLE {STAGE_BL} (ASSET_ROW_ID VARCHAR2(30))")

                for accnt_batch in _batches(all_accnt_ids):
                    ph = ', '.join([f':{i + 1}' for i in range(len(accnt_batch))])
                    cursor.execute(f"""
                        INSERT INTO {STAGE_BL} (ASSET_ROW_ID)
                        SELECT SA.ROW_ID
                        FROM SIEBEL.S_ASSET SA
                        WHERE SA.OWNER_ACCNT_ID IN ({ph})
                          AND SA.PROD_ID IN ('1-6RE2', '1-6REC')
                          AND SA.PAR_ASSET_ID = SA.ROOT_ASSET_ID
                    """, accnt_batch)
                connection.commit()

                cursor.execute(f"SELECT COUNT(*) FROM {STAGE_BL}")
                bl_total = cursor.fetchone()[0]
                logs.append(f"  → {bl_total} contratos BL identificados.")

                # ── 3. UPDATE MOVEL ─────────────────────────────────────────
                logs.append(f"Atualizando LAST_UPD em {movel_total} ROOT MOVEL (S_ASSET)...")
                cursor.execute(f"""
                    DECLARE
                        v_count NUMBER := 0;
                    BEGIN
                        FOR rec IN (SELECT ASSET_ROW_ID FROM {STAGE_MOVEL}) LOOP
                            UPDATE SIEBEL.S_ASSET
                               SET LAST_UPD    = SYSDATE,
                                   LAST_UPD_BY = '1-0'
                             WHERE ROW_ID = rec.ASSET_ROW_ID;
                            v_count := v_count + 1;
                            IF v_count >= 1000 THEN
                                COMMIT;
                                v_count := 0;
                            END IF;
                        END LOOP;
                        COMMIT;
                    END;
                """)
                logs.append("  → UPDATE MOVEL concluído.")

                # ── 4. UPDATE BL ────────────────────────────────────────────
                logs.append(f"Atualizando LAST_UPD em {bl_total} SUB_ACESSO BL (S_ASSET)...")
                cursor.execute(f"""
                    DECLARE
                        v_count NUMBER := 0;
                    BEGIN
                        FOR rec IN (SELECT ASSET_ROW_ID FROM {STAGE_BL}) LOOP
                            UPDATE SIEBEL.S_ASSET
                               SET LAST_UPD    = SYSDATE,
                                   LAST_UPD_BY = '1-0'
                             WHERE ROW_ID = rec.ASSET_ROW_ID;
                            v_count := v_count + 1;
                            IF v_count >= 1000 THEN
                                COMMIT;
                                v_count := 0;
                            END IF;
                        END LOOP;
                        COMMIT;
                    END;
                """)
                logs.append("  → UPDATE BL concluído.")

                # ── 5. Limpeza ───────────────────────────────────────────────
                drop_if_exists(cursor, STAGE_MOVEL)
                drop_if_exists(cursor, STAGE_BL)
                connection.commit()
                logs.append("Tabelas stage removidas.")
                logs.append(
                    f"\nResumo: {movel_total} MOVEL + {bl_total} BL = "
                    f"{movel_total + bl_total} contratos marcados para extração."
                )

            except Exception as e:
                logs.append(f"\nERRO: {e}")
                try:
                    connection.rollback()
                except Exception:
                    pass
                raise e

    return "\n".join(logs)
