from __future__ import annotations

from datetime import datetime, timedelta


TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"


def now_string() -> str:
    return datetime.now().strftime(TIME_FORMAT)


def today_string() -> str:
    return datetime.now().strftime(DATE_FORMAT)


def future_time_string(days: int = 30) -> str:
    return (datetime.now() + timedelta(days=days)).strftime(TIME_FORMAT)


def is_future_time(value: str | None) -> bool:
    if not value:
        return False
    try:
        return datetime.strptime(value, TIME_FORMAT) > datetime.now()
    except ValueError:
        return False
