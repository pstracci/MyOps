# C:\Meus Projetos\MyOps\modules\contestacao\contestacao_ui.py

import logging
import configparser  # Importado para ler as conexões diretamente
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QLabel, QLineEdit, QGroupBox,
                             QStackedWidget, QMessageBox, QHeaderView, QComboBox,
                             QTabWidget, QDateEdit, QCheckBox, QSpinBox, QGridLayout)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QDate
from modules.contestacao import contestacao_logic as logic

# --- WORKERS (Threads para operações de banco - SEM ALTERAÇÕES) ---
class SearchWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, db_key, sr, msisdn, start_date, end_date, status):
        super().__init__()
        self.db_key, self.sr, self.msisdn, self.start_date, self.end_date, self.status = db_key, sr, msisdn, start_date, end_date, status
    def run(self):
        try:
            self.finished.emit(logic.search_contestacoes(self.db_key, self.sr, self.msisdn, self.start_date, self.end_date, self.status))
        except Exception as e:
            self.error.emit(str(e))

class InterfaceSearchWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, db_key, status, hours):
        super().__init__()
        self.db_key, self.status, self.hours = db_key, status, hours
    def run(self):
        try:
            self.finished.emit(logic.search_interfaces(self.db_key, self.status, self.hours))
        except Exception as e:
            self.error.emit(str(e))

class DetailsWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, db_key, request_id):
        super().__init__()
        self.db_key, self.request_id = db_key, request_id
    def run(self):
        logging.info(f"Worker {self.__class__.__name__} iniciado em background.")
        try:
            logging.info("Executando a lógica de busca de detalhes do cabeçalho...")
            results = logic.get_request_details(self.db_key, self.request_id)
            logging.info("Lógica de busca de detalhes do cabeçalho concluída.")
            self.finished.emit(results)
        except Exception as e:
            logging.error(f"Erro no {self.__class__.__name__}", exc_info=True)
            self.error.emit(str(e))

class AnalysisWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, db_key, sr):
        super().__init__()
        self.db_key, self.sr = db_key, sr
    def run(self):
        logging.info(f"Worker {self.__class__.__name__} iniciado em background.")
        try:
            logging.info("Executando a lógica de busca de análise...")
            results = logic.get_analysis_details(self.db_key, self.sr)
            logging.info("Lógica de busca de análise concluída.")
            self.finished.emit(results)
        except Exception as e:
            logging.error(f"Erro no {self.__class__.__name__}", exc_info=True)
            self.error.emit(str(e))

class InterfaceWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, db_key, sr):
        super().__init__()
        self.db_key, self.sr = db_key, sr
    def run(self):
        logging.info(f"Worker {self.__class__.__name__} iniciado em background.")
        try:
            logging.info("Executando a lógica de busca de interfaces...")
            results = logic.get_interface_details(self.db_key, self.sr)
            logging.info("Lógica de busca de interfaces concluída.")
            self.finished.emit(results)
        except Exception as e:
            logging.error(f"Erro no {self.__class__.__name__}", exc_info=True)
            self.error.emit(str(e))

class AdjustWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, db_key, sr):
        super().__init__()
        self.db_key, self.sr = db_key, sr
    def run(self):
        logging.info(f"Worker {self.__class__.__name__} iniciado em background.")
        try:
            logging.info("Executando a lógica de busca de ajuste futuro...")
            results = logic.get_adjust_details(self.db_key, self.sr)
            logging.info("Lógica de busca de ajuste futuro concluída.")
            self.finished.emit(results)
        except Exception as e:
            logging.error(f"Erro no {self.__class__.__name__}", exc_info=True)
            self.error.emit(str(e))

class DiscardWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, db_key, sr):
        super().__init__()
        self.db_key, self.sr = db_key, sr
    def run(self):
        logging.info(f"Worker {self.__class__.__name__} iniciado em background.")
        try:
            logging.info("Executando a lógica para descartar contestação...")
            results = logic.descartar_contestacao(self.db_key, self.sr)
            logging.info("Lógica para descartar contestação concluída.")
            self.finished.emit(results)
        except Exception as e:
            logging.error(f"Erro no {self.__class__.__name__}", exc_info=True)
            self.error.emit(str(e))

