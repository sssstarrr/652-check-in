from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.core.models import Account, LoginType
from app.storage.secure_store import SecureStore
from app.utils.logger import app_data_dir
from app.utils.time_utils import future_time_string, now_string


class AccountStore:
    def __init__(self, path: Path | None = None, secure_store: SecureStore | None = None):
        self.path = path or (app_data_dir() / "accounts.json")
        self.secure_store = secure_store or SecureStore()

    def list_accounts(self) -> list[Account]:
        return [Account.from_dict(item) for item in self._load().get("accounts", [])]

    def get_account(self, account_id: str) -> Account | None:
        return next((account for account in self.list_accounts() if account.id == account_id), None)

    def save_account(self, account: Account) -> None:
        account.updated_at = now_string()
        data = self._load()
        accounts = data.setdefault("accounts", [])
        item = account.to_dict()
        for index, old in enumerate(accounts):
            if old.get("id") == account.id:
                accounts[index] = item
                break
        else:
            accounts.append(item)
        self._save(data)

    def add_password_account(
        self,
        student_id: str,
        name: str = "",
        password: str = "",
        remember_password: bool = False,
        selected_location: str = "宜宾",
    ) -> Account:
        existing = next((account for account in self.list_accounts() if account.student_id == student_id), None)
        account = existing or Account(id=str(uuid.uuid4()), student_id=student_id)
        account.name = name
        account.login_type = LoginType.PASSWORD
        account.selected_location = selected_location
        account.remember_password = remember_password
        if remember_password and password:
            self.secure_store.set_password(account.id, password)
        else:
            self.secure_store.delete_password(account.id)
        self.save_account(account)
        return account

    def add_qr_account(
        self,
        student_id: str,
        name: str,
        session_token: str,
        selected_location: str = "宜宾",
    ) -> Account:
        existing = next((account for account in self.list_accounts() if account.student_id == student_id), None)
        account = existing or Account(id=str(uuid.uuid4()), student_id=student_id)
        account.name = name
        account.login_type = LoginType.QR
        account.session_token = session_token
        account.session_expire_time = future_time_string(30)
        account.selected_location = selected_location
        self.save_account(account)
        return account

    def get_password(self, account: Account) -> str:
        return self.secure_store.get_password(account.id)

    def update_session(self, account: Account, session_token: str, days: int = 30) -> None:
        account.session_token = session_token
        account.session_expire_time = future_time_string(days)
        self.save_account(account)

    def delete_account(self, account_id: str) -> None:
        data = self._load()
        data["accounts"] = [item for item in data.get("accounts", []) if item.get("id") != account_id]
        self.secure_store.delete_password(account_id)
        self._save(data)

    def _load(self) -> dict:
        if not self.path.exists():
            return {"accounts": []}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"accounts": []}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
