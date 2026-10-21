# C:\Meus Projetos\MyOps\modules\protocolo\protocolo_logic.py

import configparser
import os
import oracledb
from modules.common import security

SIEBEL_SECTION = 'database_siebel'
SGP_SECTION    = 'database_sgp'
PROC_NAME      = 'ACC_SBL_INFO_AC_FINALIZA_PROT'

# ─────────────────────────────────────────────────────────────────────────────
# Esquema real do Siebel Pós (TIM), validado no dicionário de dados:
#   • O número de PROTOCOLO fica em S_SRV_REQ.X_PROTOCOLO (NÃO em SR_NUM).
#   • A data de fechamento é ACT_CLOSE_DT (a antiga "CLOSED_DT" não existe → ORA-00904).
#   • CPF  = S_ORG_EXT.NAME            → S_ORG_EXT.ROW_ID = S_SRV_REQ.CST_OU_ID
#   • MSISDN = S_ASSET.SERIAL_NUM      → S_ASSET.OWNER_ACCNT_ID = conta (CST_OU_ID)
#                                         / S_ASSET.ROW_ID       = S_SRV_REQ.ASSET_ID
# As relações acima também estão documentadas em SIEBEL.EXP_RELATIONSHIP_TABLE.
#
# Para nunca mais quebrar por coluna inexistente, o SELECT é montado
# dinamicamente a partir das colunas que realmente existem em S_SRV_REQ
# (ALL_TAB_COLUMNS). Campos ausentes são simplesmente ignorados.
# ─────────────────────────────────────────────────────────────────────────────

# Marcador especial '__CLOSE__': a data de fechamento real nesta instância TIM é
# X_CLOSED_DT (ACT_CLOSE_DT fica nula). Usamos COALESCE entre as candidatas que
# existirem, na ordem de prioridade abaixo.
_CLOSE_CANDIDATES = ('X_CLOSED_DT', 'ACT_CLOSE_DT', 'EXP_CLOSE_DT')

# (coluna, rótulo, é_data) — ordem = ordem de exibição.
# Subconjunto usado na LISTA de resultados (busca por CPF/MSISDN ou protocolo).
_LIST_FIELDS = [
    ('X_PROTOCOLO',    'Protocolo',        False),
    ('SR_NUM',         'SR',               False),
    ('SR_STAT_ID',     'Status',           False),
    ('SR_SUB_STAT_ID', 'Substatus',        False),
    ('SR_TYPE_CD',     'Tipo',             False),
    ('SR_AREA',        'Área',             False),
    ('SR_SUB_AREA',    'Subárea',          False),
    ('CREATED',        'Criado em',        True),
    ('__CLOSE__',      'Fechado em',       True),
]

# Conjunto completo usado no DETALHE de um único protocolo.
_DETAIL_FIELDS = [
    ('X_PROTOCOLO',     'Protocolo',            False),
    ('X_PROTOCOLO_PAI', 'Protocolo Pai',        False),
    ('SR_NUM',          'SR (Nº)',              False),
    ('SR_STAT_ID',      'Status',               False),
    ('SR_SUB_STAT_ID',  'Substatus',            False),
    ('SR_TYPE_CD',      'Tipo',                 False),
    ('SR_CAT_TYPE_CD',  'Categoria',            False),
    ('SR_AREA',         'Área',                 False),
    ('SR_SUB_AREA',     'Subárea',              False),
    ('SR_SEV_CD',       'Severidade',           False),
    ('SR_PRIO_CD',      'Prioridade',           False),
    ('CREATED',         'Protocolo/SR criado em', True),
    ('SR_CREATED_DT',   'SR criada em',         True),
    ('SR_STAT_DT',      'Data do status',       True),
    ('__CLOSE__',       'Fechado em',           True),
    ('LAST_UPD',        'Última atualização',   True),
]


# ─── Conexão / config ───────────────────────────────────────────────────────

def get_config(section):
    config = configparser.ConfigParser()
    config.read('config.ini')
    if section not in config:
        raise ConnectionError(f"Seção '{section}' não encontrada no config.ini.")
    user = config[section].get('user', '')
    enc  = config[section].get('password', '')
    dsn  = config[section].get('dsn', config[section].get('url', ''))
    return user, security.decrypt_password(enc), dsn


def _init_thick():
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')
        client_path = config.get('general', 'instant_client_path', fallback=None)
        if client_path and os.path.isdir(client_path):
            oracledb.init_oracle_client(lib_dir=client_path)
    except Exception:
        pass


def is_sgp_configured():
    # O SGP é acessado via DB LINK a partir da própria conexão Siebel Pós
    # (não usa conexão TNS própria). Logo, está disponível sempre que o
    # Siebel Pós estiver configurado.
    return True


