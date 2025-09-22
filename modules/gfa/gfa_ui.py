# C:\Meus Projetos\fixer\modules\gfa\gfa_ui.py

import sys
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QMessageBox, QMainWindow, QLabel, QGroupBox, QHBoxLayout, QTreeWidget, QTreeWidgetItem)
from PyQt6.QtGui import QFont, QAction, QColor
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from modules.gfa import gfa_logic as db
from modules.common.widgets import SettingsDialog

class GfaCheckWorker(QThread):
    finished = pyqtSignal(list); error = pyqtSignal(str)
    def run(self):
        try: self.finished.emit(db.get_gfa_status())
        except Exception as e: self.error.emit(str(e))

class GfaRestartWorker(QThread):
    finished = pyqtSignal(str); error = pyqtSignal(str)
    def __init__(self, server_name):
        super().__init__(); self.server_name = server_name
    def run(self):
        try: self.finished.emit(db.restart_gfa_server(self.server_name))
        except Exception as e: self.error.emit(str(e))

class GfaMonitorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        main_layout = QVBoxLayout(self)

        controls_group = QGroupBox("Monitor GFA via API REST")
        controls_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Verificar Status dos Servidores")
        self.refresh_button.clicked.connect(self.on_refresh)
        self.restart_button = QPushButton("Restartar Servidor Selecionado")
        self.restart_button.clicked.connect(self.on_restart)
        self.restart_button.setEnabled(False)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addStretch()
        controls_layout.addWidget(self.restart_button)
        controls_group.setLayout(controls_layout)
        
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Servidor", "Status", "Health State"])
        self.results_tree.currentItemChanged.connect(self.on_selection_change)
        
        main_layout.addWidget(controls_group)
        main_layout.addWidget(self.results_tree)

    def on_refresh(self):
        self.refresh_button.setEnabled(False); self.refresh_button.setText("Verificando...")
        self.restart_button.setEnabled(False)
        self.results_tree.clear()
        self.worker = GfaCheckWorker(); self.worker.finished.connect(self.on_refresh_finished); self.worker.error.connect(self.on_worker_error); self.worker.start()

    def on_restart(self):
        selected_item = self.results_tree.currentItem()
        if not selected_item or selected_item.childCount() > 0:
            QMessageBox.warning(self, "Ação Inválida", "Por favor, selecione um servidor individual para reiniciar."); return

        server_name = selected_item.text(0)
        reply = QMessageBox.question(self, 'Confirmação de Restart', f"Tem certeza que deseja enviar os comandos de restart para o servidor '{server_name}'?\n\nO WebLogic iniciará o processo em segundo plano.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return

        self.refresh_button.setEnabled(False); self.restart_button.setEnabled(False); self.restart_button.setText("Enviando...")
        self.worker = GfaRestartWorker(server_name); self.worker.finished.connect(self.on_restart_finished); self.worker.error.connect(self.on_worker_error); self.worker.start()

    def on_restart_finished(self, output_message):
        self.restart_button.setText("Restartar Servidor Selecionado")
        QMessageBox.information(self, "Comandos Enviados", output_message)
        # Inicia uma atualização automática após alguns segundos para ver o novo status
        self.refresh_button.setText("Atualizando status...")
        QApplication.processEvents() # Força a UI a atualizar
        import time; time.sleep(5) # Espera 5 segundos antes de atualizar
        self.on_refresh()

    def on_selection_change(self, current_item, previous_item):
        if current_item and current_item.childCount() == 0:
            self.restart_button.setEnabled(True)
        else:
            self.restart_button.setEnabled(False)

    def on_refresh_finished(self, server_list):
        self.refresh_button.setEnabled(True); self.refresh_button.setText("Verificar Status dos Servidores")
        if not server_list: QMessageBox.information(self, "Concluído", "Nenhum servidor foi retornado pela API."); return
            
        ok_item = QTreeWidgetItem(self.results_tree, ["Servidores OK"]); ok_item.setFont(0, QFont("Arial", 9, QFont.Weight.Bold))
        not_ok_item = QTreeWidgetItem(self.results_tree, ["Servidores com Atenção"]); not_ok_item.setFont(0, QFont("Arial", 9, QFont.Weight.Bold)); not_ok_item.setForeground(0, QColor("orange"))

        for server in sorted(server_list, key=lambda x: x['name']):
            parent = ok_item if server['is_ok'] else not_ok_item
            item = QTreeWidgetItem(parent, [server['name'], server['state'], server['health']])
            color = QColor("green") if server['is_ok'] else QColor("red")
            for i in range(item.columnCount()): item.setForeground(i, color)

        self.results_tree.expandAll()
        for i in range(self.results_tree.columnCount()): self.results_tree.resizeColumnToContents(i)

    def on_worker_error(self, error_message):
        self.refresh_button.setEnabled(True); self.refresh_button.setText("Verificar Status dos Servidores")
        self.restart_button.setEnabled(False); self.restart_button.setText("Restartar Servidor Selecionado")
        QMessageBox.critical(self, "Erro na Operação", error_message)

class GfaToolWindow(QMainWindow):
    def __init__(self, launcher_instance):
        super().__init__(); self.launcher = launcher_instance; self.setWindowTitle("Monitor de Servidores GFA (WebLogic REST)")
        self.setGeometry(100, 100, 900, 700); self._create_menu_bar()
        self.main_widget = GfaMonitorWidget(); self.setCentralWidget(self.main_widget)
    def _create_menu_bar(self):
        menu_bar = self.menuBar(); sistemas_menu = menu_bar.addMenu("Sistemas")
        back_action = QAction("Voltar para o Seletor", self); back_action.triggered.connect(self.go_back_to_launcher); sistemas_menu.addAction(back_action)
    def go_back_to_launcher(self): self.launcher.show(); self.close()