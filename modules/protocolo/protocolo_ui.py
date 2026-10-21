# C:\Meus Projetos\MyOps\modules\protocolo\protocolo_ui.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QGroupBox, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTextEdit, QMessageBox, QSizePolicy, QSplitter,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDateTime

from modules.protocolo import protocolo_logic as logic


# ─── Workers ─────────────────────────────────────────────────────────────────

class SearchWorker(QThread):
    """Busca a LISTA de protocolos (por protocolo / CPF / MSISDN)."""
    result = pyqtSignal(dict)      # {'columns', 'rows', 'count'}
    log    = pyqtSignal(str)
    error  = pyqtSignal(str)

    def __init__(self, identifier, mode):
        super().__init__()
        self.identifier = identifier
        self.mode = mode

    def run(self):
        try:
            self.log.emit(f"Consultando Siebel ({self.mode})...")
            data = logic.search_protocols(self.identifier, self.mode)
            self.result.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class DetailWorker(QThread):
    """Carrega o DETALHE de um protocolo (Siebel + SGP)."""
    siebel_done = pyqtSignal(object)   # list[(label,value)] | None
    sgp_done    = pyqtSignal(object)   # list | None | str
    log         = pyqtSignal(str)
    finished_ok = pyqtSignal()
    error       = pyqtSignal(str)

    def __init__(self, protocol_num):
        super().__init__()
        self.protocol_num = protocol_num

    def run(self):
        try:
            self.log.emit(f"Carregando detalhe do protocolo {self.protocol_num}...")
            self.siebel_done.emit(logic.get_protocol_status_siebel(self.protocol_num))

            if logic.is_sgp_configured():
                try:
                    self.sgp_done.emit(logic.get_protocol_status_sgp(self.protocol_num))
                except Exception as e:
                    self.sgp_done.emit(f"Erro SGP: {e}")
            else:
                self.sgp_done.emit("não_configurado")
            self.finished_ok.emit()
        except Exception as e:
            self.error.emit(str(e))


class FinalizarWorker(QThread):
    result = pyqtSignal(str)
    error  = pyqtSignal(str)

    def __init__(self, protocol_num):
        super().__init__()
        self.protocol_num = protocol_num

    def run(self):
        try:
            self.result.emit(logic.finalizar_protocolo(self.protocol_num))
        except Exception as e:
            self.error.emit(str(e))


# ─── Widget principal ────────────────────────────────────────────────────────

