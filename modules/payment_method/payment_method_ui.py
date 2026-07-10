# C:\Meus Projetos\MyOps\modules\payment_method\payment_method_ui.py

import os
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton,
    QMessageBox, QLineEdit, QLabel, QGroupBox, QComboBox, QTextEdit, QFileDialog,
    QSpinBox, QDialog, QProgressBar, QRadioButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QButtonGroup, QCheckBox
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDateTime

from modules.payment_method import payment_method_logic as db


class DropArea(QLabel):
    """Área de arrastar-e-soltar para o arquivo de entrada."""
    fileDropped = pyqtSignal(str)

    def __init__(self, text="Arraste e solte o arquivo (.txt/.csv) aqui"):
        super().__init__(text)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("QLabel { border: 2px dashed #aaa; border-radius: 5px; font: 11pt; color: #888; padding: 8px; }")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and len(event.mimeData().urls()) == 1:
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().urls()[0].isLocalFile():
            self.fileDropped.emit(event.mimeData().urls()[0].toLocalFile())


class LoadingDialog(QDialog):
    """Diálogo modal de 'carregando' exibido enquanto o processo roda."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Processando...")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setFixedSize(420, 130)

        layout = QVBoxLayout(self)
        self.label = QLabel("Iniciando...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)

        layout.addWidget(self.label)
        layout.addWidget(self.progress)

    def set_message(self, message):
        self.label.setText(message)
        QApplication.processEvents()

    # Impede fechar com ESC durante o processamento.
    def reject(self):
        pass


class PrepareWorker(QThread):
    """
    Fase 1 (somente leitura/preparação): cria a tabela temporária, carrega o
    arquivo com o SQL*Loader e monta a tabela filtrada com os candidatos reais.
    NÃO altera nada em S_INV_PROF.
    """
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, file_path, db_key, table_name, operation, file_info):
        super().__init__()
        self.file_path = file_path
        self.db_key = db_key
        self.table_name = table_name
        self.operation = operation
        self.file_info = file_info

    def run(self):
        try:
            self.progress.emit(f"Criando tabela temporária '{self.table_name}'...")
            table_name, schema = db.create_temp_table(self.db_key, self.table_name, self.operation)

            self.progress.emit("Gerando control file e executando o SQL*Loader...")
            ctl_path, data_copy = db.generate_control_file(
                self.file_path, table_name, schema, self.operation,
                self.file_info['delimiter'], self.file_info['skip']
            )
            try:
                log_content, bad_content, exit_code = db.run_sql_loader(self.db_key, ctl_path)
            finally:
                # Remove a cópia temporária de dados (nome ASCII) criada para a carga.
                try:
                    if os.path.exists(data_copy):
                        os.remove(data_copy)
                except OSError:
                    pass

            if exit_code not in (0, 2):
                raise RuntimeError(
                    f"Falha na carga do SQL*Loader (exit code {exit_code}).\n\n{log_content}"
                )

            loaded = db.count_table_rows(self.db_key, table_name)
            self.progress.emit(f"Carga concluída: {loaded} registro(s) carregado(s).")
            if loaded == 0:
                raise RuntimeError("Nenhum registro foi carregado na tabela temporária.")

            self.progress.emit("Identificando clientes que realmente serão alterados...")
            filtered_table, candidates = db.build_filtered_table(
                self.db_key, table_name, self.operation
            )

            self.finished.emit({
                'table_name': table_name,
                'filtered_table': filtered_table,
                'schema': schema,
                'loaded': loaded,
                'candidates': candidates,
                'skipped': loaded - candidates,
                'log_content': log_content,
                'bad_content': bad_content,
            })
        except Exception as e:
            self.error.emit(str(e))


class UpdateWorker(QThread):
    """Fase 2: executa a alteração de fato sobre a tabela filtrada."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, db_key, filtered_table, operation, batch_size, sleep_seconds, notify):
        super().__init__()
        self.db_key = db_key
        self.filtered_table = filtered_table
        self.operation = operation
        self.batch_size = batch_size
        self.sleep_seconds = sleep_seconds
        self.notify = notify

    def run(self):
        try:
            self.progress.emit("Executando a alteração do método de pagamento em produção...")
            updated = db.run_payment_update(
                self.db_key, self.filtered_table, self.operation,
                self.batch_size, self.sleep_seconds, self.notify
            )
            self.finished.emit(updated)
        except Exception as e:
            self.error.emit(str(e))


