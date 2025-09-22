# C:\Meus Projetos\MyOps\modules\bat223\bat223_ui.py

import sys
import re
import configparser  # Importado para ler as conexões
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QMessageBox, QMainWindow,
    QLineEdit, QLabel, QGroupBox, QHBoxLayout, QTextEdit, QRadioButton, QComboBox
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDateTime

from modules.bat223 import bat223_logic as db

class Bat223Worker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    # --- ALTERAÇÃO 1: Adicionado 'connection_section' ao construtor ---
    def __init__(self, environment, msisdn_list, connection_section):
        super().__init__()
        self.environment = environment
        self.msisdn_list = msisdn_list
        self.connection_section = connection_section

    def run(self):
        try:
            # --- ALTERAÇÃO 2: Passa a conexão selecionada para a lógica ---
            result_message = db.force_bat223_extraction(self.environment, self.msisdn_list, self.connection_section)
            self.finished.emit(result_message)
        except Exception as e:
            self.error.emit(str(e))

class Bat223ToolWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        main_layout = QVBoxLayout(self)

        controls_group = QGroupBox("Forçar Extração de Clientes (BAT223)")
        controls_layout = QVBoxLayout(controls_group)

        # --- ALTERAÇÃO 3: Layout para seleção de conexão ---
        connection_layout = QHBoxLayout()
        connection_layout.addWidget(QLabel("Selecione a Conexão:"))
        self.connection_combo = QComboBox()
        self.populate_connections() # Popula o ComboBox com as conexões do config.ini
        connection_layout.addWidget(self.connection_combo, 1)

        # --- Layout para tipo de ambiente (a lógica SQL depende disso) ---
        env_layout = QHBoxLayout()
        env_layout.addWidget(QLabel("Tipo de Ambiente:"))
        self.pos_radio = QRadioButton("Pós-Pago"); self.pos_radio.setChecked(True)
        self.pre_radio = QRadioButton("Pré-Pago")
        env_layout.addWidget(self.pos_radio)
        env_layout.addWidget(self.pre_radio)
        env_layout.addStretch()

        description_label = QLabel("Informe um ou mais MSISDNs, separados por vírgula ou quebra de linha.")
        description_label.setWordWrap(True)

        self.msisdn_input = QTextEdit()
        self.msisdn_input.setPlaceholderText("Ex: 5521999998888, 5511988887777\n5541977776666")
        self.msisdn_input.setMinimumHeight(120)

        button_layout = QHBoxLayout()
        self.run_button = QPushButton("Forçar Extração BAT223")
        self.run_button.setMinimumHeight(40)
        self.clear_button = QPushButton("Limpar")
        self.clear_button.setMinimumHeight(40)
        button_layout.addWidget(self.run_button, 2)
        button_layout.addWidget(self.clear_button, 1)

        # Adiciona os novos layouts
        controls_layout.addLayout(connection_layout) # Adicionado
        controls_layout.addLayout(env_layout)
        controls_layout.addWidget(description_label)
        controls_layout.addWidget(self.msisdn_input)
        controls_layout.addLayout(button_layout)

        log_group = QGroupBox("Log de Operações")
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextEdit(readOnly=True)
        self.log_output.setFont(QFont("Courier", 9))

        log_layout.addWidget(self.log_output)

        main_layout.addWidget(controls_group)
        main_layout.addWidget(log_group, 1)

        self.run_button.clicked.connect(self.on_run_process)
        self.clear_button.clicked.connect(self.on_clear)

    # --- ALTERAÇÃO 4: Nova função para popular o ComboBox de conexões ---
    def populate_connections(self):
        self.connection_combo.clear()
        config = configparser.ConfigParser()
        try:
            config.read('config.ini')
            db_connections = [s for s in config.sections() if s.startswith('database_')]
            self.connection_combo.addItems(sorted(db_connections))
        except Exception as e:
            self.log_message(f"Erro ao ler conexões do config.ini: {e}")
            QMessageBox.critical(self, "Erro de Configuração", f"Não foi possível ler as conexões do arquivo config.ini.\n\n{e}")

    def log_message(self, message):
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        self.log_output.append(f"[{timestamp}] {message}")

    def on_run_process(self):
        # --- ALTERAÇÃO 5: Obtém a conexão selecionada pelo usuário ---
        selected_connection = self.connection_combo.currentText()
        if not selected_connection:
            QMessageBox.warning(self, "Seleção Inválida", "Nenhuma conexão de banco de dados foi selecionada. Verifique o Gerenciador de Conexões.")
            return

        input_text = self.msisdn_input.toPlainText().strip()
        if not input_text:
            QMessageBox.warning(self, "Entrada Inválida", "Por favor, informe ao menos um MSISDN.")
            return

        msisdn_list = re.split(r'[,\s\n]+', input_text)
        msisdn_list = [num for num in msisdn_list if num]

        if not msisdn_list:
            QMessageBox.warning(self, "Entrada Inválida", "Nenhum MSISDN válido foi encontrado.")
            return

        environment = 'pos' if self.pos_radio.isChecked() else 'pre'

        reply = QMessageBox.question(self, 'Confirmação',
            f"Você está prestes a forçar a extração de {len(msisdn_list)} clientes na conexão '{selected_connection}' (ambiente {environment.upper()}).\n\nEsta ação irá TRUNCAR tabelas e executar UPDATES em produção.\n\nDeseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.No:
            return

        self.run_button.setEnabled(False)
        self.run_button.setText("Processando...")
        self.log_message(f"Iniciando processo para {len(msisdn_list)} MSISDNs na conexão '{selected_connection}' ({environment.upper()})...")

        # --- ALTERAÇÃO 6: Passa a conexão selecionada para o Worker ---
        self.worker = Bat223Worker(environment, msisdn_list, selected_connection)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def on_clear(self):
        self.msisdn_input.clear()
        self.log_output.clear()
        self.log_message("Campos limpos.")

    def on_worker_finished(self, message):
        self.log_output.append("\n--- LOG DETALHADO DA EXECUÇÃO ---\n")
        self.log_output.append(message)
        self.log_output.append("\n--- PROCESSO FINALIZADO ---")
        QMessageBox.information(self, "Processo Concluído", "A operação foi concluída com sucesso. Verifique o log para detalhes.")
        self.run_button.setEnabled(True)
        self.run_button.setText("Forçar Extração BAT223")

    def on_worker_error(self, error_message):
        self.log_output.append(f"\n--- ERRO NA EXECUÇÃO ---\n{error_message}")
        QMessageBox.critical(self, "Erro na Operação", error_message)
        self.run_button.setEnabled(True)
        self.run_button.setText("Forçar Extração BAT223")