# C:\Meus Projetos\MyOps\modules\gfa\gfa_ui.py (Versão Revertida - Terminal Externo)
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QComboBox,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QLabel, QGroupBox)
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from . import gfa_logic as logic

class GfaWorker(QThread):
    finished = pyqtSignal(tuple)

    def __init__(self, host_alias):
        super().__init__()
        self.host_alias = host_alias

    def run(self):
        # Chama a função de lógica que usa o terminal externo
        success, output = logic.run_health_check_with_temp_script(self.host_alias)
        self.finished.emit((success, output))

class GfaHealthWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.setWindowTitle("Monitor de Health Check - GFA")

        main_layout = QVBoxLayout(self)
        controls_group = QGroupBox("Controles")
        controls_layout = QVBoxLayout(controls_group)
        self.connection_combo = QComboBox()
        self.connection_combo.addItem("Produção GFA", "gfa-prod")
        self.run_button = QPushButton("🚀 Iniciar Verificação de Health Check")
        self.run_button.setMinimumHeight(40)
        self.run_button.clicked.connect(self.start_check)
        self.status_label = QLabel("Pronto para iniciar.")
        controls_layout.addWidget(QLabel("Selecione a Conexão:"))
        controls_layout.addWidget(self.connection_combo)
        controls_layout.addWidget(self.run_button)
        controls_layout.addWidget(self.status_label)
        results_group = QGroupBox("Resultados")
        results_layout = QVBoxLayout(results_group)
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(8)
        self.results_table.setHorizontalHeaderLabels([
            "Servidor", "Cluster", "Máquina", "Estado", "Saúde", 
            "Porta", "Sockets Abertos", "Carga CPU"
        ])
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        results_layout.addWidget(self.results_table)
        main_layout.addWidget(controls_group)
        main_layout.addWidget(results_group)

    def start_check(self):
        self.run_button.setEnabled(False)
        self.run_button.setText("Aguardando no Terminal Externo...")
        self.results_table.setRowCount(0)
        self.status_label.setText("Aguardando autenticação no terminal pop-up...")

        host_alias = self.connection_combo.currentData()
        self.worker = GfaWorker(host_alias)
        self.worker.finished.connect(self.on_check_finished)
        self.worker.start()

    def on_check_finished(self, result):
        success, output = result
        if success:
            self.status_label.setText("Execução concluída com sucesso. Resultados abaixo.")
            self.parse_and_display_log(output)
        else:
            self.status_label.setText(f"ERRO: {output}")
        self.run_button.setEnabled(True)
        self.run_button.setText("🚀 Iniciar Verificação de Health Check")

    def parse_and_display_log(self, log_content):
        lines = [line for line in log_content.strip().split('\n') if line.strip()]
        if not lines:
            self.status_label.setText("Execução concluída, mas nenhum dado foi retornado.")
            return
        self.results_table.setRowCount(len(lines))
        for row, line in enumerate(lines):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) != 8:
                item = QTableWidgetItem(f"Linha de dados inválida: {line}")
                self.results_table.setItem(row, 0, item)
                for col in range(1, 8):
                    self.results_table.setItem(row, col, QTableWidgetItem("-"))
                continue
            server, cluster, machine, state, health, port, sockets, cpu = parts
            color = QColor("white")
            if "RUNNING" not in state.upper():
                color = QColor("#fff3cd")
            if "HEALTH_OK" not in health.upper():
                color = QColor("#f8d7da")
            if "RUNNING" in state.upper() and "HEALTH_OK" in health.upper():
                color = QColor("#d4edda")
            columns_data = [server, cluster, machine, state, health, port, sockets, cpu]
            for col, data in enumerate(columns_data):
                item = QTableWidgetItem(data)
                item.setBackground(color)
                self.results_table.setItem(row, col, item)