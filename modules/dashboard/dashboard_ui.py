# C:\Meus Projetos\MyOps\modules\dashboard\dashboard_ui.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QStyle
from PyQt6.QtCore import Qt, pyqtSignal
from .todo_list_widget import TodoListWidget

class DashboardWidget(QWidget):
    toggle_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(2)

        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(5, 5, 5, 0)
        self.toggle_button = QPushButton()
        self.toggle_button.setFixedWidth(30)
        
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.toggle_button)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        
        self.main_layout.addLayout(top_bar_layout)
        self.main_layout.addWidget(self.tab_widget)

        self.toggle_button.clicked.connect(self.toggle_requested.emit)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        
        # Inicia com o ícone de expandido
        self.update_toggle_button_icon(True)
        self.open_todo_list_tab()

    def open_todo_list_tab(self):
        for i in range(self.tab_widget.count()):
            if isinstance(self.tab_widget.widget(i), TodoListWidget):
                self.tab_widget.setCurrentIndex(i)
                return

        todo_widget = TodoListWidget()
        self.tab_widget.addTab(todo_widget, "To-do List")
        self.tab_widget.setCurrentWidget(todo_widget)

    def close_tab(self, index):
        widget_to_remove = self.tab_widget.widget(index)
        self.tab_widget.removeTab(index)
        widget_to_remove.deleteLater()

    def update_toggle_button_icon(self, is_expanded):
        # --- ALTERAÇÃO: Usa ícones padrão do sistema em vez de texto ---
        if is_expanded:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowLeft)
            self.toggle_button.setToolTip("Recolher painel")
            self.tab_widget.setVisible(True)
        else:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowRight)
            self.toggle_button.setToolTip("Expandir painel")
            self.tab_widget.setVisible(False)
        self.toggle_button.setIcon(icon)