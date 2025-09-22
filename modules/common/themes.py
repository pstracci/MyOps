# C:\Meus Projetos\MyOps\modules\common\themes.py

def get_dark_theme_qss():
    """
    Retorna uma folha de estilos QSS (Qt Style Sheets) para um tema escuro completo.
    Isso garante que todos os widgets, incluindo menus, sejam estilizados corretamente.
    """
    return """
        /* Estilo geral para todos os widgets */
        QWidget {
            background-color: #353535; /* Cinza escuro */
            color: #e0e0e0; /* Cinza claro para texto */
            font-size: 10pt;
            border-color: #555555;
        }

        /* Área central com a imagem de fundo */
        QMdiArea {
            background-color: #2c3e50; /* Azul escuro/acinzentado */
        }

        /* --- Barra de Menu Superior --- */
        QMenuBar {
            background-color: #353535;
            color: #e0e0e0;
        }
        QMenuBar::item {
            background-color: transparent;
            padding: 4px 8px;
        }
        QMenuBar::item:selected { /* quando o mouse passa por cima */
            background-color: #525252;
        }
        QMenuBar::item:pressed { /* quando o menu é aberto */
            background-color: #42a5f5; /* Azul claro */
        }

        /* --- Menus Dropdown --- */
        QMenu {
            background-color: #3c3c3c; /* Fundo do menu */
            border: 1px solid #555555;
            color: #e0e0e0;
        }
        QMenu::item {
            padding: 4px 25px 4px 25px;
        }
        QMenu::item:selected {
            background-color: #42a5f5; /* Azul claro no item selecionado */
            color: #ffffff;
        }
        QMenu::separator {
            height: 1px;
            background: #555555;
            margin: 4px 0px;
        }

        /* --- Botões --- */
        QPushButton {
            background-color: #555555;
            color: #ffffff;
            border: 1px solid #666666;
            padding: 5px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #6a6a6a;
            border-color: #777777;
        }
        QPushButton:pressed {
            background-color: #42a5f5;
            border-color: #42a5f5;
        }
        QPushButton:disabled {
            background-color: #444444;
            color: #888888;
        }

        /* --- Campos de Entrada e ComboBox --- */
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDateTimeEdit {
            background-color: #2a2a2a;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 4px;
        }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
            border: 1px solid #42a5f5; /* Destaque azul ao focar */
        }
        QComboBox::drop-down {
            border: none;
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
        }

        /* --- Outros Widgets --- */
        QGroupBox {
            border: 1px solid #555555;
            border-radius: 4px;
            margin-top: 12px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 5px;
        }

        QHeaderView::section {
            background-color: #4a4a4a;
            color: #e0e0e0;
            padding: 4px;
            border: 1px solid #666666;
        }

        QTableWidget {
            gridline-color: #555555;
        }

        QScrollBar:vertical {
            border: none;
            background: #2a2a2a;
            width: 12px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: #555555;
            min-height: 20px;
            border-radius: 6px;
        }

        QScrollBar:horizontal {
            border: none;
            background: #2a2a2a;
            height: 12px;
            margin: 0px;
        }
        QScrollBar::handle:horizontal {
            background: #555555;
            min-width: 20px;
            border-radius: 6px;
        }
    """

