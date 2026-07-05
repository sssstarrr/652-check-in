from __future__ import annotations

from app.core.checkin_service import CheckinService
from app.core.models import OperationResult


class QRLoginManager:
    def __init__(self, service: CheckinService):
        self.service = service

    def start(self) -> OperationResult:
        return self.service.start_qr_login()

    def poll(self, client_id: str) -> OperationResult:
        return self.service.poll_qr_login_status(client_id)

    def finish(self, callback_url: str) -> OperationResult:
        return self.service.finish_qr_login(callback_url)