# --- WIDGET PRINCIPAL ---
class ContestacaoViewerWidget(QWidget):
    def __init__(self):
        super().__init__()
        logging.info("Iniciando o widget ContestacaoViewerWidget...")
        self.current_sr = None
        self.current_request_id = None
        self.loaded_tabs = set()
        main_layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        self.search_page = self._create_search_page()
        self.details_page = self._create_details_page()
        self.stack.addWidget(self.search_page)
        self.stack.addWidget(self.details_page)
        main_layout.addWidget(self.stack)
        logging.info("Widget ContestacaoViewerWidget inicializado com sucesso.")

    def _create_search_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        db_group = QGroupBox("Conexão")
        db_layout = QHBoxLayout(db_group)
        self.db_combo = QComboBox()
        self.populate_db_combo()
        db_layout.addWidget(QLabel("Consultar Base:"))
        db_layout.addWidget(self.db_combo)
        
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
        self.status_combo.addItems([
            "Todos", "Iniciada", "Erro na busca", "Fatura não encontrada",
            "Conta contábil não cadastrada", "Erro de alçada", "Descartada",
            "Gerada", "Finalizada", "Itens já contestados", "Erro na validação",
            "Finalizada Improcedente"
        ])
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
        self.details_button.setEnabled(False)
        buttons_layout.addWidget(self.search_button)
        buttons_layout.addWidget(self.details_button)
        buttons_layout.addStretch()

        results_group = QGroupBox("Resultados")
        results_layout = QVBoxLayout(results_group)
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Protocolo (SR)", "MSISDN", "Fatura", "Data", "Status"])
        header = self.results_tree.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.results_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.results_tree.itemSelectionChanged.connect(self._on_selection_changed)
        results_layout.addWidget(self.results_tree)
        
        layout.addWidget(filters_group)
        layout.addLayout(buttons_layout)
        layout.addWidget(results_group)
        
        self.search_button.clicked.connect(self._perform_search)
        self.details_button.clicked.connect(self._on_details_button_clicked)
        self.period_check.toggled.connect(self.start_date_input.setEnabled)
        self.period_check.toggled.connect(self.end_date_input.setEnabled)
        
        return page

    def _create_interface_search_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)

        filters_group = QGroupBox("Filtros de Busca de Interfaces")
        filters_layout = QGridLayout(filters_group)

        self.interface_status_combo = QComboBox()
        self.interface_status_combo.addItems([
            "Todos", "Sucesso", "Nao enviado", "Aguardando Retorno",
            "Erro Permanente", "Envio Cancelado", "Erro Temporario"
        ])
        
        self.hours_spinbox = QSpinBox()
        self.hours_spinbox.setRange(1, 720) # De 1 hora a 30 dias
        self.hours_spinbox.setValue(24) # Padrão de 24 horas
        
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
        logging.info(f"{len(results) if results else 0} interfaces encontradas.")
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
        
        for i in range(self.interface_results_tree.columnCount()):
            self.interface_results_tree.resizeColumnToContents(i)

    def _perform_search(self):
        logging.info("Botão 'Buscar' clicado. Iniciando SearchWorker...")
        self.search_button.setEnabled(False)
        self.details_button.setEnabled(False)
        self.results_tree.clear()
        
        db_key = self.db_combo.currentData()
        if not db_key:
            logging.warning("Busca cancelada: Nenhuma base de dados selecionada.")
            QMessageBox.warning(self, "Atenção", "Nenhuma base de dados selecionada.")
            self.search_button.setEnabled(True)
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
        self.details_tabs.addTab(analysis_page, "Análise da Fatura")

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
        logging.info("Retornando para a página de busca.")
        self.stack.setCurrentWidget(self.search_page)
        self.details_button.setEnabled(False)

    # --- ALTERAÇÃO PRINCIPAL AQUI ---
    def populate_db_combo(self):
        """
        Popula o QComboBox com todas as conexões de banco de dados encontradas
        no arquivo config.ini que começam com 'database_'.
        """
        self.db_combo.clear()
        config = configparser.ConfigParser()
        try:
            config.read('config.ini')
            # Busca todas as seções que começam com 'database_'
            db_connections = [s for s in config.sections() if s.startswith('database_')]
            
            if db_connections:
                for section_name in sorted(db_connections):
                    # O texto exibido será o nome da seção, e o dado interno também.
                    self.db_combo.addItem(section_name, section_name)
            else:
                self.db_combo.addItem("Nenhuma conexão de banco encontrada", None)
        except Exception as e:
            QMessageBox.critical(self, "Erro de Configuração", f"Não foi possível ler as conexões do arquivo config.ini.\n\n{e}")

    def _on_tab_changed(self, index):
        tab_name = self.details_tabs.tabText(index)
        logging.debug(f"Aba alterada para: '{tab_name}' (índice {index}). Abas já carregadas: {self.loaded_tabs}")
        if tab_name in self.loaded_tabs or not self.current_sr:
            return
        
        logging.info(f"Iniciando carregamento sob demanda para a aba: '{tab_name}'")
        db_key = self.db_combo.currentData()
        if tab_name == "Análise da Fatura":
            for i in range(self.analysis_summary_group.layout().count()): self.analysis_summary_group.layout().itemAt(i).widget().hide()
            self.analysis_summary_group.layout().addWidget(QLabel("Carregando..."))
            self.analysis_worker = AnalysisWorker(db_key, self.current_sr)
            self.analysis_worker.finished.connect(self._on_analysis_finished)
            self.analysis_worker.error.connect(self._on_worker_error)
            self.analysis_worker.start()
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
        logging.debug(f"Seleção na lista de resultados alterada. Habilitando botão de detalhes: {is_selected}")
        self.details_button.setEnabled(is_selected)

    def _on_details_button_clicked(self):
        logging.info("Botão 'Ver Detalhes' clicado.")
        selected = self.results_tree.selectedItems()
        if selected:
            self._fetch_and_show_details(selected[0])
        else:
            logging.warning("Botão 'Ver Detalhes' clicado, mas nenhum item estava selecionado.")
    
    def _on_item_double_clicked(self, item, column):
        logging.info(f"Item '{item.text(0)}' recebeu duplo-clique.")
        self._fetch_and_show_details(item)
    
    def _fetch_and_show_details(self, item):
        self.current_request_id = item.data(0, Qt.ItemDataRole.UserRole)
        self.current_sr = item.text(0)
        logging.info(f"Iniciando busca de detalhes para SR: {self.current_sr} (ID: {self.current_request_id})")
        self._refresh_details()
    
    def _on_search_finished(self, results):
        logging.info("Worker de busca finalizado.")
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
    
    def _refresh_details(self):
        if not self.current_request_id:
            return
        logging.info("Atualizando detalhes. Resetando abas e iniciando DetailsWorker...")
        self.loaded_tabs.clear()
        self._reset_detail_tabs()
        
        self.details_worker = DetailsWorker(self.db_combo.currentData(), self.current_request_id)
        self.details_worker.finished.connect(self._on_details_finished)
        self.details_worker.error.connect(self._on_worker_error)
        self.details_worker.start()

    def _reset_detail_tabs(self):
        logging.debug("Resetando o conteúdo de todas as abas de detalhes.")
        self.analysis_tree.clear()
        layout = self.analysis_summary_group.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        layout.addWidget(QLabel("Clique nesta aba para carregar."))

        self.interfaces_tree.clear()
        QTreeWidgetItem(self.interfaces_tree, ["Clique nesta aba para carregar..."])
        self.adjust_summary_label.setText("<b>Status Geral:</b> Clique nesta aba para carregar os dados.")
        self.adjust_tree.clear()

    def _on_details_finished(self, details):
        logging.info("Worker de detalhes do cabeçalho finalizado.")
        if not details:
            logging.warning(f"Não foi possível carregar o cabeçalho para a SR {self.current_sr}.")
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
        
        logging.info("Mudando para a tela de detalhes e forçando o carregamento da primeira aba.")
        self.stack.setCurrentWidget(self.details_page)
        self.details_tabs.setCurrentIndex(0)
        self._on_tab_changed(0)

    def _confirm_and_discard(self):
        if not self.current_sr:
            logging.warning("Tentativa de descarte sem SR selecionado.")
            QMessageBox.warning(self, "Ação Inválida", "Nenhuma contestação selecionada.")
            return
            
        reply = QMessageBox.question(self, "Confirmar Ação", f"Tem certeza que deseja DESCARTAR a contestação SR {self.current_sr}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            logging.info(f"Iniciando descarte para a SR {self.current_sr}.")
            self.discard_worker = DiscardWorker(self.db_combo.currentData(), self.current_sr)
            self.discard_worker.finished.connect(self._on_discard_finished)
            self.discard_worker.error.connect(self._on_worker_error)
            self.discard_worker.start()
            
    def _on_discard_finished(self, message):
        logging.info(f"Descarte concluído para a SR {self.current_sr}.")
        QMessageBox.information(self, "Sucesso", message)
        self._refresh_details()

    def _on_worker_error(self, message):
        logging.error(f"Ocorreu um erro em uma operação de background: {message}", exc_info=True)
        if hasattr(self, 'search_button'):
            self.search_button.setEnabled(True)
        if hasattr(self, 'interface_search_button'):
            self.interface_search_button.setEnabled(True)
        QMessageBox.critical(self, "Erro", message)
