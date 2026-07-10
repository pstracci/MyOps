# C:\Meus Projetos\fixer\modules\object_viewer\object_viewer_ui.py

import sys
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QMessageBox, QMainWindow,
    QLineEdit, QLabel, QGroupBox, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QSplitter, QComboBox, QCheckBox
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

class SortableTreeWidgetItem(QTreeWidgetItem):
    """Item customizado para ordenação correta de colunas numéricas."""
    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        
        # Coluna 4 = Tamanho (GB) - ordenação numérica
        if column == 4:
            try:
                val_self = self.data(column, Qt.ItemDataRole.UserRole)
                val_other = other.data(column, Qt.ItemDataRole.UserRole)
                if val_self is None:
                    val_self = 0
                if val_other is None:
                    val_other = 0
                return float(val_self) < float(val_other)
            except (ValueError, TypeError):
                return self.text(column) < other.text(column)
        
        # Outras colunas - ordenação alfabética padrão
        return self.text(column).lower() < other.text(column).lower()

class ObjectSearchWorker(QThread):
    finished = pyqtSignal(list); error = pyqtSignal(str)
    def __init__(self, object_name, object_types=None, db_key=None): 
        super().__init__()
        self.object_name = object_name
        self.object_types = object_types
        self.db_key = db_key
        self.is_cancelled = False
        
    def cancel(self):
        """Cancela a execução do worker."""
        self.is_cancelled = True
        
    def run(self):
        try: 
            if not self.is_cancelled:
                self.finished.emit(db.search_objects(self.object_name, self.object_types, self.db_key, lambda: self.is_cancelled))
        except Exception as e: 
            if not self.is_cancelled:
                self.error.emit(str(e))

class ObjectSourceWorker(QThread):
    finished = pyqtSignal(str); error = pyqtSignal(str)
    def __init__(self, db_key, owner, object_name, object_type): 
        super().__init__()
        self.db_key = db_key
        self.owner = owner
        self.object_name = object_name
        self.object_type = object_type
    def run(self):
        try: self.finished.emit(db.get_object_source(self.db_key, self.owner, self.object_name, self.object_type))
        except Exception as e: self.error.emit(str(e))

class RecompileWorker(QThread):
    finished = pyqtSignal(str); error = pyqtSignal(str)
    def __init__(self, db_key, owner, object_name, object_type): 
        super().__init__()
        self.db_key = db_key
        self.owner = owner
        self.object_name = object_name
        self.object_type = object_type
    def run(self):
        try: self.finished.emit(db.recompile_object(self.db_key, self.owner, self.object_name, self.object_type))
        except Exception as e: self.error.emit(str(e))

class DropObjectWorker(QThread):
    finished = pyqtSignal(str); error = pyqtSignal(str)
    def __init__(self, db_key, owner, object_name, object_type): 
        super().__init__()
        self.db_key = db_key
        self.owner = owner
        self.object_name = object_name
        self.object_type = object_type
    def run(self):
        try: self.finished.emit(db.drop_object(self.db_key, self.owner, self.object_name, self.object_type))
        except Exception as e: self.error.emit(str(e))

class ObjectViewerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setLayout(QVBoxLayout()); self.layout().addWidget(main_splitter)

        left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
        search_group = QGroupBox("Busca de Objetos"); search_layout = QVBoxLayout()
        
        # Linha de seleção de base
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("Base de Dados:"))
        self.db_combo = QComboBox()
        self.populate_db_combo()
        db_layout.addWidget(self.db_combo, 1)
        
        # Linha de busca
        search_input_layout = QHBoxLayout()
        self.search_input = QLineEdit(placeholderText="Ex: BAT509"); self.search_input.returnPressed.connect(self.on_search)
        self.search_button = QPushButton("Buscar"); self.search_button.clicked.connect(self.on_search)
        self.cancel_button = QPushButton("Cancelar"); self.cancel_button.clicked.connect(self.on_cancel_search)
        self.cancel_button.setEnabled(False)  # Inicialmente desabilitado
        self.cancel_button.setStyleSheet("QPushButton { background-color: #ff9800; color: white; font-weight: bold; }")
        search_input_layout.addWidget(QLabel("Nome:"))
        search_input_layout.addWidget(self.search_input, 1)
        search_input_layout.addWidget(self.search_button)
        search_input_layout.addWidget(self.cancel_button)
        
        # Filtros de tipo de objeto
        type_filter_label = QLabel("Tipos de Objeto:")
        type_filter_layout = QHBoxLayout()
        
        self.type_checkboxes = {}
        object_types = ['PACKAGE', 'PROCEDURE', 'FUNCTION', 'TABLE', 'VIEW', 'INDEX', 'TRIGGER', 'SEQUENCE', 'SYNONYM']
        for obj_type in object_types:
            checkbox = QCheckBox(obj_type)
            checkbox.setChecked(True)  # Todos marcados por padrão
            self.type_checkboxes[obj_type] = checkbox
            type_filter_layout.addWidget(checkbox)
        
        type_filter_layout.addStretch()
        
        search_layout.addLayout(db_layout)
        search_layout.addLayout(search_input_layout)
        search_layout.addWidget(type_filter_label)
        search_layout.addLayout(type_filter_layout)
        search_group.setLayout(search_layout)
        
        self.results_tree = QTreeWidget()
        # ALTERADO: Adiciona colunas de Tipo e Tamanho (GB)
        self.results_tree.setHeaderLabels(["Objeto", "Tipo", "Owner", "Status", "Tamanho (GB)", "Criado em", "Última Alteração"])
        self.results_tree.setSortingEnabled(True)  # Habilita ordenação clicável
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
        self.drop_button = QPushButton("Excluir Objeto"); self.drop_button.clicked.connect(self.on_drop_object)
        self.drop_button.setStyleSheet("QPushButton { background-color: #d32f2f; color: white; font-weight: bold; }")
        button_layout = QHBoxLayout(); button_layout.addStretch(); button_layout.addWidget(self.copy_button); button_layout.addWidget(self.recompile_button); button_layout.addWidget(self.drop_button)
        source_layout.addWidget(self.source_code_edit); source_layout.addLayout(button_layout)
        source_group.setLayout(source_layout)
        right_layout.addWidget(source_group)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([500, 700])

    def populate_db_combo(self):
        """Popula o ComboBox com as conexões de banco disponíveis."""
        try:
            connections = db.get_all_db_connections()
            for key, name in connections.items():
                self.db_combo.addItem(name, key)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível carregar as conexões do config.ini:\n{e}")

    def on_search(self):
        object_name = self.search_input.text().strip()
        if not object_name: QMessageBox.warning(self, "Busca Inválida", "Por favor, informe um nome de objeto para buscar."); return
        
        # Coleta os tipos selecionados
        selected_types = [obj_type for obj_type, checkbox in self.type_checkboxes.items() if checkbox.isChecked()]
        if not selected_types:
            QMessageBox.warning(self, "Filtro Inválido", "Por favor, selecione pelo menos um tipo de objeto.")
            return
        
        self.search_button.setEnabled(False); self.search_button.setText("Buscando...")
        self.cancel_button.setEnabled(True)
        self.results_tree.clear(); self.source_code_edit.clear()
        # Obtém a base selecionada
        selected_db_key = self.db_combo.currentData()
        
        self.worker = ObjectSearchWorker(object_name, selected_types, selected_db_key)
        self.worker.finished.connect(self.on_search_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()
        
    def on_cancel_search(self):
        """Cancela a busca atual."""
        if self.worker and hasattr(self.worker, 'cancel'):
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText("Cancelando...")
            self.search_button.setEnabled(True)
            self.search_button.setText("Buscar")
            QMessageBox.information(self, "Busca Cancelada", "A busca foi cancelada pelo usuário.")
        
    def on_search_finished(self, results):
        self.search_button.setEnabled(True); self.search_button.setText("Buscar")
        self.cancel_button.setEnabled(False); self.cancel_button.setText("Cancelar")
        
        if not results: QMessageBox.information(self, "Busca Concluída", "Nenhum objeto encontrado."); return
        
        results_by_db = {}; 
        for res in results:
            db_name = res['db_friendly_name']
            if db_name not in results_by_db: results_by_db[db_name] = []
            results_by_db[db_name].append(res)
        
        for db_name, objects in results_by_db.items():
            # Não mostra o agrupamento por base quando é apenas uma base
            if len(results_by_db) == 1:
                # Adiciona objetos diretamente à tree
                for obj in objects:
                    if obj.get('is_error'):
                        child_item = SortableTreeWidgetItem(self.results_tree, [obj['object_name']]); 
                        child_item.setForeground(0, QColor("red"))
                    else:
                        # Popula as colunas com datas formatadas, tipo e tamanho
                        created_str = obj.get('created', datetime.min).strftime('%Y-%m-%d %H:%M:%S')
                        last_ddl_str = obj.get('last_ddl_time', datetime.min).strftime('%Y-%m-%d %H:%M:%S')
                        size_gb = obj.get('size_gb', 0)
                        size_str = f"{size_gb:.4f}" if size_gb else "0.0000"
                        child_item = SortableTreeWidgetItem(self.results_tree, [obj['object_name'], obj['object_type'], obj['owner'], obj['status'], size_str, created_str, last_ddl_str])
                        # Armazena o tamanho numérico para ordenação correta
                        child_item.setData(4, Qt.ItemDataRole.UserRole, size_gb)
                        child_item.setData(0, Qt.ItemDataRole.UserRole, obj)
            else:
                # Comportamento antigo com agrupamento por base
                db_item = SortableTreeWidgetItem(self.results_tree, [f"{db_name} ({len(objects)} encontrados)"]); db_item.setFont(0, QFont("Arial", 9, QFont.Weight.Bold))
                for obj in objects:
                    if obj.get('is_error'):
                        child_item = SortableTreeWidgetItem(db_item, [obj['object_name']]); 
                        child_item.setForeground(0, QColor("red"))
                    else:
                        # Popula as colunas com datas formatadas, tipo e tamanho
                        created_str = obj.get('created', datetime.min).strftime('%Y-%m-%d %H:%M:%S')
                        last_ddl_str = obj.get('last_ddl_time', datetime.min).strftime('%Y-%m-%d %H:%M:%S')
                        size_gb = obj.get('size_gb', 0)
                        size_str = f"{size_gb:.4f}" if size_gb else "0.0000"
                        child_item = SortableTreeWidgetItem(db_item, [obj['object_name'], obj['object_type'], obj['owner'], obj['status'], size_str, created_str, last_ddl_str])
                        # Armazena o tamanho numérico para ordenação correta
                        child_item.setData(4, Qt.ItemDataRole.UserRole, size_gb)
                        child_item.setData(0, Qt.ItemDataRole.UserRole, obj)
        self.results_tree.expandAll()
        for i in range(self.results_tree.columnCount()): self.results_tree.resizeColumnToContents(i)

    def on_object_selected(self, current_item, previous_item):
        self.source_code_edit.clear()
        if not current_item or not current_item.data(0, Qt.ItemDataRole.UserRole): return
        
        obj_data = current_item.data(0, Qt.ItemDataRole.UserRole)
        obj_type = obj_data.get('object_type', 'UNKNOWN')
        self.source_code_edit.setText(f"-- Carregando {obj_type} {obj_data['owner']}.{obj_data['object_name']} de {obj_data['db_friendly_name']}...")
        self.worker = ObjectSourceWorker(obj_data['db_key'], obj_data['owner'], obj_data['object_name'], obj_type)
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
        obj_type = obj_data.get('object_type', 'UNKNOWN')
        
        # Verifica se o tipo suporta recompilação
        if obj_type not in ['PACKAGE', 'PROCEDURE', 'FUNCTION', 'TRIGGER', 'VIEW']:
            QMessageBox.warning(self, "Ação Não Suportada", f"Objetos do tipo '{obj_type}' não podem ser recompilados.")
            return
        
        reply = QMessageBox.question(self, 'Confirmação', f"Tem certeza que deseja recompilar o {obj_type} '{obj_data['owner']}.{obj_data['object_name']}' no banco de dados '{obj_data['db_friendly_name']}'?\n\nEsta ação usa o código-fonte que está no banco, não o texto editado na tela.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        
        self.recompile_button.setEnabled(False)
        self.worker = RecompileWorker(obj_data['db_key'], obj_data['owner'], obj_data['object_name'], obj_type)
        self.worker.finished.connect(self.on_recompile_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def on_recompile_finished(self, message):
        self.recompile_button.setEnabled(True)
        QMessageBox.information(self, "Resultado da Compilação", message)
        self.on_search()

    def on_drop_object(self):
        current_item = self.results_tree.currentItem()
        if not current_item or not current_item.data(0, Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, "Ação Inválida", "Por favor, selecione um objeto válido na lista para excluir.")
            return
        
        obj_data = current_item.data(0, Qt.ItemDataRole.UserRole)
        obj_type = obj_data.get('object_type', 'UNKNOWN')
        obj_name = obj_data['object_name']
        owner = obj_data['owner']
        db_name = obj_data['db_friendly_name']
        
        # PRIMEIRA CONFIRMAÇÃO
        first_reply = QMessageBox.warning(
            self, 
            '⚠️ ATENÇÃO - Confirmação de Exclusão (1/2)',
            f"Você está prestes a EXCLUIR PERMANENTEMENTE o seguinte objeto:\n\n"
            f"Tipo: {obj_type}\n"
            f"Nome: {owner}.{obj_name}\n"
            f"Banco: {db_name}\n\n"
            f"⚠️ ESTA AÇÃO NÃO PODE SER DESFEITA! ⚠️\n\n"
            f"Deseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if first_reply == QMessageBox.StandardButton.No:
            return
        
        # SEGUNDA CONFIRMAÇÃO (mais enfática)
        second_reply = QMessageBox.critical(
            self,
            '🛑 ÚLTIMA CONFIRMAÇÃO (2/2)',
            f"ÚLTIMA CHANCE PARA CANCELAR!\n\n"
            f"Você confirma a EXCLUSÃO DEFINITIVA de:\n"
            f"{obj_type}: {owner}.{obj_name}\n\n"
            f"Digite mentalmente 'SIM' e clique em Yes para prosseguir.\n"
            f"Clique em No para CANCELAR.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if second_reply == QMessageBox.StandardButton.No:
            QMessageBox.information(self, "Cancelado", "Operação de exclusão cancelada com sucesso.")
            return
        
        # Executa a exclusão
        self.drop_button.setEnabled(False)
        self.drop_button.setText("Excluindo...")
        self.worker = DropObjectWorker(obj_data['db_key'], owner, obj_name, obj_type)
        self.worker.finished.connect(self.on_drop_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()
    
    def on_drop_finished(self, message):
        self.drop_button.setEnabled(True)
        self.drop_button.setText("Excluir Objeto")
        
        if "sucesso" in message.lower():
            QMessageBox.information(self, "Exclusão Concluída", message)
            # Atualiza a lista
            self.on_search()
        else:
            QMessageBox.critical(self, "Erro na Exclusão", message)

    def on_worker_error(self, error_message):
        QMessageBox.critical(self, "Erro", error_message)
        self.search_button.setEnabled(True); self.search_button.setText("Buscar")
        self.cancel_button.setEnabled(False); self.cancel_button.setText("Cancelar")
        self.recompile_button.setEnabled(True)
        self.drop_button.setEnabled(True); self.drop_button.setText("Excluir Objeto")

# ALTERADO: A classe da Janela agora é mais simples
class ObjectViewerToolWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visualizador de Objetos de Banco")
        self.setGeometry(100, 100, 1200, 800)
        self.main_widget = ObjectViewerWidget()
        self.setCentralWidget(self.main_widget)