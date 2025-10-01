# C:\Meus Projetos\MyOps\main_app.py

import sys
import os
import oracledb
import configparser
import logging
from logging.handlers import RotatingFileHandler

# --- Seção de Log ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s (%(filename)s:%(lineno)d)')
log_file = 'myops_debug.log'
file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)
logging.info("Aplicação iniciada. Sistema de log configurado.")

# --- BLOCO DE INICIALIZAÇÃO DO ORACLE CLIENT (NÃO-FATAL) ---
try:
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    config_path = os.path.join(base_path, 'config.ini')
    logging.info(f"Procurando arquivo de configuracao em: {config_path}")

    client_path = None
    if os.path.exists(config_path):
        config = configparser.ConfigParser()
        config.read(config_path)
        client_path = config.get('general', 'instant_client_path', fallback=None)

    if client_path and os.path.isdir(client_path):
        logging.info(f"Tentando inicializar Oracle Client a partir do caminho configurado: {client_path}")
        os.environ['PATH'] = client_path + os.pathsep + os.environ.get('PATH', '')
        oracledb.init_oracle_client(lib_dir=client_path)
        logging.info(f"Oracle Client inicializado com sucesso na inicialização. Versao do cliente: {oracledb.clientversion()}")
    else:
        logging.warning(
            f"O caminho para o Oracle Instant Client nao foi encontrado ou nao esta configurado. "
            f"Verifique a chave 'instant_client_path' na secao [general] do arquivo '{config_path}'. "
            f"A aplicacao continuara, mas funcionalidades de banco de dados falharao."
        )
except Exception as e:
    logging.error(f"AVISO: Nao foi possivel inicializar o Oracle Client durante a inicializacao. Erro: {e}", exc_info=True)

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QMessageBox, QMdiArea, QMdiSubWindow
from PyQt6.QtGui import QFont, QAction, QColor, QBrush, QPixmap, QPainter, QActionGroup, QIcon
from PyQt6.QtCore import Qt, QPoint

# --- Import dos módulos da aplicação ---
from modules.gfa.gfa_ui import GfaHealthWidget
from modules.bat452_scheduler.bat452_scheduler_ui import Bat452SchedulerWidget
from modules.dms_extractor.dms_extractor_ui import DmsExtractorWidget
from modules.contestacao.contestacao_ui import ContestacaoViewerWidget
from modules.bat509.bat509_ui import Bat509ToolWidget
from modules.object_viewer.object_viewer_ui import ObjectViewerWidget
from modules.pgu.pgu_ui import PGUToolWidget
from modules.espelho.espelho_ui import EspelhoToolWidget
from modules.common.widgets import SettingsDialog, ConnectionManagerDialog
from modules.sql_loader.sql_loader_ui import SqlLoaderWidget
from modules.session_monitor.session_monitor_ui import SessionMonitorWidget
from modules.top_sql.top_sql_ui import TopSqlMonitorWidget
from modules.bat223.bat223_ui import Bat223ToolWidget
from modules.siebel_relation.siebel_relation_ui import SiebelRelationWidget
from modules.common import themes
from modules.common import license_validator

