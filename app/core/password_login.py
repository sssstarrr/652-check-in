from __future__ import annotations

from app.core.checkin_service import CheckinService
from app.core.models import OperationResult


class PasswordLoginManager:
    def __init__(self, service: CheckinService):
        self.service = service

    def fetch_captcha(self) -> OperationResult:
        return self.service.fetch_captcha()

    def login(self, username: str, password: str, captcha_code: str) -> OperationResult:
        return self.service.login_with_password(username, password, captcha_code)
