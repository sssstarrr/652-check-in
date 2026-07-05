from __future__ import annotations

import base64
from io import BytesIO

import qrcode
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.checkin_service import CheckinService
from app.storage.account_store import AccountStore
from app.ui.workers import FunctionWorker


class QRLoginWidget(QWidget):
    login_succeeded = pyqtSignal(object)
    log_message = pyqtSignal(str)

    def __init__(self, service: CheckinService, account_store: AccountStore, parent=None):
        super().__init__(parent)
        self.service = service
        self.account_store = account_store
        self.worker: FunctionWorker | None = None
        self.client_id = ""
        self.polling = False
        self.poll_busy = False
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.poll_status)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title = QLabel("微信扫码登录")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self.qr_label = QLabel("点击获取二维码")
        self.qr_label.setFixedSize(260, 260)
        self.qr_label.setObjectName("QrImage")
        self.qr_label.setScaledContents(True)
        layout.addWidget(self.qr_label)

        self.start_button = QPushButton("获取二维码")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.clicked.connect(self.start_login)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("停止轮询")
        self.stop_button.clicked.connect(self.stop_polling)
        self.stop_button.setDisabled(True)
        layout.addWidget(self.stop_button)

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusText")
        layout.addWidget(self.status_label)
        layout.addStretch()

    def start_login(self) -> None:
        self.start_button.setDisabled(True)
        self.status_label.setText("正在获取二维码...")
        self.worker = FunctionWorker(self.service.start_qr_login)
        self.worker.succeeded.connect(self._on_start_result)
        self.worker.failed.connect(self._on_error)
        self.worker.finished_always.connect(lambda: self.start_button.setDisabled(False))
        self.worker.start()

    def poll_status(self) -> None:
        if not self.client_id or self.poll_busy:
            return
        self.poll_busy = True
        self.worker = FunctionWorker(self.service.poll_qr_login_status, self.client_id)
        self.worker.succeeded.connect(self._on_poll_result)
        self.worker.failed.connect(self._on_error)
        self.worker.finished_always.connect(lambda: setattr(self, "poll_busy", False))
        self.worker.start()

    def stop_polling(self) -> None:
        self.polling = False
        self.timer.stop()
        self.stop_button.setDisabled(True)
        self.status_label.setText("已停止轮询")

    def closeEvent(self, event) -> None:
        self.stop_polling()
        super().closeEvent(event)

    def _on_start_result(self, result) -> None:
        if not result.success:
            self.status_label.setText(result.message)
            return
        payload = result.data
        self.client_id = payload.client_id
        self._show_qr(payload.qr_image)
        self.status_label.setText("等待扫码确认")
        self.stop_button.setDisabled(False)
        self.polling = True
        self.timer.start()

    def _on_poll_result(self, result) -> None:
        self.status_label.setText(result.message)
        self.log_message.emit(result.message)
        if result.status == "confirmed":
            self.stop_polling()
            data = result.data or {}
            callback_url = data.get("callback_url") or data.get("callbackUrl") or ""
            self._finish(callback_url)

    def _finish(self, callback_url: str) -> None:
        self.status_label.setText("正在完成 SSO...")
        self.worker = FunctionWorker(self.service.finish_qr_login, callback_url)
        self.worker.succeeded.connect(self._on_finish_result)
        self.worker.failed.connect(self._on_error)
        self.worker.start()

    def _on_finish_result(self, result) -> None:
        if not result.success:
            self.status_label.setText(result.message)
            self.log_message.emit(result.message)
            return
        session = result.data
        account = self.account_store.add_qr_account(
            student_id=session.student_id or "unknown",
            name=session.name or session.student_id or "扫码账号",
            session_token=result.cookies,
        )
        self.status_label.setText("扫码登录成功")
        self.login_succeeded.emit({"account": account, "cookies": result.cookies, "session": session})

    def _show_qr(self, qr_data: str) -> None:
        pixmap = QPixmap()
        raw = qr_data.strip()
        if raw.startswith("data:image"):
            raw = raw.split(",", 1)[1]
        if raw.startswith("http://") or raw.startswith("https://"):
            img = qrcode.make(raw)
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            pixmap.loadFromData(buffer.getvalue())
        else:
            try:
                pixmap.loadFromData(base64.b64decode(raw))
            except Exception:
                img = qrcode.make(raw)
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                pixmap.loadFromData(buffer.getvalue())
        self.qr_label.setPixmap(pixmap)

    def _on_error(self, message: str) -> None:
        safe = message.splitlines()[0]
        self.status_label.setText(safe)
        self.log_message.emit(safe)
        self.start_button.setDisabled(False)