class BackgroundMdiArea(QMdiArea):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.background_pixmap = QPixmap(image_path)
        if self.background_pixmap.isNull():
            logging.warning(f"Imagem de fundo '{image_path}' não encontrada ou não pôde ser carregada.")
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.background_pixmap.isNull(): return
        painter = QPainter(self.viewport())
        painter.setOpacity(0.3)
        area_size = self.viewport().size()
        scaled_pixmap = self.background_pixmap.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        point = QPoint((area_size.width() - scaled_pixmap.width()) // 2, (area_size.height() - scaled_pixmap.height()) // 2)
        painter.drawPixmap(point, scaled_pixmap)

class MainApplicationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MyOps - Ferramentas de Automação e Suporte")

        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        icon_path = os.path.join(base_path, 'assets', 'icone.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            logging.warning(f"Ícone da aplicação não encontrado em: {icon_path}")

        image_path = os.path.join(base_path, 'assets', 'fundo.png')
        logging.info(f"Procurando imagem de fundo em: {image_path}")
        if not os.path.exists(image_path):
            logging.warning(f"Arquivo de imagem '{image_path}' NÃO FOI ENCONTRADO no caminho esperado!")

        self.mdi_area = BackgroundMdiArea(image_path)
        self.setCentralWidget(self.mdi_area)

        self.config = configparser.ConfigParser()
        self.light_mode_action = None
        self.dark_mode_action = None

        self._create_menu_bar()
        self.load_and_apply_theme()

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        open_menu = menu_bar.addMenu("Abrir")

        self.module_map = {
            "Agendador de Processamento Massivo (BAT452)": (Bat452SchedulerWidget, "Agendador BAT452"),
            "Consultar Relacionamentos Siebel": (SiebelRelationWidget, "Consultar Relacionamentos Siebel"),
            "Carregador de Arquivos (SQL*Loader)": (SqlLoaderWidget, "Carregador de Arquivos"),
            "Extrator de Faturas DMS": (DmsExtractorWidget, "Extrator de Faturas - DMS"),
            "Ferramentas Base Espelho": (EspelhoToolWidget, "Ferramentas Base Espelho"),
            "Ferramentas PGU": (PGUToolWidget, "Ferramentas PGU"),
            "Forçar Extração de Clientes/Contratos BAT223": (Bat223ToolWidget, "Forçar Extração de Clientes (BAT223)"),
            "Forçar Extração de Ordem (BAT509)": (Bat509ToolWidget, "Ferramenta de Marcação - BAT509"),
            "Monitor de Sessões": (SessionMonitorWidget, "Monitor de Sessões"),
            "Monitor de 'Top SQL' (Agregado)": (TopSqlMonitorWidget, "Monitor de Top SQL em Tempo Real"),
            "Visualizador de Contestações": (ContestacaoViewerWidget, "Visualizador de Contestações"),
            "Visualizador de Objetos de Banco": (ObjectViewerWidget, "Visualizador de Objetos"),
            "Monitor Health GFA": (GfaHealthWidget, "Monitor de Health Check - GFA"),
        }
        
        menu_structure = {
            "Ferramentas de Banco de Dados": ["Carregador de Arquivos (SQL*Loader)",  "Monitor de Sessões", "Monitor de 'Top SQL' (Agregado)", "Visualizador de Objetos de Banco"],
            "BATS": ["Agendador de Processamento Massivo (BAT452)", "Forçar Extração de Clientes/Contratos BAT223", "Forçar Extração de Ordem (BAT509)"],
            "Sistemas Legados": ["Consultar Relacionamentos Siebel", "Extrator de Faturas DMS", "Ferramentas PGU", "Monitor Health GFA", "Visualizador de Contestações", "Ferramentas Base Espelho"]
        }

        for category_name in sorted(menu_structure.keys()):
            sub_menu = open_menu.addMenu(category_name)
            for module_text in sorted(menu_structure[category_name]):
                if module_text in self.module_map:
                    action = QAction(module_text, self)
                    action.triggered.connect(self.open_module_window)
                    sub_menu.addAction(action)

        window_menu = menu_bar.addMenu("Janelas")
        cascade_action = QAction("Cascata", self); cascade_action.triggered.connect(self.mdi_area.cascadeSubWindows); window_menu.addAction(cascade_action)
        tile_action = QAction("Lado a Lado", self); tile_action.triggered.connect(self.mdi_area.tileSubWindows); window_menu.addAction(tile_action)
        close_all_action = QAction("Fechar Todas", self); close_all_action.triggered.connect(self.mdi_area.closeAllSubWindows); window_menu.addAction(close_all_action)

        settings_menu = menu_bar.addMenu("Configurações")
        conn_manager_action = QAction("Gerenciador de Conexões...", self); conn_manager_action.triggered.connect(self.open_connection_manager); settings_menu.addAction(conn_manager_action)
        client_path_action = QAction("Definir Local do Instant Client...", self); client_path_action.triggered.connect(self.open_settings_dialog); settings_menu.addAction(client_path_action)

        preferences_menu = menu_bar.addMenu("Preferências")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)

        self.light_mode_action = QAction("Modo Claro (Light)", self, checkable=True)
        self.light_mode_action.triggered.connect(lambda: self.apply_theme('light'))
        preferences_menu.addAction(self.light_mode_action)
        theme_group.addAction(self.light_mode_action)

        self.dark_mode_action = QAction("Modo Escuro (Dark)", self, checkable=True)
        self.dark_mode_action.triggered.connect(lambda: self.apply_theme('dark'))
        preferences_menu.addAction(self.dark_mode_action)
        theme_group.addAction(self.dark_mode_action)

        help_menu = menu_bar.addMenu("Ajuda")
        about_action = QAction("Sobre", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def apply_theme(self, theme_name, from_load=False):
        app = QApplication.instance()
        if theme_name == 'dark':
            app.setStyleSheet(themes.get_dark_theme_qss())
        else:
            # --- ESTA É A LINHA QUE FOI ALTERADA ---
            app.setStyleSheet(themes.get_light_theme_qss())
        if not from_load: self.save_theme_preference(theme_name)

    def save_theme_preference(self, theme_name):
        try:
            self.config.read('config.ini')
            if not self.config.has_section('general'): self.config.add_section('general')
            self.config.set('general', 'theme', theme_name)
            with open('config.ini', 'w') as configfile: self.config.write(configfile)
        except Exception as e: logging.error(f"Não foi possível salvar a preferência de tema: {e}")

    def load_and_apply_theme(self):
        self.config.read('config.ini')
        theme = self.config.get('general', 'theme', fallback='light')
        self.apply_theme(theme, from_load=True)
        if theme == 'dark': self.dark_mode_action.setChecked(True)
        else: self.light_mode_action.setChecked(True)

    def open_module_window(self):
        action_text = self.sender().text()
        widget_class, title = self.module_map[action_text]
        for window in self.mdi_area.subWindowList():
            if window.windowTitle() == title:
                window.setFocus()
                return
        sub_window = QMdiSubWindow()
        sub_window.setWidget(widget_class())
        sub_window.setWindowTitle(title)
        sub_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.mdi_area.addSubWindow(sub_window)
        sub_window.show()
        sub_window.resize(1200, 800)

    def open_connection_manager(self):
        dialog = ConnectionManagerDialog(self)
        dialog.exec()

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def show_about_dialog(self):
        about_text = """<b>MyOps - Ferramentas de Automação e Suporte</b>
<p>Versão 1.0.0</p>
<p>© 2025. Todos os direitos reservados.</p>
<p>Esta aplicação foi desenvolvida para otimizar e agilizar
rotinas operacionais, consultas de banco de dados e tarefas de desenvolvimento.</p>
"""
        QMessageBox.about(self, "Sobre o MyOps", about_text)

if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        is_valid, message = license_validator.check_license()
        if not is_valid:
            QMessageBox.critical(None, "Erro de Licença - MyOps", message)
            logging.error(f"Falha na validação da licença: {message}")
            sys.exit(1)
        logging.info(message)
        main_window = MainApplicationWindow()
        main_window.showMaximized()
        sys.exit(app.exec())
    except Exception as e:
        logging.critical("Ocorreu um erro fatal e a aplicação será encerrada.", exc_info=True)
        QMessageBox.critical(None, "Erro Crítico", f"A aplicação encontrou um erro fatal e precisa ser fechada.\n\nDetalhes foram salvos em 'myops_debug.log'.\n\nErro: {e}")
        sys.exit(1)