def _connect_siebel():
    _init_thick()
    user, password, dsn = get_config(SIEBEL_SECTION)
    return oracledb.connect(user=user, password=password, dsn=dsn)


# ─── Introspecção de colunas (resiliência a ORA-00904) ──────────────────────

def _existing_sr_columns(cursor):
    """Colunas realmente existentes em SIEBEL.S_SRV_REQ (upper-case)."""
    cursor.execute(
        """
        SELECT column_name FROM all_tab_columns
        WHERE owner = 'SIEBEL' AND table_name = 'S_SRV_REQ'
        """
    )
    return {r[0].upper() for r in cursor.fetchall()}


def _build_select(fields, existing, alias='sr'):
    """Monta (lista_de_expressões, lista_de_rótulos) só com colunas existentes."""
    exprs, labels = [], []
    for col, label, is_date in fields:
        if col == '__CLOSE__':
            cc = [c for c in _CLOSE_CANDIDATES if c in existing]
            if not cc:
                continue
            inner = ", ".join(f"{alias}.{c}" for c in cc)
            exprs.append(f"TO_CHAR(COALESCE({inner}), 'DD/MM/YYYY HH24:MI:SS')")
            labels.append(label)
        elif col in existing:
            if is_date:
                exprs.append(f"TO_CHAR({alias}.{col}, 'DD/MM/YYYY HH24:MI:SS')")
            else:
                exprs.append(f"{alias}.{col}")
            labels.append(label)
    return exprs, labels


def _fmt(v):
    return str(v) if v is not None else '—'


# ─── Busca de protocolos (lista) ────────────────────────────────────────────

MAX_RESULTS = 500


def _subqueries_for_mode(identifier, mode, existing):
    """
    Lista de (where_clause, binds) — cada uma usa UM predicado indexado, para
    performance. Evita OR entre colunas diferentes (que causa full scan em
    S_SRV_REQ). Os resultados são unidos/deduplicados em Python.
    """
    if mode == 'cpf':
        # CPF em S_ORG_EXT.NAME (indexado); conta (ROW_ID) liga em CST_OU_ID.
        return [(
            "sr.CST_OU_ID IN (SELECT ROW_ID FROM SIEBEL.S_ORG_EXT WHERE NAME = :id)",
            {'id': identifier},
        )]

    if mode == 'msisdn':
        # MSISDN = S_ASSET.SERIAL_NUM (indexado). Duas buscas indexadas separadas:
        #  1) protocolos da própria linha (ASSET_ID)
        #  2) protocolos da conta dona da linha (OWNER_ACCNT_ID = CST_OU_ID)
        return [
            ("sr.ASSET_ID IN (SELECT ROW_ID FROM SIEBEL.S_ASSET WHERE SERIAL_NUM = :id)",
             {'id': identifier}),
            ("sr.CST_OU_ID IN (SELECT OWNER_ACCNT_ID FROM SIEBEL.S_ASSET WHERE SERIAL_NUM = :id)",
             {'id': identifier}),
        ]

    # 'protocolo' (padrão): X_PROTOCOLO (indexado) e SR_NUM (indexado), separados.
    subs = []
    if 'X_PROTOCOLO' in existing:
        subs.append(("sr.X_PROTOCOLO = :id", {'id': identifier}))
    subs.append(("sr.SR_NUM = :id", {'id': identifier}))
    return subs


def search_protocols(identifier, mode):
    """
    Busca protocolos/SRs no Siebel Pós (apenas leitura).

    mode:
      'protocolo' → por número de protocolo (S_SRV_REQ.X_PROTOCOLO, fallback SR_NUM)
      'cpf'       → todos os protocolos do cliente (S_ORG_EXT.NAME = CPF)
      'msisdn'    → todos os protocolos da linha/cliente (S_ASSET.SERIAL_NUM = MSISDN)

    Retorna dict: {'columns': [rótulos...], 'rows': [[valores...], ...], 'count': n}
    """
    identifier = str(identifier).strip()
    if not identifier:
        return {'columns': [], 'rows': [], 'count': 0}

    with _connect_siebel() as conn:
        with conn.cursor() as cur:
            cur.callTimeout = 45000  # 45 s por statement
            existing = _existing_sr_columns(cur)
            exprs, labels = _build_select(_LIST_FIELDS, existing, alias='sr')

            # Cada subquery traz: ROW_ID (dedup), CREATED (ordenação) + campos visíveis.
            merged = {}  # ROW_ID -> (created_dt, [valores formatados])
            for where, binds in _subqueries_for_mode(identifier, mode, existing):
                sql = f"""
                    SELECT sr.ROW_ID, sr.CREATED, {', '.join(exprs)}
                    FROM SIEBEL.S_SRV_REQ sr
                    WHERE {where} AND ROWNUM <= {MAX_RESULTS}
                """
                cur.execute(sql, binds)
                for r in cur.fetchall():
                    row_id, created = r[0], r[1]
                    if row_id not in merged:
                        merged[row_id] = (created, [_fmt(v) for v in r[2:]])
                # 'protocolo': se já achou por X_PROTOCOLO, não precisa do fallback SR_NUM
                if mode == 'protocolo' and merged:
                    break

            ordered = sorted(
                merged.values(),
                key=lambda t: (t[0] is not None, t[0]),
                reverse=True,
            )[:MAX_RESULTS]
            rows = [vals for _created, vals in ordered]
            return {'columns': labels, 'rows': rows, 'count': len(rows)}


