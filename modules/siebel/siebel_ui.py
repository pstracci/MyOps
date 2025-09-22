# C:\Meus Projetos\MyOps\modules\siebel\siebel_ui.py

import sys
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QMessageBox, QMainWindow, QLineEdit, QLabel, QGroupBox, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QTextEdit, QHeaderView, QComboBox, QSplitter, QTabWidget, QMenu, QFileDialog, QCheckBox, QSpinBox, QStyle)
from PyQt6.QtGui import QFont, QAction, QTextCharFormat, QColor, QSyntaxHighlighter
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRegularExpression, QTimer
from sql_formatter.core import format_sql
from modules.siebel import siebel_logic as db

class SqlHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent); self.highlightingRules = []
        keyword_format = QTextCharFormat(); keyword_format.setForeground(QColor("#FC5683"))
        keywords = ["SELECT", "FROM", "WHERE", "AND", "OR", "GROUP BY", "ORDER BY", "HAVING", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "TABLE", "INDEX", "VIEW", "AS", "SET", "VALUES", "JOIN", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "OUTER JOIN", "ON", "CASE", "WHEN", "THEN", "ELSE", "END", "IN", "NOT IN", "EXISTS", "NOT EXISTS", "DISTINCT", "NULL", "PACKAGE", "BODY", "IS", "BEGIN", "PROCEDURE", "FUNCTION", "RETURN", "DECLARE", "TYPE", "RECORD", "CURSOR", "LOOP", "END LOOP", "IF", "ELSIF", "EXCEPTION", "WHEN", "OTHERS", "THEN"]
        self.add_rule(keywords, keyword_format)
        type_format = QTextCharFormat(); type_format.setForeground(QColor("#66D9EF"))
        types = ["VARCHAR2", "NUMBER", "DATE", "TIMESTAMP", "CLOB", "BLOB", "COUNT", "SUM", "AVG", "MAX", "MIN", "TO_CHAR", "TO_DATE", "NVL", "DECODE", "SYSDATE", "ROWNUM"]
        self.add_rule(types, type_format)
        string_format = QTextCharFormat(); string_format.setForeground(QColor("#E6DB74"))
        self.highlightingRules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format))
        number_format = QTextCharFormat(); number_format.setForeground(QColor("#AE81FF"))
        self.highlightingRules.append((QRegularExpression(r"\b\d+(\.\d+)?\b"), number_format))
        comment_format = QTextCharFormat(); comment_format.setForeground(QColor("#75715E"))
        self.highlightingRules.append((QRegularExpression(r"--[^\n]*"), comment_format))
        self.comment_format = comment_format; self.multiLineCommentStartExpression = QRegularExpression(r"/\*"); self.multiLineCommentEndExpression = QRegularExpression(r"\*/")
    def add_rule(self, patterns, format_obj):
        for pattern in patterns: self.highlightingRules.append((QRegularExpression(r"\b" + pattern + r"\b", QRegularExpression.PatternOption.CaseInsensitiveOption), format_obj))
    def highlightBlock(self, text):
        for pattern, format_obj in self.highlightingRules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next(); self.setFormat(match.capturedStart(), match.capturedLength(), format_obj)
        self.setCurrentBlockState(0); startIndex = 0
        if self.previousBlockState() != 1: match = self.multiLineCommentStartExpression.match(text); startIndex = match.capturedStart()
        while startIndex >= 0:
            match = self.multiLineCommentEndExpression.match(text, startIndex); endIndex = match.capturedStart(); commentLength = 0
            if endIndex == -1: self.setCurrentBlockState(1); commentLength = len(text) - startIndex
            else: commentLength = endIndex - startIndex + match.capturedLength()
            self.setFormat(startIndex, commentLength, self.comment_format)
            match = self.multiLineCommentStartExpression.match(text, startIndex + commentLength); startIndex = match.capturedStart()

class PlanHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlightingRules = []
        operation_format = QTextCharFormat(); operation_format.setForeground(QColor("#66D9EF")); operation_format.setFontWeight(QFont.Weight.Bold)
        operations = ["TABLE ACCESS", "INDEX", "NESTED LOOPS", "HASH JOIN", "MERGE JOIN", "SORT", "FILTER", "VIEW", "PARTITION", "SELECT STATEMENT", "LOAD TABLE CONVENTIONAL", "FOR ALL ENTRIES"]
        self.add_rule(operations, operation_format)
        detail_format = QTextCharFormat(); detail_format.setForeground(QColor("#FC5683"))
        details = ["FULL", "UNIQUE SCAN", "RANGE SCAN", "BY INDEX ROWID", "AGGREGATE", "ORDER BY", "GROUP BY", "OUTER", "STORAGE"]
        self.add_rule(details, detail_format)
        section_format = QTextCharFormat(); section_format.setForeground(QColor("#E6DB74")); section_format.setFontItalic(True)
        self.highlightingRules.append((QRegularExpression(r"^-+\n(.*?)\n-+$", QRegularExpression.PatternOption.MultilineOption), section_format))
        self.highlightingRules.append((QRegularExpression(r"Predicate Information \(identified by operation id\):"), section_format))
        self.highlightingRules.append((QRegularExpression(r"Note"), section_format))
        structure_format = QTextCharFormat(); structure_format.setForeground(QColor("#75715E"))
        self.highlightingRules.append((QRegularExpression(r"^\|.*\|$"), structure_format))
    def add_rule(self, patterns, format_obj):
        for pattern in patterns:
            self.highlightingRules.append((QRegularExpression(r"\b" + pattern + r"\b", QRegularExpression.PatternOption.CaseInsensitiveOption), format_obj))
    def highlightBlock(self, text):
        for pattern, format_obj in self.highlightingRules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format_obj)

class SortableTreeWidgetItem(QTreeWidgetItem):
    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        numeric_columns = [0, 1, 8]; duration_columns = [6, 7]
        if column in numeric_columns:
            try: return float(self.text(column) or -1) < float(other.text(column) or -1)
            except (ValueError, TypeError): return self.text(column).lower() < other.text(column).lower()
        if column in duration_columns:
            val_self = self.data(column, Qt.ItemDataRole.UserRole) or -1
            val_other = other.data(column, Qt.ItemDataRole.UserRole) or -1
            return val_self < val_other
        return self.text(column).lower() < other.text(column).lower()

class SessionWorker(QThread):
    finished = pyqtSignal(object); error = pyqtSignal(str)
    def run(self):
        try: self.finished.emit(db.get_active_sessions())
        except Exception as e: self.error.emit(str(e))

class SingleSessionWorker(QThread):
    finished = pyqtSignal(object); error = pyqtSignal(str)
    def __init__(self, session_data):
        super().__init__(); self.data = session_data
    def run(self):
        try: self.finished.emit(db.get_single_session_details(self.data['inst_id'], self.data['sid'], self.data['serial#']))
        except Exception as e: self.error.emit(str(e))

class SqlTextWorker(QThread):
    finished = pyqtSignal(str); error = pyqtSignal(str)
    def __init__(self, session_data):
        super().__init__(); self.data = session_data
    def run(self):
        try: self.finished.emit(db.get_sql_text(self.data['inst_id'], self.data['sql_address'], self.data['sql_hash_value'], self.data['prev_sql_address'], self.data['prev_hash_value']))
        except Exception as e: self.error.emit(str(e))

class PlanWorker(QThread):
    finished = pyqtSignal(str); error = pyqtSignal(str)
    def __init__(self, session_data, plan_format='TYPICAL'):
        super().__init__(); self.data = session_data; self.format = plan_format
    def run(self):
        try: self.finished.emit(db.get_execution_plan(self.data['sql_id'], self.data['sql_child_number'], self.data['prev_sql_id'], self.format))
        except Exception as e: self.error.emit(str(e))

