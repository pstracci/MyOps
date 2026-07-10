# C:\Meus Projetos\MyOps\modules\payment_method\payment_method_logic.py

import os
import re
import time
import shutil
import oracledb

# Reutiliza a infraestrutura já consolidada do módulo SQL*Loader
# (leitura de config, modo thick, execução do sqlldr).
from modules.sql_loader import sql_loader_logic as loader

# Reexporta utilitários usados pela UI
get_config = loader.get_config
init_thick_mode = loader.init_thick_mode
get_all_db_connections = loader.get_all_db_connections
run_sql_loader = loader.run_sql_loader

# --- Operações suportadas ---------------------------------------------------
# OP_FATURA : Débito Automático  -> Fatura   (arquivo só com CUSTOMER_ID)
# OP_DACC   : Fatura             -> Débito Automático / DACC
#             (arquivo com CUSTOMER_ID; CODIGO_BANCO_RMA; AGENCIA; CONTA)
OP_FATURA = "FATURA"
OP_DACC = "DACC"

# Valor gravado em S_INV_PROF.PAYMT_METH_CD para cada método.
# (mantém a grafia exata utilizada na base Siebel, conforme script de referência)
METHOD_FATURA = "Fatura"
METHOD_DACC = "Débito Automatico"

# Estado de origem esperado para cada operação (usado para filtrar candidatos)
FROM_METHOD = {
    OP_FATURA: METHOD_DACC,   # sai de Débito Automático
    OP_DACC: METHOD_FATURA,   # sai de Fatura
}
TO_METHOD = {
    OP_FATURA: METHOD_FATURA,
    OP_DACC: METHOD_DACC,
}

# Colunas da tabela temporária carregada pelo SQL*Loader, por operação.
# A ordem reflete o layout dos arquivos de entrada.
COLUMNS = {
    OP_FATURA: [("CUSTOMER_ID", "NUMBER")],
    OP_DACC: [
        ("CUSTOMER_ID", "NUMBER"),
        ("CODIGO_BANCO_RMA", "VARCHAR2(100)"),
        ("AGENCIA", "VARCHAR2(100)"),
        ("CONTA", "VARCHAR2(100)"),
    ],
}


# Query de conferência exibida no log ao final do processamento.
VERIFY_QUERY = """SELECT h.payment_meth                         AS metodo_gravado,
       CASE WHEN b.paymt_meth_cd = h.payment_meth
            THEN 'OK - alterado'
            ELSE 'DIVERGENTE'
       END                                     AS situacao,
       COUNT(*)                                AS qtd
  FROM acc_sbl_wa_dacc_hist h
  JOIN s_inv_prof b
    ON b.name = h.customer_id
 WHERE TRUNC(h.exec_date) = TRUNC(SYSDATE)
 GROUP BY h.payment_meth,
          CASE WHEN b.paymt_meth_cd = h.payment_meth
               THEN 'OK - alterado'
               ELSE 'DIVERGENTE'
          END
 ORDER BY metodo_gravado, situacao;"""


def validate_table_name(table_name, max_len=26):
    """
    Valida e higieniza o nome da tabela temporária.
    Regra de segurança: precisa começar com PM_TMP e conter apenas
    caracteres válidos para identificadores Oracle.

    O limite padrão (26) garante que a tabela filtrada derivada
    (sufixo '_F2') não ultrapasse 30 caracteres.
    Retorna o nome já em maiúsculas.
    """
    table_name = (table_name or "").strip()
    if not table_name:
        raise ValueError("O nome da tabela temporária é obrigatório.")

    sane = re.sub(r'[^A-Za-z0-9_$#]', '', table_name).upper()
    if sane != table_name.upper():
        raise ValueError("O nome da tabela contém caracteres inválidos.")

    if not sane.startswith("PM_TMP"):
        raise ValueError("Operação não permitida. O nome da tabela deve começar com 'PM_TMP'.")

    if len(sane) > max_len:
        raise ValueError(f"O nome da tabela não pode exceder {max_len} caracteres.")

    return sane


# --- Análise / preview do arquivo de entrada --------------------------------

