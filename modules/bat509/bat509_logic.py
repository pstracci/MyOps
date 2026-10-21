# C:\Meus Projetos\MyOps\modules\bat509\bat509_logic.py

import oracledb
import configparser
import logging
import os
import subprocess
import time
from datetime import datetime
from modules.common import security

STAGING_TABLE = "BAT509_STAGE"


def get_config(section):
    config = configparser.ConfigParser()
    config.read('config.ini')
    if section in config:
        user = config[section].get('user', '')
        encrypted_password = config[section].get('password', '')
        dsn = config[section].get('dsn', '')
        password = security.decrypt_password(encrypted_password)
        return user, password, dsn
    raise ConnectionError(f"Seção '{section}' não encontrada no 'config.ini'.")


def _get_sqlldr_exe():
    config = configparser.ConfigParser()
    config.read('config.ini')
    client_path = config.get('general', 'instant_client_path', fallback='')
    return os.path.join(client_path, 'sqlldr.exe'), client_path


def _ensure_staging_table(cursor):
    """Cria BAT509_STAGE no schema do usuário conectado, se não existir."""
    cursor.execute("""
        BEGIN
            EXECUTE IMMEDIATE 'CREATE TABLE BAT509_STAGE (ORDER_NUM VARCHAR2(100))';
        EXCEPTION
            WHEN OTHERS THEN
                IF SQLCODE != -955 THEN RAISE; END IF;
        END;
    """)


