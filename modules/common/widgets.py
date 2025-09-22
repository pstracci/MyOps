# C:\Meus Projetos\MyOps\modules\common\widgets.py

import configparser
import re
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QPushButton, QFormLayout, 
    QDialogButtonBox, QFileDialog, QMessageBox, QLabel, QHBoxLayout,
    QListWidget, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from . import security
from . import db_utils

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Opções de Configuração Geral")
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        info_label = QLabel("Alterações aqui requerem que a aplicação seja reiniciada.")
        self.client_path_input = QLineEdit()
        browse_button = QPushButton("Procurar Pasta...")

        form_layout.addRow(info_label)
        form_layout.addRow(QLabel("Local do Oracle Instant Client:"), self.client_path_input)
        form_layout.addRow(browse_button)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addLayout(form_layout)
        layout.addWidget(button_box)

        browse_button.clicked.connect(self.browse_folder)
        
        self.load_settings()

    def browse_folder(self):
        directory = QFileDialog.getExistingDirectory(self, "Selecione a pasta do Instant Client")
        if directory:
            self.client_path_input.setText(directory)

    def load_settings(self):
        if self.config.has_section('general'):
            path = self.config.get('general', 'instant_client_path', fallback='')
            self.client_path_input.setText(path)

    def accept(self):
        if not self.config.has_section('general'):
            self.config.add_section('general')
        
        self.config.set('general', 'instant_client_path', self.client_path_input.text())
        
        try:
            with open('config.ini', 'w') as configfile:
                self.config.write(configfile)
            QMessageBox.information(self, "Sucesso", "Configurações salvas. Por favor, reinicie a aplicação para que as mudanças tenham efeito.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar o arquivo config.ini:\n{e}")
            
        super().accept()


class ConnectionTestWorker(QThread):
    """Worker para testar a conexão em background sem travar a UI."""
    finished = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, user, password, dsn):
        super().__init__()
        self.user, self.password, self.dsn = user, password, dsn

    def run(self):
        try:
            # ======================================================================= #
            # CORREÇÃO: Adicionada a descriptografia da senha antes de conectar.
            # A função security.decrypt_password é inteligente: se a senha não
            # estiver criptografada (ex: uma nova senha digitada), ela retorna
            # o texto original.
            # ======================================================================= #
            decrypted_pass = security.decrypt_password(self.password)
            db_utils.test_db_connection(self.user, decrypted_pass, self.dsn)
            self.finished.emit(True)
        except Exception as e:
            self.error.emit(str(e))


class ConnectionManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gerenciador de Conexões")
        self.setMinimumSize(700, 450)
        
        self.config = configparser.ConfigParser()
        self.original_section_name = None

        main_layout = QHBoxLayout(self)
        
        # --- Lado Esquerdo: Lista de Conexões ---
        left_group = QGroupBox("Conexões Salvas")
        left_layout = QVBoxLayout(left_group)
        self.conn_list = QListWidget()
        self.populate_list()
        
        list_button_layout = QHBoxLayout()
        self.new_button = QPushButton("Nova")
        self.delete_button = QPushButton("Excluir")
        list_button_layout.addWidget(self.new_button)
        list_button_layout.addWidget(self.delete_button)

        left_layout.addWidget(self.conn_list)
        left_layout.addLayout(list_button_layout)

        # --- Lado Direito: Detalhes da Conexão ---
        right_group = QGroupBox("Detalhes da Conexão")
        right_layout = QVBoxLayout(right_group)
        
        form_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("letras_numeros_e_underscore")
        self.user_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.dsn_input = QLineEdit()
        
        form_layout.addRow("Nome da Seção:", self.name_input)
        form_layout.addRow("Usuário:", self.user_input)
        form_layout.addRow("Senha:", self.password_input)
        form_layout.addRow("DSN / URL:", self.dsn_input)
        
        form_button_layout = QHBoxLayout()
        self.save_button = QPushButton("Salvar Alterações")
        self.test_button = QPushButton("Testar Conexão")
        form_button_layout.addStretch()
        form_button_layout.addWidget(self.test_button)
        form_button_layout.addWidget(self.save_button)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-style: italic;")

        right_layout.addLayout(form_layout)
        right_layout.addStretch()
        right_layout.addWidget(self.status_label)
        right_layout.addLayout(form_button_layout)

        main_layout.addWidget(left_group, 1)
        main_layout.addWidget(right_group, 2)

        # --- Conexões de Sinais e Slots ---
        self.conn_list.currentItemChanged.connect(self.on_selection_change)
        self.new_button.clicked.connect(self.on_new)
        self.delete_button.clicked.connect(self.on_delete)
        self.save_button.clicked.connect(self.on_save)
        self.test_button.clicked.connect(self.on_test)
        self.name_input.textChanged.connect(self._validate_section_name)

        self.enable_form(False)

    def populate_list(self):
        self.conn_list.clear()
        self.config.read('config.ini')
        sections_to_show = [s for s in self.config.sections() if s.startswith(('database_', 'weblogic_'))]
        self.conn_list.addItems(sorted(sections_to_show))
    
    def on_selection_change(self, current, previous):
        if not current:
            self.clear_fields()
            self.enable_form(False)
            return
        
        self.enable_form(True)
        section_name = current.text()
        self.original_section_name = section_name
        section = self.config[section_name]
        
        self.name_input.setText(section_name)
        self.user_input.setText(section.get('user', ''))
        self.password_input.setText("******")
        self.password_input.setPlaceholderText("Deixe em branco para não alterar")
        self.dsn_input.setText(section.get('dsn', section.get('url', '')))
        self.status_label.clear()

    def on_new(self):
        self.conn_list.clearSelection()
        self.clear_fields()
        self.enable_form(True)
        self.delete_button.setEnabled(False)
        self.original_section_name = None
        self.name_input.setFocus()
    
    def on_delete(self):
        current_item = self.conn_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Ação Inválida", "Selecione uma conexão para excluir.")
            return

        section_name = current_item.text()
        reply = QMessageBox.question(self, "Confirmar Exclusão", f"Tem certeza que deseja excluir a conexão '{section_name}'?")
        if reply == QMessageBox.StandardButton.Yes:
            self.config.remove_section(section_name)
            self._write_config()
            self.populate_list()
            self.clear_fields()

    def on_save(self):
        new_section_name = self.name_input.text().strip()
        if not self._validate_section_name(new_section_name):
            QMessageBox.warning(self, "Nome Inválido", "O Nome da Seção só pode conter letras, números e underscore (_).")
            return
        
        if self.original_section_name and self.original_section_name != new_section_name:
            if self.config.has_section(self.original_section_name):
                self.config.remove_section(self.original_section_name)

        if not self.config.has_section(new_section_name):
            self.config.add_section(new_section_name)

        self.config.set(new_section_name, 'user', self.user_input.text())
        dsn_or_url = self.dsn_input.text()
        self.config.set(new_section_name, 'dsn', dsn_or_url)
        self.config.set(new_section_name, 'url', dsn_or_url)

        password_from_ui = self.password_input.text()
        if password_from_ui and password_from_ui != "******":
            encrypted_pass = security.encrypt_password(password_from_ui)
            self.config.set(new_section_name, 'password', encrypted_pass)

        self._write_config()
        QMessageBox.information(self, "Sucesso", f"Conexão '{new_section_name}' salva com sucesso.")
        self.populate_list()
        items = self.conn_list.findItems(new_section_name, Qt.MatchFlag.MatchExactly)
        if items:
            self.conn_list.setCurrentItem(items[0])

    def on_test(self):
        self.status_label.setText("Testando conexão...")
        self.status_label.setStyleSheet("font-style: italic; color: orange;")
        
        user = self.user_input.text()
        dsn = self.dsn_input.text()
        password_to_test = self.password_input.text()

        if password_to_test == "******" and self.original_section_name:
            self.config.read('config.ini')
            password_to_test = self.config.get(self.original_section_name, 'password', fallback='')
        
        self.test_worker = ConnectionTestWorker(user, password_to_test, dsn)
        self.test_worker.finished.connect(self._on_test_finished)
        self.test_worker.error.connect(self._on_test_finished)
        self.test_worker.start()

    def _on_test_finished(self, result):
        if isinstance(result, bool) and result:
            self.status_label.setText("Sucesso! Conexão bem-sucedida.")
            self.status_label.setStyleSheet("font-style: normal; color: green;")
        else:
            error_message = str(result)
            if len(error_message) > 100:
                error_message = error_message[:100] + "..."
            self.status_label.setText(f"Erro: {error_message}")
            self.status_label.setStyleSheet("font-style: normal; color: red;")

    def clear_fields(self):
        self.name_input.clear()
        self.user_input.clear()
        self.password_input.clear()
        self.password_input.setPlaceholderText("Digite a nova senha")
        self.dsn_input.clear()
        self.status_label.clear()
        self.original_section_name = None

    def enable_form(self, enabled):
        for widget in [self.name_input, self.user_input, self.password_input, 
                       self.dsn_input, self.save_button, self.test_button, self.delete_button]:
            widget.setEnabled(enabled)
    
    def _validate_section_name(self, text):
        is_valid = bool(re.match(r'^[a-zA-Z0-9_]+$', text))
        if is_valid or not text:
            self.name_input.setStyleSheet("")
            self.save_button.setEnabled(is_valid)
        else:
            self.name_input.setStyleSheet("border: 1px solid red;")
            self.save_button.setEnabled(False)
        return is_valid
    
    def _write_config(self):
        try:
            with open('config.ini', 'w') as configfile:
                self.config.write(configfile)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar o arquivo config.ini:\n{e}")