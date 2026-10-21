# C:\Meus Projetos\MyOps\modules\bat509\bat509_ui.py

import re
import configparser
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QTableWidget,
                             QTableWidgetItem, QHeaderView, QLabel, QGroupBox,
                             QHBoxLayout, QMessageBox, QComboBox, QTextEdit,
                             QProgressBar)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QColor
from . import bat509_logic as logic


class Bat509Worker(QThread):
    finished = pyqtSignal(tuple)
    progress_updated = pyqtSignal(int, str)  # (percentual 0-100, mensagem de etapa)

    def __init__(self, order_id_list, connection_section):
        super().__init__()
        self.order_id_list = order_id_list
        self.connection_section = connection_section

    def run(self):
        try:
            success, output = logic.force_extraction(
                self.order_id_list,
                self.connection_section,
                progress_callback=lambda pct, msg: self.progress_updated.emit(pct, msg),
            )
            self.finished.emit((success, output))
        except Exception as e:
            self.finished.emit((False, f"Erro fatal no worker: {e}"))


class Bat509ToolWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.setWindowTitle("Ferramenta de Marcação - BAT509")

        main_layout = QVBoxLayout(self)

        controls_group = QGroupBox("Controles")
        controls_layout = QVBoxLayout(controls_group)

        connection_layout = QHBoxLayout()
        connection_layout.addWidget(QLabel("Selecione a Conexão:"))
        self.connection_combo = QComboBox()
        self.populate_connections()
        connection_layout.addWidget(self.connection_combo, 1)

        input_label = QLabel("ID da(s) Ordem(ns):")

        self.order_id_input = QTextEdit()
        self.order_id_input.setMinimumHeight(100)
        self.order_id_input.setPlaceholderText(
            "Insira uma ou mais ordens.\nSepare por vírgula, espaço ou quebra de linha (uma por linha)."
        )

        self.run_button = QPushButton("🚀 Forçar Extração")
        self.run_button.setMinimumHeight(40)
        self.run_button.clicked.connect(self.start_extraction)

        self.status_label = QLabel("Pronto para iniciar.")

        # Barra de progresso + contador
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_counter = QLabel("")
        self.progress_counter.setVisible(False)
        progress_layout.addWidget(self.progress_bar, 1)
        progress_layout.addWidget(self.progress_counter)

        controls_layout.addLayout(connection_layout)
        controls_layout.addWidget(input_label)
        controls_layout.addWidget(self.order_id_input)
        controls_layout.addWidget(self.run_button)
        controls_layout.addWidget(self.status_label)
        controls_layout.addLayout(progress_layout)

        results_group = QGroupBox("Resultados")
        results_layout = QVBoxLayout(results_group)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Ordens Enviadas", "Status", "Relatório Detalhado"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        results_layout.addWidget(self.results_table)

        main_layout.addWidget(controls_group)
        main_layout.addWidget(results_group, 1)

    def populate_connections(self):
        self.connection_combo.clear()
        config = configparser.ConfigParser()
        try:
            config.read('config.ini')
            db_connections = [s for s in config.sections() if s.startswith('database_')]
            if not db_connections:
                self.status_label.setText("AVISO: Nenhuma conexão 'database_*' encontrada no config.ini.")
            self.connection_combo.addItems(sorted(db_connections))
        except Exception as e:
            QMessageBox.critical(self, "Erro de Configuração", f"Não foi possível ler as conexões do arquivo config.ini.\n\n{e}")

    def start_extraction(self):
        order_ids_text = self.order_id_input.toPlainText().strip()
        if not order_ids_text:
            QMessageBox.warning(self, "Entrada Inválida", "O campo de ordens não pode ser vazio.")
            return

        selected_connection = self.connection_combo.currentText()
        if not selected_connection:
            QMessageBox.warning(self, "Seleção Inválida", "Nenhuma conexão de banco de dados foi selecionada.")
            return

        order_id_list = re.split(r'[,\s\n]+', order_ids_text)
        order_id_list = [item for item in order_id_list if item]

        if not order_id_list:
            QMessageBox.warning(self, "Entrada Inválida", "Nenhuma ordem válida encontrada após a limpeza.")
            return

        total = len(order_id_list)
        self.run_button.setEnabled(False)
        self.run_button.setText("Executando...")
        self.results_table.setRowCount(0)
        self.status_label.setText(f"Processando {total:,} ordem(ns) em '{selected_connection}'...")

        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.progress_counter.setText("0%")
        self.progress_counter.setVisible(True)

        self.worker = Bat509Worker(order_id_list, selected_connection)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.finished.connect(self.on_extraction_finished)
        self.worker.start()

    def on_progress_updated(self, pct, msg):
        self.progress_bar.setValue(pct)
        self.progress_counter.setText(f"{pct}%")
        self.status_label.setText(msg)

    def on_extraction_finished(self, result):
        success, report_message = result

        self.progress_bar.setVisible(False)
        self.progress_counter.setVisible(False)

        self.results_table.setRowCount(1)

        # Determina status visual baseado no conteúdo da mensagem
        msg_lower = report_message.lower()
        if success:
            status_text = "Sucesso"
            bg_color = QColor("#d4edda")
        elif "já marcadas" in msg_lower or "already" in msg_lower:
            status_text = "Aviso"
            bg_color = QColor("#fff3cd")
        else:
            status_text = "Falha"
            bg_color = QColor("#f8d7da")

        text_color = QColor("#212529")  # sempre texto escuro legível

        item_orders = QTableWidgetItem(f"{len(self.worker.order_id_list):,} ordens enviadas")
        item_status = QTableWidgetItem(status_text)
        item_report = QTableWidgetItem(report_message)

        self.results_table.setItem(0, 0, item_orders)
        self.results_table.setItem(0, 1, item_status)
        self.results_table.setItem(0, 2, item_report)

        for col in range(3):
            self.results_table.item(0, col).setBackground(bg_color)
            self.results_table.item(0, col).setForeground(text_color)

        self.status_label.setText(f"Processo finalizado. Status: {status_text}.")
        self.run_button.setEnabled(True)
        self.run_button.setText("🚀 Forçar Extração")
