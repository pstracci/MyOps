# C:\Meus Projetos\fixer\modules\espelho\espelho_ui.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QMessageBox, QMainWindow, 
    QLineEdit, QTableWidget, QTableWidgetItem, QLabel, QHeaderView, QComboBox, 
    QTextEdit, QGroupBox, QFormLayout, QHBoxLayout, QRadioButton, QTabWidget,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtGui import QFont, QAction
from PyQt6.QtCore import Qt
from modules.espelho import espelho_logic as db

class ImdbWidget(QWidget):
    # O conteúdo desta classe permanece o mesmo
    def __init__(self):
        super().__init__(); self.current_gsm = None; main_layout = QVBoxLayout(self)
        info_label = QLabel("Esta tela busca os dados do cliente diretamente da API do IMDB.\nA aba é habilitada após uma busca bem-sucedida na tela 'Consulta de Cliente'."); info_label.setWordWrap(True)
        self.fetch_button = QPushButton("Buscar Dados no IMDB"); self.result_tree = QTreeWidget(); self.result_tree.setColumnCount(2); self.result_tree.setHeaderLabels(["Chave", "Valor"])
        self.result_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents); self.result_tree.header().setStretchLastSection(True)
        main_layout.addWidget(info_label); main_layout.addWidget(self.fetch_button); main_layout.addWidget(self.result_tree); self.fetch_button.clicked.connect(self.on_fetch_data)
    def set_gsm(self, gsm): self.current_gsm = gsm
    def clear_view(self): self.result_tree.clear(); self.current_gsm = None
    def on_fetch_data(self):
        if not self.current_gsm: QMessageBox.warning(self, "Atenção", "Nenhum GSM definido. Por favor, faça uma busca na aba 'Consulta de Cliente' primeiro."); return
        self.result_tree.clear(); QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            imdb_data = db.get_imdb_data(self.current_gsm)
            self._populate_tree_from_json(self.result_tree, imdb_data.get('body', imdb_data)); self.result_tree.expandToDepth(2)
        except Exception as e: QMessageBox.critical(self, "Erro ao buscar dados do IMDB", str(e))
        finally: QApplication.restoreOverrideCursor()
    def _populate_tree_from_json(self, parent_item, data):
        if isinstance(data, dict):
            for key, value in data.items():
                child_item = QTreeWidgetItem([str(key)])
                if isinstance(parent_item, QTreeWidget): parent_item.addTopLevelItem(child_item)
                else: parent_item.addChild(child_item)
                self._populate_tree_from_json(child_item, value)
        elif isinstance(data, list):
            for index, value in enumerate(data):
                child_item = QTreeWidgetItem([f"[{index}]"])
                if isinstance(parent_item, QTreeWidget): parent_item.addTopLevelItem(child_item)
                else: parent_item.addChild(child_item)
                self._populate_tree_from_json(child_item, value)
        else: parent_item.setText(1, str(data))

