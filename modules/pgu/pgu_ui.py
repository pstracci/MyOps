# C:\Meus Projetos\MyOps\modules\pgu\pgu_ui.py

import sys
import configparser
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QMessageBox, QMainWindow, 
    QLineEdit, QTableWidget, QTableWidgetItem, QLabel, QHeaderView, QComboBox, 
    QTextEdit, QGroupBox, QFormLayout, QHBoxLayout, QRadioButton, QTabWidget,
    QListWidget, QListWidgetItem
)
from PyQt6.QtGui import QFont, QAction
from PyQt6.QtCore import Qt
from modules.pgu import pgu_logic as db

class ProfileManagerWidget(QWidget):
    # ... (Esta classe não foi modificada)
    def __init__(self, parent_widget):
        super().__init__()
        self.parent_widget = parent_widget
        main_layout = QVBoxLayout(self); search_group = QGroupBox("1. Pesquisar Perfil"); search_layout = QFormLayout()
        self.profile_input = QLineEdit(placeholderText="Digite o ID do perfil (ex: VNBASVE1)"); self.search_button = QPushButton("Pesquisar")
        search_layout.addRow(QLabel("ID do Perfil:"), self.profile_input); search_layout.addRow(self.search_button); search_group.setLayout(search_layout)
        filter_group = QGroupBox("Filtro de Resultados"); filter_layout = QHBoxLayout(); filter_layout.addWidget(QLabel("Filtrar por Feature ID:"))
        self.filter_input = QLineEdit(placeholderText="Digite o código para filtrar..."); filter_layout.addWidget(self.filter_input); filter_group.setLayout(filter_layout)
        self.results_table = QTableWidget(); self.results_table.setColumnCount(4); self.results_table.setHorizontalHeaderLabels(["Profile ID", "Perfil", "Feature ID", "Descrição"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        action_group = QGroupBox("2. Executar Ação"); action_layout = QFormLayout()
        self.features_input = QLineEdit(placeholderText="Informe as funcionalidades separadas por vírgula"); self.action_combo = QComboBox(); self.action_combo.addItems(["Adicionar", "Remover"])
        self.sargento_combo = QComboBox(); self.sargento_combo.addItems(["Não", "Sim"]); action_buttons_layout = QHBoxLayout()
        self.execute_button = QPushButton("Executar Procedure"); self.execute_button.setEnabled(False); self.clear_button = QPushButton("Limpar Tela")
        action_buttons_layout.addWidget(self.execute_button); action_buttons_layout.addWidget(self.clear_button); action_layout.addRow(QLabel("Funcionalidades:"), self.features_input)
        action_layout.addRow(QLabel("Ação:"), self.action_combo); action_layout.addRow(QLabel("Perfil Sargento:"), self.sargento_combo); action_layout.addRow(action_buttons_layout); action_group.setLayout(action_layout)
        result_group = QGroupBox("3. Resultado da Execução"); result_layout = QVBoxLayout(); self.result_output = QTextEdit(readOnly=True); self.result_output.setFont(QFont("Courier", 10))
        result_layout.addWidget(self.result_output); result_group.setLayout(result_layout); main_layout.addWidget(search_group); main_layout.addWidget(filter_group); main_layout.addWidget(self.results_table)
        main_layout.addWidget(action_group); main_layout.addWidget(result_group); self.search_button.clicked.connect(self.on_search); self.execute_button.clicked.connect(self.on_execute)
        self.clear_button.clicked.connect(self.clear_all_fields); self.profile_input.returnPressed.connect(self.on_search); self.filter_input.textChanged.connect(self.apply_filter)
    def get_db_key(self): return self.parent_widget.db_combo.currentData()
    def clear_all_fields(self):
        self.profile_input.clear(); self.filter_input.clear(); self.results_table.setRowCount(0); self.features_input.clear(); self.result_output.clear()
        self.action_combo.setCurrentIndex(0); self.sargento_combo.setCurrentIndex(0); self.execute_button.setEnabled(False); self.profile_input.setFocus()
    def on_search(self):
        db_key = self.get_db_key()
        if not db_key: QMessageBox.warning(self, "Atenção", "Por favor, selecione uma conexão válida."); return
        self.execute_button.setEnabled(False); profile_id = self.profile_input.text().strip().upper()
        if not profile_id: QMessageBox.warning(self, "Atenção", "Por favor, informe um ID de perfil."); return
        try:
            results = db.search_profile(db_key, profile_id); self.populate_table(results)
            if results: self.execute_button.setEnabled(True)
            else: QMessageBox.information(self, "Resultado", f"Nenhum perfil encontrado para o ID '{profile_id}'.")
        except Exception as e: QMessageBox.critical(self, "Erro de Banco de Dados", str(e))
    def on_execute(self):
        db_key = self.get_db_key()
        if not db_key: QMessageBox.warning(self, "Atenção", "Por favor, selecione uma conexão válida."); return
        if QMessageBox.question(self, 'Confirmação', "Esta ação é irreversível e irá modificar os dados no banco. Deseja continuar?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No: return
        profile_id = self.profile_input.text().strip().upper(); functionalities = "".join(self.features_input.text().strip().split())
        action_code = 'A' if self.action_combo.currentText() == "Adicionar" else 'R'; sargento_code = 'S' if self.sargento_combo.currentText() == 'Sim' else 'N'
        if not functionalities: QMessageBox.warning(self, "Atenção", "O campo de funcionalidades deve ser preenchido."); return
        self.result_output.setText("Executando, por favor aguarde..."); QApplication.processEvents()
        try:
            result = db.execute_gerenciar_perfil(db_key, profile_id, functionalities, action_code, sargento_code)
            self.result_output.setText(f"--- Resultado ---\nCódigo: {result['cod_retorno']}\nMensagem: {result['msg_retorno']}\n\n--- Saída DBMS_OUTPUT ---\n{result['dbms_output']}")
            if result.get("cod_retorno") == 0: self.on_search()
        except Exception as e: QMessageBox.critical(self, "Erro de Banco de Dados", str(e))
    def populate_table(self, data):
        self.results_table.setRowCount(0)
        for row_num, row_data in enumerate(data):
            self.results_table.insertRow(row_num)
            for col_num, cell_data in enumerate(row_data): self.results_table.setItem(row_num, col_num, QTableWidgetItem(str(cell_data)))
    def apply_filter(self):
        filter_text = self.filter_input.text().strip().lower()
        for row in range(self.results_table.rowCount()):
            item = self.results_table.item(row, 2)
            if item: self.results_table.setRowHidden(row, filter_text not in item.text().lower())

class SellerQueryWidget(QWidget):
    def __init__(self, parent_widget):
        super().__init__()
        self.parent_widget = parent_widget
        self.current_seller_login = None
        main_layout = QVBoxLayout(self)
        search_group = QGroupBox("1. Pesquisar Vendedor")
        search_layout = QFormLayout()
        search_options_layout = QHBoxLayout()
        self.cpf_radio = QRadioButton("CPF"); self.cpf_radio.setChecked(True)
        self.login_radio = QRadioButton("Login/Matrícula")
        search_options_layout.addWidget(self.cpf_radio); search_options_layout.addWidget(self.login_radio)
        self.seller_input = QLineEdit(placeholderText="Digite o CPF ou Login do vendedor")
        self.search_seller_button = QPushButton("Pesquisar Vendedor")
        search_layout.addRow(QLabel("Buscar por:"), search_options_layout)
        search_layout.addRow(QLabel("Identificador:"), self.seller_input)
        search_layout.addRow(self.search_seller_button)
        search_group.setLayout(search_layout)
        results_group = QGroupBox("2. Dados do Vendedor")
        results_layout = QVBoxLayout(results_group)
        self.seller_details_output = QTextEdit(readOnly=True)
        self.seller_details_output.setFont(QFont("Courier", 10))
        results_layout.addWidget(self.seller_details_output)
        pdvs_group = QGroupBox("PDVs Associados")
        pdvs_layout = QVBoxLayout(pdvs_group)
        self.pdv_table = QTableWidget()
        self.pdv_table.setColumnCount(8)
        self.pdv_table.setHorizontalHeaderLabels(["CPF", "PDV", "Nickname", "Classificação", "Regional", "Operador", "Segmento", "Risco Fraude"])
        self.pdv_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.pdv_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.pdv_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        pdvs_layout.addWidget(self.pdv_table)
        action_group = QGroupBox("3. Ações")
        action_buttons_layout = QHBoxLayout(action_group)
        self.delete_button = QPushButton("Excluir Vendedor da Base")
        self.delete_button.setEnabled(False)
        self.clear_button = QPushButton("Limpar Tela")
        action_buttons_layout.addWidget(self.delete_button)
        action_buttons_layout.addWidget(self.clear_button)
        delete_result_group = QGroupBox("4. Resultado da Exclusão")
        delete_result_layout = QVBoxLayout(delete_result_group)
        self.delete_output = QTextEdit(readOnly=True)
        self.delete_output.setFont(QFont("Courier", 10))
        delete_result_layout.addWidget(self.delete_output)
        main_layout.addWidget(search_group)
        main_layout.addWidget(results_group, 40)
        main_layout.addWidget(pdvs_group, 60)
        main_layout.addWidget(action_group)
        main_layout.addWidget(delete_result_group)
        self.search_seller_button.clicked.connect(self.on_search_seller)
        self.seller_input.returnPressed.connect(self.on_search_seller)
        self.delete_button.clicked.connect(self.on_delete_seller)
        self.clear_button.clicked.connect(lambda: self.clear_all_fields(clear_input=True))

    def get_db_key(self):
        return self.parent_widget.db_combo.currentData()

    def clear_all_fields(self, clear_input=False):
        # --- LÓGICA DE LIMPEZA CORRIGIDA ---
        if clear_input:
            self.seller_input.clear()
        
        self.seller_details_output.clear()
        self.pdv_table.setRowCount(0)
        self.delete_output.clear()
        self.delete_button.setEnabled(False)
        self.current_seller_login = None
        
        if clear_input:
            self.cpf_radio.setChecked(True)
            self.seller_input.setFocus()

    def on_search_seller(self):
        db_key = self.get_db_key()
        if not db_key:
            QMessageBox.warning(self, "Atenção", "Por favor, selecione uma conexão válida.")
            return

        # --- LÓGICA DE PESQUISA CORRIGIDA ---
        # 1. Lê o identificador PRIMEIRO
        identifier = self.seller_input.text().strip()
        
        # 2. Limpa apenas os resultados anteriores, mantendo o campo de busca
        self.clear_all_fields(clear_input=False)
        
        search_type = 'login' if self.login_radio.isChecked() else 'cpf'
        
        # 3. Verifica se o identificador está vazio APÓS a leitura
        if not identifier:
            QMessageBox.warning(self, "Atenção", "Por favor, informe um identificador.")
            return

        try:
            seller_data = db.get_seller_details(db_key, identifier, search_type)
            if not seller_data:
                QMessageBox.information(self, "Resultado", f"Nenhum vendedor encontrado para '{identifier}'.")
                return

            self.current_seller_login = seller_data.get('VENDOR_LOGIN')
            is_blacklisted = db.check_cpf_blacklist(db_key, seller_data.get('VENDOR_ID'))
            
            details_html = ""
            if is_blacklisted:
                details_html += "<p><b style='color:red;'>ALERTA: CPF ENCONTRADO NA BLACKLIST!</b></p>"
            
            details_html += f"""
                <p>
                <b>CPF (VENDOR_ID):</b> <u>{seller_data.get('VENDOR_ID', 'N/A')}</u><br>
                <b>Nome Completo:</b> <u>{seller_data.get('NAME', '')} {seller_data.get('LAST_NAME', '')}</u><br>
                <b>Login/Matrícula:</b> <u>{seller_data.get('VENDOR_LOGIN', 'N/A')}</u><br>
                <b>Status:</b> <u>{'Ativo' if seller_data.get('STATUS') == 1 else 'Inativo'} ({seller_data.get('STATUS')})</u><br>
                <b>Perfil:</b> <u>{seller_data.get('VAR_PROF_VEND_PROF_ID', 'N/A')}</u><br>
                <b>Email:</b> {seller_data.get('EMAIL', 'N/A')}<br>
                <b>Data de Criação:</b> {seller_data.get('CREATE_DATE', 'N/A')}<br>
                <b>Data de Nascimento:</b> {seller_data.get('BIRTH_DATE', 'N/A')}<br>
                <b>Primeiro Acesso:</b> {seller_data.get('FIRST_ACCESS', 'N/A')}<br>
                <b>ID Sargento:</b> {seller_data.get('VAR_SARGENTO_SARGENTO_ID', 'N/A')}<br>
                <b>Matrícula Carga:</b> {seller_data.get('MATRICULA_RESPONSAVEL_CARGA', 'N/A')}
                </p>
            """
            self.seller_details_output.setHtml(details_html)
            
            pdv_list = db.get_seller_pdvs(db_key, seller_data.get('VENDOR_ID'))
            self.pdv_table.setRowCount(0)
            for row_num, row_data in enumerate(pdv_list):
                self.pdv_table.insertRow(row_num)
                for col_num, cell_data in enumerate(row_data):
                    self.pdv_table.setItem(row_num, col_num, QTableWidgetItem(str(cell_data)))
            
            self.delete_button.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "Erro de Banco de Dados", str(e))
    
    def on_delete_seller(self):
        db_key = self.get_db_key()
        if not db_key:
            QMessageBox.warning(self, "Atenção", "Por favor, selecione uma conexão válida.")
            return

        if not self.current_seller_login:
            QMessageBox.critical(self, "Erro", "Nenhum vendedor carregado para exclusão. Faça uma nova pesquisa.")
            return
            
        if QMessageBox.question(self, 'Confirmação', f"Esta ação é irreversível e irá deletar o vendedor com login '{self.current_seller_login}'.\n\nDeseja continuar?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No:
            return

        self.delete_output.setText(f"Executando deleção para {self.current_seller_login}, por favor aguarde...")
        QApplication.processEvents()
        
        try:
            result_text = db.execute_delete_seller(db_key, self.current_seller_login)
            self.delete_output.setText(result_text)
            self.clear_all_fields(clear_input=True)
        except Exception as e:
            self.delete_output.setText(f"Falha na execução.\n\nErro: {str(e)}")
            QMessageBox.critical(self, "Erro de Banco de Dados", str(e))

class PdvManagerWidget(QWidget):
    # ... (Esta classe não foi modificada)
    def __init__(self, parent_widget):
        super().__init__()
        self.parent_widget = parent_widget
        self.current_vendor_id = None; self.changes_made = False; main_layout = QVBoxLayout(self)
        search_group = QGroupBox("1. Pesquisar Vendedor"); search_layout = QFormLayout(); search_options_layout = QHBoxLayout()
        self.cpf_radio = QRadioButton("CPF"); self.login_radio = QRadioButton("Login/Matrícula"); self.cpf_radio.setChecked(True)
        search_options_layout.addWidget(self.cpf_radio); search_options_layout.addWidget(self.login_radio); self.seller_input = QLineEdit(placeholderText="Digite o CPF ou Login do vendedor")
        self.search_button = QPushButton("Pesquisar Vendedor"); search_layout.addRow(QLabel("Buscar por:"), search_options_layout); search_layout.addRow(QLabel("Identificador:"), self.seller_input)
        search_layout.addRow(self.search_button); search_group.setLayout(search_layout); self.searched_seller_label = QLabel("Nenhum vendedor pesquisado.")
        self.searched_seller_label.setFont(QFont("Arial", 10, QFont.Weight.Bold)); assignment_group = QGroupBox("2. Gerenciar PDVs"); assignment_layout = QHBoxLayout()
        available_layout = QVBoxLayout(); available_layout.addWidget(QLabel("PDVs Disponíveis")); self.available_filter_input = QLineEdit(placeholderText="Filtrar disponíveis...")
        available_layout.addWidget(self.available_filter_input); self.available_list = QListWidget(); self.available_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        available_layout.addWidget(self.available_list); arrows_layout = QVBoxLayout(); arrows_layout.addStretch(); self.add_button = QPushButton("  >  "); self.remove_button = QPushButton("  <  ")
        arrows_layout.addWidget(self.add_button); arrows_layout.addWidget(self.remove_button); arrows_layout.addStretch(); assigned_layout = QVBoxLayout()
        assigned_layout.addWidget(QLabel("PDVs Atribuídos")); self.assigned_filter_input = QLineEdit(placeholderText="Filtrar atribuídos..."); assigned_layout.addWidget(self.assigned_filter_input)
        self.assigned_list = QListWidget(); self.assigned_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection); assigned_layout.addWidget(self.assigned_list)
        assignment_layout.addLayout(available_layout, 45); assignment_layout.addLayout(arrows_layout, 10); assignment_layout.addLayout(assigned_layout, 45); assignment_group.setLayout(assignment_layout)
        action_group = QGroupBox("3. Executar Ação"); action_buttons_layout = QHBoxLayout(); self.apply_button = QPushButton("Aplicar Mudanças"); self.apply_button.setEnabled(False)
        self.clear_button = QPushButton("Limpar Tela"); action_buttons_layout.addWidget(self.apply_button); action_buttons_layout.addWidget(self.clear_button); action_group.setLayout(action_buttons_layout)
        result_group = QGroupBox("4. Resultado da Execução"); result_layout = QVBoxLayout(); self.result_output = QTextEdit(readOnly=True); self.result_output.setFont(QFont("Courier", 10))
        result_layout.addWidget(self.result_output); result_group.setLayout(result_layout); main_layout.addWidget(search_group); main_layout.addWidget(self.searched_seller_label)
        main_layout.addWidget(assignment_group); main_layout.addWidget(action_group); main_layout.addWidget(result_group); self.search_button.clicked.connect(self.on_search)
        self.seller_input.returnPressed.connect(self.on_search); self.add_button.clicked.connect(self.move_to_assigned); self.remove_button.clicked.connect(self.move_to_available)
        self.apply_button.clicked.connect(self.on_apply_changes); self.clear_button.clicked.connect(self.clear_all_fields); self.available_filter_input.textChanged.connect(self.filter_available_list)
        self.assigned_filter_input.textChanged.connect(self.filter_assigned_list)
    def get_db_key(self): return self.parent_widget.db_combo.currentData()
    def on_search(self):
        db_key = self.get_db_key()
        if not db_key: QMessageBox.warning(self, "Atenção", "Por favor, selecione uma conexão válida."); return
        self.clear_all_fields(clear_input=False); identifier = self.seller_input.text().strip(); search_type = 'login' if self.login_radio.isChecked() else 'cpf'
        if not identifier: QMessageBox.warning(self, "Atenção", "Informe um identificador."); return
        try:
            seller_info = db.get_seller_info_for_pdv(db_key, identifier, search_type)
            if not seller_info: QMessageBox.information(self, "Não encontrado", f"Nenhum vendedor encontrado para '{identifier}'."); self.searched_seller_label.setText("Nenhum vendedor pesquisado."); return
            self.current_vendor_id, seller_name = seller_info; self.searched_seller_label.setText(f"Gerenciando PDVs para: {seller_name} (CPF: {self.current_vendor_id})")
            assigned_pdvs_data = db.get_assigned_pdvs(db_key, self.current_vendor_id); all_pdvs_data = db.get_all_available_pdvs(db_key)
            assigned_codes = {pdv[0] for pdv in assigned_pdvs_data}
            for code, nickname in assigned_pdvs_data: item = QListWidgetItem(f"{code} - {nickname}"); item.setData(Qt.ItemDataRole.UserRole, code); self.assigned_list.addItem(item)
            for code, nickname in all_pdvs_data:
                if code not in assigned_codes: item = QListWidgetItem(f"{code} - {nickname}"); item.setData(Qt.ItemDataRole.UserRole, code); self.available_list.addItem(item)
        except Exception as e: QMessageBox.critical(self, "Erro de Banco de Dados", str(e))
    def _move_items(self, source_list, dest_list):
        selected_items = source_list.selectedItems()
        if not selected_items: return
        for item in selected_items: source_list.takeItem(source_list.row(item)); dest_list.addItem(item)
        self.changes_made = True; self.apply_button.setEnabled(True); self.filter_available_list(); self.filter_assigned_list()
    def move_to_assigned(self): self._move_items(self.available_list, self.assigned_list)
    def move_to_available(self): self._move_items(self.assigned_list, self.available_list)
    def on_apply_changes(self):
        db_key = self.get_db_key()
        if not db_key: QMessageBox.warning(self, "Atenção", "Por favor, selecione uma conexão válida."); return
        if not self.current_vendor_id: return
        if QMessageBox.question(self, 'Confirmação', f"Esta ação é irreversível e irá alterar as associações de PDV para o vendedor. Deseja continuar?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No: return
        self.result_output.setText("Aplicando mudanças, por favor aguarde..."); QApplication.processEvents(); final_assigned_codes = []
        for i in range(self.assigned_list.count()): final_assigned_codes.append(self.assigned_list.item(i).data(Qt.ItemDataRole.UserRole))
        try:
            result_message = db.apply_pdv_changes(db_key, self.current_vendor_id, final_assigned_codes); self.result_output.setText(result_message)
            self.changes_made = False; self.apply_button.setEnabled(False)
        except Exception as e: QMessageBox.critical(self, "Erro de Banco de Dados", str(e)); self.result_output.setText(f"Falha ao aplicar mudanças:\n{e}")
    def clear_all_fields(self, clear_input=True):
        if clear_input: self.seller_input.clear()
        self.assigned_list.clear(); self.available_list.clear(); self.assigned_filter_input.clear(); self.available_filter_input.clear(); self.result_output.clear()
        if clear_input: self.cpf_radio.setChecked(True); self.searched_seller_label.setText("Nenhum vendedor pesquisado."); self.seller_input.setFocus()
        self.apply_button.setEnabled(False); self.changes_made = False; self.current_vendor_id = None
    def filter_list(self, list_widget, filter_input):
        filter_text = filter_input.text().strip().lower()
        for i in range(list_widget.count()): list_widget.item(i).setHidden(filter_text not in list_widget.item(i).text().lower())
    def filter_available_list(self): self.filter_list(self.available_list, self.available_filter_input)
    def filter_assigned_list(self): self.filter_list(self.assigned_list, self.assigned_filter_input)

# Classe principal que contém as abas
class PGUToolWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        main_layout = QVBoxLayout(self)

        conn_group = QGroupBox("Conexão")
        conn_layout = QHBoxLayout(conn_group)
        self.db_combo = QComboBox()
        conn_layout.addWidget(QLabel("Consultar Base:"))
        conn_layout.addWidget(self.db_combo)
        
        main_layout.addWidget(conn_group)

        self.tabs = QTabWidget()
        self.seller_query_tab = SellerQueryWidget(self)
        self.profile_tab = ProfileManagerWidget(self)
        self.pdv_tab = PdvManagerWidget(self)
        
        self.tabs.addTab(self.seller_query_tab, "Consulta Vendedor")
        self.tabs.addTab(self.profile_tab, "Gerenciar Perfis")
        self.tabs.addTab(self.pdv_tab, "Atribuir PDVs")
        
        main_layout.addWidget(self.tabs)
        
        self.populate_db_combo()
        self.load_last_connection()
        self.db_combo.currentTextChanged.connect(self.save_last_connection)
    
    def populate_db_combo(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        for section in config.sections():
            if section.startswith('database'):
                self.db_combo.addItem(section, section)

    def save_last_connection(self, db_key):
        config = configparser.ConfigParser()
        config.read('config.ini')
        if not config.has_section('pgu_settings'):
            config.add_section('pgu_settings')
        config.set('pgu_settings', 'last_connection', db_key)
        with open('config.ini', 'w') as configfile:
            config.write(configfile)

    def load_last_connection(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        last_conn = config.get('pgu_settings', 'last_connection', fallback='database')
        self.db_combo.setCurrentText(last_conn)