class PaymentMethodWidget(QWidget):
    # Rótulos das operações
    OP_LABELS = {
        db.OP_FATURA: "Débito Automático → Fatura",
        db.OP_DACC: "Fatura → Débito Automático (DACC)",
    }

    def __init__(self):
        super().__init__()
        self.prepare_worker = None
        self.update_worker = None
        self.loading_dialog = None
        self.selected_file_path = ""
        self.file_info = None
        self.prepared = None  # resultado da fase de preparação

        main_layout = QVBoxLayout(self)

        # --- Grupo 1: Arquivo de entrada + preview ---
        group1 = QGroupBox("1. Arquivo de Entrada")
        layout1 = QVBoxLayout(group1)

        top_row = QHBoxLayout()
        self.drop_area = DropArea()
        self.drop_area.setMinimumHeight(70)
        self.browse_button = QPushButton("Selecionar Arquivo...")
        top_row.addWidget(self.drop_area, 1)
        top_row.addWidget(self.browse_button)
        layout1.addLayout(top_row)

        self.file_info_label = QLabel("Nenhum arquivo carregado.")
        self.file_info_label.setStyleSheet("color: #888;")
        layout1.addWidget(self.file_info_label)

        self.preview_table = QTableWidget()
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setMinimumHeight(140)
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout1.addWidget(QLabel("Preview (amostra):"))
        layout1.addWidget(self.preview_table)
        main_layout.addWidget(group1, 1)

        # --- Grupo 2: Operação ---
        group2 = QGroupBox("2. Operação")
        layout2 = QVBoxLayout(group2)
        self.op_group = QButtonGroup(self)
        self.rb_fatura = QRadioButton(self.OP_LABELS[db.OP_FATURA]
                                      + "  (arquivo só com customer_id)")
        self.rb_dacc = QRadioButton(self.OP_LABELS[db.OP_DACC]
                                    + "  (arquivo com banco, agência e conta)")
        self.op_group.addButton(self.rb_fatura, 0)
        self.op_group.addButton(self.rb_dacc, 1)
        self.rb_fatura.setChecked(True)
        layout2.addWidget(self.rb_fatura)
        layout2.addWidget(self.rb_dacc)
        self.op_hint = QLabel("")
        self.op_hint.setStyleSheet("color: #c0392b;")
        self.op_hint.setWordWrap(True)
        layout2.addWidget(self.op_hint)
        main_layout.addWidget(group2)

        # --- Grupo 3: Configurações da execução ---
        group3 = QGroupBox("3. Configurações da Execução")
        layout3 = QFormLayout(group3)

        self.db_combo = QComboBox()

        default_table = "PM_TMP_PAY_" + datetime.now().strftime("%d%m%y_%H%M%S")
        self.table_input = QLineEdit(default_table)
        self.table_input.setPlaceholderText("Deve começar com PM_TMP")

        self.batch_input = QSpinBox()
        self.batch_input.setRange(1, 1000000)
        self.batch_input.setValue(1000)

        self.sleep_input = QSpinBox()
        self.sleep_input.setRange(0, 3600)
        self.sleep_input.setValue(20)
        self.sleep_input.setSuffix(" s")

        self.notify_check = QCheckBox(
            "Disparar notificação para BSCS e RMCA "
            "(seta x_tim_eai_status='Pendente' e X_TIM_PAYMENT_CHANGE='Y')"
        )
        self.notify_check.setChecked(False)  # default: Não

        layout3.addRow("Base de Dados (Siebel Pós):", self.db_combo)
        layout3.addRow("Tabela Temporária:", self.table_input)
        layout3.addRow("Clientes por Lote (COMMIT):", self.batch_input)
        layout3.addRow("Duração do Sleep:", self.sleep_input)
        layout3.addRow("Notificação:", self.notify_check)
        main_layout.addWidget(group3)

        # Botão de execução
        self.run_button = QPushButton("Carregar, Analisar e Alterar Método de Pagamento")
        self.run_button.setMinimumHeight(40)
        main_layout.addWidget(self.run_button)

        # --- Grupo 4: Log ---
        group4 = QGroupBox("4. Log e Resultados")
        layout4 = QVBoxLayout(group4)
        self.log_output = QTextEdit(readOnly=True)
        self.log_output.setFont(QFont("Courier", 9))
        layout4.addWidget(self.log_output)
        main_layout.addWidget(group4, 1)

        # Conexões e sinais
        self.populate_db_combo()
        self.browse_button.clicked.connect(self.on_browse)
        self.drop_area.fileDropped.connect(self.on_file_selected)
        self.run_button.clicked.connect(self.on_run)

    # --- Conexões ---
    def populate_db_combo(self):
        try:
            connections = db.get_all_db_connections()
            for key, name in connections.items():
                self.db_combo.addItem(name, key)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível carregar as conexões do config.ini:\n{e}")

    def log_message(self, message):
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        self.log_output.append(f"[{timestamp}] {message}")

    # --- Seleção / análise de arquivo ---
    def on_browse(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Selecione o arquivo de entrada", "",
            "TXT e CSV (*.txt *.csv);;Todos os Arquivos (*)"
        )
        if file_path:
            self.on_file_selected(file_path)

    def on_file_selected(self, file_path):
        self.selected_file_path = file_path
        self.drop_area.setText(f"Arquivo Selecionado:\n{os.path.basename(file_path)}")
        try:
            self.file_info = db.analyze_file(file_path)
        except Exception as e:
            self.file_info = None
            self.file_info_label.setText("")
            self.preview_table.clear()
            self.preview_table.setRowCount(0)
            QMessageBox.critical(self, "Erro ao ler arquivo", str(e))
            return

        self._populate_preview(self.file_info)
        self._apply_operation_rules(self.file_info)

    def _populate_preview(self, info):
        headers = info['headers']
        rows = info['rows']
        self.preview_table.clear()
        self.preview_table.setColumnCount(len(headers))
        self.preview_table.setHorizontalHeaderLabels(headers)
        self.preview_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c in range(len(headers)):
                value = row[c] if c < len(row) else ""
                self.preview_table.setItem(r, c, QTableWidgetItem(value))

        delim = {';': "ponto-e-vírgula", ',': "vírgula", '\t': "tabulação",
                 '|': "pipe"}.get(info['delimiter'], "coluna única")
        self.file_info_label.setText(
            f"{info['total_rows']} linha(s) de dados • {info['column_count']} coluna(s) • "
            f"delimitador: {delim} • cabeçalho: {'sim' if info['has_header'] else 'não'}"
        )
        self.file_info_label.setStyleSheet("color: #2980b9;")

    def _apply_operation_rules(self, info):
        """Libera/bloqueia a opção DACC conforme o conteúdo do arquivo."""
        if info['dacc_capable']:
            self.rb_dacc.setEnabled(True)
            self.rb_dacc.setChecked(True)
            self.op_hint.setText("")
        else:
            self.rb_dacc.setEnabled(False)
            self.rb_fatura.setChecked(True)
            self.op_hint.setText(
                "O arquivo possui apenas o customer_id. A opção "
                "\"Fatura → Débito Automático (DACC)\" está desabilitada, pois "
                "não há dados bancários (banco, agência e conta) no arquivo."
            )

    def _current_operation(self):
        return db.OP_DACC if self.rb_dacc.isChecked() else db.OP_FATURA

    # --- Execução ---
    def on_run(self):
        db_key = self.db_combo.currentData()
        table_name = self.table_input.text().strip()

        if not self.selected_file_path or not self.file_info:
            QMessageBox.warning(self, "Campos Incompletos", "Selecione um arquivo de entrada válido.")
            return
        if not db_key:
            QMessageBox.warning(self, "Campos Incompletos", "Selecione a base de dados.")
            return

        operation = self._current_operation()
        if operation == db.OP_DACC and not self.file_info['dacc_capable']:
            QMessageBox.warning(self, "Operação Inválida",
                                "O arquivo não possui dados bancários para a operação DACC.")
            return

        try:
            table_name = db.validate_table_name(table_name)
        except ValueError as e:
            QMessageBox.critical(self, "Erro de Validação", str(e))
            return

        from_m = db.FROM_METHOD[operation]
        to_m = db.TO_METHOD[operation]
        reply = QMessageBox.question(
            self, "Confirmação — Etapa 1/2 (Preparação)",
            f"Será feita a carga do arquivo e a análise dos clientes.\n"
            f"Nenhuma alteração é feita nesta etapa.\n\n"
            f"- Operação: {self.OP_LABELS[operation]}\n"
            f"  ({from_m}  →  {to_m})\n"
            f"- Conexão: {self.db_combo.currentText()}\n"
            f"- Arquivo: {os.path.basename(self.selected_file_path)}\n"
            f"- Linhas no arquivo: {self.file_info['total_rows']}\n"
            f"- Tabela temporária: {table_name}\n\n"
            "Deseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        self.run_button.setEnabled(False)
        self.log_output.clear()
        self.log_message(f"Iniciando preparação — operação: {self.OP_LABELS[operation]}")

        self.loading_dialog = LoadingDialog(self)
        self.loading_dialog.set_message("Iniciando...")

        self.prepare_worker = PrepareWorker(
            self.selected_file_path, db_key, table_name, operation, self.file_info
        )
        self.prepare_worker.progress.connect(self.on_progress)
        self.prepare_worker.finished.connect(self.on_prepared)
        self.prepare_worker.error.connect(self.on_error)
        self.prepare_worker.start()
        self.loading_dialog.exec()

    def on_progress(self, message):
        self.log_message(message)
        if self.loading_dialog:
            self.loading_dialog.set_message(message)

    def _close_loading(self):
        if self.loading_dialog:
            self.loading_dialog.done(0)
            self.loading_dialog = None

    def on_prepared(self, result):
        self._close_loading()
        self.prepared = result
        operation = self._current_operation()
        from_m = db.FROM_METHOD[operation]
        to_m = db.TO_METHOD[operation]

        self.log_message(
            f"Preparação concluída: {result['loaded']} carregado(s), "
            f"{result['candidates']} candidato(s), {result['skipped']} ignorado(s)."
        )

        if result['candidates'] == 0:
            QMessageBox.information(
                self, "Nada a Alterar",
                "Nenhum cliente do arquivo está no estado de origem esperado "
                f"('{from_m}'). Nada será alterado."
            )
            db.drop_temp_tables(self.db_combo.currentData(),
                                result['table_name'], result['filtered_table'])
            self.run_button.setEnabled(True)
            return

        db_key = self.db_combo.currentData()
        batch_size = self.batch_input.value()
        sleep_seconds = self.sleep_input.value()
        notify = self.notify_check.isChecked()

        reply = QMessageBox.warning(
            self, "Confirmação — Etapa 2/2 (ALTERAÇÃO EM PRODUÇÃO)",
            f"A carga e a análise foram concluídas.\n\n"
            f"RESUMO DA PRÉ-ANÁLISE\n"
            f"- Operação: {self.OP_LABELS[operation]}  ({from_m} → {to_m})\n"
            f"- Registros no arquivo: {result['loaded']}\n"
            f"- Serão ALTERADOS (estão em '{from_m}'): {result['candidates']}\n"
            f"- Serão IGNORADOS (fora do estado de origem): {result['skipped']}\n"
            f"- Lote (COMMIT): {batch_size}  •  Sleep entre lotes: {sleep_seconds}s\n"
            f"- Notificar BSCS/RMCA: {'SIM' if notify else 'NÃO'}\n\n"
            f"Esta ação executará UPDATE/INSERT em PRODUÇÃO sobre "
            f"{result['candidates']} cliente(s).\n\nDeseja DISPARAR a alteração agora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            self.log_message("Alteração cancelada pelo usuário após a pré-análise.")
            db.drop_temp_tables(db_key, result['table_name'], result['filtered_table'])
            self.run_button.setEnabled(True)
            return

        self.loading_dialog = LoadingDialog(self)
        self.loading_dialog.set_message("Executando alteração...")
        self.update_worker = UpdateWorker(
            db_key, result['filtered_table'], operation, batch_size, sleep_seconds, notify
        )
        self.update_worker.progress.connect(self.on_progress)
        self.update_worker.finished.connect(self.on_update_finished)
        self.update_worker.error.connect(self.on_error)
        self.update_worker.start()
        self.loading_dialog.exec()

    def on_update_finished(self, updated):
        self._close_loading()
        result = self.prepared
        operation = self._current_operation()
        db_key = self.db_combo.currentData()

        notify = self.notify_check.isChecked()
        summary = (
            "=== RESUMO DA ALTERAÇÃO ===\n"
            f"Operação................: {self.OP_LABELS[operation]}\n"
            f"De......................: {db.FROM_METHOD[operation]}\n"
            f"Para....................: {db.TO_METHOD[operation]}\n"
            f"Registros no arquivo....: {result['loaded']}\n"
            f"Candidatos (pré-análise): {result['candidates']}\n"
            f"Ignorados...............: {result['skipped']}\n"
            f"Linhas ATUALIZADAS......: {updated}\n"
            f"Notificar BSCS/RMCA.....: {'SIM' if notify else 'NÃO'}\n"
            f"Histórico gravado em....: ACC_SBL_WA_DACC_HIST\n"
        )
        if result.get('bad_content'):
            summary += f"\n--- REGISTROS REJEITADOS (.bad) ---\n{result['bad_content']}\n"

        self.log_output.append("\n" + summary)
        self.log_output.append(
            "--- QUERY DE CONFERÊNCIA (copie e execute na base) ---\n"
            + db.VERIFY_QUERY + "\n"
        )
        self.log_message("Removendo tabelas temporárias...")
        db.drop_temp_tables(db_key, result['table_name'], result['filtered_table'])

        QMessageBox.information(
            self, "Processo Concluído",
            f"Alteração concluída com sucesso.\n\n"
            f"{updated} cliente(s) alterado(s) de '{db.FROM_METHOD[operation]}' "
            f"para '{db.TO_METHOD[operation]}'."
        )
        self.run_button.setEnabled(True)

    def on_error(self, error_message):
        self._close_loading()
        self.log_output.append(f"\n--- ERRO NA EXECUÇÃO ---\n{error_message}")
        QMessageBox.critical(self, "Erro na Operação", error_message)
        self.run_button.setEnabled(True)