def _detect_delimiter(header_line):
    """Detecta o delimitador com base na linha de cabeçalho."""
    for delim in (';', ',', '\t', '|'):
        if delim in header_line:
            return delim
    return None  # arquivo de coluna única


def _read_text_lines(file_path, max_lines=None):
    """Lê o arquivo tentando UTF-8 (com BOM) e caindo para latin-1."""
    for encoding in ('utf-8-sig', 'latin-1'):
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                if max_lines is None:
                    return [ln.rstrip('\r\n') for ln in f]
                lines = []
                for i, ln in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(ln.rstrip('\r\n'))
                return lines
        except UnicodeDecodeError:
            continue
    raise RuntimeError("Não foi possível decodificar o arquivo (UTF-8/latin-1).")


def analyze_file(file_path, preview_rows=50):
    """
    Analisa o arquivo de entrada e devolve um dicionário com as informações
    necessárias para o preview e para a decisão de qual operação liberar.

    Retorno:
        {
          'delimiter':   str | None,
          'has_header':  bool,
          'skip':        int (linhas a pular no SQL*Loader),
          'column_count':int,
          'headers':     [str, ...]  (nomes exibidos no preview),
          'rows':        [[str, ...], ...]  (amostra),
          'total_rows':  int (linhas de dados, excluindo cabeçalho/vazias),
          'dacc_capable':bool (arquivo possui dados bancários),
        }
    """
    sample = _read_text_lines(file_path, max_lines=preview_rows + 1)
    sample = [ln for ln in sample if ln.strip() != ""]
    if not sample:
        raise ValueError("O arquivo está vazio.")

    header_line = sample[0]
    delimiter = _detect_delimiter(header_line)

    def split(line):
        return line.split(delimiter) if delimiter else [line]

    first_fields = [c.strip() for c in split(header_line)]
    # É cabeçalho quando o primeiro campo (customer_id) não é numérico.
    has_header = not re.fullmatch(r'\d+', first_fields[0] or '')

    if has_header:
        headers = [h.strip() for h in first_fields]
        data_lines = sample[1:]
    else:
        column_count = len(first_fields)
        headers = ([c for c, _ in COLUMNS[OP_DACC]] if column_count >= 4
                   else [c for c, _ in COLUMNS[OP_FATURA]])[:column_count]
        data_lines = sample

    rows = [[c.strip() for c in split(ln)] for ln in data_lines[:preview_rows]]
    column_count = len(headers)
    dacc_capable = column_count >= 4

    # Contagem total de linhas de dados (leitura completa; arquivos são pequenos).
    all_lines = _read_text_lines(file_path)
    non_empty = sum(1 for ln in all_lines if ln.strip() != "")
    total_rows = non_empty - (1 if has_header else 0)

    return {
        'delimiter': delimiter,
        'has_header': has_header,
        'skip': 1 if has_header else 0,
        'column_count': column_count,
        'headers': headers,
        'rows': rows,
        'total_rows': max(total_rows, 0),
        'dacc_capable': dacc_capable,
    }


# --- Criação da tabela temporária e carga -----------------------------------

def create_temp_table(db_key, table_name, operation):
    """
    Cria (drop + create) a tabela temporária no schema do usuário conectado,
    com as colunas adequadas à operação escolhida.
    Retorna (table_name, schema).
    """
    table_name = validate_table_name(table_name)
    if operation not in COLUMNS:
        raise ValueError(f"Operação inválida: {operation}")

    init_thick_mode()
    user, password, dsn = get_config(db_key)

    column_defs = ", ".join(f'"{name}" {ctype}' for name, ctype in COLUMNS[operation])

    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        with connection.cursor() as cursor:
            _drop_table_if_exists(cursor, table_name)
            cursor.execute(f'CREATE TABLE "{table_name}" ({column_defs})')

    return table_name, user


def _drop_table_if_exists(cursor, table_name):
    try:
        cursor.execute(f'DROP TABLE "{table_name}"')
    except oracledb.DatabaseError as e:
        # ORA-00942: tabela não existe -> comportamento esperado.
        if 'ORA-00942' not in str(e):
            raise


