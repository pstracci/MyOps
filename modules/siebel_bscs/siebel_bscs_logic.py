# C:\Meus Projetos\MyOps\modules\siebel_bscs\siebel_bscs_logic.py

import oracledb
import configparser
from modules.common import security

# ... Funções get_database_sections, get_config, etc. (sem alterações) ...
def get_database_sections():
    config = configparser.ConfigParser(); config.read('config.ini')
    return [s for s in config.sections() if s.startswith('database_')]

def get_config(section):
    config = configparser.ConfigParser(); config.read('config.ini')
    if section in config:
        user = config[section].get('user', ''); encrypted_password = config[section].get('password', '')
        dsn = config[section].get('dsn', ''); password = security.decrypt_password(encrypted_password) if encrypted_password else ''
        return user, password, dsn
    raise ConnectionError(f"Seção '{section}' não encontrada no 'config.ini'.")

def _convert_row_to_dict(cursor, row):
    if row is None: return None
    return dict(zip([d[0].upper() for d in cursor.description], row))

def _convert_fetchall_to_dict_list(cursor, rows):
    if not rows: return []
    cols = [d[0].upper() for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]

def get_comparison_data(msisdn, db_section):
    user, password, dsn = get_config(db_section)
    all_data = {
        "siebel": {"profile": None, "assets": []},
        "bscsix": {"profile": None, "services": []},
        "validation": {"plan_match_status": "N/A"},
        "comparison": {}
    }
    try:
        with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
            with connection.cursor() as cursor:
                all_data["siebel"] = _get_siebel_customer_and_assets(cursor, msisdn)
                all_data["bscsix"] = _get_bscsix_full_profile_and_services(cursor, msisdn)
                
                siebel_plan_code = all_data["siebel"].get("profile", {}).get('PLANO_CODIGO')
                bscsix_plan_code = all_data["bscsix"].get("profile", {}).get('PLANO_CODIGO')
                if siebel_plan_code and bscsix_plan_code:
                    all_data["validation"] = _validate_plans(cursor, siebel_plan_code, bscsix_plan_code)
                
                # CORREÇÃO: Chamando a função de comparação por código
                all_data["comparison"] = _compare_assets_and_services_by_code(cursor, all_data["siebel"]["assets"], all_data["bscsix"]["services"])
    except oracledb.DatabaseError as e:
        error, = e.args; raise Exception(f"Erro de banco de dados: {error.message.strip()}")
    return all_data

def _get_siebel_customer_and_assets(cursor, msisdn):
    # ... (Esta função já está correta e não precisa de alterações) ...
    data = {"profile": None, "assets": []}
    query = """
        SELECT c.name as cpf_cnpj, c.alias_name as nome_cliente, c.cust_stat_cd as status_cliente,
               a.serial_num, a.status_cd as status_asset, a.bill_profile_id,
               p.name as nome_produto, p.part_num as codigo_produto, p.category_cd,
               a.integration_id, a.x_integ_id
        FROM siebel.s_asset a
        JOIN siebel.s_org_ext c ON c.row_id = a.owner_accnt_id
        JOIN siebel.s_prod_int p ON a.prod_id = p.row_id
        WHERE a.root_asset_id IN (
            SELECT root_asset_id FROM siebel.s_asset
            WHERE serial_num = :msisdn AND status_cd <> 'Cancelado' AND ROWNUM = 1
        ) AND a.status_cd <> 'Cancelado' ORDER BY p.name
    """
    cursor.execute(query, msisdn=msisdn)
    assets = _convert_fetchall_to_dict_list(cursor, cursor.fetchall())
    if assets:
        main_asset = next((asset for asset in assets if asset.get('SERIAL_NUM') == msisdn), assets[0])
        plan_asset = next((asset for asset in assets if asset.get('CATEGORY_CD') == 'PLANO'), main_asset)
        custcode = None
        billing_profile_id = main_asset.get('BILL_PROFILE_ID')
        if billing_profile_id:
            custcode_query = "SELECT x_custcode FROM siebel.s_inv_prof WHERE row_id = :bpid"
            cursor.execute(custcode_query, bpid=billing_profile_id)
            custcode_result = cursor.fetchone()
            if custcode_result: custcode = custcode_result[0]
        data["profile"] = {
            'NOME_CLIENTE': main_asset.get('NOME_CLIENTE'), 'CPF_CNPJ': main_asset.get('CPF_CNPJ'),
            'STATUS_CLIENTE': main_asset.get('STATUS_CLIENTE'), 'CO_ID': main_asset.get('X_INTEG_ID'),
            'STATUS_ASSET': main_asset.get('STATUS_ASSET'),
            'PLANO_NOME': plan_asset.get('NOME_PRODUTO'), 'PLANO_CODIGO': plan_asset.get('CODIGO_PRODUTO'),
            'CUSTCODE': custcode
        }
        data["assets"] = assets
    return data