def force_extraction(order_numbers: list, db_section_name: str, progress_callback=None):
    """
    Marca ordens para re-extração via SQL*Loader + INSERT bulk:
      1. Grava ordens em arquivo CSV
      2. sqlldr carrega na BAT509_STAGE (TRUNCATE + load)
      3. INSERT...SELECT em lote juntando staging com S_ORDER/S_ORDER_ITEM
    """
    def emit(pct, msg):
        if progress_callback:
            progress_callback(pct, msg)

    try:
        user, password, dsn = get_config(db_section_name)
    except ConnectionError as e:
        logging.error(f"BAT509 config error: {e}")
        return False, str(e)

    clean_orders = list(dict.fromkeys(o.strip() for o in order_numbers if o.strip()))
    total = len(clean_orders)
    if not clean_orders:
        return False, "Nenhuma ordem válida encontrada."

    src_file = f"BAT801_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    execution_id = int(datetime.now().timestamp())

    sqlldr_exe, client_path = _get_sqlldr_exe()
    if not os.path.exists(sqlldr_exe):
        return False, f"SQL*Loader não encontrado em: {sqlldr_exe}\nVerifique o caminho do Instant Client nas configurações."

    # --- Fase 1: Garantir staging table ---
    emit(2, f"Preparando tabela de staging ({total:,} ordens)...")
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as conn:
            with conn.cursor() as cur:
                _ensure_staging_table(cur)
    except Exception as e:
        logging.error(f"BAT509 staging table error: {e}", exc_info=True)
        return False, f"Erro ao criar tabela de staging: {e}"

    # --- Fase 2: Gravar arquivo de ordens ---
    emit(5, f"Gravando {total:,} ordens em arquivo temporário...")
    temp_dir = os.path.join(os.getcwd(), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    ts = int(time.time())
    data_file = os.path.join(temp_dir, f"bat509_{ts}.csv")
    ctl_file  = os.path.join(temp_dir, f"bat509_{ts}.ctl")
    log_file  = os.path.join(temp_dir, f"bat509_{ts}.log")
    bad_file  = os.path.join(temp_dir, f"bat509_{ts}.bad")
    dsc_file  = os.path.join(temp_dir, f"bat509_{ts}.dsc")

    try:
        with open(data_file, 'w', encoding='latin-1') as f:
            for order in clean_orders:
                f.write(f"{order}|\n")
    except Exception as e:
        return False, f"Erro ao gravar arquivo temporário: {e}"

    # --- Fase 3: Gerar CTL e rodar sqlldr ---
    emit(10, f"Carregando {total:,} ordens via SQL*Loader...")
    ctl_content = (
        f'OPTIONS (SKIP=0, ERRORS=99999, BINDSIZE=512000, ROWS=50000, DIRECT=YES)\n'
        f'LOAD DATA\n'
        f'INFILE "{data_file}"\n'
        f'BADFILE "{bad_file}"\n'
        f'DISCARDFILE "{dsc_file}"\n'
        f'TRUNCATE\n'
        f'INTO TABLE "{STAGING_TABLE}"\n'
        f'FIELDS TERMINATED BY \'|\'\n'
        f'TRAILING NULLCOLS\n'
        f'(\n"ORDER_NUM"\n)\n'
    )
    try:
        with open(ctl_file, 'w', encoding='utf-8') as f:
            f.write(ctl_content)
    except Exception as e:
        return False, f"Erro ao gerar arquivo CTL: {e}"

    env = os.environ.copy()
    env['NLS_LANG'] = '.UTF8'
    env['PATH'] = client_path + os.pathsep + env.get('PATH', '')

    sqlldr_cmd = [
        sqlldr_exe,
        f"userid={user}/{password}@{dsn}",
        f"control={ctl_file}",
        f"log={log_file}",
    ]

    sqlldr_proc = subprocess.run(
        sqlldr_cmd, capture_output=True, text=True, encoding='latin-1', env=env
    )

    sqlldr_log = ""
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='latin-1') as f:
            sqlldr_log = f.read()

    if sqlldr_proc.returncode not in (0, 2):  # 0=ok, 2=ok com warnings
        _cleanup(data_file, ctl_file, log_file, bad_file, dsc_file)
        msg = f"SQL*Loader falhou (código {sqlldr_proc.returncode})."
        if sqlldr_log:
            last_lines = "\n".join(sqlldr_log.splitlines()[-20:])
            msg += f"\n\nLog:\n{last_lines}"
        logging.error(f"BAT509 sqlldr failed: {msg}")
        return False, msg

    rows_rejected = 0
    if os.path.exists(bad_file):
        try:
            with open(bad_file, 'r', encoding='latin-1') as f:
                rows_rejected = sum(1 for line in f if line.strip())
        except Exception:
            pass

    rows_loaded = total - rows_rejected
    emit(60, f"SQL*Loader concluído. Executando marcação em lote ({rows_loaded:,} ordens)...")

    # --- Fase 4: INSERT bulk + estatísticas ---
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as conn:
            with conn.cursor() as cur:

                # INSERT em lote: staging → S_ORDER → S_ORDER_ITEM → ACC_SBL_MARC_BAT509
                cur.execute("""
                    INSERT INTO SIEBEL.ACC_SBL_MARC_BAT509 (
                        ID, CREATED, LAST_UPD, CREATED_BY, LAST_UPD_BY, SRC_FILE,
                        PROJETO, SERVICE_ID, ROW_ID, DATA_EXTRACAO, NOME_EXTRACAO
                    )
                    SELECT :exec_id,
                           TO_CHAR(SO.CREATED, 'DD-MM-YYYY HH24:MI:SS'),
                           TO_CHAR(SYSDATE, 'DD-MM-YYYY HH24:MI:SS'),
                           '0-1', '0-1', :src_file,
                           'Marcacao para extracao da BAT509',
                           SOI.X_SERVICE_ID, SO.ROW_ID, NULL, NULL
                    FROM (
                        SELECT SO2.ORDER_NUM, SO2.ROW_ID, SO2.CREATED,
                               ROW_NUMBER() OVER (
                                   PARTITION BY SO2.ORDER_NUM ORDER BY SO2.CREATED DESC
                               ) AS RN
                        FROM BAT509_STAGE STG
                        JOIN SIEBEL.S_ORDER SO2 ON SO2.ORDER_NUM = STG.ORDER_NUM
                        WHERE NOT EXISTS (
                            SELECT 1 FROM SIEBEL.ACC_SBL_MARC_BAT509 M
                            WHERE M.ROW_ID = SO2.ROW_ID
                              AND M.DATA_EXTRACAO IS NULL
                        )
                    ) SO
                    LEFT JOIN SIEBEL.S_ORDER_ITEM SOI
                        ON SO.ROW_ID = SOI.ORDER_ID
                       AND SOI.ROW_ID = SOI.ROOT_ORDER_ITEM_ID
                    WHERE SO.RN = 1
                """, exec_id=execution_id, src_file=src_file)

                rows_inserted = cur.rowcount
                emit(90, f"Inserção concluída ({rows_inserted:,} marcadas). Coletando estatísticas...")

                # Não encontradas no Siebel
                cur.execute("""
                    SELECT COUNT(*) FROM BAT509_STAGE STG
                    WHERE NOT EXISTS (
                        SELECT 1 FROM SIEBEL.S_ORDER SO
                        WHERE SO.ORDER_NUM = STG.ORDER_NUM
                    )
                """)
                not_found = cur.fetchone()[0]

            conn.commit()

    except Exception as e:
        logging.error(f"BAT509 bulk insert error: {e}", exc_info=True)
        _cleanup(data_file, ctl_file, log_file, bad_file, dsc_file)
        return False, f"Erro no banco durante INSERT bulk:\n{e}"

    _cleanup(data_file, ctl_file, log_file, bad_file, dsc_file)
    emit(100, "Concluído.")

    already_marked = max(0, rows_loaded - rows_inserted - not_found)

    summary = [f"Ordens marcadas com sucesso: {rows_inserted:,}"]
    if already_marked > 0:
        summary.append(f"Ordens já marcadas/pendentes: {already_marked:,}")
    if not_found > 0:
        summary.append(f"Ordens não encontradas no Siebel: {not_found:,}")
    if rows_rejected > 0:
        summary.append(f"Rejeitadas pelo SQL*Loader: {rows_rejected:,}")

    final_report = "\n".join(summary)
    if rows_inserted > 0:
        final_report += f"\n\nID de Execução deste lote: {execution_id}"

    return rows_inserted > 0, final_report or "Nenhuma ordem processada."


def _cleanup(*paths):
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
