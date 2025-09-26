# C:\Meus Projetos\MyOps\modules\dms_extractor\dms_extractor_ui.py

import os
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLabel, QGroupBox, 
                             QLineEdit, QHBoxLayout, QMessageBox, QComboBox,
                             QDateEdit, QCheckBox, QApplication, QPlainTextEdit)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QCursor
from . import dms_extractor_logic as logic

class DateTableWidgetItem(QTableWidgetItem):
    """
    Item de tabela personalizado para ordenar datas no formato DD/MM/YYYY corretamente.
    """
    def __lt__(self, other):
        try:
            d1 = datetime.strptime(self.text(), '%d/%m/%Y')
            d2 = datetime.strptime(other.text(), '%d/%m/%Y')
            return d1 < d2
        except (ValueError, TypeError):
            return super().__lt__(other)

class DmsExtractorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Extrator de Faturas - DMS")
        self.available_invoices = []

        main_layout = QVBoxLayout(self)
        controls_group = QGroupBox("Parâmetros de Busca")
        controls_layout = QVBoxLayout(controls_group)
        
        line1_layout = QHBoxLayout()
        self.db_combo = QComboBox()
        self.connections = logic.get_all_db_connections()
        for key, name in self.connections.items():
            self.db_combo.addItem(name, key)
        default_dms_key = next((key for key, name in self.connections.items() if 'dms' in name.lower()), None)
        if default_dms_key: self.db_combo.setCurrentText(self.connections[default_dms_key])
        
        self.siebel_db_combo = QComboBox()
        for key, name in self.connections.items():
            self.siebel_db_combo.addItem(name, key)
        default_siebel_key = next((key for key, name in self.connections.items() if 'siebel' in name.lower() and 'pre' not in name.lower()), None)
        if default_siebel_key:
            self.siebel_db_combo.setCurrentText(self.connections[default_siebel_key])

        self.search_type_combo = QComboBox()
        self.search_type_combo.addItem("Customer ID(s)", "customer_id")
        self.search_type_combo.addItem("Custcode(s)", "custcode")
        self.search_type_combo.currentIndexChanged.connect(self.update_placeholder_text)
        
        line1_layout.addWidget(QLabel("Base DMS:"))
        line1_layout.addWidget(self.db_combo)
        line1_layout.addWidget(QLabel("Base Siebel:"))
        line1_layout.addWidget(self.siebel_db_combo)
        line1_layout.addWidget(QLabel("Buscar por:"))
        line1_layout.addWidget(self.search_type_combo)
        line1_layout.addStretch()

        self.search_value_input = QPlainTextEdit()
        self.search_value_input.setFixedHeight(80)
        self.update_placeholder_text()

        line2_layout = QHBoxLayout()
        self.due_date_checkbox = QCheckBox("Filtrar por Vencimento (Mês/Ano):")
        self.due_date_input = QDateEdit()
        self.due_date_input.setCalendarPopup(True)
        self.due_date_input.setDisplayFormat("MM/yyyy")
        self.due_date_input.setEnabled(False)
        self.due_date_checkbox.toggled.connect(self.due_date_input.setEnabled)
        self.search_button = QPushButton("Buscar Faturas Disponíveis")
        self.search_button.clicked.connect(self.search_invoices)
        line2_layout.addWidget(self.due_date_checkbox)
        line2_layout.addWidget(self.due_date_input)
        line2_layout.addStretch()
        line2_layout.addWidget(self.search_button)

        controls_layout.addLayout(line1_layout)
        controls_layout.addWidget(self.search_value_input)
        controls_layout.addLayout(line2_layout)

        results_group = QGroupBox("Faturas Encontradas (selecione as desejadas com checkbox)")
        results_layout = QVBoxLayout(results_group)
        self.results_table = QTableWidget()
        self.results_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.results_table.setSortingEnabled(True)
        results_layout.addWidget(self.results_table)
        
        self.extract_button = QPushButton("🚀 Iniciar Extração das Faturas Selecionadas")
        self.extract_button.setMinimumHeight(40)
        self.extract_button.clicked.connect(self.start_extraction)
        self.extract_button.setEnabled(False)
        
        self.status_label = QLabel("Selecione os parâmetros e clique em 'Buscar Faturas'.")
        
        main_layout.addWidget(controls_group)
        main_layout.addWidget(results_group, 1)
        main_layout.addWidget(self.extract_button)
        main_layout.addWidget(self.status_label)

    def update_placeholder_text(self):
        if self.search_type_combo.currentData() == "custcode":
            self.search_value_input.setPlaceholderText("Digite ou cole um ou mais Custcodes (um por linha)...")
        else:
            self.search_value_input.setPlaceholderText("Digite ou cole um ou mais Customer IDs (um por linha)...")

    def search_invoices(self):
        search_values_raw = self.search_value_input.toPlainText().strip()
        search_type = self.search_type_combo.currentData()
        db_section_key = self.db_combo.currentData()
        siebel_db_key = self.siebel_db_combo.currentData()

        if not search_values_raw:
            QMessageBox.warning(self, "Erro", f"O campo de {self.search_type_combo.currentText()} está vazio.")
            return

        due_date_prefix = None
        if self.due_date_checkbox.isChecked():
            due_date_prefix = self.due_date_input.date().toString("yyyyMM")

        try:
            self.search_button.setEnabled(False)
            self.status_label.setText("Buscando dados no Siebel e DMS... Este processo pode demorar alguns minutos, por favor aguarde.")
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
            QApplication.processEvents()
            
            success, result = logic.get_available_invoices(db_section_key, siebel_db_key, search_type, search_values_raw, due_date_prefix)
            
            if not success:
                QMessageBox.critical(self, "Erro de Banco de Dados", result)
                self.status_label.setText("Falha na busca.")
                return

            self.available_invoices = result
            self.results_table.setRowCount(0)
            
            headers = ["", "Customer ID", "Custcode", "Vencimento", "Nº Fatura", "Qtd. Páginas"]
            self.results_table.setColumnCount(len(headers))
            self.results_table.setHorizontalHeaderLabels(headers)
            self.results_table.setRowCount(len(self.available_invoices))
            
            for row, inv in enumerate(self.available_invoices):
                chk_item = QTableWidgetItem()
                chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk_item.setCheckState(Qt.CheckState.Unchecked)
                chk_item.setData(Qt.ItemDataRole.UserRole, inv)
                self.results_table.setItem(row, 0, chk_item)
                
                self.results_table.setItem(row, 1, QTableWidgetItem(str(inv.get('customeridfatura', ''))))
                self.results_table.setItem(row, 2, QTableWidgetItem(str(inv.get('custcode', ''))))
                self.results_table.setItem(row, 3, DateTableWidgetItem(inv.get('vencimento_formatado', '-')))
                self.results_table.setItem(row, 4, QTableWidgetItem(str(inv.get('nufatura', ''))))
                self.results_table.setItem(row, 5, QTableWidgetItem(str(inv.get('qtd_paginas', ''))))
            
            self.results_table.resizeColumnsToContents()
            self.results_table.setColumnWidth(0, 30)
            self.extract_button.setEnabled(len(self.available_invoices) > 0)
            self.status_label.setText(f"{len(self.available_invoices)} faturas encontradas. Selecione e ordene como desejar.")

        finally:
            QApplication.restoreOverrideCursor()
            self.search_button.setEnabled(True)

    def start_extraction(self):
        invoices_to_process = []
        for row in range(self.results_table.rowCount()):
            chk_item = self.results_table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.CheckState.Checked:
                invoice_data = chk_item.data(Qt.ItemDataRole.UserRole)
                invoices_to_process.append(invoice_data)

        if not invoices_to_process:
            QMessageBox.warning(self, "Seleção Vazia", "Por favor, marque pelo menos uma fatura na tabela.")
            return
        
        first_customer_id = invoices_to_process[0].get('customeridfatura', 'N/D')
        reply = QMessageBox.question(self, "Confirmar Extração", 
                                     f"Confirma a extração de {len(invoices_to_process)} fatura(s)?\n\n(Referência: Cliente {first_customer_id})",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        self.extract_button.setEnabled(False)
        self.status_label.setText("Iniciando processo de extração no servidor...")
        try:
            success, message = logic.run_remote_extraction(invoices_to_process)
            if success: QMessageBox.information(self, "Processo Iniciado", message)
            else: QMessageBox.critical(self, "Erro", message)
        finally:
            self.extract_button.setEnabled(True)
            self.status_label.setText("Pronto.")