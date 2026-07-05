from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Callable


SECRET_KEYS = ("password", "cookie", "token", "session", "ticket", "_sop_session_")


def app_data_dir() -> Path:
    root = os.getenv("APPDATA")
    if root:
        base = Path(root)
    else:
        base = Path.home() / ".config"
    path = base / "SUSE-OAA-Checkin-Desktop"
    path.mkdir(parents=True, exist_ok=True)
    return path


def redact_value(value: str | None, keep: int = 6) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "***"
    return f"{value[:keep]}...{value[-keep:]}"


def redact_message(message: str) -> str:
    result = message
    for key in SECRET_KEYS:
        result = re.sub(
            rf"({re.escape(key)}\s*[=:]\s*)([^;\s,]+)",
            lambda m: m.group(1) + redact_value(m.group(2)),
            result,
            flags=re.IGNORECASE,
        )
    result = re.sub(
        r"((?:CASTGC|SESSION|_sop_session_)=)([^;\s]+)",
        lambda m: m.group(1) + redact_value(m.group(2)),
        result,
        flags=re.IGNORECASE,
    )
    return result


class AppLogger:
    def __init__(self, callback: Callable[[str], None] | None = None, debug: bool = False):
        self.callback = callback
        self.debug = debug
        self.logger = logging.getLogger("checkin_desktop")
        self.logger.setLevel(logging.DEBUG if debug else logging.INFO)
        if not self.logger.handlers:
            handler = logging.FileHandler(app_data_dir() / "app.log", encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self.logger.addHandler(handler)

    def set_callback(self, callback: Callable[[str], None] | None) -> None:
        self.callback = callback

    def info(self, message: str) -> None:
        self._write(logging.INFO, message)

    def debug_log(self, message: str) -> None:
        if self.debug:
            self._write(logging.DEBUG, message)

    def error(self, message: str) -> None:
        self._write(logging.ERROR, message)

    def _write(self, level: int, message: str) -> None:
        safe = redact_message(message)
        self.logger.log(level, safe)
        if self.callback:
            self.callback(safe)