def generate_control_file(file_path, table_name, schema, operation, delimiter, skip):
    """
    Gera o control file do SQL*Loader para a operação/arquivo informados.

    O arquivo de entrada é copiado para o diretório temporário com um nome
    100% ASCII, pois o SQL*Loader não abre caminhos com caracteres acentuados
    ou especiais (ex.: "Atualização", "contém"). Retorna (ctl_path, data_copy).
    O chamador deve remover 'data_copy' após a carga.
    """
    temp_dir = os.path.join(os.getcwd(), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    file_base = f"pm_sqlldr_{int(time.time())}_{os.getpid()}"
    ctl_path = os.path.join(temp_dir, f"{file_base}.ctl")

    # Cópia do arquivo de entrada com nome ASCII seguro.
    data_copy = os.path.join(temp_dir, f"{file_base}.dat")
    shutil.copyfile(file_path, data_copy)

    data_file = f'"{data_copy}"'
    bad_file = f'"{os.path.join(temp_dir, f"{file_base}.bad")}"'
    discard_file = f'"{os.path.join(temp_dir, f"{file_base}.dsc")}"'

    # Delimitador: se o arquivo tem coluna única, usamos vírgula (irrelevante).
    field_delim = delimiter if delimiter else ','

    column_list = ",\n".join(f'"{name}"' for name, _ in COLUMNS[operation])

    ctl_content = f"""
OPTIONS (SKIP={int(skip)}, ERRORS=99999, BINDSIZE=1048576, ROWS=50000)
LOAD DATA
CHARACTERSET UTF8
INFILE {data_file}
BADFILE {bad_file}
DISCARDFILE {discard_file}
APPEND
INTO TABLE "{schema.upper()}"."{table_name.upper()}"
FIELDS TERMINATED BY '{field_delim}'
TRAILING NULLCOLS
(
{column_list}
)
"""
    with open(ctl_path, 'w', encoding='utf-8') as f:
        f.write(ctl_content)
    return ctl_path, data_copy


def count_table_rows(db_key, table_name):
    """Conta as linhas de uma tabela (temporária ou filtrada)."""
    table_name = validate_table_name(table_name, max_len=30)
    init_thick_mode()
    user, password, dsn = get_config(db_key)
    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            return cursor.fetchone()[0]


# --- Preparação (tabela filtrada de candidatos) -----------------------------

def build_filtered_table(db_key, base_table, operation):
    """
    Cria a tabela filtrada (<base>_F2) contendo apenas os clientes do arquivo
    que ainda estão no estado de ORIGEM esperado (e portanto serão realmente
    alterados). Devolve (filtered_table, candidate_count).
    """
    base_table = validate_table_name(base_table)
    filtered_table = validate_table_name(base_table + "_F2", max_len=30)
    from_method = FROM_METHOD[operation]

    init_thick_mode()
    user, password, dsn = get_config(db_key)

    create_sql = (
        f'CREATE TABLE "{filtered_table}" AS '
        f'SELECT a.* FROM "{base_table}" a '
        f'WHERE EXISTS (SELECT 1 FROM s_inv_prof b '
        f'             WHERE b.name = TO_CHAR(a.customer_id) '
        f'               AND b.paymt_meth_cd = :from_method)'
    )

    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        with connection.cursor() as cursor:
            _drop_table_if_exists(cursor, filtered_table)
            # DDL não aceita bind; injeta o valor de forma segura (literal fixo).
            cursor.execute(create_sql.replace(':from_method',
                                              "'" + from_method.replace("'", "''") + "'"))
            cursor.execute(f'SELECT COUNT(*) FROM "{filtered_table}"')
            candidate_count = cursor.fetchone()[0]

    return filtered_table, candidate_count


# --- Execução da alteração ---------------------------------------------------

def _build_update_block(filtered_table, operation, notify):
    """
    Monta o bloco PL/SQL de atualização conforme a operação.

    Quando 'notify' é True, o UPDATE também seta x_tim_eai_status='Pendente'
    e x_tim_payment_change='Y', que são os gatilhos de propagação/notificação
    da alteração para o BSCS e o RMCA. Quando False (padrão), apenas o método
    de pagamento e a data de modificação são atualizados.
    """
    # Colunas extras que disparam a notificação para BSCS/RMCA.
    notify_clause = (
        ",\n               x_tim_eai_status = 'Pendente',"
        "\n               x_tim_payment_change = 'Y'"
    ) if notify else ""

    if operation == OP_FATURA:
        set_clause = f"""
           SET paymt_meth_cd = '{METHOD_FATURA}',
               bk_accnt_num = NULL,
               bank_name = NULL,
               bank_branch = NULL,
               x_tim_pmnt_type_mod_dt = TRUNC(SYSDATE){notify_clause}"""
        hist_method = METHOD_FATURA
    else:  # OP_DACC
        set_clause = f"""
           SET paymt_meth_cd = '{METHOD_DACC}',
               bk_accnt_num = TRIM(REPLACE(rec.conta, CHR(13), '')),
               bank_name = TRIM(REPLACE(rec.codigo_banco_rma, CHR(13), '')),
               bank_branch = TRIM(REPLACE(rec.agencia, CHR(13), '')),
               x_tim_pmnt_type_mod_dt = TRUNC(SYSDATE){notify_clause}"""
        hist_method = METHOD_DACC

    return f"""
DECLARE
    vCount   NUMBER := 0;
    vUpdated NUMBER := 0;
BEGIN
    FOR rec IN (SELECT * FROM "{filtered_table}") LOOP

        UPDATE s_inv_prof
        {set_clause}
         WHERE name = TO_CHAR(rec.customer_id);

        vUpdated := vUpdated + SQL%ROWCOUNT;

        INSERT INTO ACC_SBL_WA_DACC_HIST (customer_id, payment_meth, exec_date)
        VALUES (TO_CHAR(rec.customer_id), '{hist_method}', SYSDATE);

        vCount := vCount + 1;

        IF vCount >= :batch_size THEN
            COMMIT;
            DBMS_LOCK.SLEEP(:sleep_seconds);
            vCount := 0;
        END IF;

    END LOOP;
    COMMIT;
    :updated_out := vUpdated;
END;
"""


def run_payment_update(db_key, filtered_table, operation, batch_size, sleep_seconds, notify=False):
    """
    Executa o bloco PL/SQL que altera o método de pagamento sobre a tabela
    filtrada (<base>_F2) e registra o histórico em ACC_SBL_WA_DACC_HIST.

    Se 'notify' for True, o UPDATE também dispara a notificação para
    BSCS/RMCA (x_tim_eai_status='Pendente', x_tim_payment_change='Y').
    Retorna a quantidade de linhas efetivamente atualizadas em S_INV_PROF.
    """
    filtered_table = validate_table_name(filtered_table, max_len=30)
    if operation not in (OP_FATURA, OP_DACC):
        raise ValueError(f"Operação inválida: {operation}")

    try:
        batch_size = int(batch_size)
    except (TypeError, ValueError):
        raise ValueError("A quantidade de clientes por lote deve ser um número inteiro.")
    if batch_size < 1:
        raise ValueError("A quantidade de clientes por lote deve ser maior ou igual a 1.")

    try:
        sleep_seconds = int(sleep_seconds)
    except (TypeError, ValueError):
        raise ValueError("A duração do sleep deve ser um número inteiro (segundos).")
    if sleep_seconds < 0:
        raise ValueError("A duração do sleep não pode ser negativa.")

    plsql_block = _build_update_block(filtered_table, operation, notify)

    init_thick_mode()
    user, password, dsn = get_config(db_key)
    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        with connection.cursor() as cursor:
            updated_out = cursor.var(oracledb.NUMBER)
            try:
                cursor.execute(plsql_block, {
                    'batch_size': batch_size,
                    'sleep_seconds': sleep_seconds,
                    'updated_out': updated_out,
                })
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            return int(updated_out.getvalue() or 0)


def drop_temp_tables(db_key, *table_names):
    """Remove tabelas temporárias/filtradas ao final do processo (best-effort)."""
    init_thick_mode()
    user, password, dsn = get_config(db_key)
    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        with connection.cursor() as cursor:
            for tname in table_names:
                if not tname:
                    continue
                try:
                    _drop_table_if_exists(cursor, validate_table_name(tname, max_len=30))
                except Exception:
                    pass
