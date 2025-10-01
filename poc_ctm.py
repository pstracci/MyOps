import subprocess
import xml.etree.ElementTree as ET # Usaremos a biblioteca de XML para interpretar a saída

def get_controlm_job_status_with_emwacli(
    folder_name: str, 
    job_name: str, 
    ctm_user: str, 
    ctm_pass: str, 
    em_host: str
) -> str:
    """
    Usa o EM WA CLI (emwacli) para obter o status de um job específico no Control-M.
    NOTA: O emwacli retorna a saída em formato XML.
    """
    emwacli_path = r"C:\Program Files\BMC Software\Control-M EM 9.0.00\Default\bin\emwacli.exe"
    
    # Monta o comando. O filtro é a parte mais importante.
    # Filtramos pela pasta e pelo nome do job para um resultado mais preciso.
    command = [
        emwacli_path, 
        "-u", ctm_user, 
        "-p", ctm_pass, 
        "-s", em_host, 
        "-cmd", "View:Jobs",
        "-filter", f"Folder={folder_name}",
        "-filter", f"JobName={job_name}" # Adiciona filtro para o nome do job
    ]

    print(f"Executando comando EM WA CLI...")

    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=True, encoding='utf-8'
        )
        
        xml_output = result.stdout
        print("\n--- Saída Bruta do emwacli (XML) ---")
        print(xml_output)
        print("------------------------------------\n")

        # --- Interpretação do XML ---
        # O emwacli retorna um XML. Vamos extrair a informação dele.
        if not xml_output.strip():
            return f"Nenhum job encontrado com o nome '{job_name}' na pasta '{folder_name}'."

        root = ET.fromstring(xml_output)
        # A tag <job> geralmente está dentro de <result>/<jobs> mas pode variar
        # Vamos usar uma busca mais genérica com './/job'
        job_element = root.find(f".//job[@JobName='{job_name}']")

        if job_element is not None:
            status = job_element.get('JobStatus') # O status geralmente é um atributo do elemento job
            return f"Status encontrado: '{status}'"
        else:
            return f"Job '{job_name}' encontrado na pasta, mas não foi possível extrair o status do XML."

    except FileNotFoundError:
        return f"Erro: O comando '{emwacli_path}' não foi encontrado. Verifique o caminho da instalação."
    except subprocess.CalledProcessError as e:
        # Captura a saída de SUCESSO (stdout) ou de ERRO (stderr), pois o emwacli
        # pode mandar mensagens de erro no canal de sucesso.
        error_output = e.stdout or e.stderr
        return f"Erro ao executar o comando emwacli. Saída do comando:\n---\n{error_output.strip()}\n---"
    except ET.ParseError:
        return "Erro: A saída do emwacli não foi um XML válido. Verifique a resposta bruta."
    except Exception as e:
        return f"Ocorreu um erro inesperado: {e}"

# --- Início da Execução da PoC ---
if __name__ == "__main__":
    # --- CONFIGURE AQUI ---
    TARGET_FOLDER = "OCI_PRD_SBL_POS_New"
    TARGET_JOB = "OCI_SBLPOS_BAT715.0"
    CTM_USER = "T3360240"      # <-- SUBSTITUA
    CTM_PASSWORD = "Accenture#29!!..."     # <-- SUBSTITUA
    EM_SERVER_HOST = "snelnxb193" # <-- SUBSTITUA (o mesmo que você usa na GUI)
    # ----------------------

    final_status = get_controlm_job_status_with_emwacli(
        TARGET_FOLDER, TARGET_JOB, CTM_USER, CTM_PASSWORD, EM_SERVER_HOST
    )

    print("\n--- Resultado da PoC ---")
    print(final_status)
    print("------------------------")