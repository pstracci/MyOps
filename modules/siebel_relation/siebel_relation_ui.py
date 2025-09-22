# C:\Meus Projetos\MyOps\modules\siebel_relation\siebel_relation_ui.py

import configparser
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QComboBox, QGroupBox, QTableWidget, QTableWidgetItem, QMessageBox,
    QHeaderView
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt

from modules.siebel_relation import siebel_relation_logic as logic

class RelationQueryWorker(QThread):
    """Executa a consulta em background para não travar a UI."""
    finished = pyqtSignal(list, list)
    error = pyqtSignal(str)

    def __init__(self, db_section, src_table, dest_table):
        super().__init__()
        self.db_section = db_section
        self.src_table = src_table
        self.dest_table = dest_table

    def run(self):
        try:
            headers, data = logic.get_relationships(self.db_section, self.src_table, self.dest_table)
            self.finished.emit(headers, data)
        except Exception as e:
            self.error.emit(str(e))

class SiebelRelationWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        main_layout = QVBoxLayout(self)

        # --- Grupo de Controles ---
        controls_group = QGroupBox("Parâmetros da Consulta")
        controls_layout = QVBoxLayout(controls_group)

        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Conexão Siebel:"))
        self.connection_combo = QComboBox()
        self.populate_connections()
        form_layout.addWidget(self.connection_combo, 1)

        form_layout.addWidget(QLabel("Tabela de Origem:"))
        self.src_table_input = QLineEdit()
        self.src_table_input.setPlaceholderText("Ex: S_ASSET")
        form_layout.addWidget(self.src_table_input, 1)

        form_layout.addWidget(QLabel("Tabela de Destino:"))
        self.dest_table_input = QLineEdit()
        self.dest_table_input.setPlaceholderText("Ex: S_ORG_EXT")
        form_layout.addWidget(self.dest_table_input, 1)

        button_layout = QHBoxLayout()
        self.run_button = QPushButton("Consultar Relacionamentos")
        self.clear_button = QPushButton("Nova Consulta")
        button_layout.addStretch()
        button_layout.addWidget(self.run_button)
        button_layout.addWidget(self.clear_button)

        controls_layout.addLayout(form_layout)
        controls_layout.addLayout(button_layout)
        
        # --- Grupo de Resultados ---
        results_group = QGroupBox("Resultados")
        results_layout = QVBoxLayout(results_group)
        self.results_table = QTableWidget()
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.status_label = QLabel("Informe as tabelas e clique em 'Consultar'.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        results_layout.addWidget(self.status_label)
        results_layout.addWidget(self.results_table)

        main_layout.addWidget(controls_group)
        main_layout.addWidget(results_group, 1)

        # --- Conexões de Sinais ---
        self.run_button.clicked.connect(self.on_run_query)
        self.clear_button.clicked.connect(self.on_clear)

    def populate_connections(self):
        self.connection_combo.clear()
        config = configparser.ConfigParser()
        try:
            config.read('config.ini')
            db_connections = [s for s in config.sections() if s.startswith('database_')]
            self.connection_combo.addItems(sorted(db_connections))
        except Exception as e:
            QMessageBox.critical(self, "Erro de Configuração", f"Não foi possível ler as conexões do arquivo config.ini.\n\n{e}")

    def on_run_query(self):
        db_section = self.connection_combo.currentText()
        src_table = self.src_table_input.text().strip()
        dest_table = self.dest_table_input.text().strip()

        if not db_section:
            QMessageBox.warning(self, "Ação Inválida", "Selecione uma conexão de banco de dados.")
            return
        if not src_table or not dest_table:
            QMessageBox.warning(self, "Ação Inválida", "Preencha os nomes das duas tabelas.")
            return

        self.run_button.setEnabled(False)
        self.run_button.setText("Consultando...")
        self.status_label.setText(f"Buscando relacionamentos entre '{src_table.upper()}' e '{dest_table.upper()}'...")
        self.results_table.setRowCount(0)

        self.worker = RelationQueryWorker(db_section, src_table, dest_table)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def on_clear(self):
        self.src_table_input.clear()
        self.dest_table_input.clear()
        self.results_table.setRowCount(0)
        self.results_table.setColumnCount(0)
        self.status_label.setText("Informe as tabelas e clique em 'Consultar'.")
        self.src_table_input.setFocus()

    def on_worker_finished(self, headers, data):
        self.run_button.setEnabled(True)
        self.run_button.setText("Consultar Relacionamentos")

        if not data:
            self.status_label.setText("Nenhum relacionamento encontrado para as tabelas informadas.")
            return

        self.status_label.setText(f"{len(data)} relacionamento(s) encontrado(s).")
        
        self.results_table.setColumnCount(len(headers))
        self.results_table.setHorizontalHeaderLabels(headers)
        self.results_table.setRowCount(len(data))

        for row_idx, row_data in enumerate(data):
            for col_idx, col_item in enumerate(row_data):
                self.results_table.setItem(row_idx, col_idx, QTableWidgetItem(str(col_item)))
        
        self.results_table.resizeColumnsToContents()
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)


    def on_worker_error(self, error_message):
        self.run_button.setEnabled(True)
        self.run_button.setText("Consultar Relacionamentos")
        self.status_label.setText("Ocorreu um erro durante a consulta.")
        QMessageBox.critical(self, "Erro na Consulta", error_message)
