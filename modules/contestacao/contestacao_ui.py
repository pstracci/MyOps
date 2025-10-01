# C:\Meus Projetos\MyOps\modules\contestacao\contestacao_ui.py

import logging
import configparser
import re
import xml.dom.minidom
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QLabel, QLineEdit, QGroupBox,
                             QStackedWidget, QMessageBox, QHeaderView, QComboBox,
                             QTabWidget, QDateEdit, QCheckBox, QSpinBox, QGridLayout,
                             QDialog, QTextEdit, QMenu, QStackedLayout, QAbstractItemView)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QDate
from PyQt6.QtGui import QTextCursor, QIcon, QAction, QKeySequence, QTextDocument, QGuiApplication
from modules.contestacao import contestacao_logic as logic

# --- JANELA DE LOG (QWidget) ---
class LogViewerDialog(QWidget): 
    def __init__(self, sr, msisdn, invoicenumber, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Log de Execução - SR {sr}")
        self.setMinimumSize(900, 700)
        main_layout = QVBoxLayout(self)
        info_group = QGroupBox("Dados da Contestação (selecionável para cópia)")
        info_layout = QHBoxLayout(info_group)
        sr_label = QLabel(f"<b>SR:</b> {sr}")
        msisdn_label = QLabel(f"<b>MSISDN:</b> {msisdn}")
        invoice_label = QLabel(f"<b>Fatura:</b> {invoicenumber}")
        for label in [sr_label, msisdn_label, invoice_label]:
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_layout.addWidget(sr_label)
        info_layout.addWidget(msisdn_label)
        info_layout.addWidget(invoice_label)
        info_layout.addStretch()
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar no log...")
        self.find_next_button = QPushButton("Próximo (F3)")
        self.find_prev_button = QPushButton("Anterior (Shift+F3)")
        search_layout.addWidget(QLabel("Busca:"))
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.find_next_button)
        search_layout.addWidget(self.find_prev_button)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFontFamily("Courier")
        self.log_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log_display.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_display.customContextMenuRequested.connect(self._show_context_menu)
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.close)
        main_layout.addWidget(info_group)
        main_layout.addLayout(search_layout)
        main_layout.addWidget(self.log_display)
        main_layout.addWidget(close_button)
        self.search_input.returnPressed.connect(self._find_next)
        self.find_next_button.clicked.connect(self._find_next)
        self.find_prev_button.clicked.connect(self._find_prev)
        self._create_shortcuts()
        self.search_input.setText(invoicenumber)
        self._find_next()
    def _create_shortcuts(self):
        find_next_action = QAction(self)
        find_next_action.setShortcut(QKeySequence(Qt.Key.Key_F3))
        find_next_action.triggered.connect(self._find_next)
        self.addAction(find_next_action)
        find_prev_action = QAction(self)
        find_prev_action.setShortcut(QKeySequence("Shift+F3"))
        find_prev_action.triggered.connect(self._find_prev)
        self.addAction(find_prev_action)
    def _show_context_menu(self, pos):
        menu = QMenu()
        copy_action = menu.addAction("&Copiar")
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.setEnabled(self.log_display.textCursor().hasSelection())
        copy_action.triggered.connect(self.log_display.copy)
        menu.addSeparator()
        select_all_action = menu.addAction("Selecionar &Tudo")
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(self.log_display.selectAll)
        menu.exec(self.log_display.mapToGlobal(pos))
    def set_log_content(self, content):
        if content: self.log_display.setPlainText(content)
        else: self.log_display.setPlainText("Nenhum conteúdo de log foi retornado ou o arquivo estava vazio.")
    def _find_next(self):
        query = self.search_input.text()
        if not query: return
        if not self.log_display.find(query):
            cursor = self.log_display.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.log_display.setTextCursor(cursor)
            self.log_display.find(query)
    def _find_prev(self):
        query = self.search_input.text()
        if not query: return
        if not self.log_display.find(query, QTextDocument.FindFlag.FindBackward):
            cursor = self.log_display.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_display.setTextCursor(cursor)
            self.log_display.find(query, QTextDocument.FindFlag.FindBackward)

# --- WORKERS (Threads para operações) ---
class SearchWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, db_key, sr, msisdn, start_date, end_date, status):
        super().__init__()
        self.db_key, self.sr, self.msisdn, self.start_date, self.end_date, self.status = db_key, sr, msisdn, start_date, end_date, status
    def run(self):
        try: self.finished.emit(logic.search_contestacoes(self.db_key, self.sr, self.msisdn, self.start_date, self.end_date, self.status))
        except Exception as e: self.error.emit(str(e))

class InterfaceSearchWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, db_key, status, hours):
        super().__init__()
        self.db_key, self.status, self.hours = db_key, status, hours
    def run(self):
        try: self.finished.emit(logic.search_interfaces(self.db_key, self.status, self.hours))
        except Exception as e: self.error.emit(str(e))

class DetailsWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, db_key, request_id):
        super().__init__()
        self.db_key, self.request_id = db_key, request_id
    def run(self):
        try:
            results = logic.get_request_details(self.db_key, self.request_id)
            self.finished.emit(results)
        except Exception as e: self.error.emit(str(e))

class AnalysisWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, db_key, sr):
        super().__init__()
        self.db_key, self.sr = db_key, sr
    def run(self):
        try:
            results = logic.get_analysis_details(self.db_key, self.sr)
            self.finished.emit(results)
        except Exception as e: self.error.emit(str(e))

class InterfaceWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, db_key, sr):
        super().__init__()
        self.db_key, self.sr = db_key, sr
    def run(self):
        try:
            results = logic.get_interface_details(self.db_key, self.sr)
            self.finished.emit(results)
        except Exception as e: self.error.emit(str(e))

class AdjustWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, db_key, sr):
        super().__init__()
        self.db_key, self.sr = db_key, sr
    def run(self):
        try:
            results = logic.get_adjust_details(self.db_key, self.sr)
            self.finished.emit(results)
        except Exception as e: self.error.emit(str(e))

class ContestationAnalysisWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, db_key, sr):
        super().__init__()
        self.db_key, self.sr = db_key, sr
    def run(self):
        try:
            results = logic.get_contestation_analysis_details(self.db_key, self.sr)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))
            
class InvoiceLinesWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, db_key, invoicenumber):
        super().__init__()
        self.db_key = db_key
        self.invoicenumber = invoicenumber
    def run(self):
        try:
            results = logic.get_contested_invoice_details(self.db_key, self.invoicenumber)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))

class DiscardWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, db_key, sr):
        super().__init__()
        self.db_key, self.sr = db_key, sr
    def run(self):
        try:
            results = logic.descartar_contestacao(self.db_key, self.sr)
            self.finished.emit(results)
        except Exception as e: self.error.emit(str(e))

class LogSearchWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, sr, msisdn, invoicenumber):
        super().__init__()
        self.sr, self.msisdn, self.invoicenumber = sr, msisdn, invoicenumber
    def run(self):
        try:
            log_content = logic.fetch_remote_log(self.sr, self.msisdn, self.invoicenumber)
            self.finished.emit(log_content)
        except Exception as e: self.error.emit(str(e))

