# C:\Meus Projetos\MyOps\modules\change_manager\change_manager_ui.py

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QTextEdit, QFileDialog, QMessageBox, QFormLayout, QSplitter,
    QAbstractItemView, QMenu, QDateTimeEdit
)
from PyQt6.QtGui import QFont, QColor, QDesktopServices
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QDateTime
from modules.change_manager import change_manager_logic as logic


STATUS_COLORS = {
    "Planejada": "#3498db",
    "Em Aprovacao": "#f39c12",
    "Aprovada": "#2ecc71",
    "Em Execucao": "#e67e22",
    "Concluida": "#27ae60",
    "Cancelada": "#e74c3c",
    "Rollback": "#c0392b",
}


class FileDropArea(QLabel):
    filesDropped = pyqtSignal(list)

    def __init__(self, text="Arraste e solte arquivos aqui\n(Evidencias, Change Form, Certificados, etc.)"):
        super().__init__(text)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(100)
        self.setStyleSheet(
            "QLabel { border: 2px dashed #aaa; border-radius: 8px; "
            "font: 11pt; color: #888; padding: 15px; }"
        )

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(
                "QLabel { border: 2px dashed #3498db; border-radius: 8px; "
                "font: 11pt; color: #3498db; padding: 15px; background: rgba(52,152,219,0.05); }"
            )

    def dragLeaveEvent(self, event):
        self.setStyleSheet(
            "QLabel { border: 2px dashed #aaa; border-radius: 8px; "
            "font: 11pt; color: #888; padding: 15px; }"
        )

    def dropEvent(self, event):
        self.setStyleSheet(
            "QLabel { border: 2px dashed #aaa; border-radius: 8px; "
            "font: 11pt; color: #888; padding: 15px; }"
        )
        paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                paths.append(url.toLocalFile())
        if paths:
            self.filesDropped.emit(paths)


class ChangeManagerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._current_change_id = None
        self._init_ui()
        self._refresh_table()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # ===== LEFT PANEL: List of Changes =====
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 5, 0)

        # Search bar
        search_group = QGroupBox("Pesquisar Changes")
        search_layout = QHBoxLayout(search_group)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por numero, nome, descricao, responsavel...")
        self.search_input.setClearButtonEnabled(True)
        search_layout.addWidget(self.search_input)
        left_layout.addWidget(search_group)

        # Action buttons
        btn_layout = QHBoxLayout()
        self.btn_new = QPushButton("Nova Change")
        self.btn_new.setMinimumHeight(35)
        self.btn_delete = QPushButton("Excluir")
        self.btn_delete.setMinimumHeight(35)
        btn_layout.addWidget(self.btn_new)
        btn_layout.addWidget(self.btn_delete)
        left_layout.addLayout(btn_layout)

        # Changes table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Numero", "Nome", "Status", "Data/Hora", "Responsavel"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        left_layout.addWidget(self.table, 1)

        splitter.addWidget(left_panel)

        # ===== RIGHT PANEL: Change Details =====
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 0, 0, 0)

        # Form fields
        form_group = QGroupBox("Detalhes da Change")
        form_layout = QFormLayout(form_group)

        self.field_number = QLineEdit()
        self.field_number.setPlaceholderText("Ex: CHG0012345")
        self.field_name = QLineEdit()
        self.field_name.setPlaceholderText("Titulo da change")
        self.field_status = QComboBox()
        self.field_status.addItems(logic.STATUS_OPTIONS)
        self.field_datetime = QDateTimeEdit()
        self.field_datetime.setCalendarPopup(True)
        self.field_datetime.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.field_datetime.setDateTime(QDateTime.currentDateTime())
        self.field_responsible = QLineEdit()
        self.field_responsible.setPlaceholderText("Nome do responsavel")
        self.field_description = QTextEdit()
        self.field_description.setPlaceholderText("Descricao detalhada da change...")
        self.field_description.setMaximumHeight(120)

        form_layout.addRow("Numero:", self.field_number)
        form_layout.addRow("Nome:", self.field_name)
        form_layout.addRow("Status:", self.field_status)
        form_layout.addRow("Data/Hora:", self.field_datetime)
        form_layout.addRow("Responsavel:", self.field_responsible)
        form_layout.addRow("Descricao:", self.field_description)

        right_layout.addWidget(form_group)

        # Save button
        self.btn_save = QPushButton("Salvar Change")
        self.btn_save.setMinimumHeight(40)
        self.btn_save.setStyleSheet("QPushButton { font-weight: bold; }")
        right_layout.addWidget(self.btn_save)

        # Files section
        files_group = QGroupBox("Arquivos e Evidencias")
        files_layout = QVBoxLayout(files_group)

        self.drop_area = FileDropArea()
        files_layout.addWidget(self.drop_area)

        files_btn_layout = QHBoxLayout()
        self.btn_browse_files = QPushButton("Procurar Arquivos...")
        self.btn_remove_file = QPushButton("Remover Selecionado")
        self.btn_open_file = QPushButton("Abrir Arquivo")
        self.btn_open_folder = QPushButton("Abrir Pasta")
        files_btn_layout.addWidget(self.btn_browse_files)
        files_btn_layout.addWidget(self.btn_open_file)
        files_btn_layout.addWidget(self.btn_remove_file)
        files_btn_layout.addWidget(self.btn_open_folder)
        files_layout.addLayout(files_btn_layout)

        self.files_table = QTableWidget()
        self.files_table.setColumnCount(3)
        self.files_table.setHorizontalHeaderLabels(["Arquivo", "Origem", "Adicionado em"])
        self.files_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.files_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.files_table.horizontalHeader().setStretchLastSection(True)
        self.files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.files_table.verticalHeader().setVisible(False)
        files_layout.addWidget(self.files_table, 1)

        right_layout.addWidget(files_group, 1)

        splitter.addWidget(right_panel)
        splitter.setSizes([450, 550])

        # Connections
        self.search_input.textChanged.connect(self._on_search)
        self.btn_new.clicked.connect(self._on_new)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_save.clicked.connect(self._on_save)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.drop_area.filesDropped.connect(self._on_files_dropped)
        self.btn_browse_files.clicked.connect(self._on_browse_files)
        self.btn_remove_file.clicked.connect(self._on_remove_file)
        self.btn_open_file.clicked.connect(self._on_open_file)
        self.btn_open_folder.clicked.connect(self._on_open_folder)
        self.files_table.doubleClicked.connect(self._on_open_file)

        self._clear_form()

    def _refresh_table(self, query=""):
        changes = logic.search_changes(query) if query else logic.get_all_changes()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for row_idx, c in enumerate(changes):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(c.get('number', '')))
            self.table.setItem(row_idx, 1, QTableWidgetItem(c.get('name', '')))

            status = c.get('status', '')
            status_item = QTableWidgetItem(status)
            color = STATUS_COLORS.get(status)
            if color:
                status_item.setForeground(QColor(color))
                status_item.setFont(QFont(status_item.font().family(), -1, QFont.Weight.Bold))
            self.table.setItem(row_idx, 2, status_item)

            self.table.setItem(row_idx, 3, QTableWidgetItem(c.get('change_datetime', '')))
            self.table.setItem(row_idx, 4, QTableWidgetItem(c.get('responsible', '')))

            # Store change id in first column item
            self.table.item(row_idx, 0).setData(Qt.ItemDataRole.UserRole, c['id'])

        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        # Make Name column stretch
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    def _clear_form(self):
        self._current_change_id = None
        self.field_number.clear()
        self.field_name.clear()
        self.field_status.setCurrentIndex(0)
        self.field_datetime.setDateTime(QDateTime.currentDateTime())
        self.field_responsible.clear()
        self.field_description.clear()
        self.files_table.setRowCount(0)
        self.btn_save.setText("Salvar Change")

    def _load_change_into_form(self, change):
        self._current_change_id = change['id']
        self.field_number.setText(change.get('number', ''))
        self.field_name.setText(change.get('name', ''))

        idx = self.field_status.findText(change.get('status', ''))
        if idx >= 0:
            self.field_status.setCurrentIndex(idx)

        dt_str = change.get('change_datetime', '')
        if dt_str:
            dt = QDateTime.fromString(dt_str, "dd/MM/yyyy HH:mm")
            if dt.isValid():
                self.field_datetime.setDateTime(dt)

        self.field_responsible.setText(change.get('responsible', ''))
        self.field_description.setPlainText(change.get('description', ''))
        self.btn_save.setText("Atualizar Change")

        self._refresh_files_table(change.get('files', []))

    def _refresh_files_table(self, files):
        self.files_table.setRowCount(0)
        for row_idx, f in enumerate(files):
            self.files_table.insertRow(row_idx)
            self.files_table.setItem(row_idx, 0, QTableWidgetItem(f.get('name', '')))
            self.files_table.setItem(row_idx, 1, QTableWidgetItem(f.get('original_path', '')))
            self.files_table.setItem(row_idx, 2, QTableWidgetItem(f.get('added_at', '')))

    def _on_search(self, text):
        self._refresh_table(text)

    def _on_new(self):
        self._clear_form()
        self.table.clearSelection()
        self.field_number.setFocus()

    def _on_delete(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "Selecao Necessaria", "Selecione uma change na tabela para excluir.")
            return

        change_id = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        change_number = self.table.item(rows[0].row(), 0).text()

        reply = QMessageBox.question(
            self, "Confirmar Exclusao",
            f"Tem certeza que deseja excluir a change '{change_number}'?\n\n"
            "Todos os arquivos associados tambem serao removidos.\nEsta acao e irreversivel.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            logic.delete_change(change_id)
            self._clear_form()
            self._refresh_table(self.search_input.text())

    def _on_save(self):
        number = self.field_number.text().strip()
        name = self.field_name.text().strip()

        if not number:
            QMessageBox.warning(self, "Campo Obrigatorio", "O campo 'Numero' e obrigatorio.")
            self.field_number.setFocus()
            return

        change_data = {
            'number': number,
            'name': name,
            'status': self.field_status.currentText(),
            'change_datetime': self.field_datetime.dateTime().toString("dd/MM/yyyy HH:mm"),
            'responsible': self.field_responsible.text().strip(),
            'description': self.field_description.toPlainText().strip(),
        }

        saved_id = logic.save_change(change_data, self._current_change_id)
        self._current_change_id = saved_id
        self.btn_save.setText("Atualizar Change")

        self._refresh_table(self.search_input.text())

        # Re-select the saved change
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == saved_id:
                self.table.selectRow(row)
                break

        QMessageBox.information(self, "Sucesso", f"Change '{number}' salva com sucesso.")

    def _on_selection_changed(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        change_id = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        change = logic.get_change_by_id(change_id)
        if change:
            self._load_change_into_form(change)

    def _on_files_dropped(self, file_paths):
        if self._current_change_id is None:
            QMessageBox.warning(
                self, "Salve Primeiro",
                "Salve a change antes de adicionar arquivos.\n\n"
                "Preencha os dados e clique em 'Salvar Change'."
            )
            return
        logic.add_files_to_change(self._current_change_id, file_paths)
        change = logic.get_change_by_id(self._current_change_id)
        if change:
            self._refresh_files_table(change.get('files', []))

    def _on_browse_files(self):
        if self._current_change_id is None:
            QMessageBox.warning(
                self, "Salve Primeiro",
                "Salve a change antes de adicionar arquivos."
            )
            return
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Selecionar Arquivos", "",
            "Todos os Arquivos (*);;Documentos (*.pdf *.doc *.docx *.xlsx *.xls);;Imagens (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_paths:
            logic.add_files_to_change(self._current_change_id, file_paths)
            change = logic.get_change_by_id(self._current_change_id)
            if change:
                self._refresh_files_table(change.get('files', []))

    def _on_remove_file(self):
        if self._current_change_id is None:
            return
        rows = self.files_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "Selecao Necessaria", "Selecione um arquivo para remover.")
            return
        filename = self.files_table.item(rows[0].row(), 0).text()
        reply = QMessageBox.question(
            self, "Confirmar Remocao",
            f"Remover o arquivo '{filename}' desta change?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            logic.remove_file_from_change(self._current_change_id, filename)
            change = logic.get_change_by_id(self._current_change_id)
            if change:
                self._refresh_files_table(change.get('files', []))

    def _on_open_file(self):
        if self._current_change_id is None:
            return
        rows = self.files_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "Selecao Necessaria", "Selecione um arquivo para abrir.")
            return
        filename = self.files_table.item(rows[0].row(), 0).text()
        file_path = logic.get_file_path(self._current_change_id, filename)
        if os.path.exists(file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        else:
            QMessageBox.warning(self, "Arquivo Nao Encontrado", f"O arquivo '{filename}' nao foi encontrado no disco.")

    def _on_open_folder(self):
        if self._current_change_id is None:
            QMessageBox.warning(self, "Selecao Necessaria", "Selecione uma change primeiro.")
            return
        folder = logic.get_change_files_dir(self._current_change_id)
        if os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        else:
            QMessageBox.information(self, "Pasta Vazia", "Nenhum arquivo foi adicionado a esta change ainda.")
