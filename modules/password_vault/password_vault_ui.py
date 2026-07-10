import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialog, QFormLayout, QComboBox,
    QTextEdit, QMessageBox, QAbstractItemView, QFrame,
    QSizePolicy, QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from modules.password_vault import password_vault_logic as logic

logger = logging.getLogger(__name__)

CREDENTIAL_TYPES = [
    "Site / URL",
    "Servidor SSH / RDP",
    "Banco de Dados",
    "VPN / Rede",
    "Outro",
]

# Índices das colunas
COL_NAME        = 0
COL_TYPE        = 1
COL_HOST        = 2
COL_PORT        = 3
COL_SERVICE     = 4
COL_USERNAME    = 5
COL_PASSWORD    = 6
COL_DESCRIPTION = 7
COL_ACTIONS     = 8

COL_HEADERS = [
    "Nome",
    "Tipo",
    "Host / URL",
    "Porta",
    "Serviço / BD",
    "Usuário",
    "Senha",
    "Descrição",
    "Ações",
]

# Mapa de cores por tipo de credencial
TYPE_COLORS = {
    "Site / URL":         ("#1a6b3a", "#2ecc71"),   # verde
    "Servidor SSH / RDP": ("#1a3a6b", "#3498db"),   # azul
    "Banco de Dados":     ("#6b3a1a", "#e67e22"),   # laranja
    "VPN / Rede":         ("#4a1a6b", "#9b59b6"),   # roxo
    "Outro":              ("#3a3a3a", "#95a5a6"),   # cinza
}


# ---------------------------------------------------------------------------
# Widget da célula de senha — exibe bolinhas e tem botão de olho
# ---------------------------------------------------------------------------
class PasswordCellWidget(QWidget):
    def __init__(self, password_plain: str, parent=None):
        super().__init__(parent)
        self._password = password_plain
        self._visible = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 4, 0)
        layout.setSpacing(4)

        self.label = QLabel("●●●●●●●●")
        self.label.setFont(QFont("Consolas", 9))
        self.label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.label, 1)

        self.toggle_btn = QPushButton("👁")
        self.toggle_btn.setFixedSize(30, 26)
        self.toggle_btn.setToolTip("Mostrar / Ocultar senha")
        self.toggle_btn.setFlat(True)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)

    def _toggle(self):
        self._visible = not self._visible
        if self._visible:
            self.label.setText(self._password if self._password else "(vazio)")
            self.label.setFont(QFont("Consolas", 9))
            self.toggle_btn.setText("🙈")
        else:
            self.label.setText("●●●●●●●●")
            self.label.setFont(QFont("Consolas", 9))
            self.toggle_btn.setText("👁")

    def update_password(self, password_plain: str):
        self._password = password_plain
        self._visible = False
        self.label.setText("●●●●●●●●")
        self.toggle_btn.setText("👁")


# ---------------------------------------------------------------------------
# Widget da célula de ações — copiar usuário, copiar senha, editar, excluir
# ---------------------------------------------------------------------------
class ActionCellWidget(QWidget):
    copy_user_requested = pyqtSignal(str)
    copy_pass_requested = pyqtSignal(str)
    edit_requested      = pyqtSignal(str)
    delete_requested    = pyqtSignal(str)

    def __init__(self, entry_id: str, parent=None):
        super().__init__(parent)
        self.entry_id = entry_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(3)

        btn_cfg = [
            ("👤", "Copiar usuário",         self.copy_user_requested, "#2980b9"),
            ("🔑", "Copiar senha",            self.copy_pass_requested, "#27ae60"),
            ("✏",  "Editar acesso",           self.edit_requested,      "#f39c12"),
            ("✕",  "Excluir acesso",          self.delete_requested,    "#e74c3c"),
        ]
        for text, tooltip, signal, color in btn_cfg:
            btn = QPushButton(text)
            btn.setFixedSize(32, 28)
            btn.setToolTip(tooltip)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ color: {color}; font-size: 14px; border-radius: 4px; }}"
                f"QPushButton:hover {{ background-color: rgba(255,255,255,0.12); }}"
            )
            btn.clicked.connect(lambda _, s=signal: s.emit(self.entry_id))
            layout.addWidget(btn)