# --- WIDGET PRINCIPAL ---
class ContestacaoViewerWidget(QWidget):
    def __init__(self):
        super().__init__()
        logging.info("Iniciando o widget ContestacaoViewerWidget...")
        self.current_sr = None
        self.current_request_id = None
        self.current_invoicenumber = None
        self.loaded_tabs = set()
        self.open_log_windows = [] 
        main_layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        self.search_page = self._create_search_page()
        self.details_page = self._create_details_page()
        self.stack.addWidget(self.search_page)
        self.stack.addWidget(self.details_page)
        main_layout.addWidget(self.stack)
        logging.info("Widget ContestacaoViewerWidget inicializado com sucesso.")

    def _process_log_content(self, raw_log: str) -> str:
        cleaned_lines = []
        prefix_pattern = re.compile(r'^.*\.log[:\-]\d+[:\-]?\s?')
        xml_extract_pattern = re.compile(r'(<[a-zA-Z0-9:?].*)$')
        for line in raw_log.split('\n'):
            line_sem_prefixo = prefix_pattern.sub('', line)
            match = xml_extract_pattern.search(line_sem_prefixo)
            if match:
                xml_string = match.group(1)
                try:
                    texto_inicial = line_sem_prefixo[:match.start(1)]
                    dom = xml.dom.minidom.parseString(xml_string)
                    pretty_xml = dom.toprettyxml(indent="  ")
                    pretty_xml_cleaned = '\n'.join([l for l in pretty_xml.split('\n') if l.strip()])
                    cleaned_lines.append(texto_inicial + '\n' + pretty_xml_cleaned)
                except Exception:
                    cleaned_lines.append(line_sem_prefixo)
            else:
                cleaned_lines.append(line_sem_prefixo)
        return '\n'.join(cleaned_lines)
    
    def _create_search_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        db_group = QGroupBox("Conexão")
        db_layout = QHBoxLayout(db_group)
        self.db_combo = QComboBox()
        self.populate_db_combo()
        db_layout.addWidget(QLabel("Consultar Base:"))
        db_layout.addWidget(self.db_combo)
        
        # --- CORREÇÃO 1: Adiciona um stretch para alinhar à esquerda ---
        db_layout.addStretch()

        search_tabs = QTabWidget()
        contestacao_search_widget = self._create_contestacao_search_tab()
        interface_search_widget = self._create_interface_search_tab()
        search_tabs.addTab(contestacao_search_widget, "Buscar Contestações")
        search_tabs.addTab(interface_search_widget, "Buscar Interfaces por Status")
        layout.addWidget(db_group)
        layout.addWidget(search_tabs)
        return page

    def _create_contestacao_search_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        filters_group = QGroupBox("Filtros de Busca de Contestações")
        filters_layout = QVBoxLayout(filters_group)
        line1_layout = QHBoxLayout()
        self.sr_input = QLineEdit()
        self.msisdn_input = QLineEdit()
        line1_layout.addWidget(QLabel("Protocolo (SR):"))
        line1_layout.addWidget(self.sr_input)
        line1_layout.addWidget(QLabel("MSISDN:"))
        line1_layout.addWidget(self.msisdn_input)
        line2_layout = QHBoxLayout()
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Todos", "Iniciada", "Erro na busca", "Fatura não encontrada", "Conta contábil não cadastrada", "Erro de alçada", "Descartada", "Gerada", "Finalizada", "Itens já contestados", "Erro na validação", "Finalizada Improcedente"])
        line2_layout.addWidget(QLabel("Status da Contestação:"))
        line2_layout.addWidget(self.status_combo)
        line2_layout.addStretch(2)
        line3_layout = QHBoxLayout()
        self.period_check = QCheckBox("Buscar por Período")
        self.start_date_input = QDateEdit(calendarPopup=True)
        self.start_date_input.setDate(QDate.currentDate().addDays(-1))
        self.end_date_input = QDateEdit(calendarPopup=True)
        self.end_date_input.setDate(QDate.currentDate())
        self.start_date_input.setEnabled(False)
        self.end_date_input.setEnabled(False)
        
        # --- CORREÇÃO 2: Define uma largura mínima para os campos de data ---
        self.start_date_input.setMinimumWidth(110)
        self.end_date_input.setMinimumWidth(110)

        line3_layout.addWidget(self.period_check)
        line3_layout.addWidget(self.start_date_input)
        line3_layout.addWidget(QLabel("até"))
        line3_layout.addWidget(self.end_date_input)
        line3_layout.addStretch()
        filters_layout.addLayout(line1_layout)
        filters_layout.addLayout(line2_layout)
        filters_layout.addLayout(line3_layout)
        buttons_layout = QHBoxLayout()
        self.search_button = QPushButton("Buscar")
        self.details_button = QPushButton("Ver Detalhes")
        self.log_button = QPushButton("Buscar Log")
        self.details_button.setEnabled(False)
        self.log_button.setEnabled(False)
        buttons_layout.addWidget(self.search_button)
        buttons_layout.addWidget(self.details_button)
        buttons_layout.addWidget(self.log_button)
        buttons_layout.addStretch()
        results_group = QGroupBox("Resultados")
        self.results_layout = QStackedLayout(results_group)
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Protocolo (SR)", "MSISDN", "Fatura", "Data", "Status"])
        header = self.results_tree.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False) 
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.results_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_tree.customContextMenuRequested.connect(self._show_results_context_menu)
        self.results_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.loading_label = QLabel("Buscando... Por favor, aguarde.")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_layout.addWidget(self.results_tree)
        self.results_layout.addWidget(self.loading_label)
        layout.addWidget(filters_group)
        layout.addLayout(buttons_layout)
        layout.addWidget(results_group)
        self.results_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.results_tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.search_button.clicked.connect(self._perform_search)
        self.details_button.clicked.connect(self._on_details_button_clicked)
        self.log_button.clicked.connect(self._on_log_button_clicked)
        self.period_check.toggled.connect(self.start_date_input.setEnabled)
        self.period_check.toggled.connect(self.end_date_input.setEnabled)
        return page

    def _show_results_context_menu(self, pos):
        item = self.results_tree.itemAt(pos)
        if not item: return
        menu = QMenu()
        copy_sr_action = menu.addAction("Copiar Protocolo (SR)")
        copy_msisdn_action = menu.addAction("Copiar MSISDN")
        copy_invoice_action = menu.addAction("Copiar Fatura")
        action = menu.exec(self.results_tree.mapToGlobal(pos))
        clipboard = QGuiApplication.clipboard()
        if action == copy_sr_action: clipboard.setText(item.text(0))
        elif action == copy_msisdn_action: clipboard.setText(item.text(1))
        elif action == copy_invoice_action: clipboard.setText(item.text(2))

    def _perform_search(self):
        logging.info("Botão 'Buscar' clicado. Iniciando SearchWorker...")
        self.search_button.setEnabled(False)
        self.details_button.setEnabled(False)
        self.log_button.setEnabled(False)
        self.results_tree.clear()
        self.results_layout.setCurrentWidget(self.loading_label)
        db_key = self.db_combo.currentData()
        if not db_key:
            logging.warning("Busca cancelada: Nenhuma base de dados selecionada.")
            QMessageBox.warning(self, "Atenção", "Nenhuma base de dados selecionada.")
            self.search_button.setEnabled(True)
            self.results_layout.setCurrentWidget(self.results_tree) 
            return
        sr = self.sr_input.text().strip() or None
        msisdn = self.msisdn_input.text().strip() or None
        selected_status = self.status_combo.currentText()
        status = selected_status if selected_status != "Todos" else None
        start_date = self.start_date_input.date().toPyDate() if self.period_check.isChecked() else None
        end_date = self.end_date_input.date().toPyDate() if self.period_check.isChecked() else None
        self.search_worker = SearchWorker(self.db_combo.currentData(), sr, msisdn, start_date, end_date, status)
        self.search_worker.finished.connect(self._on_search_finished)
        self.search_worker.error.connect(self._on_worker_error)
        self.search_worker.start()

    def _on_search_finished(self, results):
        logging.info("Worker de busca finalizado.")
        self.results_layout.setCurrentWidget(self.results_tree)
        self.search_button.setEnabled(True)
        if not results:
            logging.info("Nenhum resultado encontrado na busca.")
            QMessageBox.information(self, "Busca", "Nenhuma contestação encontrada.")
            return
        for row in results:
            item = QTreeWidgetItem(self.results_tree)
            item.setText(0, row.get('sr', ''))
            item.setText(1, row.get('msisdn', ''))
            item.setText(2, row.get('invoicenumber', ''))
            item.setText(3, str(row.get('createdate', '')))
            item.setText(4, row.get('statusname', ''))
            item.setData(0, Qt.ItemDataRole.UserRole, row.get('id_'))
    
    def _on_worker_error(self, message):
        self.results_layout.setCurrentWidget(self.results_tree)
        logging.error(f"Ocorreu um erro em uma operação de background: {message}", exc_info=True)
        if hasattr(self, 'search_button'): self.search_button.setEnabled(True)
        if hasattr(self, 'interface_search_button'): self.interface_search_button.setEnabled(True)
        if hasattr(self, 'log_button'):
            self.log_button.setEnabled(bool(self.results_tree.selectedItems()))
            self.log_button.setText("Buscar Log")
        QMessageBox.critical(self, "Erro", message)

    def _on_log_button_clicked(self):
        selected = self.results_tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Atenção", "Por favor, selecione uma contestação na lista.")
            return
        item = selected[0]
        sr, msisdn, invoicenumber = item.text(0), item.text(1), item.text(2)
        self.log_button.setEnabled(False)
        self.log_button.setText("Buscando...")
        self.log_worker = LogSearchWorker(sr, msisdn, invoicenumber)
        self.log_worker.finished.connect(self._on_log_search_finished)
        self.log_worker.error.connect(self._on_worker_error)
        self.log_worker.start()

    def _on_log_search_finished(self, log_content):
        self.log_button.setEnabled(True)
        self.log_button.setText("Buscar Log")
        selected = self.results_tree.selectedItems()
        if not selected: return
        item = selected[0]
        sr, msisdn, invoicenumber = item.text(0), item.text(1), item.text(2)
        processed_content = self._process_log_content(log_content)
        log_window = LogViewerDialog(sr, msisdn, invoicenumber)
        log_window.set_log_content(processed_content)
        self.open_log_windows.append(log_window)
        log_window.show()

    def _create_interface_search_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        filters_group = QGroupBox("Filtros de Busca de Interfaces")
        filters_layout = QGridLayout(filters_group)
        self.interface_status_combo = QComboBox()
        self.interface_status_combo.addItems(["Todos", "Sucesso", "Nao enviado", "Aguardando Retorno", "Erro Permanente", "Envio Cancelado", "Erro Temporario"])
        self.hours_spinbox = QSpinBox()
        self.hours_spinbox.setRange(1, 720)
        self.hours_spinbox.setValue(24)
        self.interface_search_button = QPushButton("Buscar Interfaces")
        filters_layout.addWidget(QLabel("Status da Interface:"), 0, 0)
        filters_layout.addWidget(self.interface_status_combo, 0, 1)
        filters_layout.addWidget(QLabel("Buscar nas últimas (horas):"), 1, 0)
        filters_layout.addWidget(self.hours_spinbox, 1, 1)
        results_group = QGroupBox("Resultados da Busca de Interfaces")
        results_layout = QVBoxLayout(results_group)
        self.interface_results_tree = QTreeWidget()
        self.interface_results_tree.setHeaderLabels(["ID", "Tipo", "Status", "Data Criação", "Data Envio", "Descrição do Erro"])
        results_layout.addWidget(self.interface_results_tree)
        layout.addWidget(filters_group)
        layout.addWidget(self.interface_search_button)
        layout.addWidget(results_group)
        self.interface_search_button.clicked.connect(self._perform_interface_search)
        return page

    def _perform_interface_search(self):
        logging.info("Botão 'Buscar Interfaces' clicado.")
        self.interface_search_button.setEnabled(False)
        self.interface_results_tree.clear()
        db_key = self.db_combo.currentData()
        status = self.interface_status_combo.currentText()
        hours = self.hours_spinbox.value()
        self.interface_search_worker = InterfaceSearchWorker(db_key, status, hours)
        self.interface_search_worker.finished.connect(self._on_interface_search_finished)
        self.interface_search_worker.error.connect(self._on_worker_error)
        self.interface_search_worker.start()

    def _on_interface_search_finished(self, results):
        self.interface_search_button.setEnabled(True)
        if not results:
            QMessageBox.information(self, "Busca de Interfaces", "Nenhuma interface encontrada para os filtros informados.")
            return
        for row in results:
            item = QTreeWidgetItem(self.interface_results_tree)
            item.setText(0, str(row.get('id_', '')))
            item.setText(1, str(row.get('type_desc', '')))
            item.setText(2, str(row.get('desc_status', '')))
            item.setText(3, str(row.get('createdate', '')))
            item.setText(4, str(row.get('senddate', '')))
            item.setText(5, str(row.get('errordescription', '')))
        for i in range(self.interface_results_tree.columnCount()): self.interface_results_tree.resizeColumnToContents(i)
    
    def _create_details_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        actions_layout = QHBoxLayout()
        self.back_button = QPushButton("« Voltar para a Busca")
        self.refresh_button = QPushButton("Atualizar Dados")
        self.discard_button = QPushButton("Descartar Contestação")
        self.discard_button.setStyleSheet("background-color: #a63a3a; color: white;")
        actions_layout.addWidget(self.back_button)
        actions_layout.addWidget(self.refresh_button)
        actions_layout.addStretch()
        actions_layout.addWidget(self.discard_button)
        master_group = QGroupBox("Resumo da Contestação")
        master_group.setObjectName("MasterInfoGroup")
        master_layout = QHBoxLayout(master_group)
        self.master_labels = {}
        fields = ["Protocolo (SR)", "MSISDN", "Fatura", "CustomerID", "Data Solicitação", "Status"]
        for field in fields:
            label = QLabel(f"<b>{field}:</b> N/A")
            self.master_labels[field] = label
            master_layout.addWidget(label)
        self.details_tabs = QTabWidget()
        analysis_page = QWidget()
        analysis_layout = QVBoxLayout(analysis_page)
        self.analysis_summary_group = QGroupBox("Sumário da Análise")
        analysis_summary_layout = QHBoxLayout(self.analysis_summary_group)
        label = QLabel("Clique nesta aba para carregar.")
        analysis_summary_layout.addWidget(label)
        self.analysis_tree = QTreeWidget()
        self.analysis_tree.setHeaderLabels(["Descrição", "Valor Cobrado", "Vlr. Reclamado", "Vlr. Procedente", "Status", "Motivo"])
        analysis_layout.addWidget(self.analysis_summary_group)
        analysis_layout.addWidget(self.analysis_tree)
        invoice_lines_group = QGroupBox("Itens da Fatura Contestada")
        invoice_lines_layout = QVBoxLayout(invoice_lines_group)
        self.invoice_lines_tree = QTreeWidget()
        self.invoice_lines_tree.setHeaderLabels(["Item Fatura", "Valor", "Serviço BSCS", "Conta Contábil", "Seção da Fatura", "Invoice", "Customer", "Bill", "Page", "Amount"])
        invoice_lines_layout.addWidget(self.invoice_lines_tree)
        analysis_layout.addWidget(invoice_lines_group)
        self.details_tabs.addTab(analysis_page, "Análise da Fatura")
        self.contestation_analysis_tree = QTreeWidget()
        self.contestation_analysis_tree.setHeaderLabels(["ID Análise", "Valor Contestado", "Valor sob Análise", "Justificativa", "Status"])
        self.details_tabs.addTab(self.contestation_analysis_tree, "Análise da Contestação")
        self.interfaces_tree = QTreeWidget()
        self.interfaces_tree.setHeaderLabels(["Tipo", "Status", "Valor", "Data Envio", "Erro"])
        self.details_tabs.addTab(self.interfaces_tree, "Interfaces (RMCA/SGR)")
        adjust_page = QWidget()
        adjust_layout = QVBoxLayout(adjust_page)
        self.adjust_summary_label = QLabel("<b>Status Geral:</b> Clique nesta aba para carregar os dados.")
        self.adjust_tree = QTreeWidget()
        self.adjust_tree.setHeaderLabels(["Descrição", "Valor Corrigido", "Números Chamados", "Status"])
        adjust_layout.addWidget(self.adjust_summary_label)
        adjust_layout.addWidget(self.adjust_tree)
        self.details_tabs.addTab(adjust_page, "Conta Certa (Ajuste Futuro)")
        self.history_tree = QTreeWidget()
        self.history_tree.setHeaderLabels(["Status Anterior", "Status Novo", "Data da Mudança"])
        self.details_tabs.addTab(self.history_tree, "Histórico (Auditoria)")
        self.details_tabs.currentChanged.connect(self._on_tab_changed)
        layout.addLayout(actions_layout)
        layout.addWidget(master_group)
        layout.addWidget(self.details_tabs)
        self.back_button.clicked.connect(self.go_to_search_page)
        self.discard_button.clicked.connect(self._confirm_and_discard)
        self.refresh_button.clicked.connect(self._refresh_details)
        return page

    def go_to_search_page(self):
        self.stack.setCurrentWidget(self.search_page)
        self.details_button.setEnabled(False)
        self.log_button.setEnabled(False)
    
    def populate_db_combo(self):
        self.db_combo.clear()
        config = configparser.ConfigParser()
        try:
            config.read('config.ini')
            db_connections = [s for s in config.sections() if s.startswith('database_')]
            if db_connections:
                for section_name in sorted(db_connections):
                    self.db_combo.addItem(section_name, section_name)
            else: self.db_combo.addItem("Nenhuma conexão de banco encontrada", None)
        except Exception as e: QMessageBox.critical(self, "Erro de Configuração", f"Não foi possível ler as conexões do arquivo config.ini.\n\n{e}")

    def _on_tab_changed(self, index):
        tab_name = self.details_tabs.tabText(index)
        if tab_name in self.loaded_tabs or not self.current_sr: return
        logging.info(f"Iniciando carregamento sob demanda para a aba: '{tab_name}'")
        db_key = self.db_combo.currentData()
        if tab_name == "Análise da Fatura":
            for i in range(self.analysis_summary_group.layout().count()): self.analysis_summary_group.layout().itemAt(i).widget().hide()
            self.analysis_summary_group.layout().addWidget(QLabel("Carregando..."))
            self.analysis_worker = AnalysisWorker(db_key, self.current_sr)
            self.analysis_worker.finished.connect(self._on_analysis_finished)
            self.analysis_worker.error.connect(self._on_worker_error)
            self.analysis_worker.start()
            if self.current_invoicenumber:
                self.invoice_lines_tree.clear()
                QTreeWidgetItem(self.invoice_lines_tree, ["Carregando itens da fatura..."])
                self.invoice_lines_worker = InvoiceLinesWorker(db_key, self.current_invoicenumber)
                self.invoice_lines_worker.finished.connect(self._on_invoice_lines_finished)
                self.invoice_lines_worker.error.connect(self._on_worker_error)
                self.invoice_lines_worker.start()
        elif tab_name == "Análise da Contestação":
            self.contestation_analysis_tree.clear()
            QTreeWidgetItem(self.contestation_analysis_tree, ["Carregando..."])
            self.contestation_analysis_worker = ContestationAnalysisWorker(db_key, self.current_sr)
            self.contestation_analysis_worker.finished.connect(self._on_contestation_analysis_finished)
            self.contestation_analysis_worker.error.connect(self._on_worker_error)
            self.contestation_analysis_worker.start()
        elif tab_name == "Interfaces (RMCA/SGR)":
            self.interfaces_tree.clear()
            QTreeWidgetItem(self.interfaces_tree, ["Carregando..."])
            self.interface_worker = InterfaceWorker(db_key, self.current_sr)
            self.interface_worker.finished.connect(self._on_interface_finished)
            self.interface_worker.error.connect(self._on_worker_error)
            self.interface_worker.start()
        elif tab_name == "Conta Certa (Ajuste Futuro)":
            self.adjust_summary_label.setText("<b>Status Geral:</b> Carregando...")
            self.adjust_worker = AdjustWorker(db_key, self.current_sr)
            self.adjust_worker.finished.connect(self._on_adjust_finished)
            self.adjust_worker.error.connect(self._on_worker_error)
            self.adjust_worker.start()
    
    def _on_contestation_analysis_finished(self, details):
        logging.info("Dados da Análise da Contestação recebidos.")
        self.loaded_tabs.add("Análise da Contestação")
        self.contestation_analysis_tree.clear()
        if not details:
            QTreeWidgetItem(self.contestation_analysis_tree, ["Nenhum detalhe encontrado para a análise da contestação."])
            return
        for item in details:
            QTreeWidgetItem(self.contestation_analysis_tree, [str(item.get('id_analise', '')), str(item.get('valor_da_contestacao', '')), str(item.get('valor_sob_analise', '')), str(item.get('justificativa', '')), str(item.get('status_da_analise', ''))])
        for i in range(self.contestation_analysis_tree.columnCount()): self.contestation_analysis_tree.resizeColumnToContents(i)

    def _on_analysis_finished(self, details):
        logging.info("Dados de Análise recebidos.")
        self.loaded_tabs.add("Análise da Fatura") 
        layout = self.analysis_summary_group.layout()
        while layout.count(): item = layout.takeAt(0); widget = item.widget(); widget.deleteLater()
        if not details or 'analysis_summary' not in details:
            layout.addWidget(QLabel("Nenhum dado de análise encontrado."))
            return
        self.analysis_summary_labels = {}
        summary_fields = ["Tipo", "Valor Reclamado", "Valor Procedente"]
        for field in summary_fields:
            label = QLabel(f"<b>{field}:</b> N/A"); self.analysis_summary_labels[field] = label; layout.addWidget(label)
        summary = details.get('analysis_summary', {})
        self.analysis_summary_labels["Tipo"].setText(f"<b>Tipo:</b> {summary.get('contestationtype', 'N/A')}")
        self.analysis_summary_labels["Valor Reclamado"].setText(f"<b>Valor Reclamado:</b> R$ {summary.get('foundedvalue', 0):.2f}")
        self.analysis_summary_labels["Valor Procedente"].setText(f"<b>Valor Procedente:</b> R$ {summary.get('unfoundedvalue', 0):.2f}")
        self.analysis_tree.clear()
        for line in details.get('analysis_lines', []):
            QTreeWidgetItem(self.analysis_tree, ["Item "+str(line.get('id_')), str(line.get('contestationvalue')), str(line.get('analysisvalue')), str(line.get('linestatusname')), str(line.get('reason_name'))])
        for i in range(self.analysis_tree.columnCount()): self.analysis_tree.resizeColumnToContents(i)

    def _on_invoice_lines_finished(self, details):
        logging.info("Dados dos itens da fatura recebidos.")
        self.invoice_lines_tree.clear()
        if not details:
            QTreeWidgetItem(self.invoice_lines_tree, ["Nenhum item encontrado para esta fatura."])
            return
        for item in details:
            QTreeWidgetItem(self.invoice_lines_tree, [str(item.get('item_fatura', '')), str(item.get('valor', '')), str(item.get('servico_bscs', '')), str(item.get('conta_contabil', '')), str(item.get('seção_de_fatura', '')), str(item.get('invoicenumber', '')), str(item.get('customerid', '')), str(item.get('billnumber', '')), str(item.get('pagenumber', '')), str(item.get('amount', '')),])
        for i in range(self.invoice_lines_tree.columnCount()): self.invoice_lines_tree.resizeColumnToContents(i)

    def _on_interface_finished(self, details):
        logging.info("Dados de Interface recebidos.")
        self.loaded_tabs.add("Interfaces (RMCA/SGR)"); self.interfaces_tree.clear()
        if not details: QTreeWidgetItem(self.interfaces_tree, ["Nenhum dado de interface encontrado."]); return
        for interface in details:
            QTreeWidgetItem(self.interfaces_tree, [str(interface.get('type_desc')), str(interface.get('desc_status')), str(interface.get('adjustrmcavalue') or interface.get('occcreditvalue') or '0.0'), str(interface.get('senddate', 'N/A')), str(interface.get('errordescription',''))])
        for i in range(self.interfaces_tree.columnCount()): self.interfaces_tree.resizeColumnToContents(i)

    def _on_adjust_finished(self, details):
        logging.info("Dados de Ajuste recebidos.")
        self.loaded_tabs.add("Conta Certa (Ajuste Futuro)")
        if not details or 'adjust_summary' not in details: self.adjust_summary_label.setText("<b>Status Geral:</b> Nenhum ajuste futuro encontrado."); return
        summary = details.get('adjust_summary', {}); self.adjust_summary_label.setText(f"<b>Status Geral:</b> {summary.get('desc_status', 'N/A')}")
        self.adjust_tree.clear()
        for line in details.get('adjust_lines', []):
            QTreeWidgetItem(self.adjust_tree, [line.get('description'), str(line.get('value',0)), line.get('callednumbers',''), str(line.get('status'))])
        for i in range(self.adjust_tree.columnCount()): self.adjust_tree.resizeColumnToContents(i)
        
    def _on_selection_changed(self):
        is_selected = bool(self.results_tree.selectedItems())
        self.details_button.setEnabled(is_selected)
        self.log_button.setEnabled(is_selected)

    def _on_details_button_clicked(self):
        selected = self.results_tree.selectedItems()
        if selected: self._fetch_and_show_details(selected[0])

    def _on_item_double_clicked(self, item, column):
        self._fetch_and_show_details(item)
    
    def _fetch_and_show_details(self, item):
        self.current_request_id = item.data(0, Qt.ItemDataRole.UserRole)
        self.current_sr = item.text(0)
        self.current_invoicenumber = item.text(2) 
        self._refresh_details()

    def _refresh_details(self):
        if not self.current_request_id: return
        self.loaded_tabs.clear()
        self._reset_detail_tabs()
        self.details_worker = DetailsWorker(self.db_combo.currentData(), self.current_request_id)
        self.details_worker.finished.connect(self._on_details_finished)
        self.details_worker.error.connect(self._on_worker_error)
        self.details_worker.start()

    def _reset_detail_tabs(self):
        self.analysis_tree.clear()
        layout = self.analysis_summary_group.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget: widget.deleteLater()
        layout.addWidget(QLabel("Clique nesta aba para carregar."))
        self.invoice_lines_tree.clear() 
        self.contestation_analysis_tree.clear()
        QTreeWidgetItem(self.contestation_analysis_tree, ["Clique nesta aba para carregar..."])
        self.interfaces_tree.clear()
        QTreeWidgetItem(self.interfaces_tree, ["Clique nesta aba para carregar..."])
        self.adjust_summary_label.setText("<b>Status Geral:</b> Clique nesta aba para carregar os dados.")
        self.adjust_tree.clear()

    def _on_details_finished(self, details):
        if not details:
            QMessageBox.warning(self, "Atenção", f"Não foi possível carregar os detalhes para a SR {self.current_sr}.")
            return
        req = details.get('request', {})
        self.master_labels["Protocolo (SR)"].setText(f"<b>Protocolo (SR):</b> {req.get('sr', 'N/A')}")
        self.master_labels["MSISDN"].setText(f"<b>MSISDN:</b> {req.get('msisdn', 'N/A')}")
        self.master_labels["Fatura"].setText(f"<b>Fatura:</b> {req.get('invoicenumber', 'N/A')}")
        self.master_labels["CustomerID"].setText(f"<b>CustomerID:</b> {req.get('customerid', 'N/A')}")
        self.master_labels["Data Solicitação"].setText(f"<b>Data Solicitação:</b> {str(req.get('createdate', 'N/A'))}")
        self.master_labels["Status"].setText(f"<b>Status:</b> {req.get('statusname', 'N/A')}")
        self.history_tree.clear()
        self.loaded_tabs.add("Histórico (Auditoria)")
        history_list = details.get('history', [])
        if history_list:
            previous_status = "Criado" 
            for entry in reversed(history_list):
                current_status = entry.get('statusname')
                item = QTreeWidgetItem(self.history_tree, [previous_status, current_status, str(entry.get('modifieddate'))])
                previous_status = current_status
        self.stack.setCurrentWidget(self.details_page)
        self.details_tabs.setCurrentIndex(0)
        self._on_tab_changed(0)

    def _confirm_and_discard(self):
        if not self.current_sr: return
        reply = QMessageBox.question(self, "Confirmar Ação", f"Tem certeza que deseja DESCARTAR a contestação SR {self.current_sr}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.discard_worker = DiscardWorker(self.db_combo.currentData(), self.current_sr)
            self.discard_worker.finished.connect(self._on_discard_finished)
            self.discard_worker.error.connect(self._on_worker_error)
            self.discard_worker.start()
            
    def _on_discard_finished(self, message):
        QMessageBox.information(self, "Sucesso", message)
        self._refresh_details()