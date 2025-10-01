# C:\Meus Projetos\MyOps\modules\common\themes.py

def get_dark_theme_qss():
    """
    Retorna uma folha de estilos QSS (Qt Style Sheets) para um tema escuro completo.
    """
    return """
        /* Estilo geral para todos os widgets */
        QWidget {
            background-color: #353535;
            color: #e0e0e0;
            font-size: 10pt;
            border-color: #555555;
        }
        
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

        /* --- CORREÇÃO DE LAYOUT DO GROUPBOX AQUI --- */
        QGroupBox {
            border: 1px solid #555555;
            border-radius: 4px;
            margin-top: 15px; /* Aumentado para dar espaço vertical ao título */
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 10px;
            font-weight: bold;
            background-color: #353535;
        }
        
        #MasterInfoGroup { background-color: #4a4a4a; border-radius: 4px; border: 1px solid #666666; }

        QHeaderView::section { background-color: #4a4a4a; color: #e0e0e0; padding: 4px; border: 1px solid #666666; }
        QTableWidget, QTreeWidget { gridline-color: #555555; background-color: #2a2a2a; }
        QTableWidget::item:selected, QTreeWidget::item:selected {
            background-color: #42a5f5;
            color: #ffffff;
        }
        
        QTabWidget::pane { border: 1px solid #555555; top: -1px; }
        QTabBar::tab {
            background-color: #4a4a4a;
            border: 1px solid #555555;
            border-bottom: none;
            padding: 8px 15px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:!selected { margin-top: 2px; }
        QTabBar::tab:selected { background-color: #353535; }

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
        QWidget { background-color: #f0f0f0; color: #212121; font-size: 10pt; border-color: #c0c0c0; }
        QMdiArea { background-color: #e0e0e0; }
        QMenuBar { background-color: #f0f0f0; color: #212121; }
        QMenuBar::item { background-color: transparent; padding: 4px 8px; }
        QMenuBar::item:selected { background-color: #dcdcdc; }
        QMenuBar::item:pressed { background-color: #42a5f5; color: #ffffff; }
        QMenu { background-color: #ffffff; border: 1px solid #c0c0c0; color: #212121; }
        QMenu::item { padding: 4px 25px 4px 25px; }
        QMenu::item:selected { background-color: #42a5f5; color: #ffffff; }
        QMenu::separator { height: 1px; background: #e0e0e0; margin: 4px 0px; }
        
        QPushButton { background-color: #e0e0e0; color: #000000; border: 1px solid #c0c0c0; padding: 5px; border-radius: 3px; }
        QPushButton:hover { background-color: #e8e8e8; border-color: #b0b0b0; }
        QPushButton:pressed { background-color: #42a5f5; border-color: #42a5f5; color: #ffffff; }
        QPushButton:disabled { background-color: #f5f5f5; color: #a0a0a0; }

        QCheckBox::indicator {
            border: 1px solid #909090;
            background-color: #fcfcfc;
            width: 15px;
            height: 15px;
            border-radius: 3px;
        }
        QCheckBox::indicator:hover { border: 1px solid #42a5f5; }
        QCheckBox::indicator:checked {
            background-color: #42a5f5;
            border: 1px solid #42a5f5;
            image: url(./assets/check-light.svg);
        }
        
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDateTimeEdit { background-color: #ffffff; color: #212121; border: 1px solid #c0c0c0; border-radius: 3px; padding: 4px; }
        QComboBox::drop-down { border: none; subcontrol-origin: padding; subcontrol-position: top right; width: 20px; }
        
        /* --- CORREÇÃO DE LAYOUT DO GROUPBOX AQUI --- */
        QGroupBox {
            border: 1px solid #c0c0c0;
            border-radius: 4px;
            margin-top: 15px; /* Aumentado para dar espaço vertical ao título */
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 10px;
            font-weight: bold;
            background-color: #f0f0f0;
        }
        #MasterInfoGroup { background-color: #dcdcdc; border-radius: 4px; border: 1px solid #c0c0c0; }

        QHeaderView::section { background-color: #e8e8e8; color: #212121; padding: 4px; border: 1px solid #d0d0d0; }
        QTableWidget, QTreeWidget, QListWidget { background-color: #ffffff; alternate-background-color: #f7f7f7; gridline-color: #dcdcdc; }
        QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {
            background-color: #42a5f5;
            color: #ffffff;
        }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QTableWidget:focus, QTreeWidget:focus, QListWidget:focus { border: 1px solid #42a5f5; }
        
        QTabWidget::pane { border: 1px solid #c0c0c0; top: -1px; background-color: #f0f0f0; }
        QTabBar::tab {
            background-color: #dcdcdc;
            border: 1px solid #c0c0c0;
            border-bottom: none;
            padding: 8px 15px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:!selected { margin-top: 2px; }
        QTabBar::tab:selected { background-color: #f0f0f0; }

        QScrollBar:vertical { border: none; background: #e8e8e8; width: 12px; margin: 0px; }
        QScrollBar::handle:vertical { background: #c0c0c0; min-height: 20px; border-radius: 6px; }
        QScrollBar:horizontal { border: none; background: #e8e8e8; height: 12px; margin: 0px; }
        QScrollBar::handle:horizontal { background: #c0c0c0; min-width: 20px; border-radius: 6px; }
    """