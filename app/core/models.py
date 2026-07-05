from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.utils.time_utils import is_future_time, now_string


class LoginType(str, Enum):
    PASSWORD = "password"
    QR = "qr"


class CheckinStatus(str, Enum):
    SUCCESS = "success"
    ALREADY_CHECKED = "already_checked"
    NO_TASK = "no_task"
    FAILED = "failed"


@dataclass
class OperationResult:
    success: bool
    message: str = ""
    status: str = ""
    data: Any = None
    cookies: str = ""


@dataclass
class CheckinLocation:
    campus: str
    address: str
    longitude: float
    latitude: float

    @property
    def location_json(self) -> str:
        import json

        return json.dumps(
            {
                "point": [self.longitude, self.latitude],
                "address": self.address,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )


@dataclass
class CheckinTask:
    id: int
    name: str = ""
    status_text: str = ""
    need_time: str = ""
    start_time: str = ""
    end_time: str = ""
    checkin_time: str | None = None
    checkin_status: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "CheckinTask":
        return cls(
            id=int(data.get("id") or 0),
            name=str(data.get("rwmc") or ""),
            status_text=str(data.get("rwzt") or ""),
            need_time=str(data.get("needTime") or data.get("qdksrq") or ""),
            start_time=str(data.get("qdkssj") or data.get("start_date") or ""),
            end_time=str(data.get("qdjssj") or data.get("end_date") or ""),
            checkin_time=data.get("qdsj"),
            checkin_status=data.get("qdzt"),
            raw=data,
        )


@dataclass
class CheckinResult:
    status: CheckinStatus
    message: str
    task: CheckinTask | None = None
    location: CheckinLocation | None = None
    raw: dict[str, Any] | None = None

    @property
    def success(self) -> bool:
        return self.status in {CheckinStatus.SUCCESS, CheckinStatus.ALREADY_CHECKED, CheckinStatus.NO_TASK}


@dataclass
class Account:
    id: str
    student_id: str
    name: str = ""
    remark: str = ""
    login_type: LoginType = LoginType.PASSWORD
    selected_location: str = "宜宾"
    session_token: str = ""
    session_expire_time: str = ""
    last_checkin_time: str = ""
    last_checkin_status: str = ""
    created_at: str = field(default_factory=now_string)
    updated_at: str = field(default_factory=now_string)
    remember_password: bool = False

    @property
    def display_name(self) -> str:
        return self.name or self.student_id or "未命名账号"

    def is_session_valid(self) -> bool:
        return bool(self.session_token) and is_future_time(self.session_expire_time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "student_id": self.student_id,
            "name": self.name,
            "remark": self.remark,
            "login_type": self.login_type.value,
            "selected_location": self.selected_location,
            "session_token": self.session_token,
            "session_expire_time": self.session_expire_time,
            "last_checkin_time": self.last_checkin_time,
            "last_checkin_status": self.last_checkin_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "remember_password": self.remember_password,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Account":
        item = dict(data)
        item["login_type"] = LoginType(item.get("login_type") or LoginType.PASSWORD.value)
        return cls(**item)


@dataclass
class SmsChallenge:
    username: str
    execution: str
    phone_masked: str | None = None


@dataclass
class QRLoginPayload:
    client_id: str
    qr_image: str
    expires_minutes: int = 5


@dataclass
class LoginSession:
    cookies: str
    student_id: str = ""
    name: str = ""
    open_id: str = ""
    ticket: str = ""
