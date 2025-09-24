# C:\Meus Projetos\MyOps\modules\bat452_scheduler\bat452_scheduler_ui.py

import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLabel, QGroupBox, 
                             QLineEdit, QHBoxLayout, QFileDialog, QMessageBox,
                             QComboBox, QDialog, QDialogButtonBox, QApplication) # <-- QApplication ADICIONADO AQUI
from PyQt6.QtCore import Qt
from . import bat452_scheduler_logic as logic

# --- INÍCIO DA NOVA CLASSE PARA A JANELA DE DETALHES ---
class ExecutionDetailDialog(QDialog):
    def __init__(self, req_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Detalhes da Execução - {req_id}")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        # Campo de pesquisa
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Pesquisar:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Digite um MSISDN ou status para filtrar...")
        self.filter_input.textChanged.connect(self.filter_table)
        filter_layout.addWidget(self.filter_input)
        layout.addLayout(filter_layout)

        # Tabela de resultados
        self.table = QTableWidget()
        headers = ["Data Criação", "Última Atualização", "MSISDN (Serial Num)", "Status Final", "Atualizado Por"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True) # Habilita a ordenação por coluna
        layout.addWidget(self.table)
        
        # Botão de fechar
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def populate_data(self, data):
        self.table.setRowCount(len(data))
        for row_idx, row_data in enumerate(data):
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(str(cell_data or ''))
                self.table.setItem(row_idx, col_idx, item)
        self.table.resizeColumnsToContents()

    def filter_table(self, text):
        search_text = text.lower()
        for row in range(self.table.rowCount()):
            match = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)
# --- FIM DA NOVA CLASSE ---

