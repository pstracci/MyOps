# C:\Meus Projetos\MyOps\modules\dashboard\todo_list_widget.py

import json
import os
from datetime import datetime

from PyQt6.QtCore import Qt, QDate, QSize
from PyQt6.QtGui import QFont, QColor, QAction, QMouseEvent, QIcon, QPixmap, QPainter, QPen
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                             QPushButton, QListWidget, QListWidgetItem, QMessageBox,
                             QDialog, QCalendarWidget, QMenu)

TODO_FILE = 'todo_tasks.json'

class TodoListQListWidget(QListWidget):
    def mousePressEvent(self, event: QMouseEvent):
        if not self.itemAt(event.pos()):
            self.clearSelection()
        super().mousePressEvent(event)

class TodoListWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.tasks = []
        # Ícones agora são gerados dinamicamente, então não são mais pré-carregados aqui.
        self._init_ui()
        self.load_tasks()

    def _create_check_icon(self, checked=False):
        pixmap = QPixmap(QSize(16, 16))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        
        # --- ALTERAÇÃO: Habilita o anti-aliasing para suavizar as linhas ---
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # --- ALTERAÇÃO: Detecta o tema e define as cores dinamicamente ---
        is_dark_theme = self.palette().window().color().lightness() < 128
        
        if is_dark_theme:
            border_color = QColor("#A0A0A0")  # Cinza claro para borda no tema escuro
            tick_color = QColor("white")     # "Tick" branco no tema escuro
        else:
            border_color = QColor("#909090")  # Cinza escuro para borda no tema claro
            tick_color = QColor("black")     # "Tick" preto no tema claro

        # Desenha a caixa com a cor da borda definida
        pen = QPen(border_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(1, 1, 13, 13) # Leve ajuste no tamanho para melhor aparência

        if checked:
            # Desenha o "tick" com a cor definida
            pen.setColor(tick_color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(4, 8, 7, 11)
            painter.drawLine(7, 11, 12, 4)

        painter.end()
        return QIcon(pixmap)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        add_task_layout = QHBoxLayout()
        self.task_input = QLineEdit(placeholderText="Digite uma nova tarefa...")
        self.add_button = QPushButton("Adicionar")
        add_task_layout.addWidget(self.task_input)
        add_task_layout.addWidget(self.add_button)

        self.task_list_widget = TodoListQListWidget()
        self.task_list_widget.setAlternatingRowColors(True)
        self.task_list_widget.setMouseTracking(True)
        self.task_list_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.task_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.task_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        action_buttons_layout = QHBoxLayout()
        self.remove_button = QPushButton("Remover Tarefa")
        self.clear_completed_button = QPushButton("Limpar Concluídas")
        action_buttons_layout.addStretch()
        action_buttons_layout.addWidget(self.remove_button)
        action_buttons_layout.addWidget(self.clear_completed_button)

        main_layout.addLayout(add_task_layout)
        main_layout.addWidget(self.task_list_widget)
        main_layout.addLayout(action_buttons_layout)

        self.add_button.clicked.connect(self.add_task)
        self.task_input.returnPressed.connect(self.add_task)
        self.remove_button.clicked.connect(self.remove_task)
        self.clear_completed_button.clicked.connect(self.clear_completed_tasks)
        self.task_list_widget.itemClicked.connect(self.on_item_clicked)
        self.task_list_widget.itemDoubleClicked.connect(self.edit_due_date)
        self.task_list_widget.customContextMenuRequested.connect(self.show_task_context_menu)
        self.task_list_widget.model().rowsMoved.connect(self.on_tasks_reordered)
        self.task_list_widget.currentItemChanged.connect(self.update_button_states)

    def populate_list(self):
        self.task_list_widget.blockSignals(True)
        current_row = self.task_list_widget.currentRow()
        self.task_list_widget.clear()

        if not self.tasks:
            empty_item = QListWidgetItem("Sua lista de tarefas está vazia!\nAdicione uma nova tarefa acima.")
            empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            font = empty_item.font()
            font.setItalic(True)
            empty_item.setFont(font)
            self.task_list_widget.addItem(empty_item)
        else:
            for index, task in enumerate(self.tasks):
                text = task.get("text", "Tarefa sem nome")
                due_date_str = task.get("due_date")
                display_text = text
                if due_date_str:
                    try:
                        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                        today = datetime.now().date()
                        if due_date < today and not task.get("completed"):
                            display_text += f" (Vencida: {due_date.strftime('%d/%m/%Y')})"
                        else:
                            display_text += f" (Vence: {due_date.strftime('%d/%m/%Y')})"
                    except ValueError:
                        pass

                item = QListWidgetItem(display_text)
                
                item.setData(Qt.ItemDataRole.UserRole, index)
                item.setToolTip(text)
                
                # --- ALTERAÇÃO: Gera o ícone dinamicamente para cada item ---
                is_completed = task.get("completed", False)
                item.setIcon(self._create_check_icon(checked=is_completed))

                font = item.font()
                font.setStrikeOut(is_completed)
                item.setFont(font)
                
                task_color = task.get("color")
                if task_color:
                    item.setBackground(QColor(task_color))
                    item.setForeground(QColor("#1E1E1E")) 
                
                if not is_completed and due_date_str:
                     if datetime.strptime(due_date_str, '%Y-%m-%d').date() < datetime.now().date():
                        item.setForeground(QColor('#FF6347'))

                self.task_list_widget.addItem(item)
        
        if current_row != -1 and current_row < self.task_list_widget.count():
            self.task_list_widget.setCurrentRow(current_row)

        self.task_list_widget.blockSignals(False)
        self.update_button_states()

    def on_item_clicked(self, item: QListWidgetItem):
        task_index = item.data(Qt.ItemDataRole.UserRole)
        if task_index is None:
            return
        
        current_state = self.tasks[task_index].get("completed", False)
        self.tasks[task_index]["completed"] = not current_state
        
        self.save_tasks()
        self.populate_list()

    def load_tasks(self):
        try:
            if os.path.exists(TODO_FILE):
                with open(TODO_FILE, 'r', encoding='utf-8') as f:
                    self.tasks = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            QMessageBox.warning(self, "Erro ao Carregar", f"Não foi possível carregar as tarefas: {e}")
            self.tasks = []
        self.populate_list()

    def save_tasks(self):
        try:
            with open(TODO_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.tasks, f, indent=4, ensure_ascii=False)
        except IOError as e:
            QMessageBox.critical(self, "Erro ao Salvar", f"Não foi possível salvar as tarefas: {e}")
            
    def add_task(self):
        task_text = self.task_input.text().strip()
        if not task_text:
            return
        
        new_task = {
            "text": task_text,
            "completed": False,
            "due_date": None,
            "color": None
        }
        self.tasks.append(new_task)
        self.task_input.clear()
        self.save_tasks()
        self.populate_list()
    
    def remove_task(self):
        current_item = self.task_list_widget.currentItem()
        if not current_item or current_item.data(Qt.ItemDataRole.UserRole) is None:
            return

        reply = QMessageBox.question(self, "Confirmar Remoção", "Tem certeza que deseja remover a tarefa selecionada?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            task_index = current_item.data(Qt.ItemDataRole.UserRole)
            del self.tasks[task_index]
            self.save_tasks()
            self.populate_list()
    
    def clear_completed_tasks(self):
        if not any(t.get('completed') for t in self.tasks):
            QMessageBox.information(self, "Informação", "Nenhuma tarefa concluída para limpar.")
            return

        reply = QMessageBox.question(self, "Confirmar Limpeza", "Tem certeza que deseja remover todas as tarefas concluídas?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.tasks = [task for task in self.tasks if not task.get("completed")]
            self.save_tasks()
            self.populate_list()

    def edit_due_date(self, item):
        task_index = item.data(Qt.ItemDataRole.UserRole)
        if task_index is None: return

        dialog = QDialog(self)
        dialog.setWindowTitle("Definir Data de Vencimento")
        layout = QVBoxLayout(dialog)
        
        calendar = QCalendarWidget()
        current_due_date_str = self.tasks[task_index].get('due_date')
        if current_due_date_str:
            current_date = QDate.fromString(current_due_date_str, 'yyyy-MM-dd')
            calendar.setSelectedDate(current_date)

        layout.addWidget(calendar)
        
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        remove_date_button = QPushButton("Remover Data")
        cancel_button = QPushButton("Cancelar")
        
        button_layout.addWidget(remove_date_button)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)

        ok_button.clicked.connect(lambda: self.on_date_selected(calendar, dialog, task_index))
        remove_date_button.clicked.connect(lambda: self.on_date_removed(dialog, task_index))
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec()

    def on_date_selected(self, calendar, dialog, task_index):
        selected_date = calendar.selectedDate().toString('yyyy-MM-dd')
        self.tasks[task_index]['due_date'] = selected_date
        self.save_tasks()
        self.populate_list()
        dialog.accept()

    def on_date_removed(self, dialog, task_index):
        self.tasks[task_index]['due_date'] = None
        self.save_tasks()
        self.populate_list()
        dialog.accept()

    def update_button_states(self):
        current_item = self.task_list_widget.currentItem()
        has_selection = current_item is not None and current_item.data(Qt.ItemDataRole.UserRole) is not None
        has_completed = any(t.get('completed') for t in self.tasks)
        
        self.remove_button.setEnabled(has_selection)
        self.clear_completed_button.setEnabled(has_completed)
        
    def show_task_context_menu(self, pos):
        item = self.task_list_widget.itemAt(pos)
        if not item or item.data(Qt.ItemDataRole.UserRole) is None:
            return

        menu = QMenu()
        color_menu = menu.addMenu("Definir Cor")

        green_action = QAction("Verde", self)
        yellow_action = QAction("Amarelo", self)
        red_action = QAction("Vermelho", self)
        default_action = QAction("Padrão (Remover Cor)", self)

        color_menu.addAction(green_action)
        color_menu.addAction(yellow_action)
        color_menu.addAction(red_action)
        color_menu.addSeparator()
        color_menu.addAction(default_action)
        
        green_action.triggered.connect(lambda: self.set_task_color('#C8E6C9'))
        yellow_action.triggered.connect(lambda: self.set_task_color('#FFF9C4'))
        red_action.triggered.connect(lambda: self.set_task_color('#FFCDD2'))
        default_action.triggered.connect(lambda: self.set_task_color(None))

        menu.exec(self.task_list_widget.mapToGlobal(pos))

    def set_task_color(self, color_hex):
        current_item = self.task_list_widget.currentItem()
        if not current_item:
            return
        
        task_index = current_item.data(Qt.ItemDataRole.UserRole)
        self.tasks[task_index]['color'] = color_hex
        self.save_tasks()
        self.populate_list()
    
    def on_tasks_reordered(self, parent, start, end, destination, row):
        if start < row:
            moving_item = self.tasks.pop(start)
            self.tasks.insert(row - 1, moving_item)
        else:
            moving_item = self.tasks.pop(start)
            self.tasks.insert(row, moving_item)
        
        self.save_tasks()
        self.populate_list()