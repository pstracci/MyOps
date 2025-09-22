# C:\Meus Projetos\fixer\modules\object_viewer\object_viewer_ui.py

import sys
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QMessageBox, QMainWindow,
    QLineEdit, QLabel, QGroupBox, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QSplitter
)
from PyQt6.QtGui import QFont, QAction, QTextCharFormat, QColor, QSyntaxHighlighter
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRegularExpression

from modules.object_viewer import object_viewer_logic as db
from modules.common.widgets import SettingsDialog

# ALTERADO: Novas cores para o tema escuro
class SqlHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlightingRules = []
        
        keyword_format = QTextCharFormat(); keyword_format.setForeground(QColor("#FC5683")) # Rosa/Vermelho para palavras-chave
        keywords = ["SELECT", "FROM", "WHERE", "AND", "OR", "GROUP BY", "ORDER BY", "HAVING", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "TABLE", "INDEX", "VIEW", "AS", "SET", "VALUES", "JOIN", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "OUTER JOIN", "ON", "CASE", "WHEN", "THEN", "ELSE", "END", "IN", "NOT IN", "EXISTS", "NOT EXISTS", "DISTINCT", "NULL", "PACKAGE", "BODY", "IS", "BEGIN", "PROCEDURE", "FUNCTION", "RETURN", "DECLARE", "TYPE", "RECORD", "CURSOR", "LOOP", "END LOOP", "IF", "ELSIF", "EXCEPTION", "WHEN", "OTHERS", "THEN"]
        self.add_rule(keywords, keyword_format)
        
        type_format = QTextCharFormat(); type_format.setForeground(QColor("#66D9EF")) # Ciano para tipos e funções
        types = ["VARCHAR2", "NUMBER", "DATE", "TIMESTAMP", "CLOB", "BLOB", "COUNT", "SUM", "AVG", "MAX", "MIN", "TO_CHAR", "TO_DATE", "NVL", "DECODE", "SYSDATE", "ROWNUM"]
        self.add_rule(types, type_format)
        
        string_format = QTextCharFormat(); string_format.setForeground(QColor("#E6DB74")) # Amarelo para strings
        self.highlightingRules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format))
        
        number_format = QTextCharFormat(); number_format.setForeground(QColor("#AE81FF")) # Roxo para números
        self.highlightingRules.append((QRegularExpression(r"\b\d+(\.\d+)?\b"), number_format))
        
        comment_format = QTextCharFormat(); comment_format.setForeground(QColor("#75715E")) # Cinza para comentários
        self.highlightingRules.append((QRegularExpression(r"--[^\n]*"), comment_format))
        self.comment_format = comment_format
        self.multiLineCommentStartExpression = QRegularExpression(r"/\*"); self.multiLineCommentEndExpression = QRegularExpression(r"\*/")
        
    def add_rule(self, patterns, format_obj):
        for pattern in patterns:
            regex = QRegularExpression(r"\b" + pattern + r"\b", QRegularExpression.PatternOption.CaseInsensitiveOption)
            self.highlightingRules.append((regex, format_obj))
            
    def highlightBlock(self, text):
        for pattern, format_obj in self.highlightingRules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format_obj)
        self.setCurrentBlockState(0)
        startIndex = 0
        if self.previousBlockState() != 1:
            match = self.multiLineCommentStartExpression.match(text); startIndex = match.capturedStart()
        while startIndex >= 0:
            match = self.multiLineCommentEndExpression.match(text, startIndex)
            endIndex = match.capturedStart()
            commentLength = 0
            if endIndex == -1: self.setCurrentBlockState(1); commentLength = len(text) - startIndex
            else: commentLength = endIndex - startIndex + match.capturedLength()
            self.setFormat(startIndex, commentLength, self.comment_format)
            match = self.multiLineCommentStartExpression.match(text, startIndex + commentLength); startIndex = match.capturedStart()

class ObjectSearchWorker(QThread):
    finished = pyqtSignal(list); error = pyqtSignal(str)
    def __init__(self, object_name): super().__init__(); self.object_name = object_name
    def run(self):
        try: self.finished.emit(db.search_objects(self.object_name))
        except Exception as e: self.error.emit(str(e))

class ObjectSourceWorker(QThread):
    finished = pyqtSignal(str); error = pyqtSignal(str)
    def __init__(self, db_key, owner, object_name): super().__init__(); self.db_key = db_key; self.owner = owner; self.object_name = object_name
    def run(self):
        try: self.finished.emit(db.get_object_source(self.db_key, self.owner, self.object_name))
        except Exception as e: self.error.emit(str(e))

class RecompileWorker(QThread):
    finished = pyqtSignal(str); error = pyqtSignal(str)
    def __init__(self, db_key, owner, object_name): super().__init__(); self.db_key = db_key; self.owner = owner; self.object_name = object_name
    def run(self):
        try: self.finished.emit(db.recompile_object(self.db_key, self.owner, self.object_name))
        except Exception as e: self.error.emit(str(e))

class ObjectViewerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setLayout(QVBoxLayout()); self.layout().addWidget(main_splitter)

        left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
        search_group = QGroupBox("Busca de Objetos"); search_layout = QHBoxLayout()
        self.search_input = QLineEdit(placeholderText="Ex: BAT509"); self.search_input.returnPressed.connect(self.on_search)
        self.search_button = QPushButton("Buscar"); self.search_button.clicked.connect(self.on_search)
        search_layout.addWidget(self.search_input, 1); search_layout.addWidget(self.search_button)
        search_group.setLayout(search_layout)
        
        self.results_tree = QTreeWidget()
        # ALTERADO: Adiciona cabeçalhos para as novas colunas
        self.results_tree.setHeaderLabels(["Objeto", "Owner", "Status", "Criado em", "Última Alteração"])
        self.results_tree.currentItemChanged.connect(self.on_object_selected)
        left_layout.addWidget(search_group); left_layout.addWidget(self.results_tree)
        main_splitter.addWidget(left_panel)
        
        right_panel = QWidget(); right_layout = QVBoxLayout(right_panel)
        source_group = QGroupBox("Código-Fonte do Objeto Selecionado"); source_layout = QVBoxLayout()
        self.source_code_edit = QTextEdit()
        
        # NOVO: Aplica o tema escuro no editor de código
        self.source_code_edit.setStyleSheet("""
            QTextEdit {
                background-color: #2B2B2B;
                color: #F8F8F2;
                border: 1px solid #444;
                font-family: 'Courier New', Courier, monospace;
            }
        """)
        self.highlighter = SqlHighlighter(self.source_code_edit.document())
        self.copy_button = QPushButton("Copiar Código"); self.copy_button.clicked.connect(self.on_copy)
        self.recompile_button = QPushButton("Recompilar Objeto"); self.recompile_button.clicked.connect(self.on_recompile)
        button_layout = QHBoxLayout(); button_layout.addStretch(); button_layout.addWidget(self.copy_button); button_layout.addWidget(self.recompile_button)
        source_layout.addWidget(self.source_code_edit); source_layout.addLayout(button_layout)
        source_group.setLayout(source_layout)
        right_layout.addWidget(source_group)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([500, 700])

    def on_search(self):
        object_name = self.search_input.text().strip()
        if not object_name: QMessageBox.warning(self, "Busca Inválida", "Por favor, informe um nome de objeto para buscar."); return
        self.search_button.setEnabled(False); self.search_button.setText("Buscando...")
        self.results_tree.clear(); self.source_code_edit.clear()
        self.worker = ObjectSearchWorker(object_name)
        self.worker.finished.connect(self.on_search_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()
        
    def on_search_finished(self, results):
        self.search_button.setEnabled(True); self.search_button.setText("Buscar")
        if not results: QMessageBox.information(self, "Busca Concluída", "Nenhum objeto encontrado."); return
        
        results_by_db = {}; 
        for res in results:
            db_name = res['db_friendly_name']
            if db_name not in results_by_db: results_by_db[db_name] = []
            results_by_db[db_name].append(res)
        
        for db_name, objects in results_by_db.items():
            db_item = QTreeWidgetItem(self.results_tree, [f"{db_name} ({len(objects)} encontrados)"]); db_item.setFont(0, QFont("Arial", 9, QFont.Weight.Bold))
            for obj in objects:
                if obj.get('is_error'):
                    child_item = QTreeWidgetItem(db_item, [obj['object_name']]); 
                    child_item.setForeground(0, QColor("red"))
                else:
                    # ALTERADO: Popula as novas colunas com datas formatadas
                    created_str = obj.get('created', datetime.min).strftime('%Y-%m-%d %H:%M:%S')
                    last_ddl_str = obj.get('last_ddl_time', datetime.min).strftime('%Y-%m-%d %H:%M:%S')
                    child_item = QTreeWidgetItem(db_item, [obj['object_name'], obj['owner'], obj['status'], created_str, last_ddl_str])
                    child_item.setData(0, Qt.ItemDataRole.UserRole, obj)
        self.results_tree.expandAll()
        for i in range(self.results_tree.columnCount()): self.results_tree.resizeColumnToContents(i)

    def on_object_selected(self, current_item, previous_item):
        self.source_code_edit.clear()
        if not current_item or not current_item.data(0, Qt.ItemDataRole.UserRole): return
        
        obj_data = current_item.data(0, Qt.ItemDataRole.UserRole)
        self.source_code_edit.setText(f"-- Carregando código para {obj_data['owner']}.{obj_data['object_name']} de {obj_data['db_friendly_name']}...")
        self.worker = ObjectSourceWorker(obj_data['db_key'], obj_data['owner'], obj_data['object_name'])
        self.worker.finished.connect(self.source_code_edit.setText)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def on_copy(self):
        QApplication.clipboard().setText(self.source_code_edit.toPlainText())
        QMessageBox.information(self, "Sucesso", "Código copiado para a área de transferência!")

    def on_recompile(self):
        current_item = self.results_tree.currentItem()
        if not current_item or not current_item.data(0, Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, "Ação Inválida", "Por favor, selecione um objeto válido na lista para recompilar."); return
        
        obj_data = current_item.data(0, Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, 'Confirmação', f"Tem certeza que deseja recompilar o objeto '{obj_data['owner']}.{obj_data['object_name']}' no banco de dados '{obj_data['db_friendly_name']}'?\n\nEsta ação usa o código-fonte que está no banco, não o texto editado na tela.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        
        self.recompile_button.setEnabled(False)
        self.worker = RecompileWorker(obj_data['db_key'], obj_data['owner'], obj_data['object_name'])
        self.worker.finished.connect(self.on_recompile_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def on_recompile_finished(self, message):
        self.recompile_button.setEnabled(True)
        QMessageBox.information(self, "Resultado da Compilação", message)
        self.on_search()

    def on_worker_error(self, error_message):
        QMessageBox.critical(self, "Erro", error_message)
        self.search_button.setEnabled(True); self.search_button.setText("Buscar")
        self.recompile_button.setEnabled(True)

# ALTERADO: A classe da Janela agora é mais simples
class ObjectViewerToolWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visualizador de Objetos de Banco")
        self.setGeometry(100, 100, 1200, 800)
        self.main_widget = ObjectViewerWidget()
        self.setCentralWidget(self.main_widget)