class Bat452SchedulerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Agendador de Processamento - BAT452")
        self.current_file_path = None
        self.preview_data = []

        main_layout = QVBoxLayout(self)

        # --- Seção de Controles ---
        controls_group = QGroupBox("Agendar Novo Processamento")
        controls_layout = QVBoxLayout(controls_group)

        self.db_combo = QComboBox()
        self.connections = logic.get_all_db_connections()
        for key, name in self.connections.items():
            self.db_combo.addItem(name, key)
        
        default_index = -1
        for i in range(self.db_combo.count()):
            if 'siebel' in self.db_combo.itemText(i).lower():
                default_index = i
                break
        if default_index != -1:
            self.db_combo.setCurrentIndex(default_index)
        
        file_layout = QHBoxLayout()
        self.file_path_label = QLabel("Nenhum arquivo selecionado.")
        self.select_file_button = QPushButton("Selecionar Arquivo...")
        self.select_file_button.clicked.connect(self.select_input_file)
        file_layout.addWidget(QLabel("Arquivo de Entrada:"))
        file_layout.addWidget(self.file_path_label, 1)
        file_layout.addWidget(self.select_file_button)

        req_layout = QHBoxLayout()
        self.req_id_input = QLineEdit()
        self.req_id_input.setPlaceholderText("Ex: RITM0123456")
        req_layout.addWidget(QLabel("Número da REQ:"))
        req_layout.addWidget(self.req_id_input)

        self.schedule_button = QPushButton("✔ Agendar Processamento")
        self.schedule_button.setMinimumHeight(40)
        self.schedule_button.clicked.connect(self.schedule_job)
        self.schedule_button.setEnabled(False)

        controls_layout.addWidget(QLabel("Base de Dados:"))
        controls_layout.addWidget(self.db_combo)
        controls_layout.addLayout(file_layout)
        controls_layout.addLayout(req_layout)
        controls_layout.addWidget(self.schedule_button)

        # --- Seção de Preview e Status ---
        preview_group = QGroupBox("Preview do Arquivo de Entrada (100 primeiras linhas)")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_table = QTableWidget()
        preview_layout.addWidget(self.preview_table)
        
        status_group = QGroupBox("Histórico e Status dos Agendamentos")
        status_layout = QVBoxLayout(status_group)
        self.status_table = QTableWidget()
        self.status_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.status_table.itemClicked.connect(self.show_execution_details)
        self.refresh_button = QPushButton("Atualizar Status")
        self.refresh_button.clicked.connect(self.refresh_schedules)
        status_layout.addWidget(self.refresh_button)
        status_layout.addWidget(self.status_table)
        
        self.status_label = QLabel("Selecione um arquivo e informe a REQ para agendar.")
        
        main_layout.addWidget(controls_group)
        main_layout.addWidget(preview_group)
        main_layout.addWidget(status_group)
        main_layout.addWidget(self.status_label)
        
        self.refresh_schedules()

    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo de Entrada", "", "Arquivos de Texto (*.txt)")
        if file_path:
            self.current_file_path = file_path
            self.file_path_label.setText(os.path.basename(file_path))
            try:
                self.preview_data, headers = logic.preview_file(file_path)
                if not headers: raise ValueError("Arquivo vazio ou sem cabeçalho.")
                self.preview_table.setRowCount(len(self.preview_data))
                self.preview_table.setColumnCount(len(headers))
                self.preview_table.setHorizontalHeaderLabels(headers)
                for row_idx, row_data in enumerate(self.preview_data):
                    for col_idx, cell_data in enumerate(row_data):
                        self.preview_table.setItem(row_idx, col_idx, QTableWidgetItem(cell_data))
                self.preview_table.resizeColumnsToContents()
                self.schedule_button.setEnabled(True)
                self.status_label.setText(f"{len(self.preview_data)} linhas pré-visualizadas. Pronto para agendar.")
            except Exception as e:
                QMessageBox.critical(self, "Erro de Leitura", f"Não foi possível ler ou processar o arquivo:\n{e}")
                self.schedule_button.setEnabled(False)

    def schedule_job(self):
        req_id = self.req_id_input.text().strip()
        db_section_key = self.db_combo.currentData()

        if not req_id:
            QMessageBox.warning(self, "Erro", "O número da REQ é obrigatório.")
            return

        if not self.current_file_path or not self.preview_data:
            QMessageBox.warning(self, "Erro", "Nenhum arquivo válido foi selecionado.")
            return
            
        reply = QMessageBox.question(self, "Confirmar Agendamento", 
                                     f"Confirma o agendamento da carga para a REQ {req_id}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return

        self.schedule_button.setEnabled(False)
        self.status_label.setText("Agendando... Carregando dados para o servidor...")
        
        try:
            success, message = logic.schedule_job(db_section_key, req_id, self.preview_data, os.path.basename(self.current_file_path))
            if success:
                QMessageBox.information(self, "Sucesso", message)
                self.refresh_schedules()
                self.req_id_input.clear()
                self.file_path_label.setText("Nenhum arquivo selecionado.")
                self.preview_table.setRowCount(0)
                self.preview_table.setColumnCount(0)
                self.current_file_path = None
                self.preview_data = []
            else:
                QMessageBox.critical(self, "Erro no Agendamento", message)
        finally:
            self.schedule_button.setEnabled(True)
            self.status_label.setText("Pronto.")

    def refresh_schedules(self):
        db_section_key = self.db_combo.currentData()
        if not db_section_key:
            self.status_label.setText("Nenhuma base de dados selecionada.")
            return
            
        success, data = logic.get_scheduled_jobs(db_section_key)
        if success:
            headers = ["ID", "REQ ID", "Status", "Data Agend.", "Data Proc.", "Arquivo", "Usuário", "Msg Erro"]
            self.status_table.setRowCount(len(data))
            self.status_table.setColumnCount(len(headers))
            self.status_table.setHorizontalHeaderLabels(headers)
            for row_idx, row_data in enumerate(data):
                for col_idx, cell_data in enumerate(row_data):
                    self.status_table.setItem(row_idx, col_idx, QTableWidgetItem(str(cell_data or '')))
            self.status_table.resizeColumnsToContents()
            self.status_label.setText("Status dos agendamentos atualizado. Clique em uma linha no histórico para ver detalhes.")
        else:
            self.status_label.setText(f"Erro ao buscar agendamentos: {data}")

    def show_execution_details(self, item):
        row = item.row()
        req_id_item = self.status_table.item(row, 1)
        status_item = self.status_table.item(row, 2)

        if not req_id_item or not status_item:
            return

        if status_item.text() not in ["COMPLETED", "COMPLETED_WITH_WARNING", "ERROR"]:
            QMessageBox.information(self, "Aguarde", "Os detalhes de validação só estão disponíveis após a finalização do processo.")
            return

        req_id = req_id_item.text()
        db_section_key = self.db_combo.currentData()
        
        self.status_label.setText(f"Buscando detalhes para a REQ {req_id}...")
        QApplication.processEvents()
        
        success, data = logic.get_final_asset_status(db_section_key, req_id)
        
        self.status_label.setText("Pronto.")
        
        if not success:
            QMessageBox.warning(self, "Erro", f"Não foi possível buscar os detalhes para a REQ {req_id}:\n{data}")
            return

        dialog = ExecutionDetailDialog(req_id, self)
        dialog.populate_data(data)
        dialog.exec()