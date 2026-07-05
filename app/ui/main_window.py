from __future__ import annotations

from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.checkin_service import CheckinService
from app.core.location import default_location, fixed_location, location_summary, random_location_for_campus
from app.core.models import Account
from app.storage.account_store import AccountStore
from app.storage.settings_store import SettingsStore
from app.ui.account_manager_dialog import AccountManagerDialog
from app.ui.settings_dialog import SettingsDialog
from app.ui.workers import FunctionWorker
from app.utils.time_utils import today_string


class MainWindow(QMainWindow):
    request_relogin = pyqtSignal()
    request_add_account = pyqtSignal()

    def __init__(self, service: CheckinService, account_store: AccountStore, parent=None):
        super().__init__(parent)
        self.service = service
        self.account_store = account_store
        self.settings_store = SettingsStore()
        self.worker: FunctionWorker | None = None
        self.current_account: Account | None = None
        self.settings = self.settings_store.load()
        self.service.api.timeout = int(self.settings.get("timeout") or 15)
        self.force_quit = False
        self.setWindowTitle("652 打卡桌面版")
        self.setMinimumSize(980, 680)
        self._build_ui()
        self._setup_tray()
        self._setup_auto_checkin_timer()
        self._apply_style()
        self._update_auto_schedule_label()
        self.refresh_accounts()

    def handle_login_context(self, context: dict) -> None:
        account = context.get("account")
        cookies = context.get("cookies") or ""
        if account:
            self.current_account = account
            self.settings["campus"] = account.selected_location
            if cookies and self.settings.get("save_session", True):
                self.account_store.update_session(account, cookies)
                self.service.current_cookies = cookies
        self.refresh_accounts()
        self._set_current_account(account)
        self.append_log("登录成功，正在刷新任务")
        self.refresh_tasks()

    def refresh_accounts(self) -> None:
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        for account in self.account_store.list_accounts():
            self.account_combo.addItem(f"{account.display_name} ({account.login_type.value})", account.id)
        self.account_combo.blockSignals(False)
        if self.current_account:
            idx = self.account_combo.findData(self.current_account.id)
            if idx >= 0:
                self.account_combo.setCurrentIndex(idx)
        elif self.account_combo.count():
            self._select_account(0)

    def refresh_tasks(self) -> None:
        account = self.current_account
        cookies = self._account_cookies()
        if not account or not cookies:
            self.append_log("未选择账号或 Session 不可用")
            return
        self.refresh_button.setDisabled(True)
        self._run(lambda: self.service.load_tasks(cookies), self._on_tasks_loaded)

    def perform_checkin(self) -> None:
        account = self.current_account
        if not account:
            self.append_log("请先选择账号")
            return
        location = self._selected_location(account)
        self.checkin_button.setDisabled(True)
        self.append_log(f"本次签到位置：{location_summary(location)}")
        self._run(lambda: self.service.perform_checkin(account, location), self._on_checkin_done)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        top = QHBoxLayout()
        self.account_combo = QComboBox()
        self.account_combo.currentIndexChanged.connect(self._select_account)
        top.addWidget(QLabel("当前账号"))
        top.addWidget(self.account_combo, 1)
        self.add_account_button = QPushButton("添加账号")
        self.add_account_button.clicked.connect(self.request_add_account.emit)
        self.manage_accounts_button = QPushButton("账号管理")
        self.manage_accounts_button.clicked.connect(self.open_account_manager)
        self.relogin_button = QPushButton("重新登录")
        self.relogin_button.clicked.connect(self.request_relogin.emit)
        self.delete_button = QPushButton("删除账号")
        self.delete_button.clicked.connect(self.delete_current_account)
        self.settings_button = QPushButton("设置")
        self.settings_button.clicked.connect(self.open_settings)
        top.addWidget(self.add_account_button)
        top.addWidget(self.manage_accounts_button)
        top.addWidget(self.relogin_button)
        top.addWidget(self.delete_button)
        top.addWidget(self.settings_button)
        layout.addLayout(top)

        info_group = QGroupBox("账号信息")
        info_layout = QGridLayout(info_group)
        self.name_label = QLabel("-")
        self.student_label = QLabel("-")
        self.login_type_label = QLabel("-")
        self.status_label = QLabel("-")
        self.updated_label = QLabel("-")
        self.location_label = QLabel("-")
        info_layout.addWidget(QLabel("名称"), 0, 0)
        info_layout.addWidget(self.name_label, 0, 1)
        info_layout.addWidget(QLabel("学号"), 0, 2)
        info_layout.addWidget(self.student_label, 0, 3)
        info_layout.addWidget(QLabel("登录方式"), 1, 0)
        info_layout.addWidget(self.login_type_label, 1, 1)
        info_layout.addWidget(QLabel("上次状态"), 1, 2)
        info_layout.addWidget(self.status_label, 1, 3)
        info_layout.addWidget(QLabel("更新时间"), 2, 0)
        info_layout.addWidget(self.updated_label, 2, 1)
        info_layout.addWidget(QLabel("校区"), 2, 2)
        info_layout.addWidget(self.location_label, 2, 3)
        layout.addWidget(info_group)

        buttons = QHBoxLayout()
        self.checkin_button = QPushButton("一键打卡")
        self.checkin_button.setObjectName("PrimaryButton")
        self.checkin_button.clicked.connect(self.perform_checkin)
        self.checkin_all_button = QPushButton("全部打卡")
        self.checkin_all_button.clicked.connect(lambda: self.perform_all_checkins())
        self.refresh_button = QPushButton("刷新任务")
        self.refresh_button.clicked.connect(self.refresh_tasks)
        buttons.addWidget(self.checkin_button)
        buttons.addWidget(self.checkin_all_button)
        buttons.addWidget(self.refresh_button)
        buttons.addStretch()
        self.auto_schedule_label = QLabel("")
        self.auto_schedule_label.setObjectName("StatusText")
        buttons.addWidget(self.auto_schedule_label)
        layout.addLayout(buttons)

        tables = QHBoxLayout()
        self.pending_table = self._make_table("待签到任务")
        self.completed_table = self._make_table("已完成任务")
        tables.addWidget(self.pending_table)
        tables.addWidget(self.completed_table)
        layout.addLayout(tables, 1)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(120)
        layout.addWidget(self.log_edit)

    def _make_table(self, title: str) -> QTableWidget:
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels([title, "状态", "日期", "开始", "签到时间"])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        return table

    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.windowIcon() or QIcon())
        menu = QMenu()
        show_action = QAction("打开主界面", self)
        show_action.triggered.connect(self.showNormal)
        checkin_action = QAction("一键打卡", self)
        checkin_action.triggered.connect(self.perform_checkin)
        checkin_all_action = QAction("全部打卡", self)
        checkin_all_action.triggered.connect(lambda: self.perform_all_checkins())
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.exit_app)
        menu.addAction(show_action)
        menu.addAction(checkin_action)
        menu.addAction(checkin_all_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def _select_account(self, index: int) -> None:
        account_id = self.account_combo.itemData(index)
        account = self.account_store.get_account(account_id) if account_id else None
        self._set_current_account(account)

    def _set_current_account(self, account: Account | None) -> None:
        self.current_account = account
        if not account:
            return
        self.name_label.setText(account.display_name)
        self.student_label.setText(account.student_id)
        self.login_type_label.setText("扫码登录" if account.login_type.value == "qr" else "密码登录")
        self.status_label.setText(account.last_checkin_status or "-")
        self.updated_label.setText(account.updated_at or "-")
        self.location_label.setText(account.selected_location)
        self.settings["campus"] = account.selected_location

    def _account_cookies(self) -> str:
        account = self.current_account
        if account and account.is_session_valid():
            return account.session_token
        return self.service.current_cookies

    def _selected_location(self, account: Account):
        campus = account.selected_location or self.settings.get("campus")
        mode = self.settings.get("location_mode") or "默认地点"
        if mode == "固定地点":
            return fixed_location(campus, int(self.settings.get("fixed_location_index") or 0))
        if mode == "随机偏移地点":
            return random_location_for_campus(campus, random_offset=True)
        return default_location(campus)

    def _on_tasks_loaded(self, result) -> None:
        self.refresh_button.setDisabled(False)
        if not result.success:
            self.append_log(result.message)
            return
        data = result.data or {}
        self._fill_table(self.pending_table, data.get("pending") or [])
        self._fill_table(self.completed_table, data.get("completed") or [])
        self.append_log("任务列表已刷新")

    def _on_checkin_done(self, result) -> None:
        self.checkin_button.setDisabled(False)
        self.checkin_all_button.setDisabled(False)
        self.append_log(result.message)
        if result.location:
            self.append_log(f"提交位置：{location_summary(result.location)}")
        self.refresh_accounts()
        self.refresh_tasks()

    def perform_all_checkins(self, accounts: list[Account] | None = None, auto_trigger: bool = False) -> None:
        if isinstance(accounts, bool):
            accounts = None
        accounts = accounts if accounts is not None else self.account_store.list_accounts()
        if not accounts:
            self.append_log("没有可打卡账号，请先添加账号")
            return
        self.checkin_button.setDisabled(True)
        self.checkin_all_button.setDisabled(True)
        self.refresh_button.setDisabled(True)
        prefix = "定时自动打卡" if auto_trigger else "批量打卡"
        self.append_log(f"开始{prefix}，共 {len(accounts)} 个账号")
        self._run(lambda: self._perform_all_checkins_job(accounts), self._on_all_checkins_done)

    def _perform_all_checkins_job(self, accounts: list[Account]):
        results = []
        for account in accounts:
            if not account.is_session_valid():
                account.last_checkin_status = "Session 失效"
                from app.utils.time_utils import now_string

                account.last_checkin_time = now_string()
                self.account_store.save_account(account)
                results.append((account.display_name, "Session 失效，请重新登录", None))
                continue
            location = self._selected_location(account)
            result = self.service.perform_checkin_with_cookies(account.session_token, account, location)
            results.append((account.display_name, result.message, result.location))
        return results

    def _on_all_checkins_done(self, results) -> None:
        self.checkin_button.setDisabled(False)
        self.checkin_all_button.setDisabled(False)
        self.refresh_button.setDisabled(False)
        for account_name, message, location in results:
            self.append_log(f"{account_name}: {message}")
            if location:
                self.append_log(f"{account_name} 位置：{location_summary(location)}")
        self.refresh_accounts()
        self.refresh_tasks()

    def _fill_table(self, table: QTableWidget, tasks) -> None:
        table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            values = [task.name, task.status_text, task.need_time, task.start_time, task.checkin_time or ""]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                table.setItem(row, col, item)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_() == dialog.Accepted:
            self.settings.update(dialog.values())
            if self.current_account:
                self.current_account.selected_location = self.settings["campus"]
                self.account_store.save_account(self.current_account)
                self._set_current_account(self.current_account)
            self.service.api.timeout = int(self.settings["timeout"])
            self.settings_store.save(self.settings)
            self._update_auto_schedule_label()
            self.append_log("设置已保存")

    def open_account_manager(self) -> None:
        dialog = AccountManagerDialog(self.account_store, self)
        if dialog.exec_() == dialog.Accepted:
            self.refresh_accounts()
            if dialog.selected_account_id:
                account = self.account_store.get_account(dialog.selected_account_id)
                self._set_current_account(account)
                if account:
                    idx = self.account_combo.findData(account.id)
                    if idx >= 0:
                        self.account_combo.setCurrentIndex(idx)
                    self.append_log(f"已切换账号：{account.display_name}")

    def delete_current_account(self) -> None:
        if not self.current_account:
            return
        if QMessageBox.question(self, "删除账号", "确定删除当前账号吗？") == QMessageBox.Yes:
            self.account_store.delete_account(self.current_account.id)
            self.current_account = None
            self.refresh_accounts()
            self.append_log("账号已删除")

    def append_log(self, message: str) -> None:
        self.log_edit.append(message)

    def _run(self, fn, on_success) -> None:
        self.worker = FunctionWorker(fn)
        self.worker.succeeded.connect(on_success)
        self.worker.failed.connect(self._on_error)
        self.worker.finished_always.connect(lambda: self.refresh_button.setDisabled(False))
        self.worker.start()

    def _setup_auto_checkin_timer(self) -> None:
        self.auto_checkin_timer = QTimer(self)
        self.auto_checkin_timer.setInterval(30_000)
        self.auto_checkin_timer.timeout.connect(self._check_auto_checkin)
        self.auto_checkin_timer.start()

    def _check_auto_checkin(self) -> None:
        if not self.settings.get("auto_checkin_enabled"):
            return
        if self.worker and self.worker.isRunning():
            return

        from datetime import datetime

        now = datetime.now()
        target = str(self.settings.get("auto_checkin_time") or "19:31")
        target_minutes = self._time_to_minutes(target)
        if target_minutes is None:
            return
        current_minutes = now.hour * 60 + now.minute
        if current_minutes < target_minutes:
            return

        today = today_string()
        if self.settings.get("last_auto_checkin_date") == today:
            return

        scope = self.settings.get("auto_checkin_scope") or "全部账号"
        if scope == "当前账号":
            accounts = [self.current_account] if self.current_account else []
        else:
            accounts = self.account_store.list_accounts()
        accounts = [account for account in accounts if account is not None]

        self.settings["last_auto_checkin_date"] = today
        self.settings_store.save(self.settings)
        self._update_auto_schedule_label()

        if not accounts:
            self.append_log("定时自动打卡触发，但没有可用账号")
            return
        self.perform_all_checkins(accounts=accounts, auto_trigger=True)

    @staticmethod
    def _time_to_minutes(value: str) -> int | None:
        try:
            hour_text, minute_text = value.split(":", 1)
            hour = int(hour_text)
            minute = int(minute_text)
        except (TypeError, ValueError):
            return None
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            return None
        return hour * 60 + minute

    def _update_auto_schedule_label(self) -> None:
        if not hasattr(self, "auto_schedule_label"):
            return
        if self.settings.get("auto_checkin_enabled"):
            time_text = self.settings.get("auto_checkin_time") or "19:31"
            scope = self.settings.get("auto_checkin_scope") or "全部账号"
            self.auto_schedule_label.setText(f"自动打卡 {time_text} / {scope}")
        else:
            self.auto_schedule_label.setText("自动打卡未启用")

    def exit_app(self) -> None:
        self.force_quit = True
        if self.tray:
            self.tray.hide()
        QApplication.instance().quit()

    def _on_error(self, message: str) -> None:
        self.checkin_button.setDisabled(False)
        self.checkin_all_button.setDisabled(False)
        self.refresh_button.setDisabled(False)
        self.append_log(message.splitlines()[0])

    def closeEvent(self, event) -> None:
        if self.force_quit:
            if self.tray:
                self.tray.hide()
            super().closeEvent(event)
            return
        event.ignore()
        self.hide()
        if self.tray:
            self.tray.showMessage("652 打卡桌面版", "程序已隐藏到托盘，定时自动打卡会继续运行。", QSystemTrayIcon.Information, 2500)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f4f6f8; font-family: 'Microsoft YaHei UI', 'Segoe UI'; color: #1f2937; }
            QGroupBox {
                border: 1px solid #d9dee7;
                border-radius: 6px;
                margin-top: 10px;
                padding: 12px;
                background: #ffffff;
                font-weight: 600;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QTableWidget, QTextEdit {
                background: #ffffff;
                border: 1px solid #d9dee7;
                border-radius: 6px;
                gridline-color: #e6eaf0;
            }
            QHeaderView::section { background: #edf1f6; padding: 6px; border: none; font-weight: 600; }
            QLineEdit, QComboBox, QSpinBox {
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
