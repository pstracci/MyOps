# C:\Meus Projetos\MyOps\modules\bat509\bat509_ui.py (Versão Corrigida)

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLabel, QGroupBox, 
                             QLineEdit, QHBoxLayout)
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QColor
# Assumindo que você terá um arquivo bat509_logic.py para a lógica desta ferramenta
from . import bat509_logic as logic 

# CLASSE RENOMEADA: De GfaWorker para Bat509Worker
class Bat509Worker(QThread):
    finished = pyqtSignal(tuple)

    # Lógica adaptada para o BAT509 (ex: passar um ID de ordem)
    def __init__(self, order_id):
        super().__init__()
        self.order_id = order_id

    def run(self):
        # Chama uma função de lógica específica do BAT509
        # (O nome da função 'force_extraction' é um exemplo)
        success, output = logic.force_extraction(self.order_id)
        self.finished.emit((success, output))

# CLASSE PRINCIPAL RENOMEADA: De GfaHealthWidget para Bat509ToolWidget
class Bat509ToolWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        # TÍTULO CORRIGIDO
        self.setWindowTitle("Ferramenta de Marcação - BAT509")

        main_layout = QVBoxLayout(self)
        
        # --- UI Adaptada para a ferramenta BAT509 ---
        controls_group = QGroupBox("Controles")
        controls_layout = QVBoxLayout(controls_group)
        
        input_layout = QHBoxLayout()
        self.order_id_input = QLineEdit()
        self.order_id_input.setPlaceholderText("Digite o ID da Ordem ou Contrato...")
        
        input_layout.addWidget(QLabel("ID da Ordem:"))
        input_layout.addWidget(self.order_id_input)
        
        self.run_button = QPushButton("🚀 Forçar Extração")
        self.run_button.setMinimumHeight(40)
        self.run_button.clicked.connect(self.start_extraction)
        
        self.status_label = QLabel("Pronto para iniciar.")
        
        controls_layout.addLayout(input_layout)
        controls_layout.addWidget(self.run_button)
        controls_layout.addWidget(self.status_label)
        
        # --- Grupo de Resultados Adaptado ---
        results_group = QGroupBox("Resultados")
        results_layout = QVBoxLayout(results_group)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Ordem", "Status", "Mensagem"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        results_layout.addWidget(self.results_table)

        main_layout.addWidget(controls_group)
        main_layout.addWidget(results_group)

    def start_extraction(self):
        order_id = self.order_id_input.text().strip()
        if not order_id:
            self.status_label.setText("ERRO: O ID da Ordem não pode ser vazio.")
            return

        self.run_button.setEnabled(False)
        self.run_button.setText("Executando...")
        self.results_table.setRowCount(0)
        self.status_label.setText(f"Processando extração para a ordem: {order_id}...")
        
        self.worker = Bat509Worker(order_id)
        self.worker.finished.connect(self.on_extraction_finished)
        self.worker.start()

    def on_extraction_finished(self, result):
        success, output = result
        
        if success:
            self.status_label.setText("Execução concluída com sucesso.")
            # Adapte a lógica de parsing para o resultado esperado do BAT509
            self.parse_and_display_log(output) 
        else:
            self.status_label.setText(f"ERRO: {output}")
        
        self.run_button.setEnabled(True)
        self.run_button.setText("🚀 Forçar Extração")

    def parse_and_display_log(self, log_content):
        # Esta função é um exemplo de como você poderia exibir o resultado.
        # Você precisará adaptá-la para o formato real do retorno do seu bat509_logic.
        self.results_table.setRowCount(1)
        order_id = self.order_id_input.text().strip()
        
        status_item = QTableWidgetItem("Sucesso")
        color = QColor("#d4edda") # Verde
        
        self.results_table.setItem(0, 0, QTableWidgetItem(order_id))
        self.results_table.setItem(0, 1, status_item)
        self.results_table.setItem(0, 2, QTableWidgetItem(log_content))
        
        # Pinta o fundo da linha
        for col in range(3):
            self.results_table.item(0, col).setBackground(color)