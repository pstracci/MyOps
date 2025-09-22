# C:\Meus Projetos\MyOps\modules\top_sql\top_sql_ui.py

import sys
import time
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QSplitter, QTextEdit, QLabel, QSpinBox,
                             QComboBox, QHeaderView, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from modules.top_sql.top_sql_logic import TopSqlLogic
from modules.session_monitor.session_monitor_logic import get_all_db_connections

class TopSqlWorker(QThread):
    """Worker que orquestra as etapas e emite sinais de progresso."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, db_key, interval):
        super().__init__()
        self.db_key = db_key
        self.interval = interval

    def run(self):
        try:
            logic = TopSqlLogic(self.db_key)

            self.progress.emit("Iniciando 1º snapshot...")
            snapshot1 = logic.take_snapshot()

            self.progress.emit(f"1º snapshot concluído. Aguardando {self.interval}s...")
            time.sleep(self.interval)

            self.progress.emit("Iniciando 2º snapshot...")
            snapshot2 = logic.take_snapshot()

            self.progress.emit("Calculando deltas...")
            delta_results = self.calculate_deltas(snapshot1, snapshot2)
            
            self.progress.emit("Dados prontos.")
            self.finished.emit(delta_results)

        except Exception as e:
            self.error.emit(str(e))
    
    def calculate_deltas(self, s1, s2, top_n=50):
        delta_results = []
        for sql_id, s2_data in s2.items():
            s1_data = s1.get(sql_id)
            if s1_data and s2_data['elapsed_time'] > s1_data['elapsed_time']:
                cpu_delta = (s2_data['cpu_time'] - s1_data['cpu_time']) / 1_000_000
                elapsed_delta = (s2_data['elapsed_time'] - s1_data['elapsed_time']) / 1_000_000
                executions_delta = s2_data['executions'] - s1_data['executions']
                disk_reads_delta = s2_data['disk_reads'] - s1_data['disk_reads']
                rows_processed_delta = s2_data['rows_processed'] - s1_data['rows_processed']

                if elapsed_delta > 0 or executions_delta > 0:
                    delta_results.append({
                        'sql_id': sql_id, 'parsing_schema_name': s2_data['parsing_schema_name'],
                        'cpu_s': cpu_delta, 'elapsed_s': elapsed_delta, 'executions': executions_delta,
                        'disk_reads': disk_reads_delta, 'rows_processed': rows_processed_delta,
                        'sql_text': s2_data['sql_text_snippet']
                    })
        return sorted(delta_results, key=lambda x: x['elapsed_s'], reverse=True)[:top_n]


class TopSqlMonitorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.is_monitoring = False
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.run_worker_update)

        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)
        top_widget = QWidget()
        bottom_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        
        controls_layout = QHBoxLayout()
        self.db_combo = QComboBox()
        self.populate_db_combo()
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(5, 60)
        self.interval_spinbox.setValue(10)
        self.interval_spinbox.setSuffix(" s")
        self.start_stop_button = QPushButton("▶ Iniciar Monitoramento")
        self.status_label = QLabel("Parado.")
        self.status_label.setStyleSheet("color: gray;")
        
        controls_layout.addWidget(QLabel("Base:"))
        controls_layout.addWidget(self.db_combo)
        controls_layout.addWidget(QLabel("Intervalo:"))
        controls_layout.addWidget(self.interval_spinbox)
        controls_layout.addWidget(self.start_stop_button, 1)
        controls_layout.addStretch()
        controls_layout.addWidget(self.status_label)

        self.results_tree = QTreeWidget()
        self.results_tree.setColumnCount(7)
        self.results_tree.setHeaderLabels(["SQL ID", "Schema", "Δ Tempo Decorrido (s)", "Δ Tempo CPU (s)", 
                                           "Δ Execuções", "Δ Leituras de Disco", "Início do SQL"])
        self.results_tree.setSortingEnabled(True)
        self.results_tree.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        
        top_layout.addLayout(controls_layout)
        top_layout.addWidget(self.results_tree)

        bottom_layout = QVBoxLayout(bottom_widget)
        self.sql_text_edit = QTextEdit()
        self.sql_text_edit.setReadOnly(True)
        self.sql_text_edit.setFont(QFont("Consolas", 10))
        self.sql_text_edit.setStyleSheet("background-color: #2B2B2B; color: #F8F8F2;")
        bottom_layout.addWidget(QLabel("Texto Completo do SQL Selecionado:"))
        bottom_layout.addWidget(self.sql_text_edit)

        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setSizes([600, 200])
        
        self.start_stop_button.clicked.connect(self.toggle_monitoring)
        self.results_tree.currentItemChanged.connect(self.display_full_sql)

    def populate_db_combo(self):
        try:
            connections = get_all_db_connections()
            for key, name in connections.items():
                self.db_combo.addItem(name, key)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível carregar as conexões: {e}")

    def toggle_monitoring(self):
        if self.is_monitoring:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self):
        self.is_monitoring = True
        self.db_combo.setEnabled(False)
        self.interval_spinbox.setEnabled(False)
        self.start_stop_button.setText("■ Parar Monitoramento")
        
        interval_ms = self.interval_spinbox.value() * 1000
        self.monitor_timer.start(interval_ms)
        self.run_worker_update()

    def stop_monitoring(self):
        self.is_monitoring = False
        self.monitor_timer.stop()
        
        self.db_combo.setEnabled(True)
        self.interval_spinbox.setEnabled(True)
        self.start_stop_button.setText("▶ Iniciar Monitoramento")
        self.status_label.setText("Parado.")
        self.status_label.setStyleSheet("color: gray;")

    def run_worker_update(self):
        if self.worker and self.worker.isRunning():
            return

        db_key = self.db_combo.currentData()
        interval = self.interval_spinbox.value()
        
        self.worker = TopSqlWorker(db_key, interval)
        self.worker.progress.connect(self.update_status_label) # Conectar novo sinal de progresso
        self.worker.finished.connect(self.on_data_ready)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def update_status_label(self, message):
        """Atualiza a label de status com o progresso do worker."""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: orange;")

    def on_data_ready(self, data):
        self.status_label.setText("Monitorando...")
        self.status_label.setStyleSheet("color: green;")
        
        self.results_tree.clear()
        for item in data:
            tree_item = QTreeWidgetItem(self.results_tree)
            tree_item.setText(0, item['sql_id'])
            tree_item.setText(1, item['parsing_schema_name'])
            tree_item.setText(2, f"{item['elapsed_s']:.4f}")
            tree_item.setText(3, f"{item['cpu_s']:.4f}")
            tree_item.setText(4, f"{item['executions']:,}")
            tree_item.setText(5, f"{item['disk_reads']:,}")
            tree_item.setText(6, item['sql_text'].replace('\n', ' ').strip())
            
            tree_item.setData(0, Qt.ItemDataRole.UserRole, item['sql_text'])

        for i in range(self.results_tree.columnCount()):
            self.results_tree.resizeColumnToContents(i)

    def on_worker_error(self, error_message):
        QMessageBox.critical(self, "Erro no Monitoramento", error_message)
        self.stop_monitoring()

    def display_full_sql(self, current_item, previous_item):
        if current_item:
            full_sql = current_item.data(0, Qt.ItemDataRole.UserRole)
            self.sql_text_edit.setText(full_sql)

    def closeEvent(self, event):
        self.stop_monitoring()
        super().closeEvent(event)