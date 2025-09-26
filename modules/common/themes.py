# C:\Meus Projetos\MyOps\modules\common\themes.py

def get_dark_theme_qss():
    """
    Retorna uma folha de estilos QSS (Qt Style Sheets) para um tema escuro completo.
    """
    return """
        /* Estilo geral para todos os widgets */
        QWidget {
            background-color: #353535; /* Cinza escuro */
            color: #e0e0e0; /* Cinza claro para texto */
            font-size: 10pt;
            border-color: #555555;
        }
        /* ... (o resto do seu tema escuro continua aqui, sem alterações) ... */
        QMdiArea { background-color: #2c3e50; }
        QMenuBar { background-color: #353535; color: #e0e0e0; }
        QMenuBar::item { background-color: transparent; padding: 4px 8px; }
        QMenuBar::item:selected { background-color: #525252; }
        QMenuBar::item:pressed { background-color: #42a5f5; }
        QMenu { background-color: #3c3c3c; border: 1px solid #555555; color: #e0e0e0; }
        QMenu::item { padding: 4px 25px 4px 25px; }
        QMenu::item:selected { background-color: #42a5f5; color: #ffffff; }
        QMenu::separator { height: 1px; background: #555555; margin: 4px 0px; }
        QPushButton { background-color: #555555; color: #ffffff; border: 1px solid #666666; padding: 5px; border-radius: 3px; }
        QPushButton:hover { background-color: #6a6a6a; border-color: #777777; }
        QPushButton:pressed { background-color: #42a5f5; border-color: #42a5f5; }
        QPushButton:disabled { background-color: #444444; color: #888888; }
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDateTimeEdit { background-color: #2a2a2a; color: #e0e0e0; border: 1px solid #555555; border-radius: 3px; padding: 4px; }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus { border: 1px solid #42a5f5; }
        QComboBox::drop-down { border: none; subcontrol-origin: padding; subcontrol-position: top right; width: 20px; }
        QGroupBox { border: 1px solid #555555; border-radius: 4px; margin-top: 12px; }
        QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 5px; }
        QHeaderView::section { background-color: #4a4a4a; color: #e0e0e0; padding: 4px; border: 1px solid #666666; }
        QTableWidget { gridline-color: #555555; }
        QScrollBar:vertical { border: none; background: #2a2a2a; width: 12px; margin: 0px; }
        QScrollBar::handle:vertical { background: #555555; min-height: 20px; border-radius: 6px; }
        QScrollBar:horizontal { border: none; background: #2a2a2a; height: 12px; margin: 0px; }
        QScrollBar::handle:horizontal { background: #555555; min-width: 20px; border-radius: 6px; }
    """

def get_light_theme_qss():
    """
    Retorna uma folha de estilos QSS para um tema claro completo e independente.
    """
    return """
        /* Estilo geral para todos os widgets */
        QWidget {
            background-color: #f0f0f0; /* Cinza muito claro */
            color: #212121; /* Cinza muito escuro para texto */
            font-size: 10pt;
            border-color: #c0c0c0;
        }

        /* Área central com a imagem de fundo */
        QMdiArea {
            background-color: #e0e0e0; /* Cinza um pouco mais escuro para contraste */
        }

        /* --- Barra de Menu Superior --- */
        QMenuBar {
            background-color: #f0f0f0;
            color: #212121;
        }
        QMenuBar::item {
            background-color: transparent;
            padding: 4px 8px;
        }
        QMenuBar::item:selected { /* quando o mouse passa por cima */
            background-color: #dcdcdc;
        }
        QMenuBar::item:pressed { /* quando o menu é aberto */
            background-color: #42a5f5; /* Azul claro (mantido para destaque) */
            color: #ffffff;
        }

        /* --- Menus Dropdown --- */
        QMenu {
            background-color: #ffffff; /* Fundo branco para menus */
            border: 1px solid #c0c0c0;
            color: #212121;
        }
        QMenu::item {
            padding: 4px 25px 4px 25px;
        }
        QMenu::item:selected {
            background-color: #42a5f5;
            color: #ffffff;
        }
        QMenu::separator {
            height: 1px;
            background: #e0e0e0;
            margin: 4px 0px;
        }

        /* --- Botões --- */
        QPushButton {
            background-color: #e0e0e0;
            color: #000000;
            border: 1px solid #c0c0c0;
            padding: 5px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #e8e8e8;
            border-color: #b0b0b0;
        }
        QPushButton:pressed {
            background-color: #42a5f5;
            border-color: #42a5f5;
            color: #ffffff;
        }
        QPushButton:disabled {
            background-color: #f5f5f5;
            color: #a0a0a0;
        }

        /* --- Campos de Entrada e ComboBox --- */
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDateTimeEdit {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #c0c0c0;
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
            border: 1px solid #c0c0c0;
            border-radius: 4px;
            margin-top: 12px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 5px;
        }

        QHeaderView::section {
            background-color: #e8e8e8;
            color: #212121;
            padding: 4px;
            border: 1px solid #d0d0d0;
        }

        QTableWidget {
            gridline-color: #dcdcdc;
        }

        QScrollBar:vertical {
            border: none;
            background: #e8e8e8;
            width: 12px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: #c0c0c0;
            min-height: 20px;
            border-radius: 6px;
        }

        QScrollBar:horizontal {
            border: none;
            background: #e8e8e8;
            height: 12px;
            margin: 0px;
        }
        QScrollBar::handle:horizontal {
            background: #c0c0c0;
            min-width: 20px;
            border-radius: 6px;
        }
    """