# ─── Detalhe de um protocolo ────────────────────────────────────────────────

def get_protocol_status_siebel(protocol_num):
    """
    Detalhe de um único protocolo (lista de pares (rótulo, valor)) ou None.
    Inclui dados do cliente (CPF) e da linha (MSISDN) via LEFT JOIN.
    """
    protocol_num = str(protocol_num).strip()
    with _connect_siebel() as conn:
        with conn.cursor() as cur:
            cur.callTimeout = 60000
            existing = _existing_sr_columns(cur)
            exprs, labels = _build_select(_DETAIL_FIELDS, existing, alias='sr')

            # Enriquecimento: CPF (conta) e MSISDN (linha), quando as FKs existem.
            extra_exprs, extra_labels = [], []
            if 'CST_OU_ID' in existing:
                extra_exprs.append("oe.NAME")
                extra_labels.append("CPF/Documento (conta)")
            if 'ASSET_ID' in existing:
                extra_exprs.append("ast.SERIAL_NUM")
                extra_labels.append("MSISDN (linha)")

            join_cpf = ("LEFT JOIN SIEBEL.S_ORG_EXT oe ON oe.ROW_ID = sr.CST_OU_ID"
                        if 'CST_OU_ID' in existing else "")
            join_ast = ("LEFT JOIN SIEBEL.S_ASSET ast ON ast.ROW_ID = sr.ASSET_ID"
                        if 'ASSET_ID' in existing else "")

            all_exprs = exprs + extra_exprs
            all_labels = labels + extra_labels

            base = f"""
                SELECT {', '.join(all_exprs)}
                FROM SIEBEL.S_SRV_REQ sr
                {join_cpf}
                {join_ast}
                WHERE {{pred}} AND ROWNUM = 1
            """
            # Tenta por protocolo (indexado) e, se não achar, por SR_NUM (indexado).
            for where, _b in _subqueries_for_mode(protocol_num, 'protocolo', existing):
                cur.execute(base.format(pred=where), {'id': protocol_num})
                row = cur.fetchone()
                if row is not None:
                    return list(zip(all_labels, [_fmt(v) for v in row]))
            return None


# ─── SGP (via DB LINK do Siebel Pós → SGP) ───────────────────────────────────
# Em vez de uma conexão TNS própria ao SGP, consultamos a tabela remota
# SGP001.TB_PROTOCOLO através do DB LINK LK_GPP1_SGP001_01, usando a conexão
# Siebel Pós já existente.

SGP_DBLINK       = 'LK_GPP1_SGP001_01'
SGP_REMOTE_TABLE = f'SGP001.TB_PROTOCOLO@{SGP_DBLINK}'
SGP_CONFIG_TABLE = f'SGP001.TB_CONFIG@{SGP_DBLINK}'

# Os códigos numéricos do SGP são traduzidos pela tabela de configuração do
# gerador (SGP001.TB_CONFIG: GRP + KEY + VALUE). Cada campo codificado abaixo
# resolve a descrição via subquery escalar por (GRP, KEY), tudo no lado remoto.
# STATUS_SIEBEL espelha o SR_STAT_ID do Siebel (ex.: 25 = "Fechado Em Linha").
def _cfg(grp, key_expr):
    return (f"(SELECT c.VALUE FROM {SGP_CONFIG_TABLE} c "
            f"WHERE c.GRP = '{grp}' AND c.KEY = {key_expr})")

