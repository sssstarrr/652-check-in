from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.core.location import campus_names
from app.storage.account_store import AccountStore


class AccountManagerDialog(QDialog):
    def __init__(self, account_store: AccountStore, parent=None):
        super().__init__(parent)
        self.account_store = account_store
        self.selected_account_id: str | None = None
        self.setWindowTitle("账号管理")
        self.setMinimumSize(760, 430)
        self._build_ui()
        self._apply_style()
        self.refresh_table()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["名称", "学号", "登录方式", "Session", "上次状态", "校区", "更新时间"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self._sync_selection_controls)
        layout.addWidget(self.table, 1)

        edit_row = QHBoxLayout()
        edit_row.addWidget(QLabel("选中账号校区"))
        self.campus_combo = QComboBox()
        self.campus_combo.addItems(campus_names())
        edit_row.addWidget(self.campus_combo)
        self.save_location_button = QPushButton("保存校区")
        self.save_location_button.clicked.connect(self.save_selected_location)
        edit_row.addWidget(self.save_location_button)
        edit_row.addStretch()
        layout.addLayout(edit_row)

        button_row = QHBoxLayout()
        self.select_button = QPushButton("设为当前")
        self.select_button.setObjectName("PrimaryButton")
        self.select_button.clicked.connect(self.select_current)
        self.delete_button = QPushButton("删除账号")
        self.delete_button.clicked.connect(self.delete_selected)
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.accept)
        button_row.addWidget(self.select_button)
        button_row.addWidget(self.delete_button)
        button_row.addStretch()
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

    def refresh_table(self) -> None:
        accounts = self.account_store.list_accounts()
        self.table.setRowCount(len(accounts))
        for row, account in enumerate(accounts):
            values = [
                account.display_name,
                account.student_id,
                "扫码登录" if account.login_type.value == "qr" else "密码登录",
                "有效" if account.is_session_valid() else "需重新登录",
                account.last_checkin_status or "-",
                account.selected_location,
                account.updated_at or "-",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, account.id)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.table.setItem(row, col, item)
        if accounts:
            self.table.selectRow(0)
        self._sync_selection_controls()

    def selected_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def select_current(self) -> None:
        account_id = self.selected_id()
        if not account_id:
            return
        self.selected_account_id = account_id
        self.accept()

    def save_selected_location(self) -> None:
        account_id = self.selected_id()
        account = self.account_store.get_account(account_id) if account_id else None
        if not account:
            return
        account.selected_location = self.campus_combo.currentText()
        self.account_store.save_account(account)
        self.refresh_table()

    def delete_selected(self) -> None:
        account_id = self.selected_id()
        if not account_id:
            return
        if QMessageBox.question(self, "删除账号", "确定删除选中的账号吗？") != QMessageBox.Yes:
            return
        self.account_store.delete_account(account_id)
        self.refresh_table()

    def _sync_selection_controls(self) -> None:
        account_id = self.selected_id()
        account = self.account_store.get_account(account_id) if account_id else None
        enabled = account is not None
        self.select_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)
        self.save_location_button.setEnabled(enabled)
        if account:
            index = self.campus_combo.findText(account.selected_location)
            self.campus_combo.setCurrentIndex(max(0, index))

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QDialog { background: #f4f6f8; font-family: 'Microsoft YaHei UI', 'Segoe UI'; color: #1f2937; }
            QTableWidget {
                background: #ffffff;
                border: 1px solid #d9dee7;
                border-radius: 6px;
                gridline-color: #e6eaf0;
            }
            QHeaderView::section { background: #edf1f6; padding: 6px; border: none; font-weight: 600; }
            QComboBox {
                min-height: 32px;
                border: 1px solid #ccd3dd;
                border-radius: 6px;
                padding: 3px 8px;
                background: white;
            }
            QPushButton {
                min-height: 32px;
                border-radius: 6px;
                padding: 5px 12px;
                border: 1px solid #b8c0cc;
                background: #ffffff;
            }
            QPushButton:hover { background: #f3f6fb; }
            QPushButton#PrimaryButton { background: #165dff; color: white; border-color: #165dff; font-weight: 600; }
            QPushButton#PrimaryButton:hover { background: #0f4fd6; }
            QPushButton:disabled { color: #98a2b3; background: #eef1f5; border-color: #d8dde6; }
            """
        )
