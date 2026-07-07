from __future__ import annotations

import base64
import json
import re
from typing import Any

from bs4 import BeautifulSoup

from app.core.checkin_api import CheckinApi, wechat_app_id
from app.core.location import build_checkin_body, default_location
from app.core.models import (
    Account,
    CheckinLocation,
    CheckinResult,
    CheckinStatus,
    CheckinTask,
    LoginSession,
    OperationResult,
    QRLoginPayload,
    SmsChallenge,
)
from app.core.rsa_encryptor import encrypt_password
from app.storage.account_store import AccountStore
from app.utils.cookie_utils import (
    cookie_jar_to_string,
    extract_cookie_value,
    merge_cookie_strings,
    response_set_cookie_headers,
    set_cookie_headers_to_string,
)
from app.utils.logger import AppLogger
from app.utils.time_utils import future_time_string, today_string


SMS_REQUIRED_MESSAGE = "检测到短信二次验证"


class CheckinService:
    def __init__(
        self,
        api: CheckinApi | None = None,
        account_store: AccountStore | None = None,
        logger: AppLogger | None = None,
    ):
        self.api = api or CheckinApi()
        self.account_store = account_store
        self.logger = logger or AppLogger()
        self.cached_execution: str | None = None
        self.pending_sms_challenge: SmsChallenge | None = None
        self.current_cookies: str = ""

    def fetch_captcha(self) -> OperationResult:
        self.api.session.cookies.clear()
        self.pending_sms_challenge = None
        response = self.api.get_login_page()
        if response.status_code != 200:
            return OperationResult(False, f"无法访问登录页面 ({response.status_code})")
        self.cached_execution = self._extract_execution(response.text)
        if not self.cached_execution:
            return OperationResult(False, "未找到 execution token")
        image = self.api.get_captcha_image()
        self.logger.info(f"验证码获取成功，图片大小 {len(image)} bytes")
        return OperationResult(True, "验证码获取成功", data=image)

    def login_with_password(self, username: str, password: str, captcha_code: str) -> OperationResult:
        execution = self.cached_execution
        if not execution:
            return OperationResult(False, "请先获取验证码")
        if not username or not password or not captcha_code:
            return OperationResult(False, "请输入学号、密码和验证码")

        encrypted_password = encrypt_password(password)
        self.pending_sms_challenge = None
        response = self.api.submit_login(username, encrypted_password, execution, captcha_code)
        if response.status_code == 302:
            redirect_url = response.headers.get("Location")
            if not redirect_url:
                return OperationResult(False, "登录成功但重定向地址为空")
            return self._finalize_login_after_redirect(redirect_url)

        body = response.text
        if self._is_sms_required(body):
            sms_execution = self._extract_execution(body) or execution
            self.pending_sms_challenge = SmsChallenge(
                username=username,
                execution=sms_execution,
                phone_masked=self._extract_phone_masked(body),
            )
            return OperationResult(False, f"{SMS_REQUIRED_MESSAGE}，请发送并输入短信验证码继续", status="sms_required")

        return OperationResult(False, self._extract_login_error(body, response.status_code))

    def send_sms_code(self, username: str | None = None) -> OperationResult:
        challenge = self.pending_sms_challenge
        target = username or (challenge.username if challenge else "")
        if not target:
            return OperationResult(False, "短信验证上下文已失效，请重新登录")
        response = self.api.send_sms_code(target)
        if not (200 <= response.status_code < 300):
            return OperationResult(False, f"短信发送失败 ({response.status_code})")
        text = response.text
        if any(flag in text.lower() for flag in ("false", "error")) or "失败" in text:
            return OperationResult(False, "短信发送失败，请稍后重试")
        return OperationResult(True, "短信验证码已发送")

    def submit_sms_code(self, sms_code: str) -> OperationResult:
        challenge = self.pending_sms_challenge
        if not challenge:
            return OperationResult(False, "短信验证上下文已失效，请重新登录")
        if not sms_code:
            return OperationResult(False, "请输入短信验证码")
        response = self.api.submit_sms_verification(
            username=challenge.username,
            execution=challenge.execution,
            sms_code=sms_code,
            phone_masked=challenge.phone_masked,
        )
        if response.status_code == 302:
            redirect_url = response.headers.get("Location")
            if not redirect_url:
                return OperationResult(False, "短信验证成功但重定向为空")
            result = self._finalize_login_after_redirect(redirect_url)
            if result.success:
                self.pending_sms_challenge = None
            return result

        body = response.text
        new_execution = self._extract_execution(body)
        if new_execution:
            self.pending_sms_challenge = SmsChallenge(
                username=challenge.username,
                execution=new_execution,
                phone_masked=self._extract_phone_masked(body) or challenge.phone_masked,
            )
        return OperationResult(False, "短信验证码错误或已过期")

    def start_qr_login(self) -> OperationResult:
        response = self.api.get_wechat_client_id()
        if response.status_code != 200:
            return OperationResult(False, f"获取 ClientId 失败 ({response.status_code})")
        payload = response.json()
        client_id = ((payload.get("data") or {}).get("client_id") or (payload.get("data") or {}).get("clientId"))
        if not client_id:
            return OperationResult(False, "ClientId 为空")

        qr_response = self.api.get_wechat_qrcode_url(wechat_app_id(), client_id)
        if qr_response.status_code != 200:
            return OperationResult(False, f"获取二维码失败 ({qr_response.status_code})")
        qr_payload = qr_response.json()
        data = qr_payload.get("data") or {}
        qr_image = data.get("img") or data.get("url") or ""
        if not qr_image:
            return OperationResult(False, "二维码数据为空")
        return OperationResult(
            True,
            "二维码获取成功",
            data=QRLoginPayload(client_id=client_id, qr_image=qr_image, expires_minutes=int(data.get("minute") or 5)),
        )

    def poll_qr_login_status(self, client_id: str) -> OperationResult:
        response = self.api.check_wechat_scan_status(client_id)
        if response.status_code != 200:
            return OperationResult(False, f"检查扫码状态失败 ({response.status_code})")
        payload = response.json()
        data = payload.get("data") or {}
        status = int(data.get("status") or 0)
        if status == 2:
            return OperationResult(True, "扫码已确认", status="confirmed", data=data)
        if status == 1:
            return OperationResult(True, "已扫码，请在微信中确认", status="scanned", data=data)
        if status == 0:
            return OperationResult(True, "等待扫码", status="waiting", data=data)
        return OperationResult(False, payload.get("msg") or payload.get("message") or "扫码状态异常", status="error", data=data)

    def finish_qr_login(self, callback_url: str) -> OperationResult:
        if not callback_url:
            return OperationResult(False, "扫码确认后未返回 callbackUrl")
        response = self.api.handle_wechat_callback(callback_url)
        header_cookies = set_cookie_headers_to_string(response_set_cookie_headers(response))
        cookies = merge_cookie_strings(header_cookies, cookie_jar_to_string(self.api.session.cookies))
        sop_value = extract_cookie_value(cookies, "_sop_session_")
        if not sop_value:
            return OperationResult(False, "未能获取 _sop_session_ Cookie")

        full_cookies = self.api.complete_sso_with_sop_session(cookies)
        self.current_cookies = full_cookies
        payload = self.parse_sop_session(sop_value)
        extra = payload.get("extra_parsed") or {}
        session = LoginSession(
            cookies=full_cookies,
            student_id=str(payload.get("uid") or extra.get("uid") or ""),
            name=str(extra.get("userName") or extra.get("name") or ""),
            open_id=str(extra.get("openId") or extra.get("open_id") or ""),
            ticket=str(payload.get("ticket") or ""),
        )
        return OperationResult(True, "扫码登录成功", data=session, cookies=full_cookies)

    def load_tasks(self, cookies: str | None = None) -> OperationResult:
        effective_cookies = cookies or self.current_cookies or None
        result: dict[str, list[CheckinTask]] = {}
        for status, key in ((1, "pending"), (2, "completed"), (3, "absent")):
            response = self.api.get_task_list(status=status, cookies=effective_cookies)
            if response.status_code != 200:
                return OperationResult(False, f"获取任务列表失败 ({response.status_code})")
            payload = response.json()
            if payload.get("resultCode") != 0 or not payload.get("success"):
                return OperationResult(False, payload.get("errorMsg") or "获取任务列表失败")
            tasks = ((payload.get("result") or {}).get("data") or [])
            result[key] = [CheckinTask.from_api(item) for item in tasks]
        return OperationResult(True, "任务列表获取成功", data=result)

    def perform_checkin(self, account: Account, selected_location: CheckinLocation | None = None) -> CheckinResult:
        cookies = account.session_token if account.is_session_valid() else self.current_cookies or cookie_jar_to_string(self.api.session.cookies)
        if not cookies:
            return CheckinResult(CheckinStatus.FAILED, "未找到可用 Session，请重新登录")
        return self.perform_checkin_with_cookies(cookies, account, selected_location)

    def perform_checkin_with_cookies(
        self,
        cookies: str,
        account: Account,
        selected_location: CheckinLocation | None = None,
    ) -> CheckinResult:
        effective_cookies = self._refresh_session_from_sop(cookies)

        task_response = self.api.get_task_list(status=1, cookies=effective_cookies)
        if task_response.status_code != 200:
            return self._checkin_failed(account, f"获取任务列表失败 ({task_response.status_code})")
        task_payload = task_response.json()
        if task_payload.get("resultCode") != 0 or not task_payload.get("success"):
            return self._checkin_failed(
                account,
                self._api_error_message("获取任务列表失败", task_payload.get("errorMsg"), effective_cookies),
            )

        tasks = [CheckinTask.from_api(item) for item in ((task_payload.get("result") or {}).get("data") or [])]
        if not tasks:
            return self._checkin_no_task(account, "当前没有待签到的任务")

        today = today_string()
        task = next((item for item in tasks if item.need_time == today and item.status_text == "进行中"), tasks[0])
        detail_response = self.api.get_task_detail(task.id, cookies=effective_cookies)
        if detail_response.status_code != 200:
            return self._checkin_failed(account, f"获取任务详情失败 ({detail_response.status_code})")
        detail_payload = detail_response.json()
        if detail_payload.get("resultCode") != 0 or not detail_payload.get("success"):
            return self._checkin_failed(
                account,
                self._api_error_message("获取任务详情失败", detail_payload.get("errorMsg"), effective_cookies),
            )

        dkxx = (((detail_payload.get("result") or {}).get("data") or {}).get("dkxx") or {})
        if int(dkxx.get("qdzt") or 0) == 1:
            return self._checkin_already(account, "今日已签到", task)

        location = selected_location or default_location(account.selected_location)
        body = build_checkin_body(task.id, location)
        submit_response = self.api.submit_location_checkin(body, cookies=effective_cookies)
        if submit_response.status_code != 200:
            return self._checkin_failed(account, f"签到提交失败 ({submit_response.status_code})")
        submit_payload = submit_response.json()
        if submit_payload.get("success") and submit_payload.get("resultCode") == 0:
            return self._checkin_success(account, "签到成功", task, location, effective_cookies)
        return self._checkin_failed(
            account,
            self._api_error_message("签到失败", submit_payload.get("errorMsg"), effective_cookies),
        )

    def _refresh_session_from_sop(self, cookies: str) -> str:
        if "_sop_session_=" not in cookies:
            return cookies
        try:
            refreshed = self.api.complete_sso_with_sop_session(cookies)
            return refreshed or cookies
        except Exception as exc:
            self.logger.error(f"SSO SESSION 获取失败: {exc}")
            return cookies

    def _api_error_message(self, fallback: str, message: Any, cookies: str) -> str:
        text = str(message or fallback)
        if "身份信息" not in text:
            return text
        if "_sop_session_=" in cookies:
            return f"{text}；GitHub Secret 中的登录态已失效，请重新登录桌面版后复制最新完整 session_token"
        return f"{text}；GitHub Secret 只包含 SESSION 或已过期，请复制 accounts.json 中完整 session_token"

    def parse_sop_session(self, jwt: str) -> dict[str, Any]:
        parts = jwt.split(".")
        if len(parts) != 3:
            raise ValueError("_sop_session_ 不是有效 JWT")
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        parsed = json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
        extra = parsed.get("extra")
        if isinstance(extra, str) and extra:
            try:
                parsed["extra_parsed"] = json.loads(extra)
            except json.JSONDecodeError:
                parsed["extra_parsed"] = {}
        return parsed

    def extract_ticket_from_sop_session(self, jwt: str) -> str | None:
        return self.parse_sop_session(jwt).get("ticket")

    def extract_openid_from_sop_session(self, jwt: str) -> str | None:
        parsed = self.parse_sop_session(jwt)
        extra = parsed.get("extra_parsed") or {}
        return extra.get("openId") or extra.get("open_id")

    def extract_user_info_from_sop_session(self, jwt: str) -> tuple[str, str] | None:
        parsed = self.parse_sop_session(jwt)
        uid = parsed.get("uid")
        if not uid:
            return None
        extra = parsed.get("extra_parsed") or {}
        return str(uid), str(extra.get("userName") or extra.get("name") or "")

    def _finalize_login_after_redirect(self, redirect_url: str) -> OperationResult:
        self.api.follow_redirect(redirect_url)
        cookies = cookie_jar_to_string(self.api.session.cookies)
        if "SESSION=" not in cookies:
            return OperationResult(False, "登录成功但未获取到 qfhy SESSION")
        self.cached_execution = None
        self.current_cookies = cookies
        return OperationResult(True, "登录成功", data=LoginSession(cookies=cookies), cookies=cookies)

    def _extract_execution(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        node = soup.find("input", attrs={"name": "execution"})
        if node and node.get("value"):
            return str(node["value"])
        match = re.search(r"name=[\"']execution[\"'][^>]*value=[\"']([^\"']+)", html)
        return match.group(1) if match else None

    def _extract_phone_masked(self, html: str) -> str | None:
        match = re.search(r"name\s*=\s*[\"']phone[\"'][^>]*value\s*=\s*[\"']([^\"']+)", html)
        return match.group(1) if match else None

    def _is_sms_required(self, html: str) -> bool:
        lower = html.lower()
        return "smscode" in lower or "doublesubmit" in lower or "sendsms_double" in lower or "短信" in html

    def _extract_login_error(self, html: str, status_code: int) -> str:
        soup = BeautifulSoup(html, "html.parser")
        error_node = soup.find(class_=re.compile("error", re.I))
        if error_node:
            text = error_node.get_text(strip=True)
            if text:
                return text
        if "验证码" in html:
            return "验证码错误或已过期"
        if "密码" in html:
            return "用户名或密码错误"
        if "用户" in html:
            return "用户名不存在"
        return f"登录失败 ({status_code})"

    def _checkin_success(self, account: Account, message: str, task: CheckinTask, location: CheckinLocation, cookies: str) -> CheckinResult:
        self._update_account(account, "成功", cookies)
        return CheckinResult(CheckinStatus.SUCCESS, message, task=task, location=location)

    def _checkin_already(self, account: Account, message: str, task: CheckinTask) -> CheckinResult:
        self._update_account(account, "已签到")
        return CheckinResult(CheckinStatus.ALREADY_CHECKED, message, task=task)

    def _checkin_no_task(self, account: Account, message: str) -> CheckinResult:
        self._update_account(account, "无任务")
        return CheckinResult(CheckinStatus.NO_TASK, message)

    def _checkin_failed(self, account: Account, message: str) -> CheckinResult:
        self._update_account(account, f"失败: {message}")
        return CheckinResult(CheckinStatus.FAILED, message)

    def _update_account(self, account: Account, status: str, cookies: str | None = None) -> None:
        account.last_checkin_status = status
        from app.utils.time_utils import now_string

        account.last_checkin_time = now_string()
        if cookies:
            account.session_token = cookies
            account.session_expire_time = future_time_string(30)
        if self.account_store:
            self.account_store.save_account(account)