_SGP_QUERY = f"""
    SELECT
        p.ID_PROT,
        p.STATUS,            {_cfg('ENUM.STATUS_PROT',          'TO_CHAR(p.STATUS)')},
        p.STATUS_SIEBEL,     {_cfg('ENUM.STATUS_SIEBEL',        'TO_CHAR(p.STATUS_SIEBEL)')},
        p.SERVICO_RECLAMADO, {_cfg('ENUM.TP_SERVICO_RECLAMADO', 'TO_CHAR(p.SERVICO_RECLAMADO)')},
        p.CANAL,             {_cfg('ENUM.CHANNEL',              'TO_CHAR(p.CANAL)')},
        p.TIPO_INTERACAO,    {_cfg('ENUM.TP_INT',               'TO_CHAR(p.TIPO_INTERACAO)')},
        p.DIRECAO,           {_cfg('ENUM.DIRECAO',              'TO_CHAR(p.DIRECAO)')},
        p.DOCUMENTO,
        p.MSISDN,
        TO_CHAR(p.DT_CRIACAO,      'DD/MM/YYYY HH24:MI:SS'),
        TO_CHAR(p.DATA_FECHAMENTO, 'DD/MM/YYYY HH24:MI:SS'),
        TO_CHAR(p.DT_ATUALIZA,     'DD/MM/YYYY HH24:MI:SS')
    FROM {SGP_REMOTE_TABLE} p
    WHERE p.ID_PROT = :1
"""


def _coded(code, desc):
    """Formata 'Descrição (código)'; só código se não houver descrição; '—' se vazio."""
    if code is None or str(code).strip() == '':
        return '—'
    desc = (desc or '').strip()
    return f"{desc} ({code})" if desc else str(code)


def get_protocol_status_sgp(protocol_num):
    """
    Detalhe do protocolo no SGP (gerador), via DB LINK a partir do Siebel Pós,
    com os códigos já traduzidos para texto pela tabela de configuração.
    Retorna list[(label, value)] ou None se não encontrado.
    """
    with _connect_siebel() as conn:
        with conn.cursor() as cur:
            cur.callTimeout = 60000
            cur.execute(_SGP_QUERY, [str(protocol_num).strip()])
            row = cur.fetchone()
            if row is None:
                return None
            (id_prot,
             status, status_d,
             status_sbl, status_sbl_d,
             servico, servico_d,
             canal, canal_d,
             tp_int, tp_int_d,
             direcao, direcao_d,
             documento, msisdn,
             dt_criacao, dt_fech, dt_atualiza) = row
            return [
                ("Número Protocolo",          _fmt(id_prot)),
                ("Status",                    _coded(status, status_d)),
                ("Status Siebel (SR_STAT_ID)", _coded(status_sbl, status_sbl_d)),
                ("Serviço Reclamado",         _coded(servico, servico_d)),
                ("Canal",                     _coded(canal, canal_d)),
                ("Tipo Interação",            _coded(tp_int, tp_int_d)),
                ("Direção",                   _coded(direcao, direcao_d)),
                ("CPF/Documento",             _fmt(documento)),
                ("MSISDN",                    _fmt(msisdn)),
                ("Criado em",                 _fmt(dt_criacao)),
                ("Fechado em",                _fmt(dt_fech)),
                ("Atualizado em",             _fmt(dt_atualiza)),
            ]


# ─── Procedure de finalização ───────────────────────────────────────────────

def get_procedure_signature():
    """Retorna list[(arg_name, position, data_type, in_out)] do dicionário."""
    with _connect_siebel() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ARGUMENT_NAME, POSITION, DATA_TYPE, IN_OUT
                FROM   ALL_ARGUMENTS
                WHERE  OBJECT_NAME = :1
                ORDER  BY POSITION
            """, [PROC_NAME])
            return cur.fetchall()


def finalizar_protocolo(protocol_num):
    """
    Chama ACC_SBL_INFO_AC_FINALIZA_PROT para o protocolo informado.
    Retorna string de resultado (do OUT param quando existir, ou mensagem de sucesso).
    """
    sig = []
    try:
        sig = get_procedure_signature()
    except Exception:
        pass

    out_params = [(name, dtype) for name, pos, dtype, direction in sig
                  if direction in ('OUT', 'IN/OUT') and pos > 0]

    with _connect_siebel() as conn:
        with conn.cursor() as cur:
            if out_params:
                out_vars = {}
                call_args = [str(protocol_num).strip()]
                for name, dtype in out_params:
                    v = cur.var(oracledb.NUMBER) if dtype == 'NUMBER' else cur.var(oracledb.STRING)
                    call_args.append(v)
                    out_vars[name] = v

                cur.callproc(PROC_NAME, call_args)
                conn.commit()

                results = {k: v.getvalue() for k, v in out_vars.items()}
                parts = [f"{k}={v}" for k, v in results.items() if v is not None]
                return "Finalizado. " + ("; ".join(parts) if parts else "OK")
            else:
                cur.callproc(PROC_NAME, [str(protocol_num).strip()])
                conn.commit()
                return "Protocolo finalizado com sucesso."