class CustomerLookupWidget(QWidget):
    # O conteúdo desta classe permanece o mesmo, mas o 'parent_window' agora é 'parent_widget'
    def __init__(self, parent_widget):
        super().__init__(); self.parent_widget = parent_widget; self.customer_type = None; self.current_profile_data = None; main_layout = QVBoxLayout(self)
        search_group = QGroupBox("1. Pesquisar Cliente"); search_layout = QFormLayout(); self.customer_input = QLineEdit(placeholderText="Digite o número GSM do cliente")
        self.search_button = QPushButton("Pesquisar Cliente"); self.clear_button = QPushButton("Limpar Tela"); search_buttons_layout = QHBoxLayout()
        search_buttons_layout.addWidget(self.search_button); search_buttons_layout.addWidget(self.clear_button); search_layout.addRow(QLabel("Buscar por GSM:"), self.customer_input)
        search_layout.addRow(search_buttons_layout); search_group.setLayout(search_layout); self.details_tabs = QTabWidget(); self.current_view_tab = QWidget()
        current_view_layout = QVBoxLayout(self.current_view_tab); profile_group = QGroupBox("2. Dados do Cliente"); profile_layout = QFormLayout(); self.profile_labels = {}
        fields_to_display = [("TIPO DE CONTA", "CUSTOMER_TYPE"), ("NOME", "ALIAS_NAME"), ("CPF", "NAME"), ("STATUS", "CUST_STAT_CD"), ("TIPO CLIENTE", "X_TIPO_CLIENTE"), ("TELEFONE", "MAIN_PH_NUM"), ("EMAIL", "MAIN_EMAIL_ADDR"), ("NOME DA MÃE", "X_NOME_MAE"), ("DATA CRIAÇÃO", "CREATED"), ("ÚLTIMA ATUALIZAÇÃO", "LAST_UPD")]
        for label_text, data_key in fields_to_display:
            label = QLabel("..."); label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            if data_key == "CUSTOMER_TYPE": label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            profile_layout.addRow(QLabel(f"{label_text}:"), label); self.profile_labels[data_key] = label
        profile_group.setLayout(profile_layout); assets_group = QGroupBox("3. Serviços / Assets Contratados"); assets_layout = QVBoxLayout(); self.assets_table = QTableWidget()
        self.assets_table.setColumnCount(8); self.assets_table.setHorizontalHeaderLabels(["Produto (Part Num)", "Nome do Produto", "Serial (GSM)", "Status", "Data Criação", "Última Atualização", "Atualizado Por", "Integration ID"])
        assets_layout.addWidget(self.assets_table); assets_group.setLayout(assets_layout); self.actions_group = QGroupBox("4. Ações para Cliente Pós-Pago"); actions_layout = QVBoxLayout()
        self.renotify_button = QPushButton("Renotificar Cliente na Base Espelho"); self.renotify_output = QTextEdit(readOnly=True); self.renotify_output.setFont(QFont("Courier", 10))
        self.renotify_output.setPlaceholderText("O resultado da renotificação aparecerá aqui..."); actions_layout.addWidget(self.renotify_button); actions_layout.addWidget(self.renotify_output)
        self.actions_group.setLayout(actions_layout); current_view_layout.addWidget(profile_group); current_view_layout.addWidget(assets_group); current_view_layout.addWidget(self.actions_group)
        self.history_tab = QWidget(); history_layout = QVBoxLayout(self.history_tab); history_client_group = QGroupBox("Histórico de Dados do Cliente (ACC_SIEBEXTRACT_STG_CLIENT_POS)"); history_client_layout = QVBoxLayout()
        self.history_client_table = QTableWidget(); self.history_client_table.setColumnCount(4); self.history_client_table.setHorizontalHeaderLabels(["Data", "Documento", "Nome", "Telefone"])
        history_client_layout.addWidget(self.history_client_table); history_client_group.setLayout(history_client_layout); history_asset_group = QGroupBox("Histórico de Assets (ACC_SIEBEXTRACT_STG_ASSET_POS)")
        history_asset_layout = QVBoxLayout(); self.history_asset_table = QTableWidget(); self.history_asset_table.setColumnCount(7); self.history_asset_table.setHorizontalHeaderLabels(["Data", "CPF", "MSISDN", "Customer ID", "Contrato", "Motivo Status", "Plano"])
        history_asset_layout.addWidget(self.history_asset_table); history_asset_group.setLayout(history_asset_layout); history_billing_group = QGroupBox("Histórico de Perfil de Faturamento (ACC_SIEBEXTRACT_STG_BP_POS)"); history_billing_layout = QVBoxLayout()
        self.history_billing_table = QTableWidget(); self.history_billing_table.setColumnCount(7); self.history_billing_table.setHorizontalHeaderLabels(["Data", "Documento", "Cust Code", "Tipo Fatura", "Vencimento", "Pagamento", "Customer ADI"])
        history_billing_layout.addWidget(self.history_billing_table); history_billing_group.setLayout(history_billing_layout); history_layout.addWidget(history_client_group); history_layout.addWidget(history_asset_group); history_layout.addWidget(history_billing_group)
        self.details_tabs.addTab(self.current_view_tab, "Visão Atual"); self.details_tabs.addTab(self.history_tab, "Histórico de Renotificação"); main_layout.addWidget(search_group); main_layout.addWidget(self.details_tabs)
        self.search_button.clicked.connect(self.on_search); self.clear_button.clicked.connect(self.clear_all_fields); self.customer_input.returnPressed.connect(self.on_search); self.renotify_button.clicked.connect(self.on_renotify); self.actions_group.setVisible(False)
    def clear_all_fields(self):
        self.customer_input.clear(); self.assets_table.setRowCount(0); self.history_client_table.setRowCount(0); self.history_asset_table.setRowCount(0); self.history_billing_table.setRowCount(0)
        for label in self.profile_labels.values(): label.setText("...")
        self.customer_type = None; self.current_profile_data = None; self.actions_group.setVisible(False); self.renotify_output.clear(); self.customer_input.setFocus(); self.parent_widget.disable_and_clear_imdb_tab()
    def on_search(self):
        gsm_identifier = self.customer_input.text().strip()
        if not gsm_identifier: QMessageBox.warning(self, "Atenção", "Por favor, informe um número GSM."); return
        self.clear_all_fields(); self.customer_input.setText(gsm_identifier); QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result_data = db.find_customer_and_determine_type(gsm_identifier)
            if not result_data: QMessageBox.information(self, "Não Encontrado", f"Nenhum cliente/serviço encontrado para o GSM '{gsm_identifier}'."); return
            self.customer_type = result_data['type']; self.profile_labels['CUSTOMER_TYPE'].setText(self.customer_type); self.current_profile_data = result_data['profile']
            if self.customer_type in ["PÓS-PAGO", "HÍBRIDO (PÓS-PAGO E PRÉ-PAGO)"]: self.actions_group.setVisible(True)
            if self.current_profile_data:
                for data_key, label in self.profile_labels.items():
                    if data_key != "CUSTOMER_TYPE": label.setText(str(self.current_profile_data.get(data_key.upper(), "N/A")))
            self.populate_table(self.assets_table, result_data['assets'], ['PART_NUM', 'NAME', 'SERIAL_NUM', 'STATUS_CD', 'CREATED', 'LAST_UPD', 'LAST_UPD_BY', 'INTEGRATION_ID'])
            history = result_data.get('history', {})
            if history:
                self.populate_table(self.history_client_table, history.get('client', []), ['ENTRY_DATE', 'DOCUMENT', 'NAME', 'MAIN_PH_NUM'])
                self.populate_table(self.history_asset_table, history.get('asset', []), ['ENTRY_DATE', 'CPF', 'MSISDN', 'CUSTOMER_ID', 'TIPO_CONTRATO', 'MOTIVO_STATUS', 'CODIGO_PLANO'])
                self.populate_table(self.history_billing_table, history.get('billing', []), ['ENTRY_DATE', 'DOCUMENT', 'CUST_CODE', 'TIPO_FATURA', 'DIA_VENCIMENTO', 'METODO_PAGAMENTO', 'CUSTOMER_ADI'])
            self.parent_widget.enable_imdb_tab(gsm_identifier)
        except Exception as e: QMessageBox.critical(self, "Erro de Banco de Dados", str(e))
        finally: QApplication.restoreOverrideCursor()
    def populate_table(self, table_widget, data, columns):
        if not data: table_widget.setRowCount(0); return
        table_widget.setRowCount(len(data))
        for row_idx, row_data in enumerate(data):
            for col_idx, col_key in enumerate(columns): table_widget.setItem(row_idx, col_idx, QTableWidgetItem(str(row_data.get(col_key.upper(), ''))))
        table_widget.resizeColumnsToContents()
    def on_renotify(self):
        if not self.current_profile_data: QMessageBox.warning(self, "Atenção", "Dados do cliente não carregados."); return
        serial_num = self.customer_input.text().strip(); cpf = self.current_profile_data.get('NAME')
        if not serial_num or not cpf: QMessageBox.warning(self, "Atenção", "Não foi possível obter o GSM ou CPF do cliente para a renotificação."); return
        if QMessageBox.question(self, 'Confirmação', f"Tem certeza que deseja executar a renotificação para o cliente com CPF {cpf} e GSM {serial_num}?\n\nEsta ação é irreversível.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No: return
        self.renotify_output.setText("Buscando Customer ID e executando a procedure..."); QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            customer_id = db.get_customer_id_for_renotify(serial_num)
            if not customer_id: raise Exception("Não foi possível encontrar o Customer ID (perfil de faturamento) associado a este GSM.")
            result = db.execute_renotify_procedure(serial_num, cpf, customer_id)
            self.renotify_output.setText(f"--- Resultado da Procedure ---\nCódigo de Retorno: {result['return_code']}\nMensagem: {result['return_msg']}\n\n--- Saída DBMS_OUTPUT ---\n{result['dbms_output']}")
        except Exception as e:
            self.renotify_output.setText(f"Falha na execução.\n\nErro: {str(e)}"); QMessageBox.critical(self, "Erro na Execução", str(e))
        finally: QApplication.restoreOverrideCursor()

class EspelhoToolWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.tabs = QTabWidget()
        self.customer_lookup_tab = CustomerLookupWidget(self)
        self.imdb_tab = ImdbWidget()
        self.tabs.addTab(self.customer_lookup_tab, "Consulta de Cliente")
        self.tabs.addTab(self.imdb_tab, "Consulta IMDB")
        self.tabs.setTabEnabled(1, False)
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

    def enable_imdb_tab(self, gsm):
        self.imdb_tab.set_gsm(gsm)
        self.tabs.setTabEnabled(1, True)

    def disable_and_clear_imdb_tab(self):
        self.imdb_tab.clear_view()
        self.tabs.setTabEnabled(1, False)