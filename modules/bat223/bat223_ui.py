# C:\Meus Projetos\MyOps\modules\bat223\bat223_ui.py

import re
import configparser
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QMessageBox,
    QLabel, QGroupBox, QHBoxLayout, QTextEdit, QComboBox
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDateTime

from modules.bat223 import bat223_logic as db


class Bat223PreviewWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, cpf_list, connection_section):
        super().__init__()
        self.cpf_list = cpf_list
        self.connection_section = connection_section

    def run(self):
        try:
            result = db.preview_bat223_by_cpf(self.cpf_list, self.connection_section)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class Bat223ExecutionWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, cpf_list, connection_section):
        super().__init__()
        self.cpf_list = cpf_list
        self.connection_section = connection_section

    def run(self):
        try:
            result = db.force_bat223_extraction_by_cpf(self.cpf_list, self.connection_section)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class Bat223ToolWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._pending_cpf_list = None

        main_layout = QVBoxLayout(self)

        # ── Painel de controles ──────────────────────────────────────────────
        controls_group = QGroupBox("Forçar Extração de Clientes (BAT223)")
        controls_layout = QVBoxLayout(controls_group)

        connection_layout = QHBoxLayout()
        connection_layout.addWidget(QLabel("Conexão:"))
        self.connection_combo = QComboBox()
        self._populate_connections()
        connection_layout.addWidget(self.connection_combo, 1)

        description_label = QLabel(
            "Informe um ou mais CPFs (11 dígitos), separados por vírgula ou quebra de linha.\n"
            "O programa identificará automaticamente contratos Móvel e Banda Larga."
        )
        description_label.setWordWrap(True)

        self.cpf_input = QTextEdit()
        self.cpf_input.setPlaceholderText(
            "Ex:\n01234567890\n98765432100, 11122233344"
        )
        self.cpf_input.setMinimumHeight(120)

        button_layout = QHBoxLayout()
        self.run_button = QPushButton("Analisar e Marcar Contratos (BAT223)")
        self.run_button.setMinimumHeight(40)
        self.clear_button = QPushButton("Limpar")
        self.clear_button.setMinimumHeight(40)
        button_layout.addWidget(self.run_button, 2)
        button_layout.addWidget(self.clear_button, 1)

        controls_layout.addLayout(connection_layout)
        controls_layout.addWidget(description_label)
        controls_layout.addWidget(self.cpf_input)
        controls_layout.addLayout(button_layout)

        # ── Log ──────────────────────────────────────────────────────────────
        log_group = QGroupBox("Log de Operações")
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextEdit(readOnly=True)
        self.log_output.setFont(QFont("Courier", 9))
        log_layout.addWidget(self.log_output)

        main_layout.addWidget(controls_group)
        main_layout.addWidget(log_group, 1)

        self.run_button.clicked.connect(self._on_run_clicked)
        self.clear_button.clicked.connect(self._on_clear)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _populate_connections(self):
        self.connection_combo.clear()
        config = configparser.ConfigParser()
        try:
            config.read('config.ini')
            db_connections = [s for s in config.sections() if s.startswith('database_')]
            self.connection_combo.addItems(sorted(db_connections))
        except Exception as e:
            QMessageBox.critical(self, "Erro de Configuração",
                                 f"Não foi possível ler as conexões do config.ini.\n\n{e}")

    def _log(self, message):
        ts = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        self.log_output.append(f"[{ts}] {message}")

    def _set_busy(self, label):
        self.run_button.setEnabled(False)
        self.run_button.setText(label)

    def _set_idle(self):
        self.run_button.setEnabled(True)
        self.run_button.setText("Analisar e Marcar Contratos (BAT223)")

    # ── passo 1: validação e preview ─────────────────────────────────────────

    def _on_run_clicked(self):
        selected_connection = self.connection_combo.currentText()
        if not selected_connection:
            QMessageBox.warning(self, "Seleção Inválida",
                                "Nenhuma conexão de banco de dados selecionada.")
            return

        raw = self.cpf_input.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, "Entrada Inválida", "Informe ao menos um CPF.")
            return

        tokens = re.split(r'[,\s\n]+', raw)
        cpf_list = [t.strip() for t in tokens if re.fullmatch(r'\d{11}', t.strip())]
        ignored = [t for t in tokens if t and not re.fullmatch(r'\d{11}', t.strip())]

        if not cpf_list:
            QMessageBox.warning(self, "Entrada Inválida",
                                "Nenhum CPF válido encontrado (necessário: 11 dígitos numéricos).")
            return

        if ignored:
            self._log(f"Aviso: {len(ignored)} token(s) ignorado(s) por não serem CPFs válidos: "
                      f"{', '.join(ignored[:10])}{'...' if len(ignored) > 10 else ''}")

        self._pending_cpf_list = cpf_list
        self._set_busy("Analisando contratos...")
        self._log(f"Consultando contratos para {len(cpf_list)} CPF(s) na conexão '{selected_connection}'...")

        self._worker = Bat223PreviewWorker(cpf_list, selected_connection)
        self._worker.finished.connect(self._on_preview_done)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    # ── passo 2: exibir preview e pedir confirmação ───────────────────────────

    def _on_preview_done(self, counts):
        self._log(
            f"Preview: {counts['movel']} Móvel + {counts['bl']} BL "
            f"= {counts['total']} contratos encontrados."
        )

        if counts['total'] == 0:
            QMessageBox.information(self, "Nenhum Contrato",
                                    "Nenhum contrato MOVEL ou BL foi encontrado para os CPFs informados.\n"
                                    "Verifique se os CPFs estão cadastrados com o campo TAX_IDEN_NUM preenchido.")
            self._set_idle()
            return

        selected_connection = self.connection_combo.currentText()
        msg = (
            f"Foram encontrados <b>{counts['total']}</b> contratos para marcar:\n\n"
            f"  • Móvel (ROOT S_ASSET): <b>{counts['movel']}</b>\n"
            f"  • Banda Larga (SUB_ACESSO S_ASSET): <b>{counts['bl']}</b>\n\n"
            f"Conexão: <b>{selected_connection}</b>\n\n"
            f"Esta ação irá atualizar LAST_UPD em produção.\n\n"
            f"Deseja continuar?"
        )
        reply = QMessageBox.question(self, "Confirmar Marcação", msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            self._log("Operação cancelada pelo usuário.")
            self._set_idle()
            return

        # ── passo 3: executar ─────────────────────────────────────────────
        self._set_busy("Marcando contratos...")
        self._log("Iniciando atualização de LAST_UPD...")
        self._worker = Bat223ExecutionWorker(self._pending_cpf_list, selected_connection)
        self._worker.finished.connect(self._on_execution_done)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    # ── passo 3 resultado ────────────────────────────────────────────────────

    def _on_execution_done(self, log_text):
        self.log_output.append("\n--- LOG DETALHADO ---\n")
        self.log_output.append(log_text)
        self.log_output.append("\n--- PROCESSO FINALIZADO ---")
        QMessageBox.information(self, "Concluído",
                                "Contratos marcados com sucesso para a próxima extração BAT223.\n"
                                "Verifique o log para detalhes.")
        self._set_idle()

    def _on_worker_error(self, error_message):
        self.log_output.append(f"\n--- ERRO ---\n{error_message}")
        QMessageBox.critical(self, "Erro na Operação", error_message)
        self._set_idle()

    def _on_clear(self):
        self.cpf_input.clear()
        self.log_output.clear()
        self._log("Campos limpos.")
