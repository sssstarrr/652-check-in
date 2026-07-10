from __future__ import annotations

import base64
import json
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.checkin_service import CheckinService
from app.core.location import build_checkin_body, default_location
from app.core.models import Account, CheckinStatus, SmsChallenge
from app.core.rsa_encryptor import encrypt_password
from app.cli.checkin_once import (
    CliConfigError,
    EXIT_FAILED,
    EXIT_NO_TASK,
    EXIT_OK,
    account_from_spec,
    cookie_diagnostics,
    finish_exit_code,
    load_account_specs,
    location_from_spec,
    parse_args,
)
from app.utils import time_utils
from app.utils.cookie_utils import extract_cookie_value, merge_cookie_strings
from app.utils.logger import redact_message
from app.ui.main_window import MainWindow


def _jwt(payload: dict) -> str:
    header = {"alg": "none", "typ": "JWT"}

    def enc(value: dict) -> str:
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f"{enc(header)}.{enc(payload)}.sig"


class CoreTests(unittest.TestCase):
    def test_encrypt_password_matches_expected_shape(self) -> None:
        first = encrypt_password("abc123")
        second = encrypt_password("abc124")
        self.assertEqual(len(first), 256)
        self.assertNotEqual(first, second)
        int(first, 16)

    def test_parse_sop_session(self) -> None:
        token = _jwt(
            {
                "uid": "23341010304",
                "ticket": "ticket-value",
                "extra": json.dumps({"userName": "测试用户", "openId": "openid-value"}, ensure_ascii=False),
            }
        )
        service = CheckinService()
        self.assertEqual(service.extract_ticket_from_sop_session(token), "ticket-value")
        self.assertEqual(service.extract_openid_from_sop_session(token), "openid-value")
        self.assertEqual(service.extract_user_info_from_sop_session(token), ("23341010304", "测试用户"))

    def test_location_body_shape(self) -> None:
        location = default_location("宜宾")
        body = build_checkin_body(1001, location)
        self.assertEqual(body["id"], 1001)
        self.assertEqual(body["qdzt"], 1)
        self.assertIn("point", body["location"])
        self.assertIn("qdddjtdz", body)

    def test_cookie_helpers_and_redaction(self) -> None:
        merged = merge_cookie_strings("SESSION=abc", "_sop_session_=secret.jwt.value")
        self.assertEqual(extract_cookie_value(merged, "SESSION"), "abc")
        redacted = redact_message(f"Cookie: {merged}")
        self.assertNotIn("secret.jwt.value", redacted)
        self.assertIn("_sop_session_=是", cookie_diagnostics(merged))

    def test_cli_single_account_env(self) -> None:
        specs = load_account_specs(
            {
                "QFHY_SESSION": "SESSION=test-value",
                "CHECKIN_STUDENT_ID": "1001",
            }
        )
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["session"], "SESSION=test-value")
        account = account_from_spec(specs[0])
        args = parse_args(["--location-mode", "fixed", "--location-index", "1"])
        location = location_from_spec(specs[0], args, account.selected_location)
        self.assertEqual(location.campus, "宜宾")

    def test_cli_accounts_json(self) -> None:
        raw = json.dumps(
            [
                {
                    "student_id": "1001",
                    "campus": "汇东",
                    "cookies": "SESSION=test-value",
                    "location_mode": "fixed",
                    "location_index": 1,
                }
            ],
            ensure_ascii=False,
        )
        specs = load_account_specs({"CHECKIN_ACCOUNTS_JSON": raw})
        self.assertEqual(specs[0]["session"], "SESSION=test-value")
        self.assertEqual(specs[0]["campus"], "汇东")

    def test_cli_desktop_accounts_json_shape(self) -> None:
        raw = json.dumps(
            {
                "accounts": [
                    {
                        "student_id": "1001",
                        "selected_location": "宜宾",
                        "session_token": "SESSION=test-value",
                    }
                ]
            },
            ensure_ascii=False,
        )
        specs = load_account_specs({"CHECKIN_ACCOUNTS_JSON": raw})
        self.assertEqual(specs[0]["session"], "SESSION=test-value")
        self.assertEqual(specs[0]["campus"], "宜宾")

    def test_cli_accounts_file(self) -> None:
        path = ROOT / "tests" / "tmp-accounts.json"
        try:
            path.write_text(
                json.dumps({"accounts": [{"student_id": "1001", "session_token": "SESSION=file-value"}]}),
                encoding="utf-8",
            )
            specs = load_account_specs({"CHECKIN_ACCOUNTS_FILE": str(path)})
            self.assertEqual(specs[0]["session"], "SESSION=file-value")
        finally:
            path.unlink(missing_ok=True)

    def test_scheduler_exit_code_for_no_task_retry(self) -> None:
        self.assertEqual(finish_exit_code(True, [], ["1001"]), EXIT_NO_TASK)
        self.assertEqual(finish_exit_code(False, [], ["1001"]), EXIT_OK)
        self.assertEqual(finish_exit_code(True, ["1001"], []), EXIT_FAILED)

    def test_cli_requires_session(self) -> None:
        with self.assertRaises(CliConfigError):
            load_account_specs({})

    def test_time_utils_respects_configured_timezone(self) -> None:
        old_value = os.environ.get("CHECKIN_TIMEZONE")
        try:
            os.environ["CHECKIN_TIMEZONE"] = "Asia/Shanghai"
            self.assertRegex(time_utils.now_string(), r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        finally:
            if old_value is None:
                os.environ.pop("CHECKIN_TIMEZONE", None)
            else:
                os.environ["CHECKIN_TIMEZONE"] = old_value

    def test_refreshes_sop_session_even_when_session_exists(self) -> None:
        class Response:
            status_code = 200

            def json(self):
                return {"success": True, "resultCode": 0, "result": {"data": []}}

        class FakeApi:
            def __init__(self):
                self.timeout = 15
                self.refreshed = False
                self.cookies_seen = ""

            def complete_sso_with_sop_session(self, cookies: str) -> str:
                self.refreshed = True
                return merge_cookie_strings(cookies, "SESSION=fresh")

            def get_task_list(self, status: int = 1, cookies: str | None = None):
                self.cookies_seen = cookies or ""
                return Response()

        api = FakeApi()
        service = CheckinService(api=api)
        account = Account(id="1", student_id="1001", session_token="_sop_session_=sop; SESSION=old")
        result = service.perform_checkin_with_cookies(account.session_token, account, default_location("宜宾"))
        self.assertEqual(result.status, CheckinStatus.NO_TASK)
        self.assertTrue(api.refreshed)
        self.assertEqual(extract_cookie_value(api.cookies_seen, "SESSION"), "fresh")
        self.assertEqual(extract_cookie_value(account.session_token, "SESSION"), "fresh")

    def test_load_tasks_returns_refreshed_cookies(self) -> None:
        class Response:
            status_code = 200

            def json(self):
                return {"success": True, "resultCode": 0, "result": {"data": []}}

        class FakeApi:
            def __init__(self):
                self.timeout = 15
                self.cookies_seen = []

            def complete_sso_with_sop_session(self, cookies: str) -> str:
                return merge_cookie_strings(cookies, "SESSION=fresh")

            def get_task_list(self, status: int = 1, cookies: str | None = None):
                self.cookies_seen.append(cookies or "")
                return Response()

        api = FakeApi()
        service = CheckinService(api=api)
        result = service.load_tasks("_sop_session_=sop; SESSION=old")
        self.assertTrue(result.success)
        self.assertEqual(extract_cookie_value(result.cookies, "SESSION"), "fresh")
        self.assertTrue(all(extract_cookie_value(cookies, "SESSION") == "fresh" for cookies in api.cookies_seen))

    def test_load_tasks_enriches_completed_checkin_time(self) -> None:
        class Response:
            status_code = 200

            def __init__(self, payload):
                self.payload = payload

            def json(self):
                return self.payload

        class FakeApi:
            def __init__(self):
                self.timeout = 15
                self.detail_ids = []

            def complete_sso_with_sop_session(self, cookies: str) -> str:
                return cookies

            def get_task_list(self, status: int = 1, cookies: str | None = None):
                tasks = [{"id": 42, "rwmc": "测试任务", "rwzt": "进行中"}] if status == 2 else []
                return Response({"success": True, "resultCode": 0, "result": {"data": tasks}})

            def get_task_detail(self, task_id: int, cookies: str | None = None):
                self.detail_ids.append(task_id)
                return Response(
                    {
                        "success": True,
                        "resultCode": 0,
                        "result": {"data": {"dkxx": {"qdzt": 1, "qdsj": "2026-07-10 20:41:08"}}},
                    }
                )

        api = FakeApi()
        result = CheckinService(api=api).load_tasks("SESSION=test")
        self.assertTrue(result.success)
        self.assertEqual(api.detail_ids, [42])
        task = result.data["completed"][0]
        self.assertEqual(task.status_text, "已签到")
        self.assertEqual(task.checkin_time, "2026-07-10 20:41:08")
        self.assertEqual(task.checkin_status, 1)

    def test_successful_checkin_records_submitted_time(self) -> None:
        class Response:
            status_code = 200

            def __init__(self, payload):
                self.payload = payload

            def json(self):
                return self.payload

        class FakeApi:
            def __init__(self):
                self.timeout = 15
                self.submitted = None

            def complete_sso_with_sop_session(self, cookies: str) -> str:
                return cookies

            def get_task_list(self, status: int = 1, cookies: str | None = None):
                return Response(
                    {
                        "success": True,
                        "resultCode": 0,
                        "result": {"data": [{"id": 7, "rwmc": "测试任务", "rwzt": "进行中"}]},
                    }
                )

            def get_task_detail(self, task_id: int, cookies: str | None = None):
                return Response({"success": True, "resultCode": 0, "result": {"data": {"dkxx": {"qdzt": 0}}}})

            def submit_location_checkin(self, request_body, cookies: str | None = None):
                self.submitted = request_body
                return Response({"success": True, "resultCode": 0, "result": {"data": True}})

        api = FakeApi()
        account = Account(id="1", student_id="1001", session_token="SESSION=test")
        result = CheckinService(api=api).perform_checkin_with_cookies(
            account.session_token,
            account,
            default_location("宜宾"),
        )
        self.assertEqual(result.status, CheckinStatus.SUCCESS)
        self.assertEqual(result.task.checkin_time, api.submitted["qdsj"])
        self.assertEqual(account.last_checkin_time, api.submitted["qdsj"])

    def test_desktop_scheduler_retry_window(self) -> None:
        now = datetime(2026, 7, 10, 20, 44, 59)
        self.assertTrue(MainWindow._auto_retry_due("", now, 5))
        self.assertFalse(MainWindow._auto_retry_due("2026-07-10 20:40:00", now, 5))
        self.assertTrue(MainWindow._auto_retry_due("2026-07-10 20:39:59", now, 5))
        self.assertTrue(MainWindow._auto_retry_due("2026-07-09 23:59:59", now, 5))

    def test_sms_send_retries_parameter_names(self) -> None:
        class Response:
            status_code = 200

            def __init__(self, text: str):
                self._text = text

            @property
            def text(self):
                return self._text

        class FakeApi:
            def __init__(self):
                self.timeout = 15
                self.fields = []

            def send_sms_code(self, username: str, field_name: str = "request_username"):
                self.fields.append(field_name)
                if field_name == "request_username":
                    return Response('{"success":false,"msg":"参数 request_username 错误"}')
                return Response('{"success":true,"code":200,"msg":"ok"}')

        api = FakeApi()
        service = CheckinService(api=api)
        service.pending_sms_challenge = SmsChallenge(username="1001", execution="e1")
        result = service.send_sms_code()
        self.assertTrue(result.success)
        self.assertEqual(api.fields[:2], ["request_username", "username"])


if __name__ == "__main__":
    unittest.main()
