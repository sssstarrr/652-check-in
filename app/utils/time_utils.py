from __future__ import annotations

import os
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 fallback only.
    ZoneInfo = None


TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"


def current_datetime() -> datetime:
    timezone = os.getenv("CHECKIN_TIMEZONE") or os.getenv("TZ")
    if timezone and ZoneInfo:
        try:
            return datetime.now(ZoneInfo(timezone)).replace(tzinfo=None)
        except Exception:
            pass
    return datetime.now()


def now_string() -> str:
    return current_datetime().strftime(TIME_FORMAT)


def today_string() -> str:
    return current_datetime().strftime(DATE_FORMAT)


def future_time_string(days: int = 30) -> str:
    return (current_datetime() + timedelta(days=days)).strftime(TIME_FORMAT)


def is_future_time(value: str | None) -> bool:
    if not value:
        return False
    try:
        return datetime.strptime(value, TIME_FORMAT) > current_datetime()
    except ValueError:
        return False
