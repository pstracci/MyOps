# C:\Meus Projetos\fixer\modules\siebel\siebel_ui.py

import sys
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QMessageBox, QMainWindow, QLineEdit, QLabel, QGroupBox, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QTextEdit, QHeaderView, QComboBox, QSplitter)
from PyQt6.QtGui import QFont, QAction, QTextCharFormat, QColor, QSyntaxHighlighter
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRegularExpression
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

class SortableTreeWidgetItem(QTreeWidgetItem):
    """Subclasse de QTreeWidgetItem para permitir ordenação numérica e por data/hora de forma segura."""
    def __lt__(self, other):
        column = self.treeWidget().sortColumn()

        # Colunas de duração: Trata valores nulos (None) como -1 para evitar erros
        duration_columns = [6, 7]
        if column in duration_columns:
            self_data = self.data(column, Qt.ItemDataRole.UserRole)
            other_data = other.data(column, Qt.ItemDataRole.UserRole)
            
            # Converte None para -1 para que a comparação numérica sempre funcione
            val_self = self_data if self_data is not None else -1
            val_other = other_data if other_data is not None else -1
            
            return val_self < val_other

        # Colunas numéricas: Trata texto vazio como -1
        numeric_columns = [0, 1, 8] # SID, Serial#, Paralelo
        if column in numeric_columns:
            try:
                # Se o texto for vazio, trata como -1 para não dar erro
                val_self = float(self.text(column)) if self.text(column) else -1
                val_other = float(other.text(column)) if other.text(column) else -1
                return val_self < val_other
            except (ValueError, TypeError):
                # Se ainda assim não for um número, compara como texto
                return self.text(column).lower() < other.text(column).lower()

        # Ordenação padrão como texto para as outras colunas
        return self.text(column).lower() < other.text(column).lower()

class SessionWorker(QThread):
    finished = pyqtSignal(object); error = pyqtSignal(str)
    def run(self):
        try: self.finished.emit(db.get_active_sessions())
        except Exception as e: self.error.emit(str(e))

class SqlTextWorker(QThread):
    finished = pyqtSignal(str); error = pyqtSignal(str)
    def __init__(self, inst_id, sql_address, sql_hash_value, prev_sql_address, prev_hash_value):
        super().__init__()
        self.inst_id, self.sql_address, self.sql_hash_value, self.prev_sql_address, self.prev_hash_value = inst_id, sql_address, sql_hash_value, prev_sql_address, prev_hash_value
    def run(self):
        try: self.finished.emit(db.get_sql_text(self.inst_id, self.sql_address, self.sql_hash_value, self.prev_sql_address, self.prev_hash_value))
        except Exception as e: self.error.emit(str(e))

class SiebelSessionManagerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.LONG_QUERY_THRESHOLD_SECONDS = 60; self.HIGH_PARALLEL_THRESHOLD = 4
        self.HIGHLIGHT_LONG_QUERY_COLOR = QColor(255, 220, 220); self.HIGHLIGHT_PARALLEL_COLOR = QColor(255, 250, 205)
        self.session_worker = None; self.sql_worker = None; self.all_sessions_data = []
        main_splitter = QSplitter(Qt.Orientation.Horizontal); self.setLayout(QVBoxLayout()); self.layout().addWidget(main_splitter)
        left_panel_widget = QWidget(); left_panel_layout = QVBoxLayout(left_panel_widget)
        filter_group = QGroupBox("Filtros"); filter_controls_layout = QHBoxLayout()
        self.status_filter_combo = QComboBox(); self.filter_input = QLineEdit(placeholderText="Filtre por qualquer campo...")
        filter_controls_layout.addWidget(QLabel("Status:")); filter_controls_layout.addWidget(self.status_filter_combo); filter_controls_layout.addWidget(self.filter_input, 1); filter_group.setLayout(filter_controls_layout)
        self.session_tree = QTreeWidget(); self.session_tree.setColumnCount(9); self.session_tree.setHeaderLabels(["SID", "Serial#", "Status", "Usuário Banco", "Usuário SO", "Programa", "Duração Sessão", "Duração Query", "Paralelo"])
        self.session_tree.setSortingEnabled(True); self.session_tree.header().setSortIndicatorShown(True); self.session_tree.header().sectionClicked.connect(self.sort_by_column); self.session_tree.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        self.kill_button = QPushButton("Encerrar Sessão Selecionada (Kill)"); self.kill_button.setEnabled(False)
        left_panel_layout.addWidget(filter_group); self.refresh_button = QPushButton("Atualizar Sessões"); left_panel_layout.addWidget(self.refresh_button)
        left_panel_layout.addWidget(self.session_tree); left_panel_layout.addWidget(self.kill_button)
        right_panel_widget = QWidget(); right_panel_layout = QVBoxLayout(right_panel_widget)
        sql_group = QGroupBox("Texto SQL da Sessão Selecionada"); sql_layout = QVBoxLayout()
        self.sql_text_edit = QTextEdit(readOnly=True); self.sql_text_edit.setStyleSheet("QTextEdit { background-color: #2B2B2B; color: #F8F8F2; border: 1px solid #444; font-family: 'Courier New', Courier, monospace; }")
        self.sql_highlighter = SqlHighlighter(self.sql_text_edit.document())
        sql_layout.addWidget(self.sql_text_edit); sql_group.setLayout(sql_layout); right_panel_layout.addWidget(sql_group)
        main_splitter.addWidget(left_panel_widget); main_splitter.addWidget(right_panel_widget); main_splitter.setSizes([750, 450])
        self.refresh_button.clicked.connect(self.on_refresh); self.filter_input.textChanged.connect(self.apply_filter)
        self.status_filter_combo.currentTextChanged.connect(self.apply_filter); self.session_tree.currentItemChanged.connect(self.on_session_selected)
        self.kill_button.clicked.connect(self.on_kill_session)
    def sort_by_column(self, column_index):
        order = self.session_tree.header().sortIndicatorOrder(); self.session_tree.setSortingEnabled(False)
        for i in range(self.session_tree.topLevelItemCount()): self.session_tree.topLevelItem(i).sortChildren(column_index, order)
        self.session_tree.setSortingEnabled(True)
    def _format_duration(self, start_time):
        if not start_time: return "", 0
        duration = datetime.now() - start_time; total_seconds = int(duration.total_seconds())
        days, rem = divmod(total_seconds, 86400); hours, rem = divmod(rem, 3600); minutes, seconds = divmod(rem, 60)
        return (f"{days}d {hours:02}:{minutes:02}:{seconds:02}" if days > 0 else f"{hours:02}:{minutes:02}:{seconds:02}"), total_seconds
    def on_refresh(self):
        self.refresh_button.setEnabled(False); self.refresh_button.setText("Atualizando...")
        self.session_worker = SessionWorker(); self.session_worker.finished.connect(self.on_refresh_finished); self.session_worker.error.connect(self.on_refresh_error); self.session_worker.start()
    def on_refresh_error(self, error_message): self.refresh_button.setEnabled(True); self.refresh_button.setText("Atualizar Sessões"); QMessageBox.critical(self, "Erro ao Buscar Sessões", error_message)
    def on_refresh_finished(self, data): self.all_sessions_data = data; self.populate_tree(data); self.populate_status_filter(data); self.refresh_button.setEnabled(True); self.refresh_button.setText("Atualizar Sessões")
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
        self.sql_text_edit.clear()
        if self.sql_worker and self.sql_worker.isRunning(): self.sql_worker.terminate()
        if not current_item or not current_item.data(0, Qt.ItemDataRole.UserRole): self.kill_button.setEnabled(False); return
        session_data = current_item.data(0, Qt.ItemDataRole.UserRole)
        if session_data:
            self.kill_button.setEnabled(True); self.sql_text_edit.setText("-- Carregando SQL...")
            inst_id = session_data.get('inst_id'); sql_address = session_data.get('sql_address'); sql_hash_value = session_data.get('sql_hash_value')
            prev_sql_address = session_data.get('prev_sql_address'); prev_hash_value = session_data.get('prev_hash_value')
            self.sql_worker = SqlTextWorker(inst_id, sql_address, sql_hash_value, prev_sql_address, prev_hash_value)
            self.sql_worker.finished.connect(self.on_sql_text_finished); self.sql_worker.error.connect(self.on_sql_text_error); self.sql_worker.start()
        else: self.kill_button.setEnabled(False)
    def on_sql_text_finished(self, sql_text):
        if sql_text: self.sql_text_edit.setText(format_sql(sql_text))
        else: self.sql_text_edit.setText("-- Nenhum SQL ativo ou recente para esta sessão --")
    def on_sql_text_error(self, error_message): self.sql_text_edit.setText(f"-- Erro ao buscar SQL --\n\n{error_message}")
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