# C:\Meus Projetos\MyOps\modules\sql_loader\sql_loader_ui.py

import sys
import csv
import os
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QMessageBox, QLineEdit, 
                             QLabel, QGroupBox, QHBoxLayout, QRadioButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QComboBox, QTextEdit, QFileDialog, QFormLayout, QTabWidget)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDateTime
from modules.sql_loader import sql_loader_logic as db

class SqlLoaderWorker(QThread):
    finished = pyqtSignal(tuple)
    error = pyqtSignal(str)

    def __init__(self, file_path, db_key, schema, table, delimiter, load_method, columns):
        super().__init__()
        self.file_path = file_path
        self.db_key = db_key
        self.schema = schema
        self.table = table
        self.delimiter = delimiter
        self.load_method = load_method
        self.columns = columns

    def run(self):
        try:
            ctl_path = db.generate_control_file(self.file_path, self.table, self.schema, self.delimiter, self.columns, self.load_method)
            log_content, bad_content, exit_code = db.run_sql_loader(self.db_key, ctl_path)
            self.finished.emit((log_content, bad_content, exit_code))
        except Exception as e:
            self.error.emit(str(e))

class DropArea(QLabel):
    fileDropped = pyqtSignal(str)
    def __init__(self, text="Arraste e solte o arquivo (.csv ou .txt) aqui"):
        super().__init__(text)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("QLabel { border: 2px dashed #aaa; border-radius: 5px; font: 12pt; color: #888; }")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and len(event.mimeData().urls()) == 1:
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().urls()[0].isLocalFile():
            self.fileDropped.emit(event.mimeData().urls()[0].toLocalFile())

class SqlLoaderWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.selected_file_path = ""
        main_layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Aba 1: Configuração
        setup_tab = QWidget()
        setup_layout = QVBoxLayout(setup_tab)
        self.tabs.addTab(setup_tab, "Configuração da Carga")
        
        # Aba 2: Log
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.tabs.addTab(log_tab, "Log e Resultados")

        # Grupo 1: Seleção de Arquivo
        group1 = QGroupBox("1. Seleção de Arquivo e Formato")
        layout1 = QVBoxLayout(group1)
        self.drop_area = DropArea()
        self.drop_area.setMinimumHeight(150)
        self.browse_button = QPushButton("Ou Selecione um Arquivo...")
        
        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Delimitador de Campos:"))
        self.delimiter_input = QLineEdit(";")
        self.delimiter_input.setFixedWidth(50)
        form_layout.addWidget(self.delimiter_input)
        form_layout.addStretch()

        layout1.addWidget(self.drop_area, 1)
        layout1.addWidget(self.browse_button)
        layout1.addLayout(form_layout)
        setup_layout.addWidget(group1)

        # Grupo 2: Destino da Carga
        group2 = QGroupBox("2. Destino da Carga")
        layout2 = QFormLayout(group2)
        self.db_combo = QComboBox()
        self.schema_input = QLineEdit(placeholderText="Ex: SIEBEL")
        self.table_input = QLineEdit(placeholderText="Deixe em branco para criar tabela automática")
        load_method_layout = QHBoxLayout()
        self.append_radio = QRadioButton("Adicionar registros à tabela")
        self.append_radio.setChecked(True)
        self.truncate_radio = QRadioButton("Truncar tabela antes de inserir")
        load_method_layout.addWidget(self.append_radio)
        load_method_layout.addWidget(self.truncate_radio)
        layout2.addRow("Base de Dados:", self.db_combo)
        layout2.addRow("Schema:", self.schema_input)
        layout2.addRow("Tabela:", self.table_input)
        layout2.addRow("Método de Carga:", load_method_layout)
        setup_layout.addWidget(group2)

        # Grupo 3: Pré-visualização
        group3 = QGroupBox("3. Pré-visualização (100 primeiras linhas)")
        layout3 = QVBoxLayout(group3)
        self.preview_table = QTableWidget()
        layout3.addWidget(self.preview_table)
        setup_layout.addWidget(group3, 1)

        # Botão de Carga
        self.load_button = QPushButton("Iniciar Carga")
        self.load_button.setMinimumHeight(40)
        setup_layout.addWidget(self.load_button)

        # Grupo 4: Log e Resultados (na segunda aba)
        group4 = QGroupBox("4. Log e Resultados")
        layout4 = QVBoxLayout(group4)
        self.log_output = QTextEdit(readOnly=True)
        self.log_output.setFont(QFont("Courier", 9))
        layout4.addWidget(self.log_output)
        log_layout.addWidget(group4)

        # Conexões
        self.populate_db_combo()
        self.browse_button.clicked.connect(self.on_browse)
        self.drop_area.fileDropped.connect(self.on_file_selected)
        self.delimiter_input.textChanged.connect(self.update_preview)
        self.load_button.clicked.connect(self.on_load)

    def populate_db_combo(self):
        try:
            connections = db.get_all_db_connections()
            for key, name in connections.items():
                self.db_combo.addItem(name, key)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível carregar as conexões do config.ini:\n{e}")

    def on_browse(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Selecione o arquivo para carga", "", "CSV e TXT (*.csv *.txt);;Todos os Arquivos (*)")
        if file_path:
            self.on_file_selected(file_path)

    def on_file_selected(self, file_path):
        self.selected_file_path = file_path
        self.drop_area.setText(f"Arquivo Selecionado:\n{os.path.basename(file_path)}")
        self.update_preview()

    def update_preview(self):
        if not self.selected_file_path:
            return
        delimiter = self.delimiter_input.text()
        if not delimiter:
            return
        self.preview_table.clear()
        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(0)
        try:
            with open(self.selected_file_path, 'r', encoding='latin-1') as f:
                reader = csv.reader(f, delimiter=delimiter)
                header = next(reader)
                self.preview_table.setColumnCount(len(header))
                self.preview_table.setHorizontalHeaderLabels(header)
                for i, row in enumerate(reader):
                    if i >= 100:
                        break
                    self.preview_table.insertRow(i)
                    for j, field in enumerate(row):
                        if j < len(header):
                            self.preview_table.setItem(i, j, QTableWidgetItem(field))
            self.preview_table.resizeColumnsToContents()
        except Exception as e:
            self.preview_table.setColumnCount(1)
            self.preview_table.setHorizontalHeaderLabels(["Erro na Pré-visualização"])
            self.preview_table.setRowCount(1)
            self.preview_table.setItem(0, 0, QTableWidgetItem(str(e)))

    def on_load(self):
        db_key = self.db_combo.currentData()
        schema = self.schema_input.text().strip()
        table = self.table_input.text().strip()
        delimiter = self.delimiter_input.text()
        load_method = "Truncar" if self.truncate_radio.isChecked() else "Adicionar"
        
        if not all([self.selected_file_path, db_key, schema, delimiter]):
            QMessageBox.warning(self, "Campos Incompletos", "Por favor, preencha todos os campos obrigatórios (Base de Dados, Schema, Delimitador) e selecione um arquivo.")
            return
        
        if table and not table.upper().startswith("PM_TMP"):
            QMessageBox.critical(self, "Erro de Segurança", "Carga não permitida. O nome da tabela de destino deve começar com 'PM_TMP'.")
            return
            
        if table and load_method == "Truncar":
            if QMessageBox.question(self, "Confirmar TRUNCATE", f"Tem certeza que deseja apagar TODOS os dados da tabela '{schema}.{table}'?\n\nEsta ação é irreversível.",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No:
                return
            
        self.load_button.setEnabled(False)
        self.load_button.setText("Analisando arquivo...")
        self.tabs.setCurrentWidget(self.tabs.widget(1)) # Muda para a aba de log
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        self.log_output.setText(f"[{timestamp}] Iniciando processo de carga...\n")
        QApplication.processEvents()

        try:
            self.log_output.append("Analisando arquivo para inferir tipos de dados...")
            QApplication.processEvents()
            inferred_columns = db.infer_column_types(self.selected_file_path, delimiter)
            self.log_output.append("Tipos de colunas inferidos com sucesso.")
            
            final_table_name = table
            if not table:
                self.log_output.append("\nNenhum nome de tabela informado. Criando tabela temporária...")
                QApplication.processEvents()
                final_table_name = db.create_temporary_table(db_key, schema, inferred_columns)
                self.log_output.append(f"Tabela temporária '{final_table_name}' criada com sucesso.")
                load_method = "Adicionar"
            
            self.load_button.setText("Carregando...")
            self.log_output.append(f"\nIniciando carga do arquivo '{os.path.basename(self.selected_file_path)}' para a tabela '{schema}.{final_table_name}'...")
            QApplication.processEvents()
            
            self.worker = SqlLoaderWorker(self.selected_file_path, db_key, schema, final_table_name, delimiter, load_method, inferred_columns)
            self.worker.finished.connect(self.on_load_finished)
            self.worker.error.connect(self.on_load_error)
            self.worker.start()

        except Exception as e:
            self.on_load_error(str(e))

    def on_load_finished(self, result_tuple):
        log_content, bad_content, exit_code = result_tuple
        self.log_output.append("\n--- LOG DO SQL*LOADER ---\n")
        self.log_output.append(log_content)
        if bad_content:
            self.log_output.append("\n--- REGISTROS REJEITADOS (.bad) ---\n")
            self.log_output.append(bad_content)
        
        if exit_code == 0:
            QMessageBox.information(self, "Carga Concluída", "A carga foi concluída com sucesso. Verifique o log para detalhes.")
        elif exit_code == 2:
            QMessageBox.warning(self, "Carga Concluída com Rejeições", "A carga foi concluída, mas alguns registros foram rejeitados. Verifique o log.")
        else:
            QMessageBox.critical(self, "Falha na Carga", "Ocorreu um erro durante a carga do SQL*Loader. Verifique o log para identificar a causa.")
            
        self.load_button.setEnabled(True)
        self.load_button.setText("Iniciar Carga")

    def on_load_error(self, error_message):
        self.log_output.append(f"\n--- ERRO NA EXECUÇÃO ---\n{error_message}")
        QMessageBox.critical(self, "Erro na Carga", error_message)
        self.load_button.setEnabled(True)
        self.load_button.setText("Iniciar Carga")