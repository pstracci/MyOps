# C:\Meus Projetos\MyOps\modules\siebel_bscs\siebel_bscs_ui.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QGroupBox, 
    QFormLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QApplication, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from modules.siebel_bscs import siebel_bscs_logic as logic

class SiebelBscsWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        main_layout = QVBoxLayout(self)
        
        search_group = QGroupBox("Pesquisa")
        search_layout = QHBoxLayout()
        self.connection_combo = QComboBox()
        self.msisdn_input = QLineEdit(placeholderText="Digite o MSISDN (GSM) do cliente")
        self.search_button = QPushButton("Pesquisar"); self.clear_button = QPushButton("Limpar")
        search_layout.addWidget(QLabel("Conexão:")); search_layout.addWidget(self.connection_combo, 1)
        search_layout.addWidget(self.msisdn_input, 2); search_layout.addWidget(self.search_button)
        search_layout.addWidget(self.clear_button); search_group.setLayout(search_layout)
        
        profiles_layout = QHBoxLayout()
        siebel_group = self._create_system_groupbox("SIEBEL")
        self.siebel_profile_labels = self._create_profile_labels_dict()
        self._create_profile_group(siebel_group.layout(), "Dados do Cliente/Contrato", self.siebel_profile_labels)
        
        bscsix_group = self._create_system_groupbox("BSCSIX")
        self.bscsix_profile_labels = self._create_profile_labels_dict()
        self._create_profile_group(bscsix_group.layout(), "Dados do Cliente/Contrato", self.bscsix_profile_labels)
        profiles_layout.addWidget(siebel_group); profiles_layout.addWidget(bscsix_group)

        comparison_group = QGroupBox("Comparativo de Serviços / Assets")
        comparison_layout = QVBoxLayout()
        self.comparison_table = self._create_comparison_table()
        comparison_layout.addWidget(self.comparison_table)
        comparison_group.setLayout(comparison_layout)
        
        main_layout.addWidget(search_group); main_layout.addLayout(profiles_layout)
        main_layout.addWidget(comparison_group)
        
        self.search_button.clicked.connect(self.on_search); self.clear_button.clicked.connect(self.clear_all_fields)
        self.msisdn_input.returnPressed.connect(self.on_search); self._populate_connections_combo()

    def on_search(self):
        msisdn = self.msisdn_input.text().strip(); db_section = self.connection_combo.currentText()
        if not db_section or not msisdn:
            QMessageBox.warning(self, "Atenção", "Selecione uma conexão e informe um MSISDN."); return
        self.clear_all_fields(keep_inputs=True)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            data = logic.get_comparison_data(msisdn, db_section)
            self._populate_siebel_data(data.get("siebel", {}))
            self._populate_bscsix_data(data.get("bscsix", {}))
            self._update_validation_status(data.get("validation", {}))
            self._populate_comparison_table(data.get("comparison", {}))
        except Exception as e:
            QMessageBox.critical(self, "Erro na Consulta", str(e))
        finally:
            QApplication.restoreOverrideCursor()

    def _populate_comparison_table(self, comparison_data):
        self.comparison_table.setSortingEnabled(False)
        self.comparison_table.setRowCount(0)
        colors = {"ok": QColor("#2E4C3E"), "siebel_only": QColor("#5A3E3E"), "bscsix_only": QColor("#5A523E")}
        
        all_items = []
        for item in comparison_data.get("matched", []):
            all_items.append(("✅ OK", item['siebel'], item['bscsix'], colors['ok']))
        for s_asset in comparison_data.get("siebel_only", []):
            all_items.append(("❌ Apenas Siebel", s_asset, None, colors['siebel_only']))
        for b_service in comparison_data.get("bscsix_only", []):
            all_items.append(("⚠️ Apenas BSCSIX", None, b_service, colors['bscsix_only']))
            
        status_order = {"✅ OK": 0, "❌ Apenas Siebel": 1, "⚠️ Apenas BSCSIX": 2}
        all_items.sort(key=lambda x: (
            status_order.get(x[0], 99), 
            (x[1] or x[2] or {}).get('NOME_PRODUTO', (x[1] or x[2] or {}).get('SERVICO', ''))
        ))

        for status, siebel_data, bscsix_data, color in all_items:
            self._add_comparison_row(status, siebel_data, bscsix_data, color)
        
        self.comparison_table.resizeColumnsToContents()
        self.comparison_table.horizontalHeader().setStretchLastSection(True)
        
        # CORREÇÃO: Força o reset da ordenação da tabela para usar a nossa ordem customizada
        self.comparison_table.sortByColumn(-1, Qt.SortOrder.AscendingOrder)
        self.comparison_table.setSortingEnabled(True)

    def _add_comparison_row(self, status, siebel_data, bscsix_data, color):
        row = self.comparison_table.rowCount()
        self.comparison_table.insertRow(row)
        siebel_data = siebel_data or {}; bscsix_data = bscsix_data or {}
        items = [
            status, siebel_data.get('NOME_PRODUTO', ''), siebel_data.get('CODIGO_PRODUTO', ''),
            bscsix_data.get('BENEFIT_DESCRIPTION') or bscsix_data.get('SERVICO', ''), bscsix_data.get('SHDES', '')
        ]
        for col, text in enumerate(items):
            item = QTableWidgetItem(str(text))
            item.setBackground(color)
            self.comparison_table.setItem(row, col, item)

    def clear_all_fields(self, keep_inputs=False):
        if not keep_inputs: self.msisdn_input.clear()
        for label_dict in [self.siebel_profile_labels, self.bscsix_profile_labels]:
            for label in label_dict.values():
                label.setText("..."); label.setStyleSheet("")
        self.comparison_table.setRowCount(0)
        if not keep_inputs: self.msisdn_input.setFocus()
        
    def _create_comparison_table(self):
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Status", "Produto (Siebel)", "Código (Siebel)", "Serviço / Benefício (BSCSIX)", "SHDES (BSCSIX)"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setSortingEnabled(True); table.setAlternatingRowColors(True)
        return table

    def _populate_siebel_data(self, data):
        profile = data.get("profile")
        if profile:
            self.siebel_profile_labels["NOME"].setText(str(profile.get('NOME_CLIENTE', 'N/A')))
            self.siebel_profile_labels["CPF/CNPJ"].setText(str(profile.get('CPF_CNPJ', 'N/A')))
            self.siebel_profile_labels["STATUS"].setText(f"{profile.get('STATUS_CLIENTE', '')} / {profile.get('STATUS_ASSET', '')}")
            self.siebel_profile_labels["CO_ID"].setText(str(profile.get('CO_ID', 'N/A')))
            self.siebel_profile_labels["CUSTCODE"].setText(str(profile.get('CUSTCODE', 'N/A')))
            self.siebel_profile_labels["PLANO"].setText(f"{profile.get('PLANO_NOME', '')} ({profile.get('PLANO_CODIGO', '')})")

    def _populate_bscsix_data(self, data):
        profile = data.get("profile")
        if profile:
            self.bscsix_profile_labels["NOME"].setText(str(profile.get('CCFNAME', 'N/A')))
            self.bscsix_profile_labels["CPF/CNPJ"].setText(str(profile.get('CSSOCIALSECNO', 'N/A')))
            self.bscsix_profile_labels["CO_ID"].setText(str(profile.get('CO_ID', 'N/A')))
            self.bscsix_profile_labels["CUSTCODE"].setText(str(profile.get('CUSTCODE', 'N/A')))
            self.bscsix_profile_labels["STATUS"].setText("Ativo" if profile.get('CH_STATUS') == 'a' else str(profile.get('CH_STATUS')))
            self.bscsix_profile_labels["PLANO"].setText(f"{profile.get('PLANO_NOME', '')} ({profile.get('PLANO_CODIGO', '')})")
    
    def _update_validation_status(self, validation_data):
        status = validation_data.get('plan_match_status', 'N/A')
        s_label = self.siebel_profile_labels["PLANO"]; b_label = self.bscsix_profile_labels["PLANO"]
        s_label.setStyleSheet(""); b_label.setStyleSheet("")
        if status == "OK":
            style = "color: lightgreen; font-weight: bold;"; s_label.setText(f"{s_label.text()} [OK]")
        elif "Divergente" in status:
            style = "color: #ff4747; font-weight: bold;"; s_label.setText(f"{s_label.text()} [{status}]")
        else:
            style = "color: #ffa500; font-weight: bold;"; s_label.setText(f"{s_label.text()} [{status}]")
        s_label.setStyleSheet(style); b_label.setStyleSheet(style)

    def _populate_connections_combo(self):
        try:
            connections = logic.get_database_sections(); self.connection_combo.addItems(connections)
            if 'database_siebel' in connections: self.connection_combo.setCurrentText('database_siebel')
        except Exception as e:
            QMessageBox.warning(self, "Erro de Configuração", f"Não foi possível carregar as conexões: {e}")
            
    def _create_profile_labels_dict(self):
        return {"NOME": QLabel("..."), "CPF/CNPJ": QLabel("..."), "STATUS": QLabel("..."),
                "CO_ID": QLabel("..."), "CUSTCODE": QLabel("..."), "PLANO": QLabel("...")}

    def _create_system_groupbox(self, title):
        group = QGroupBox(title); font = QFont(); font.setBold(True); group.setFont(font)
        group.setLayout(QVBoxLayout()); return group

    def _create_profile_group(self, parent_layout, title, labels_dict):
        profile_group = QGroupBox(title); profile_layout = QFormLayout()
        for name, label in labels_dict.items():
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            profile_layout.addRow(QLabel(f"{name}:"), label)
        profile_group.setLayout(profile_layout); parent_layout.addWidget(profile_group)