def _get_bscsix_full_profile_and_services(cursor, msisdn):
    # ... (Esta função já está correta e não precisa de alterações) ...
    data = {"profile": None, "services": []}
    profile_query = "SELECT CUSTOMER_ID, CUSTCODE, CO_ID, CH_STATUS FROM ssplunk001.PM_SPLUNK_CASCADE_POS_FIBER@LK_BSCSIX_SYSADM_001 WHERE msisdn = :msisdn and CH_STATUS = 'a'"
    cursor.execute(profile_query, msisdn=msisdn)
    profile_data = _convert_row_to_dict(cursor, cursor.fetchone())
    if not profile_data: return data
    customer_id = profile_data.get('CUSTOMER_ID')
    if customer_id:
        contact_query = "SELECT ccfname, cssocialsecno FROM ccontact_all@LK_BSCSIX_SYSADM_001 WHERE customer_id = :cid AND ccbill = 'X'"
        cursor.execute(contact_query, cid=customer_id)
        contact_data = _convert_row_to_dict(cursor, cursor.fetchone())
        if contact_data: profile_data.update(contact_data)
    contract_id = profile_data.get('CO_ID')
    services_query = """
        SELECT ps.co_id, mp.tmcode, mp.des as desc_plano, ps.sncode, sn.des as servico,
               sn.shdes, decode(st.status,'A', 'Ativo', 'D', 'Desativado', 'S', 'Suspenso' ) as status_servico,
               b.description as benefit_description
        FROM profile_service@lk_bscsix_sysadm_001 ps, pr_serv_status_hist@lk_bscsix_sysadm_001 st,
             mpusntab@lk_bscsix_sysadm_001 sn, contract_all@lk_bscsix_sysadm_001 con,
             mputmtab@lk_bscsix_sysadm_001 mp, benefits@lk_bscsix_sysadm_001 b,
             contract_benefit@lk_bscsix_sysadm_001 c
        WHERE ps.co_id = st.co_id AND ps.status_histno = st.histno
          AND ps.sncode = st.sncode AND st.sncode = sn.sncode
          AND ps.co_id = con.co_id AND con.tmcode = mp.tmcode AND mp.status = 'W'
          AND sn.shdes = b.shdes (+) AND b.benefit_id = c.benefit_id (+)
          AND ps.co_id = c.co_id (+) AND ps.co_id = :co_id
          AND st.status = 'A'
        ORDER BY sn.des
    """
    cursor.execute(services_query, co_id=contract_id)
    services_data = _convert_fetchall_to_dict_list(cursor, cursor.fetchall())
    if services_data:
        profile_data['PLANO_NOME'] = services_data[0].get('DESC_PLANO'); profile_data['PLANO_CODIGO'] = services_data[0].get('TMCODE')
    data['profile'] = profile_data; data['services'] = services_data
    return data

def _validate_plans(cursor, siebel_plan_code, bscsix_plan_code):
    """Lógica especial para o plano, que verifica se o código do cliente está na lista de códigos possíveis para aquele plano."""
    validation = {"plan_match_status": "Não Encontrado no De-Para"}
    query = "SELECT product_code FROM siebel.pm_siebel_catalog_oms_prod WHERE commercial_product_id = :siebel_code"
    cursor.execute(query, siebel_code=siebel_plan_code)
    results = cursor.fetchall()

    if results:
        possible_bscs_codes = [str(row[0]).strip() for row in results]
        bscsix_plan_code_clean = str(bscsix_plan_code).strip()
        if bscsix_plan_code_clean in possible_bscs_codes:
            validation["plan_match_status"] = "OK"
        else:
            validation["plan_match_status"] = f"Divergente (Esperado um de: {possible_bscs_codes})"
    return validation


def _compare_assets_and_services_by_code(cursor, siebel_assets, bscsix_services):
    """CORREÇÃO: Esta função agora usa estritamente a tabela de-para para a correspondência de códigos."""
    siebel_part_nums = [asset['CODIGO_PRODUTO'] for asset in siebel_assets if asset.get('CODIGO_PRODUTO')]
    if not siebel_part_nums:
        return {"matched": [], "siebel_only": siebel_assets, "bscsix_only": bscsix_services}

    format_strings = ','.join([':%d' % i for i in range(1, len(siebel_part_nums) + 1)])
    # A query de mapeamento usa a coluna correta 'product_id' que corresponde ao SHDES
    map_query = f"SELECT commercial_product_id, product_id FROM siebel.pm_siebel_catalog_oms_prod WHERE commercial_product_id IN ({format_strings})"
    cursor.execute(map_query, siebel_part_nums)
    
    # O dicionário mapeia: {Siebel Part Num -> BSCSIX SHDES}
    mapping = {str(row[0]).strip(): str(row[1]).strip() for row in cursor.fetchall()}

    matched, siebel_only, bscsix_copy = [], [], list(bscsix_services)
    
    for s_asset in siebel_assets:
        s_part_num = s_asset.get('CODIGO_PRODUTO')
        # Pula o próprio plano da lista de serviços para não poluir a comparação
        if s_asset.get('CATEGORY_CD') == 'PLANO': continue
            
        expected_shdes = mapping.get(str(s_part_num).strip())
        found_bscs_service = None
        
        if expected_shdes:
            for b_service in bscsix_copy:
                bscs_shdes = b_service.get('SHDES')
                if bscs_shdes and str(bscs_shdes).strip() == expected_shdes:
                    found_bscs_service = b_service
                    break
        
        if found_bscs_service:
            matched.append({"siebel": s_asset, "bscsix": found_bscs_service})
            bscsix_copy.remove(found_bscs_service)
        else:
            siebel_only.append(s_asset)
            
    return {"matched": matched, "siebel_only": siebel_only, "bscsix_only": bscsix_copy}