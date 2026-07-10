from __future__ import annotations

import json
from pathlib import Path

from app.utils.logger import app_data_dir


DEFAULT_SETTINGS = {
    "campus": "宜宾",
    "location_mode": "默认地点",
    "fixed_location_index": 0,
    "save_session": True,
    "debug": False,
    "timeout": 15,
    "auto_checkin_enabled": False,
    "auto_checkin_time": "19:31",
    "auto_checkin_scope": "全部账号",
    "auto_checkin_retry_minutes": 5,
    "last_auto_checkin_date": "",
    "last_auto_checkin_attempt": "",
    "last_auto_checkin_result": "",
    "last_auto_checkin_success_time": "",
    "auto_checkin_success_dates": {},
}


class SettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (app_data_dir() / "settings.json")

    def load(self) -> dict:
        settings = dict(DEFAULT_SETTINGS)
        if not self.path.exists():
            return settings
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                settings.update(data)
        except Exception:
            pass
        return settings

    def save(self, settings: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = dict(DEFAULT_SETTINGS)
        data.update(settings)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