# ---------------------------------------------------------------------------
# Diálogo de adição / edição de credencial
# ---------------------------------------------------------------------------
class CredentialDialog(QDialog):
    def __init__(self, parent=None, entry: dict = None):
        super().__init__(parent)
        self.entry = entry
        self.is_edit = entry is not None
        self.setWindowTitle("Editar Acesso" if self.is_edit else "Novo Acesso")
        self.setMinimumWidth(520)
        self.setModal(True)
        self._setup_ui()
        if self.is_edit:
            self._populate_fields()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Título
        title = QLabel("Editar Acesso" if self.is_edit else "Novo Acesso")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Nome
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Ex: Oracle Produção, SSH Gateway, Portal RH...")
        form.addRow("Nome *:", self.name_edit)

        # Tipo
        self.type_combo = QComboBox()
        self.type_combo.addItems(CREDENTIAL_TYPES)
        form.addRow("Tipo *:", self.type_combo)

        # Host / URL
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("Ex: 192.168.1.1  ou  https://portal.empresa.com")
        form.addRow("Host / URL:", self.host_edit)

        # Porta
        self.port_edit = QLineEdit()
        self.port_edit.setPlaceholderText("Ex: 1521, 22, 3389, 443")
        self.port_edit.setMaximumWidth(120)
        form.addRow("Porta:", self.port_edit)

        # Serviço / BD
        self.service_edit = QLineEdit()
        self.service_edit.setPlaceholderText("Ex: ORCL, mydb, service_name (Oracle/Postgres)")
        form.addRow("Serviço / BD:", self.service_edit)

        # Usuário
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Login / usuário")
        form.addRow("Usuário *:", self.username_edit)

        # Senha com botão olho
        pwd_container = QWidget()
        pwd_layout = QHBoxLayout(pwd_container)
        pwd_layout.setContentsMargins(0, 0, 0, 0)
        pwd_layout.setSpacing(4)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText(
            "Deixe em branco para manter a senha atual" if self.is_edit else "Senha"
        )
        pwd_layout.addWidget(self.password_edit)

        self.show_pwd_btn = QPushButton("👁")
        self.show_pwd_btn.setFixedSize(36, 32)
        self.show_pwd_btn.setCheckable(True)
        self.show_pwd_btn.setToolTip("Mostrar / Ocultar")
        self.show_pwd_btn.toggled.connect(
            lambda checked: self.password_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        pwd_layout.addWidget(self.show_pwd_btn)
        form.addRow("Senha:", pwd_container)

        # Descrição
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(72)
        self.description_edit.setPlaceholderText("Notas, observações, tags...")
        form.addRow("Descrição:", self.description_edit)

        layout.addLayout(form)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        # Botões
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setMinimumWidth(90)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("  💾  Salvar  ")
        save_btn.setMinimumWidth(110)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _populate_fields(self):
        e = self.entry
        self.name_edit.setText(e.get("name", ""))
        idx = self.type_combo.findText(e.get("type", ""))
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.host_edit.setText(e.get("host", ""))
        self.port_edit.setText(e.get("port", ""))
        self.service_edit.setText(e.get("service_name", ""))
        self.username_edit.setText(e.get("username", ""))
        self.description_edit.setPlainText(e.get("description", ""))
        # senha não é pré-preenchida por segurança

    def _save(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Campo obrigatório", "O campo 'Nome' é obrigatório.")
            self.name_edit.setFocus()
            return
        if not self.username_edit.text().strip() and not self.is_edit:
            QMessageBox.warning(self, "Campo obrigatório", "O campo 'Usuário' é obrigatório.")
            self.username_edit.setFocus()
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "name":         self.name_edit.text().strip(),
            "type":         self.type_combo.currentText(),
            "host":         self.host_edit.text().strip(),
            "port":         self.port_edit.text().strip(),
            "service_name": self.service_edit.text().strip(),
            "username":     self.username_edit.text().strip(),
            "password":     self.password_edit.text(),
            "description":  self.description_edit.toPlainText().strip(),
        }


# ---------------------------------------------------------------------------
# Widget principal — Cofre de Senhas
# ---------------------------------------------------------------------------
class PasswordVaultWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = []
        self._filtered = []
        self._decrypted_cache: dict[str, str] = {}
        self._setup_ui()
        self.load_data()

    # ------------------------------------------------------------------
    # Construção da UI
    # ------------------------------------------------------------------
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # ---- Cabeçalho -----------------------------------------------
        header_layout = QHBoxLayout()

        icon_lbl = QLabel("🔐")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 20))
        header_layout.addWidget(icon_lbl)

        title_lbl = QLabel("Cofre de Senhas")
        title_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        self.add_btn = QPushButton("  +  Novo Acesso  ")
        self.add_btn.setMinimumHeight(34)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self._add_entry)
        header_layout.addWidget(self.add_btn)

        root.addLayout(header_layout)

        # ---- Barra de pesquisa ----------------------------------------
        search_frame = QFrame()
        search_frame.setFrameShape(QFrame.Shape.StyledPanel)
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(8, 4, 8, 4)
        search_layout.setSpacing(6)

        lupa = QLabel("🔍")
        lupa.setFont(QFont("Segoe UI Emoji", 11))
        search_layout.addWidget(lupa)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Pesquisar por nome, host, usuário, tipo, serviço, descrição..."
        )
        self.search_edit.setFrame(False)
        self.search_edit.textChanged.connect(self._filter_table)
        search_layout.addWidget(self.search_edit, 1)

        clear_btn = QPushButton("✕")
        clear_btn.setFixedSize(24, 24)
        clear_btn.setFlat(True)
        clear_btn.setToolTip("Limpar pesquisa")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self.search_edit.clear)
        search_layout.addWidget(clear_btn)

        root.addWidget(search_frame)

        # ---- Tabela ---------------------------------------------------
        self.table = QTableWidget()
        self.table.setColumnCount(len(COL_HEADERS))
        self.table.setHorizontalHeaderLabels(COL_HEADERS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Larguras das colunas
        header.setSectionResizeMode(COL_NAME,        QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_TYPE,        QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_TYPE, 145)
        header.setSectionResizeMode(COL_HOST,        QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_PORT,        QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_PORT, 65)
        header.setSectionResizeMode(COL_SERVICE,     QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_SERVICE, 120)
        header.setSectionResizeMode(COL_USERNAME,    QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_USERNAME, 150)
        header.setSectionResizeMode(COL_PASSWORD,    QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_PASSWORD, 180)
        header.setSectionResizeMode(COL_DESCRIPTION, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_ACTIONS,     QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_ACTIONS, 148)

        root.addWidget(self.table, 1)

        # ---- Rodapé ---------------------------------------------------
        footer = QHBoxLayout()
        self.status_label = QLabel("Pronto.")
        self.status_label.setStyleSheet("color: gray; font-size: 11px;")
        footer.addWidget(self.status_label)
        footer.addStretch()
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: gray; font-size: 11px;")
        footer.addWidget(self.count_label)
        root.addLayout(footer)

    # ------------------------------------------------------------------
    # Carga e exibição de dados
    # ------------------------------------------------------------------
    def load_data(self):
        self._entries = logic.load_vault()
        self._decrypted_cache = {}
        for entry in self._entries:
            try:
                self._decrypted_cache[entry['id']] = logic.get_decrypted_password(entry)
            except Exception as e:
                self._decrypted_cache[entry['id']] = ""
                logger.error(f"Erro ao descriptografar id={entry['id']}: {e}")

        # Reaplica filtro atual (se houver)
        self._filter_table(self.search_edit.text())

    def _populate_table(self, entries: list):
        self.table.setRowCount(0)
        for entry in entries:
            self._add_table_row(entry)
        total = len(self._entries)
        shown = len(entries)
        self.count_label.setText(
            f"{shown} de {total} acesso(s)" if shown != total else f"{total} acesso(s)"
        )

    def _add_table_row(self, entry: dict):
        row = self.table.rowCount()
        self.table.insertRow(row)
        entry_id = entry['id']
        entry_type = entry.get('type', '')

        def make_item(text, align=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft):
            item = QTableWidgetItem(str(text) if text else "")
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            item.setTextAlignment(align)
            return item

        self.table.setItem(row, COL_NAME,    make_item(entry.get('name', '')))
        self.table.setItem(row, COL_PORT,    make_item(entry.get('port', ''), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter))
        self.table.setItem(row, COL_HOST,    make_item(entry.get('host', '')))
        self.table.setItem(row, COL_SERVICE, make_item(entry.get('service_name', '')))
        self.table.setItem(row, COL_USERNAME, make_item(entry.get('username', '')))

        # Tipo com badge colorido
        type_item = make_item(f"  {entry_type}")
        dark_bg, accent = TYPE_COLORS.get(entry_type, ("#3a3a3a", "#95a5a6"))
        type_item.setForeground(QColor(accent))
        self.table.setItem(row, COL_TYPE, type_item)

        # Descrição com tooltip
        desc = entry.get('description', '')
        desc_item = make_item(desc)
        if desc:
            desc_item.setToolTip(desc)
        self.table.setItem(row, COL_DESCRIPTION, desc_item)

        # Célula de senha
        pwd_widget = PasswordCellWidget(self._decrypted_cache.get(entry_id, ''))
        self.table.setCellWidget(row, COL_PASSWORD, pwd_widget)

        # Célula de ações
        action_widget = ActionCellWidget(entry_id)
        action_widget.copy_user_requested.connect(self._copy_username)
        action_widget.copy_pass_requested.connect(self._copy_password)
        action_widget.edit_requested.connect(self._edit_entry)
        action_widget.delete_requested.connect(self._delete_entry)
        self.table.setCellWidget(row, COL_ACTIONS, action_widget)

    # ------------------------------------------------------------------
    # Pesquisa / filtro
    # ------------------------------------------------------------------
    def _filter_table(self, query: str):
        if query.strip():
            q = query.lower()
            self._filtered = [
                e for e in self._entries
                if q in " ".join([
                    e.get('name', ''), e.get('type', ''), e.get('host', ''),
                    e.get('username', ''), e.get('service_name', ''),
                    e.get('description', ''), e.get('port', ''),
                ]).lower()
            ]
        else:
            self._filtered = list(self._entries)
        self._populate_table(self._filtered)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_entry(self, entry_id: str) -> dict | None:
        return next((e for e in self._entries if e['id'] == entry_id), None)

    def _show_status(self, msg: str):
        self.status_label.setText(msg)

    # ------------------------------------------------------------------
    # Ações CRUD
    # ------------------------------------------------------------------
    def _add_entry(self):
        dialog = CredentialDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            d = dialog.get_data()
            logic.add_entry(
                d['name'], d['type'], d['description'],
                d['host'], d['port'], d['service_name'],
                d['username'], d['password'],
            )
            self.load_data()
            self._show_status(f"✓ Acesso '{d['name']}' adicionado com sucesso.")

    def _edit_entry(self, entry_id: str):
        entry = self._get_entry(entry_id)
        if not entry:
            return
        dialog = CredentialDialog(self, entry=entry)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            d = dialog.get_data()
            logic.update_entry(
                entry_id, d['name'], d['type'], d['description'],
                d['host'], d['port'], d['service_name'],
                d['username'], d['password'],
            )
            self.load_data()
            self._show_status(f"✓ Acesso '{d['name']}' atualizado.")

    def _delete_entry(self, entry_id: str):
        entry = self._get_entry(entry_id)
        if not entry:
            return
        name = entry.get('name', '')
        reply = QMessageBox.question(
            self,
            "Confirmar Exclusão",
            f"Deseja realmente excluir o acesso <b>{name}</b>?<br><br>"
            "Esta ação <b>não pode ser desfeita</b>.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            logic.delete_entry(entry_id)
            self.load_data()
            self._show_status(f"Acesso '{name}' excluído.")

    def _copy_username(self, entry_id: str):
        entry = self._get_entry(entry_id)
        if entry:
            QApplication.clipboard().setText(entry.get('username', ''))
            self._show_status(f"✓ Usuário de '{entry.get('name', '')}' copiado para a área de transferência.")

    def _copy_password(self, entry_id: str):
        password = self._decrypted_cache.get(entry_id, '')
        entry = self._get_entry(entry_id)
        QApplication.clipboard().setText(password)
        name = entry.get('name', '') if entry else ''
        self._show_status(f"✓ Senha de '{name}' copiada para a área de transferência.")
