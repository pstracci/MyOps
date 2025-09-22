# C:\Meus Projetos\fixer\modules\bat509\bat509_ui.py

import sys
import re
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QMessageBox, QMainWindow, QLineEdit, QLabel, QGroupBox, QHBoxLayout, QTextEdit)
from PyQt6.QtGui import QFont, QAction
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDateTime

from modules.bat509 import bat509_logic as db

class MarkOrderWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, order_numbers):
        super().__init__()
        self.order_numbers = order_numbers
        
    def run(self):
        try:
            result_message = db.mark_orders_for_extraction(self.order_numbers)
            self.finished.emit(result_message)
        except Exception as e:
            self.error.emit(str(e))

class Bat509ToolWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        main_layout = QVBoxLayout(self)

        # --- Grupo de Controles ---
        controls_group = QGroupBox("Forçar Extração de Ordens de Serviço (BAT509)")
        controls_layout = QVBoxLayout()
        
        description_label = QLabel("Informe uma ou mais Ordens de Serviço (Order Number), separadas por vírgula ou quebra de linha.")
        description_label.setWordWrap(True)
        
        self.order_input = QTextEdit()
        self.order_input.setPlaceholderText("Ex: 1-ABCDE, 1-FGHIJ\n1-KLMNO")
        self.order_input.setFixedHeight(100)
        
        # --- NOVO: Layout para os botões ---
        button_layout = QHBoxLayout()
        self.mark_button = QPushButton("Marcar Ordem(ns) para Extração")
        self.mark_button.clicked.connect(self.on_mark_order)
        self.mark_button.setMinimumHeight(40)
        
        # NOVO: Botão de Limpar
        self.clear_button = QPushButton("Limpar")
        self.clear_button.clicked.connect(self.on_clear)
        self.clear_button.setMinimumHeight(40)

        button_layout.addWidget(self.mark_button, 2) # Dá mais espaço ao botão principal
        button_layout.addWidget(self.clear_button, 1)

        controls_layout.addWidget(description_label)
        controls_layout.addWidget(self.order_input)
        controls_layout.addLayout(button_layout) # Adiciona o layout dos botões
        controls_group.setLayout(controls_layout)

        # --- Grupo de Log/Resultado ---
        log_group = QGroupBox("Log de Operações")
        log_layout = QVBoxLayout()
        self.log_output = QTextEdit(readOnly=True)
        self.log_output.setFont(QFont("Courier", 9))
        self.log_output.setStyleSheet("background-color: #f0f0f0;")
        log_layout.addWidget(self.log_output)
        log_group.setLayout(log_layout)
        
        main_layout.addWidget(controls_group)
        main_layout.addWidget(log_group)

    def log_message(self, message):
        """Adiciona uma mensagem ao log com timestamp."""
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        self.log_output.append(f"[{timestamp}] {message}")

    def on_mark_order(self):
        input_text = self.order_input.toPlainText().strip()
        if not input_text:
            QMessageBox.warning(self, "Entrada Inválida", "Por favor, informe ao menos uma Ordem de Serviço.")
            return

        order_numbers = re.split(r'[,\s\n]+', input_text)
        order_numbers = [num for num in order_numbers if num]
        
        if not order_numbers:
            QMessageBox.warning(self, "Entrada Inválida", "Nenhum número de ordem válido foi encontrado na sua entrada."); return

        self.mark_button.setEnabled(False)
        self.mark_button.setText("Processando...")
        self.log_message(f"Iniciando processo para {len(order_numbers)} ordem(ns): {', '.join(order_numbers)}...")

        self.worker = MarkOrderWorker(order_numbers)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    # NOVO: Função para o botão de limpar
    def on_clear(self):
        self.order_input.clear()
        self.log_output.clear()
        self.log_message("Campos de entrada e log foram limpos.")

    def on_worker_finished(self, message):
        self.log_message(f"Processo Finalizado.\nRelatório:\n{message}\n")
        QMessageBox.information(self, "Processo Concluído", message)
        self.mark_button.setEnabled(True)
        self.mark_button.setText("Marcar Ordem(ns) para Extração")
        self.order_input.clear()

    def on_worker_error(self, error_message):
        self.log_message(f"ERRO: {error_message}")
        QMessageBox.critical(self, "Erro na Operação", error_message)
        self.mark_button.setEnabled(True)
        self.mark_button.setText("Marcar Ordem(ns) para Extração")
