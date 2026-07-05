from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from app.core.checkin_service import CheckinService
from app.storage.account_store import AccountStore
from app.ui.login_window import LoginWindow
from app.ui.main_window import MainWindow
from app.utils.logger import AppLogger


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    icon_path = Path(__file__).resolve().parent / "assets" / "app.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    account_store = AccountStore()
    logger = AppLogger()
    service = CheckinService(account_store=account_store, logger=logger)
    main_window = MainWindow(service, account_store)
    if icon_path.exists():
        main_window.setWindowIcon(QIcon(str(icon_path)))

    login_windows: list[LoginWindow] = []

    def open_login() -> None:
        login = LoginWindow(service, account_store, main_window)
        if icon_path.exists():
            login.setWindowIcon(QIcon(str(icon_path)))
        login.login_succeeded.connect(lambda context: on_login_success(context, login))
        login_windows.append(login)
        login.show()

    def on_login_success(context: object, login: LoginWindow) -> None:
        if login in login_windows:
            login_windows.remove(login)
        main_window.handle_login_context(context)
        main_window.show()
        main_window.raise_()

    main_window.request_relogin.connect(open_login)
    main_window.request_add_account.connect(open_login)

    accounts = account_store.list_accounts()
    valid_account = next((account for account in accounts if account.is_session_valid()), None)
    if valid_account:
        main_window.current_account = valid_account
        service.current_cookies = valid_account.session_token
        main_window.refresh_accounts()
        main_window.show()
        main_window.refresh_tasks()
    else:
        open_login()

    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