class ProtocoloWidget(QWidget):

    _MODES = [
        ("Protocolo", "protocolo"),
        ("CPF (todos os protocolos do cliente)", "cpf"),
        ("MSISDN (todos os protocolos da linha)", "msisdn"),
    ]

    def __init__(self):
        super().__init__()
        self._search_worker    = None
        self._detail_worker    = None
        self._finalizar_worker = None
        self._selected_protocol = None
        self._col_idx = {}   # nome do rótulo -> índice na tabela de resultados
        self._build_ui()

    # ─── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # 1. Busca
        search_box = QGroupBox("Busca de Protocolos")
        search_lay = QHBoxLayout(search_box)

        self.mode_combo = QComboBox()
        for label, _key in self._MODES:
            self.mode_combo.addItem(label)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self.search_input = QLineEdit()
        self.search_input.setMinimumWidth(240)
        self.search_input.returnPressed.connect(self.on_consultar)

        self.btn_consultar = QPushButton("Consultar")
        self.btn_consultar.setMinimumHeight(34)
        self.btn_consultar.setDefault(True)
        self.btn_consultar.clicked.connect(self.on_consultar)

        search_lay.addWidget(QLabel("Buscar por:"))
        search_lay.addWidget(self.mode_combo)
        search_lay.addWidget(self.search_input, 1)
        search_lay.addWidget(self.btn_consultar)
        root.addWidget(search_box)
        self._on_mode_changed(0)

        # 2. Resultados (lista) + Detalhe (Siebel | SGP) num splitter vertical
        splitter = QSplitter(Qt.Orientation.Vertical)

        results_box = QGroupBox("Protocolos encontrados")
        results_lay = QVBoxLayout(results_box)
        self.results_table = QTableWidget(0, 0)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.itemSelectionChanged.connect(self._on_result_selected)
        results_lay.addWidget(self.results_table)
        self._results_count = QLabel("")
        results_lay.addWidget(self._results_count)
        splitter.addWidget(results_box)

        detail_box = QGroupBox("Detalhe do protocolo selecionado")
        detail_outer = QVBoxLayout(detail_box)
        panels_row = QHBoxLayout()
        self._siebel_group, self._siebel_table = self._make_kv_group("Siebel Pós")
        self._sgp_group,    self._sgp_table    = self._make_kv_group("SGP")
        panels_row.addWidget(self._siebel_group, 1)
        panels_row.addWidget(self._sgp_group, 1)
        detail_outer.addLayout(panels_row)
        splitter.addWidget(detail_box)
        splitter.setSizes([260, 300])
        root.addWidget(splitter, 1)

        # 3. Ação
        action_box = QGroupBox("Ação")
        action_lay = QHBoxLayout(action_box)
        self.btn_finalizar = QPushButton("Finalizar Protocolo")
        self.btn_finalizar.setMinimumHeight(40)
        self.btn_finalizar.setEnabled(False)
        self.btn_finalizar.setStyleSheet(
            "QPushButton { background-color: #c0392b; color: white; font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #e74c3c; }"
            "QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }"
        )
        self.btn_finalizar.clicked.connect(self.on_finalizar)
        self._proc_label = QLabel(f"Executa: <b>{logic.PROC_NAME}</b> no banco Siebel Pós")
        self._proc_label.setTextFormat(Qt.TextFormat.RichText)
        action_lay.addWidget(self._proc_label, 1)
        action_lay.addWidget(self.btn_finalizar)
        root.addWidget(action_box)

        # 4. Log
        log_box = QGroupBox("Log")
        log_lay = QVBoxLayout(log_box)
        self._log = QTextEdit(readOnly=True)
        self._log.setFont(QFont("Courier", 9))
        self._log.setMaximumHeight(120)
        log_lay.addWidget(self._log)
        root.addWidget(log_box)

    def _make_kv_group(self, title):
        group = QGroupBox(title)
        lay = QVBoxLayout(group)
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Campo", "Valor"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(table)
        return group, table

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _mode_key(self):
        return self._MODES[self.mode_combo.currentIndex()][1]

    def _on_mode_changed(self, _idx):
        placeholders = {
            'protocolo': "Digite o número do protocolo...",
            'cpf':       "Digite o CPF (somente números)...",
            'msisdn':    "Digite o MSISDN (DDD + número)...",
        }
        self.search_input.setPlaceholderText(placeholders.get(self._mode_key(), ""))

    def _log_msg(self, text):
        ts = QDateTime.currentDateTime().toString("hh:mm:ss")
        self._log.append(f"[{ts}] {text}")

    def _set_busy(self, busy):
        self.btn_consultar.setEnabled(not busy)
        self.search_input.setEnabled(not busy)
        self.mode_combo.setEnabled(not busy)

    def _fill_kv(self, table, pairs):
        table.setRowCount(0)
        if not pairs:
            table.setRowCount(1)
            table.setItem(0, 0, QTableWidgetItem("—"))
            table.setItem(0, 1, QTableWidgetItem("Não encontrado"))
            return
        for label, value in pairs:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(label)))
            table.setItem(row, 1, QTableWidgetItem(str(value)))

    # ─── Consultar (lista) ─────────────────────────────────────────────────────

    def on_consultar(self):
        identifier = self.search_input.text().strip()
        if not identifier:
            QMessageBox.warning(self, "Campo obrigatório", "Informe o valor para a busca.")
            return

        self._set_busy(True)
        self._selected_protocol = None
        self.btn_finalizar.setEnabled(False)
        self.results_table.setRowCount(0)
        self.results_table.setColumnCount(0)
        self._siebel_table.setRowCount(0)
        self._sgp_table.setRowCount(0)
        self._results_count.setText("")
        self._log.clear()
        self._log_msg(f"Iniciando busca por {self._mode_key()}: {identifier}")

        self._search_worker = SearchWorker(identifier, self._mode_key())
        self._search_worker.result.connect(self._on_search_result)
        self._search_worker.log.connect(self._log_msg)
        self._search_worker.error.connect(self._on_error)
        self._search_worker.start()

    def _on_search_result(self, data):
        self._set_busy(False)
        columns = data.get('columns', [])
        rows = data.get('rows', [])
        self._col_idx = {name: i for i, name in enumerate(columns)}

        self.results_table.setColumnCount(len(columns))
        self.results_table.setHorizontalHeaderLabels(columns)
        self.results_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                self.results_table.setItem(r, c, QTableWidgetItem(str(val)))
        self.results_table.resizeColumnsToContents()
        hdr = self.results_table.horizontalHeader()
        if columns:
            hdr.setSectionResizeMode(len(columns) - 1, QHeaderView.ResizeMode.Stretch)

        self._results_count.setText(f"{len(rows)} protocolo(s) encontrado(s)"
                                    + (f" (exibindo até {logic.MAX_RESULTS})" if len(rows) >= logic.MAX_RESULTS else ""))
        self._log_msg(f"{len(rows)} protocolo(s) encontrado(s).")

        if not rows:
            self._fill_kv(self._siebel_table, None)
            return
        # Seleciona automaticamente o primeiro (carrega o detalhe).
        self.results_table.selectRow(0)

    # ─── Detalhe ────────────────────────────────────────────────────────────────

    def _current_row_protocol(self):
        """Nº de protocolo da linha selecionada (usa Protocolo; se vazio, a SR)."""
        sel = self.results_table.selectionModel().selectedRows()
        if not sel:
            return None
        r = sel[0].row()

        def cell(label):
            idx = self._col_idx.get(label)
            if idx is None:
                return None
            item = self.results_table.item(r, idx)
            return item.text().strip() if item else None

        prot = cell("Protocolo")
        if prot and prot != "—":
            return prot
        sr = cell("SR")
        return sr if (sr and sr != "—") else None

    def _on_result_selected(self):
        protocol = self._current_row_protocol()
        if not protocol:
            return
        self._selected_protocol = protocol
        self.btn_finalizar.setEnabled(False)
        self._siebel_table.setRowCount(0)
        self._sgp_table.setRowCount(0)

        self._detail_worker = DetailWorker(protocol)
        self._detail_worker.siebel_done.connect(self._on_siebel_detail)
        self._detail_worker.sgp_done.connect(self._on_sgp_detail)
        self._detail_worker.log.connect(self._log_msg)
        self._detail_worker.finished_ok.connect(self._on_detail_finished)
        self._detail_worker.error.connect(self._on_error)
        self._detail_worker.start()

    def _on_siebel_detail(self, data):
        self._fill_kv(self._siebel_table, data)
        if data is None:
            self._log_msg("Protocolo não encontrado no Siebel.")

    def _on_sgp_detail(self, data):
        if data == "não_configurado":
            self._sgp_group.setTitle("SGP  [não configurado]")
            self._sgp_table.setRowCount(1)
            self._sgp_table.setItem(0, 0, QTableWidgetItem("Info"))
            self._sgp_table.setItem(0, 1, QTableWidgetItem(
                "Adicione a seção 'database_sgp' no Gerenciador de Conexões para habilitar."
            ))
            return
        if isinstance(data, str) and data.startswith("Erro SGP:"):
            self._sgp_table.setRowCount(1)
            self._sgp_table.setItem(0, 0, QTableWidgetItem("Erro"))
            self._sgp_table.setItem(0, 1, QTableWidgetItem(data))
            self._log_msg(data)
            return
        self._fill_kv(self._sgp_table, data)

    def _on_detail_finished(self):
        if self._selected_protocol:
            self.btn_finalizar.setEnabled(True)

    # ─── Finalizar ──────────────────────────────────────────────────────────────

    def on_finalizar(self):
        if not self._selected_protocol:
            return
        reply = QMessageBox.warning(
            self, "Confirmar Finalização",
            f"Você está prestes a <b>FINALIZAR</b> o protocolo:<br><br>"
            f"<b>{self._selected_protocol}</b><br><br>"
            f"Isso executará <b>{logic.PROC_NAME}</b> no banco Siebel Pós.<br><br>"
            "Deseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.btn_finalizar.setEnabled(False)
        self.btn_consultar.setEnabled(False)
        self._log_msg(f"Finalizando protocolo {self._selected_protocol}...")

        self._finalizar_worker = FinalizarWorker(self._selected_protocol)
        self._finalizar_worker.result.connect(self._on_finalizar_done)
        self._finalizar_worker.error.connect(self._on_finalizar_error)
        self._finalizar_worker.start()

    def _on_finalizar_done(self, msg):
        self.btn_consultar.setEnabled(True)
        self._log_msg(f"OK: {msg}")
        QMessageBox.information(self, "Sucesso", msg)
        self._on_result_selected()  # recarrega detalhe

    def _on_finalizar_error(self, msg):
        self.btn_consultar.setEnabled(True)
        self.btn_finalizar.setEnabled(True)
        self._log_msg(f"ERRO ao finalizar: {msg}")
        QMessageBox.critical(self, "Erro ao finalizar protocolo", msg)

    # ─── Erros genéricos ─────────────────────────────────────────────────────────

    def _on_error(self, msg):
        self._set_busy(False)
        self._log_msg(f"ERRO: {msg}")
        QMessageBox.critical(self, "Erro na consulta", msg)
