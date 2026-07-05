from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.checkin_service import CheckinService
from app.storage.account_store import AccountStore
from app.ui.workers import FunctionWorker


class PasswordLoginWidget(QWidget):
    login_succeeded = pyqtSignal(object)
    log_message = pyqtSignal(str)

    def __init__(self, service: CheckinService, account_store: AccountStore, parent=None):
        super().__init__(parent)
        self.service = service
        self.account_store = account_store
        self.worker: FunctionWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title = QLabel("密码登录")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(QtAlignRight())
        form.setVerticalSpacing(12)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("学号")
        form.addRow("学号", self.username_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("默认不保存密码")
        form.addRow("密码", self.password_edit)

        captcha_row = QHBoxLayout()
        self.captcha_edit = QLineEdit()
        self.captcha_edit.setPlaceholderText("验证码")
        self.captcha_label = QLabel("点击获取验证码")
        self.captcha_label.setFixedSize(138, 48)
        self.captcha_label.setScaledContents(True)
        self.captcha_label.setObjectName("CaptchaImage")
        self.fetch_captcha_button = QPushButton("获取验证码")
        self.fetch_captcha_button.clicked.connect(self.fetch_captcha)
        captcha_row.addWidget(self.captcha_edit, 1)
        captcha_row.addWidget(self.captcha_label)
        captcha_row.addWidget(self.fetch_captcha_button)
        form.addRow("验证码", captcha_row)

        self.remember_checkbox = QCheckBox("记住密码")
        self.remember_checkbox.setToolTip("会优先保存到系统 keyring；不可用时保存到本地加密文件。")
        form.addRow("", self.remember_checkbox)

        layout.addLayout(form)

        self.login_button = QPushButton("登录并进入打卡")
        self.login_button.setObjectName("PrimaryButton")
        self.login_button.clicked.connect(self.login)
        layout.addWidget(self.login_button)

        sms_line = QHBoxLayout()
        self.sms_edit = QLineEdit()
        self.sms_edit.setPlaceholderText("短信验证码")
        self.sms_edit.hide()
        self.send_sms_button = QPushButton("发送短信")
        self.send_sms_button.clicked.connect(self.send_sms)
        self.send_sms_button.hide()
        self.submit_sms_button = QPushButton("提交短信验证")
        self.submit_sms_button.clicked.connect(self.submit_sms)
        self.submit_sms_button.hide()
        sms_line.addWidget(self.sms_edit, 1)
        sms_line.addWidget(self.send_sms_button)
        sms_line.addWidget(self.submit_sms_button)
        layout.addLayout(sms_line)

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusText")
        layout.addWidget(self.status_label)
        layout.addStretch()

    def fetch_captcha(self) -> None:
        self._run(self.service.fetch_captcha, self._on_captcha)

    def login(self) -> None:
        if self.remember_checkbox.isChecked():
            QMessageBox.information(self, "保存密码提示", "勾选记住密码后，本机可解密并自动填充该账号密码，请只在可信电脑使用。")
        self._set_busy(True, "登录中...")
        self._run(
            self.service.login_with_password,
            self._on_login_result,
            self.username_edit.text().strip(),
            self.password_edit.text(),
            self.captcha_edit.text().strip(),
        )

    def send_sms(self) -> None:
        self._run(self.service.send_sms_code, self._show_result)

    def submit_sms(self) -> None:
        self._set_busy(True, "短信验证中...")
        self._run(self.service.submit_sms_code, self._on_login_result, self.sms_edit.text().strip())

    def _on_captcha(self, result) -> None:
        self._show_result(result)
        if result.success and result.data:
            pixmap = QPixmap()
            pixmap.loadFromData(result.data)
            self.captcha_label.setPixmap(pixmap)

    def _on_login_result(self, result) -> None:
        self._set_busy(False)
        if result.success:
            account = self.account_store.add_password_account(
                student_id=self.username_edit.text().strip(),
                name=self.username_edit.text().strip(),
                password=self.password_edit.text(),
                remember_password=self.remember_checkbox.isChecked(),
            )
            if result.cookies:
                self.account_store.update_session(account, result.cookies)
            self.status_label.setText("登录成功")
            self.login_succeeded.emit({"account": account, "cookies": result.cookies, "session": result.data})
            return

        self._show_result(result)
        if result.status == "sms_required":
            self.sms_edit.show()
            self.send_sms_button.show()
            self.submit_sms_button.show()

    def _show_result(self, result) -> None:
        self.status_label.setText(result.message)
        self.log_message.emit(result.message)

    def _run(self, fn, on_success, *args) -> None:
        self.worker = FunctionWorker(fn, *args)
        self.worker.succeeded.connect(on_success)
        self.worker.failed.connect(self._on_worker_error)
        self.worker.finished_always.connect(lambda: self._set_busy(False))
        self.worker.start()

    def _on_worker_error(self, message: str) -> None:
        self._set_busy(False)
        safe_message = message.splitlines()[0]
        self.status_label.setText(safe_message)
        self.log_message.emit(safe_message)

    def _set_busy(self, busy: bool, text: str | None = None) -> None:
        self.login_button.setDisabled(busy)
        self.fetch_captcha_button.setDisabled(busy)
        self.submit_sms_button.setDisabled(busy)
        if text:
            self.status_label.setText(text)


def QtAlignRight():
    from PyQt5.QtCore import Qt

    return Qt.AlignRight
