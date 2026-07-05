from __future__ import annotations

import base64
import getpass
import hashlib
import json
import os
import platform
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

from app.utils.logger import app_data_dir


SERVICE_NAME = "SUSE-OAA-Checkin-Desktop"


class SecureStore:
    def __init__(self, fallback_path: Path | None = None):
        self.fallback_path = fallback_path or (app_data_dir() / "secrets.json")
        self._keyring = self._load_keyring()

    def set_password(self, account_id: str, password: str) -> None:
        if self._keyring:
            try:
                self._keyring.set_password(SERVICE_NAME, account_id, password)
                self._remove_fallback(account_id)
                return
            except Exception:
                pass
        data = self._load_fallback()
        data[account_id] = self._encrypt(password)
        self._save_fallback(data)

    def get_password(self, account_id: str) -> str:
        if self._keyring:
            try:
                value = self._keyring.get_password(SERVICE_NAME, account_id)
                if value:
                    return value
            except Exception:
                pass
        encrypted = self._load_fallback().get(account_id)
        return self._decrypt(encrypted) if encrypted else ""

    def delete_password(self, account_id: str) -> None:
        if self._keyring:
            try:
                self._keyring.delete_password(SERVICE_NAME, account_id)
            except Exception:
                pass
        self._remove_fallback(account_id)

    def _load_keyring(self):
        try:
            import keyring

            return keyring
        except Exception:
            return None

    def _fallback_key(self) -> bytes:
        seed = "|".join(
            [
                SERVICE_NAME,
                getpass.getuser(),
                platform.node(),
                os.getenv("USERPROFILE", str(Path.home())),
            ]
        )
        return hashlib.sha256(seed.encode("utf-8")).digest()

    def _encrypt(self, text: str) -> str:
        nonce = get_random_bytes(12)
        cipher = AES.new(self._fallback_key(), AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(text.encode("utf-8"))
        return base64.b64encode(nonce + tag + ciphertext).decode("ascii")

    def _decrypt(self, value: str) -> str:
        try:
            raw = base64.b64decode(value)
            nonce, tag, ciphertext = raw[:12], raw[12:28], raw[28:]
            cipher = AES.new(self._fallback_key(), AES.MODE_GCM, nonce=nonce)
            return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")
        except Exception:
            return ""

    def _load_fallback(self) -> dict[str, str]:
        if not self.fallback_path.exists():
            return {}
        try:
            return json.loads(self.fallback_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_fallback(self, data: dict[str, str]) -> None:
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
        self.fallback_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _remove_fallback(self, account_id: str) -> None:
        data = self._load_fallback()
        if account_id in data:
            del data[account_id]
            self._save_fallback(data)