class ExecutionPlanViewer(QTextEdit):
    def __init__(self, parent_widget):
        super().__init__(); self.parent_widget = parent_widget; self.setReadOnly(True)
        self.setFont(QFont("Consolas", 9)); self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("QTextEdit { background-color: #2B2B2B; color: #F8F8F2; border: 1px solid #444; }")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.customContextMenuRequested.connect(self.show_context_menu)
    def show_context_menu(self, pos):
        menu = QMenu(); export_action = menu.addAction("Exportar Plano de Execução (XML)")
        action = menu.exec(self.mapToGlobal(pos))
        if action == export_action: self.parent_widget.export_plan_to_xml()

class SiebelSessionManagerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.LONG_QUERY_THRESHOLD_SECONDS = 60; self.HIGH_PARALLEL_THRESHOLD = 4
        self.HIGHLIGHT_LONG_QUERY_COLOR = QColor(255, 220, 220); self.HIGHLIGHT_PARALLEL_COLOR = QColor(255, 250, 205)
        self.session_worker = None; self.sql_worker = None; self.plan_worker = None; self.export_worker = None; self.single_session_worker = None; self.all_sessions_data = []
        main_splitter = QSplitter(Qt.Orientation.Horizontal); self.setLayout(QVBoxLayout()); self.layout().addWidget(main_splitter)
        left_panel_widget = QWidget(); left_panel_layout = QVBoxLayout(left_panel_widget)
        
        filter_group = QGroupBox("Filtros"); filter_layout = QVBoxLayout(filter_group)
        search_layout = QHBoxLayout()
        self.status_filter_combo = QComboBox(); self.filter_input = QLineEdit(placeholderText="Filtre por qualquer campo...")
        search_layout.addWidget(QLabel("Status:")); search_layout.addWidget(self.status_filter_combo); search_layout.addWidget(self.filter_input, 1)
        
        auto_refresh_layout = QHBoxLayout()
        self.auto_refresh_check = QCheckBox("Atualizar a cada"); auto_refresh_layout.addWidget(self.auto_refresh_check)
        self.refresh_interval_spinbox = QSpinBox(); self.refresh_interval_spinbox.setRange(5, 3600); self.refresh_interval_spinbox.setValue(60); self.refresh_interval_spinbox.setSuffix(" s"); auto_refresh_layout.addWidget(self.refresh_interval_spinbox)
        auto_refresh_layout.addStretch()
        filter_layout.addLayout(search_layout); filter_layout.addLayout(auto_refresh_layout)

        self.refresh_button = QPushButton("Atualizar Sessões")
        self.session_tree = QTreeWidget(); self.session_tree.setColumnCount(9); self.session_tree.setHeaderLabels(["SID", "Serial#", "Status", "Usuário Banco", "Usuário SO", "Programa", "Duração Sessão", "Duração Query", "Paralelo"])
        self.session_tree.setSortingEnabled(True); self.session_tree.header().setSortIndicatorShown(True); self.session_tree.header().sectionClicked.connect(self.sort_by_column); self.session_tree.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        self.kill_button = QPushButton("Encerrar Sessão Selecionada (Kill)"); self.kill_button.setEnabled(False)
        left_panel_layout.addWidget(filter_group); left_panel_layout.addWidget(self.refresh_button); left_panel_layout.addWidget(self.session_tree); left_panel_layout.addWidget(self.kill_button)
        
        right_panel_widget = QWidget(); right_panel_layout = QVBoxLayout(right_panel_widget)
        options_layout = QHBoxLayout()
        plan_options_group = QGroupBox("Opções de Formatação do Plano"); plan_options_layout = QHBoxLayout(plan_options_group)
        self.check_predicate = QCheckBox("Predicados"); self.check_predicate.setChecked(True)
        self.check_parallel = QCheckBox("Paralelismo"); self.check_parallel.setChecked(True)
        self.check_notes = QCheckBox("Notas"); self.check_notes.setChecked(True)
        plan_options_layout.addWidget(self.check_predicate); plan_options_layout.addWidget(self.check_parallel); plan_options_layout.addWidget(self.check_notes); plan_options_layout.addStretch()
        
        self.single_refresh_button = QPushButton(""); self.single_refresh_button.setIcon(self.style().standardIcon(getattr(QStyle.StandardPixmap, "SP_BrowserReload"))); self.single_refresh_button.setToolTip("Atualizar detalhes da sessão selecionada")
        self.last_updated_label = QLabel(""); self.last_updated_label.setStyleSheet("color: gray;")
        options_layout.addWidget(plan_options_group, 1); options_layout.addWidget(self.last_updated_label); options_layout.addWidget(self.single_refresh_button)

        self.details_tabs = QTabWidget()
        self.sql_text_edit = QTextEdit(readOnly=True); self.sql_text_edit.setStyleSheet("QTextEdit { background-color: #2B2B2B; color: #F8F8F2; border: 1px solid #444; font-family: 'Consolas', 'Courier New', monospace; }")
        self.sql_highlighter = SqlHighlighter(self.sql_text_edit.document()); self.details_tabs.addTab(self.sql_text_edit, "SQL")
        self.plan_text_edit = ExecutionPlanViewer(self); self.plan_highlighter = PlanHighlighter(self.plan_text_edit.document()); self.details_tabs.addTab(self.plan_text_edit, "Plano de Execução")
        
        right_panel_layout.addLayout(options_layout); right_panel_layout.addWidget(self.details_tabs)
        main_splitter.addWidget(left_panel_widget); main_splitter.addWidget(right_panel_widget); main_splitter.setSizes([750, 450])
        
        self.refresh_timer = QTimer(self); self.refresh_timer.timeout.connect(self.on_refresh)
        self.auto_refresh_check.toggled.connect(self.on_auto_refresh_toggled)
        self.refresh_interval_spinbox.valueChanged.connect(self.on_auto_refresh_toggled)
        self.refresh_button.clicked.connect(self.on_refresh); self.session_tree.currentItemChanged.connect(self.on_session_selected)
        self.kill_button.clicked.connect(self.on_kill_session); self.single_refresh_button.clicked.connect(self.on_refresh_single_session)
        self.filter_input.textChanged.connect(self.apply_filter); self.status_filter_combo.currentTextChanged.connect(self.apply_filter)
        self.check_predicate.stateChanged.connect(self.refetch_execution_plan); self.check_parallel.stateChanged.connect(self.refetch_execution_plan); self.check_notes.stateChanged.connect(self.refetch_execution_plan)

    def on_auto_refresh_toggled(self):
        if self.auto_refresh_check.isChecked():
            interval_ms = self.refresh_interval_spinbox.value() * 1000
            self.refresh_timer.start(interval_ms)
            self.refresh_interval_spinbox.setEnabled(False)
        else:
            self.refresh_timer.stop()
            self.refresh_interval_spinbox.setEnabled(True)

    def on_refresh(self):
        if self.session_worker and self.session_worker.isRunning(): return
        self.refresh_button.setEnabled(False); self.refresh_button.setText("Atualizando...")
        self.stored_state = {'filter_text': self.filter_input.text(), 'status_filter': self.status_filter_combo.currentText(), 'selected_sid': None, 'selected_serial': None}
        current_item = self.session_tree.currentItem()
        if current_item and current_item.data(0, Qt.ItemDataRole.UserRole):
            session_data = current_item.data(0, Qt.ItemDataRole.UserRole)
            self.stored_state['selected_sid'] = session_data['sid']
            self.stored_state['selected_serial'] = session_data['serial#']
        self.session_worker = SessionWorker(); self.session_worker.finished.connect(self.on_refresh_finished); self.session_worker.error.connect(self.on_refresh_error); self.session_worker.start()

    def on_refresh_error(self, error_message):
        self.refresh_button.setEnabled(True); self.refresh_button.setText("Atualizar Sessões")
        QMessageBox.critical(self, "Erro ao Buscar Sessões", error_message)

    def on_refresh_finished(self, data):
        self.all_sessions_data = data; self.populate_tree(data); self.populate_status_filter(data)
        self.filter_input.setText(self.stored_state['filter_text'])
        self.status_filter_combo.setCurrentText(self.stored_state['status_filter'])
        self.apply_filter()
        if self.stored_state['selected_sid']: self.find_and_select_item(self.stored_state['selected_sid'], self.stored_state['selected_serial'])
        self.refresh_button.setEnabled(True); self.refresh_button.setText("Atualizar Sessões")

    def find_and_select_item(self, sid_to_find, serial_to_find):
        for i in range(self.session_tree.topLevelItemCount()):
            host_item = self.session_tree.topLevelItem(i)
            for j in range(host_item.childCount()):
                session_item = host_item.child(j)
                session_data = session_item.data(0, Qt.ItemDataRole.UserRole)
                if session_data and session_data['sid'] == sid_to_find and session_data['serial#'] == serial_to_find:
                    self.session_tree.setCurrentItem(session_item)
                    return

    def on_refresh_single_session(self):
        current_item = self.session_tree.currentItem()
        if not current_item or not current_item.data(0, Qt.ItemDataRole.UserRole): return
        session_data = current_item.data(0, Qt.ItemDataRole.UserRole)
        self.single_session_worker = SingleSessionWorker(session_data)
        self.single_session_worker.finished.connect(lambda new_data: self.on_single_session_refreshed(current_item, new_data))
        self.single_session_worker.error.connect(self.on_worker_error)
        self.single_session_worker.start()

    def on_single_session_refreshed(self, item_to_update, new_data):
        if not new_data: item_to_update.setText(0, f"{item_to_update.text(0)} (Encerrada)"); return
        item_to_update.setData(0, Qt.ItemDataRole.UserRole, new_data)
        s_dur_str, s_dur_sec = self._format_duration(new_data.get('logon_time')); q_dur_str, q_dur_sec = "", 0
        status = new_data.get('status'); q_start_time = new_data.get('sql_exec_start'); p_degree = new_data.get('parallel_degree')
        if status == 'ACTIVE' and q_start_time: q_dur_str, q_dur_sec = self._format_duration(q_start_time)
        item_to_update.setText(2, status); item_to_update.setText(6, s_dur_str); item_to_update.setText(7, q_dur_str); item_to_update.setText(8, str(p_degree or ''))
        item_to_update.setData(6, Qt.ItemDataRole.UserRole, s_dur_sec); item_to_update.setData(7, Qt.ItemDataRole.UserRole, q_dur_sec)
        self.on_session_selected(item_to_update, None)
        self.last_updated_label.setText(f"Atualizado: {datetime.now().strftime('%H:%M:%S')}")
        self.sort_by_column(self.session_tree.sortColumn())

    def sort_by_column(self, column_index):
        order = self.session_tree.header().sortIndicatorOrder(); self.session_tree.setSortingEnabled(False)
        for i in range(self.session_tree.topLevelItemCount()): self.session_tree.topLevelItem(i).sortChildren(column_index, order)
        self.session_tree.setSortingEnabled(True)

    def _format_duration(self, start_time):
        if not start_time: return "", 0
        duration = datetime.now() - start_time; total_seconds = int(duration.total_seconds())
        days, rem = divmod(total_seconds, 86400); hours, rem = divmod(rem, 3600); minutes, seconds = divmod(rem, 60)
        return (f"{days}d {hours:02}:{minutes:02}:{seconds:02}" if days > 0 else f"{hours:02}:{minutes:02}:{seconds:02}"), total_seconds

    def populate_status_filter(self, data):
        self.status_filter_combo.blockSignals(True); current_selection = self.status_filter_combo.currentText(); self.status_filter_combo.clear()
        if not data: self.status_filter_combo.blockSignals(False); return
        statuses = sorted(list(set(s.get('status', 'N/A') for s in data))); self.status_filter_combo.addItem("Todos"); self.status_filter_combo.addItems(statuses)
        index = self.status_filter_combo.findText(current_selection)
        if index != -1: self.status_filter_combo.setCurrentIndex(index)
        self.status_filter_combo.blockSignals(False)

    def populate_tree(self, data):
        self.session_tree.clear(); sessions_by_machine = {}
        for session in data:
            machine_name = session.get('machine', 'N/A')
            if machine_name not in sessions_by_machine: sessions_by_machine[machine_name] = []
            sessions_by_machine[machine_name].append(session)
        for machine_name, sessions in sorted(sessions_by_machine.items()):
            host_item = SortableTreeWidgetItem(self.session_tree, [f"{machine_name} ({len(sessions)} sessões)"]); host_item.setFont(0, QFont("Arial", 9, QFont.Weight.Bold))
            for session in sessions:
                s_dur_str, s_dur_sec = self._format_duration(session.get('logon_time')); q_dur_str, q_dur_sec = "", 0
                status = session.get('status'); q_start_time = session.get('sql_exec_start'); p_degree = session.get('parallel_degree')
                if status == 'ACTIVE' and q_start_time: q_dur_str, q_dur_sec = self._format_duration(q_start_time)
                session_item = SortableTreeWidgetItem(host_item, [str(session.get('sid')), str(session.get('serial#')), status, session.get('username'), session.get('osuser'), session.get('program'), s_dur_str, q_dur_str, str(p_degree or '')])
                session_item.setData(6, Qt.ItemDataRole.UserRole, s_dur_sec); session_item.setData(7, Qt.ItemDataRole.UserRole, q_dur_sec); session_item.setData(0, Qt.ItemDataRole.UserRole, session)
                highlight_applied = False
                if status == 'ACTIVE' and q_start_time and q_dur_sec > self.LONG_QUERY_THRESHOLD_SECONDS:
                    for i in range(session_item.columnCount()): session_item.setBackground(i, self.HIGHLIGHT_LONG_QUERY_COLOR)
                    highlight_applied = True
                if not highlight_applied and p_degree and p_degree > self.HIGH_PARALLEL_THRESHOLD:
                    for i in range(session_item.columnCount()): session_item.setBackground(i, self.HIGHLIGHT_PARALLEL_COLOR)
        self.session_tree.collapseAll()
        for i in range(self.session_tree.columnCount()): self.session_tree.resizeColumnToContents(i)
        self.sort_by_column(self.session_tree.sortColumn())

    def on_session_selected(self, current_item, previous_item):
        self.sql_text_edit.clear(); self.plan_text_edit.clear()
        if not current_item or not current_item.data(0, Qt.ItemDataRole.UserRole): self.kill_button.setEnabled(False); return
        session_data = current_item.data(0, Qt.ItemDataRole.UserRole)
        if session_data:
            self.kill_button.setEnabled(True)
            self.sql_text_edit.setText("-- Carregando SQL...")
            self.sql_worker = SqlTextWorker(session_data); self.sql_worker.finished.connect(self.on_sql_text_finished); self.sql_worker.error.connect(self.on_worker_error); self.sql_worker.start()
            self.refetch_execution_plan()
        else:
            self.kill_button.setEnabled(False)

    def refetch_execution_plan(self):
        current_item = self.session_tree.currentItem()
        if not current_item or not current_item.data(0, Qt.ItemDataRole.UserRole): return
        if self.plan_worker and self.plan_worker.isRunning(): self.plan_worker.terminate()
        session_data = current_item.data(0, Qt.ItemDataRole.UserRole)
        format_parts = ['TYPICAL']
        if self.check_predicate.isChecked(): format_parts.append('+PREDICATE')
        if self.check_parallel.isChecked(): format_parts.append('+PARALLEL')
        if self.check_notes.isChecked(): format_parts.append('+NOTE')
        format_string = ' '.join(format_parts)
        self.plan_text_edit.setText(f"-- Carregando Plano de Execução (Formato: {format_string})...")
        self.plan_worker = PlanWorker(session_data, plan_format=format_string)
        self.plan_worker.finished.connect(self.on_plan_finished)
        self.plan_worker.error.connect(self.on_worker_error)
        self.plan_worker.start()

    def on_sql_text_finished(self, sql_text):
        self.sql_text_edit.setText(format_sql(sql_text) if sql_text else "-- Nenhum SQL ativo ou recente para esta sessão --")
    def on_plan_finished(self, plan_text):
        self.plan_text_edit.setText(plan_text)
    def on_worker_error(self, error_message):
        QMessageBox.critical(self, "Erro em Operação de Fundo", error_message)
    def export_plan_to_xml(self):
        current_item = self.session_tree.currentItem()
        if not current_item or not current_item.data(0, Qt.ItemDataRole.UserRole): return
        session_data = current_item.data(0, Qt.ItemDataRole.UserRole)
        sql_id = session_data.get('sql_id') or session_data.get('prev_sql_id')
        if not sql_id: QMessageBox.warning(self, "Ação Inválida", "Não há SQL ID associado a esta sessão para exportar o plano."); return
        default_filename = f"plan_{sql_id}_{session_data.get('sid')}.xml"
        filePath, _ = QFileDialog.getSaveFileName(self, "Salvar Plano de Execução", default_filename, "XML Files (*.xml);;All Files (*)")
        if not filePath: return
        self.export_worker = PlanWorker(session_data, plan_format='XML'); self.export_worker.finished.connect(lambda xml_data: self.save_exported_plan(filePath, xml_data)); self.export_worker.error.connect(self.on_worker_error); self.export_worker.start()

    def save_exported_plan(self, file_path, xml_data):
        try:
            with open(file_path, 'w', encoding='utf-8') as f: f.write(xml_data)
            QMessageBox.information(self, "Sucesso", f"Plano de execução exportado para:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Salvar", f"Não foi possível salvar o arquivo:\n{e}")

    def apply_filter(self):
        filter_text = self.filter_input.text().strip().lower(); status_filter = self.status_filter_combo.currentText()
        for i in range(self.session_tree.topLevelItemCount()):
            host_item = self.session_tree.topLevelItem(i); host_is_visible = False
            for j in range(host_item.childCount()):
                session_item = host_item.child(j); session_data = session_item.data(0, Qt.ItemDataRole.UserRole)
                status_match = (status_filter == "Todos" or session_data.get('status') == status_filter)
                full_text_to_search = "".join(str(v).lower() for k, v in session_data.items() if k not in ['sql_fulltext', 'sql_address', 'sql_hash_value', 'prev_sql_address', 'prev_hash_value'])
                text_match = (filter_text in full_text_to_search)
                if status_match and text_match: session_item.setHidden(False); host_is_visible = True
                else: session_item.setHidden(True)
            host_item.setHidden(not host_is_visible)

    def on_kill_session(self):
        selected_item = self.session_tree.currentItem()
        if not selected_item or not selected_item.data(0, Qt.ItemDataRole.UserRole): QMessageBox.warning(self, "Ação Inválida", "Por favor, selecione uma sessão válida para encerrar."); return
        session_data = selected_item.data(0, Qt.ItemDataRole.UserRole); sid = session_data.get('sid'); serial = session_data.get('serial#')
        reply = QMessageBox.question(self, 'Confirmação', f"Esta ação é irreversível e irá encerrar a sessão abaixo:\n\nSID: {sid}\nSERIAL#: {serial}\nUsuário: {session_data.get('username')}\nHost: {session_data.get('machine')}\n\nDeseja continuar?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        try:
            result_message = db.kill_session(sid, serial); QMessageBox.information(self, "Sucesso", result_message); self.on_refresh()
        except Exception as e: QMessageBox.critical(self, "Erro ao Encerrar Sessão", str(e))