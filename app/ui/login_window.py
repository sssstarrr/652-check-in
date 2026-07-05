from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QDialog, QTabWidget, QVBoxLayout

from app.core.checkin_service import CheckinService
from app.storage.account_store import AccountStore
from app.ui.password_login_widget import PasswordLoginWidget
from app.ui.qr_login_widget import QRLoginWidget


class LoginWindow(QDialog):
    login_succeeded = pyqtSignal(object)

    def __init__(self, service: CheckinService, account_store: AccountStore, parent=None):
        super().__init__(parent)
        self.service = service
        self.account_store = account_store
        self.setWindowTitle("652 打卡登录")
        self.setMinimumSize(560, 470)
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.password_widget = PasswordLoginWidget(self.service, self.account_store)
        self.qr_widget = QRLoginWidget(self.service, self.account_store)
        self.password_widget.login_succeeded.connect(self._emit_success)
        self.qr_widget.login_succeeded.connect(self._emit_success)
        self.tabs.addTab(self.password_widget, "密码登录")
        self.tabs.addTab(self.qr_widget, "扫码登录")
        layout.addWidget(self.tabs)

    def _emit_success(self, context: object) -> None:
        self.login_succeeded.emit(context)
        self.accept()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QDialog { background: #f4f6f8; font-family: 'Microsoft YaHei UI', 'Segoe UI'; }
            QTabWidget::pane { border: 1px solid #d9dee7; background: #ffffff; }
            QTabBar::tab { padding: 9px 18px; background: #e9edf3; color: #3f4754; }
            QTabBar::tab:selected { background: #ffffff; color: #111827; font-weight: 600; }
            QLabel#PanelTitle { font-size: 20px; font-weight: 700; color: #202734; }
            QLabel#StatusText { color: #475467; min-height: 22px; }
            QLabel#CaptchaImage, QLabel#QrImage {
                background: #f8fafc;
                border: 1px solid #d9dee7;
                border-radius: 6px;
                qproperty-alignment: AlignCenter;
            }
            QLineEdit, QComboBox, QSpinBox {
                min-height: 34px;
                border: 1px solid #ccd3dd;
                border-radius: 6px;
                padding: 4px 9px;
                background: white;
            }
            QLineEdit:focus { border: 1px solid #2f6feb; }
            QPushButton {
                min-height: 34px;
                border-radius: 6px;
                padding: 5px 12px;
                border: 1px solid #b8c0cc;
                background: #ffffff;
                color: #263244;
            }
            QPushButton:hover { background: #f3f6fb; }
            QPushButton#PrimaryButton {
                background: #165dff;
                color: white;
                border: 1px solid #165dff;
                font-weight: 600;
            }
            QPushButton#PrimaryButton:hover { background: #0f4fd6; }
            QPushButton:disabled { color: #98a2b3; background: #eef1f5; border-color: #d8dde6; }
            """
        )
