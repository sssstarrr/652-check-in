from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from urllib.parse import quote, urljoin

import requests
from requests import Response
from requests.exceptions import ReadTimeout

from app.utils.cookie_utils import (
    cookie_jar_to_string,
    extract_cookie_value,
    merge_cookie_strings,
    remove_cookie,
    response_set_cookie_headers,
    set_cookie_headers_to_string,
)


UIAS_BASE = "https://uias.suse.edu.cn"
QFHY_BASE = "https://qfhy.suse.edu.cn"
QDDK_ADMIN_ENTRY = f"{QFHY_BASE}/xg/app/qddk/admin/qddkdk"
LOGIN_SERVICE = f"{QFHY_BASE}/site/appware/system/sso/login?target={QDDK_ADMIN_ENTRY}"
LOGIN_PAGE = f"{UIAS_BASE}/sso/login?service={quote(LOGIN_SERVICE, safe='')}"
CAPTCHA_URL = f"{UIAS_BASE}/sso/captcha.jpg"
SMS_SEND_URL = f"{UIAS_BASE}/sso/smsLogin/sendSms_double"
TASK_LIST_BASE_URL = f"{QFHY_BASE}/site/qddk/qdrw/api/myList.rst"
TASK_DETAIL_URL = f"{QFHY_BASE}/site/qddk/qdrw/qdxx/api/detailList.rst"
CHECKIN_LOCATION_URL = f"{QFHY_BASE}/site/qddk/qdrw/api/checkSignLocationWithPhoto.rst"
WECHAT_CALLBACK_BASE = f"{QFHY_BASE}/callback/edu/"


def wechat_app_id() -> str:
    configured = os.getenv("SUSE_WECHAT_APP_ID", "").strip()
    if configured:
        return configured
    return "wx" + "".join(("130c", "9f01", "96e2", "9149"))


@dataclass
class SseScanEvent:
    status: int
    query: str = ""

    def to_response(self, client_id: str) -> Response:
        data: dict[str, object] = {"status": self.status}
        if self.status == 2:
            separator = "&" if "?" in WECHAT_CALLBACK_BASE else "?"
            query = f"ybClientId={quote(client_id, safe='')}"
            if self.query:
                query = f"{query}&{self.query.lstrip('?&')}"
            data["callback_url"] = f"{WECHAT_CALLBACK_BASE}{separator}{query}"
            data["callbackUrl"] = data["callback_url"]
            data["redirect_url"] = data["callback_url"]
        response = Response()
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        response._content = json.dumps({"code": 200, "msg": "ok", "data": data}, ensure_ascii=False).encode("utf-8")
        return response


class CheckinApi:
    def __init__(self, timeout: int = 15, session: requests.Session | None = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
        )

    def get_login_page(self, login_cookies: str | None = None) -> requests.Response:
        headers = self._html_headers()
        if login_cookies:
            headers["Cookie"] = login_cookies
        return self.session.get(LOGIN_PAGE, headers=headers, timeout=self.timeout, allow_redirects=False)

    def get_captcha_image(self) -> bytes:
        headers = {
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": LOGIN_PAGE,
        }
        response = self.session.get(CAPTCHA_URL, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.content

    def submit_login(
        self,
        username: str,
        encrypted_password: str,
        execution: str,
        captcha_code: str,
    ) -> requests.Response:
        data = {
            "username": username,
            "password": encrypted_password,
            "authcode": captcha_code,
            "execution": execution,
            "encrypted": "true",
            "_eventId": "submit",
            "loginType": "1",
            "rememberMe": "true",
        }
        headers = self._html_headers(
            {
                "Origin": UIAS_BASE,
                "Referer": LOGIN_PAGE,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        return self.session.post(LOGIN_PAGE, data=data, headers=headers, timeout=self.timeout, allow_redirects=False)

    def send_sms_code(self, username: str, field_name: str = "request_username") -> requests.Response:
        headers = {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Origin": UIAS_BASE,
            "Referer": LOGIN_PAGE,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        return self.session.post(
            SMS_SEND_URL,
            data={field_name: username, "type": "1"},
            headers=headers,
            timeout=self.timeout,
        )

    def submit_sms_verification(
        self,
        username: str,
        execution: str,
        sms_code: str,
        phone_masked: str | None = None,
    ) -> requests.Response:
        data = {
            "username": username,
            "smsCode": sms_code,
            "execution": execution,
            "encrypted": "true",
            "_eventId": "doubleSubmit",
            "loginType": "2",
            "rememberMe": "true",
        }
        if phone_masked:
            data["phone"] = phone_masked
        headers = self._html_headers(
            {
                "Origin": UIAS_BASE,
                "Referer": LOGIN_PAGE,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        return self.session.post(LOGIN_PAGE, data=data, headers=headers, timeout=self.timeout, allow_redirects=False)

    def follow_redirect(self, url: str, max_redirects: int = 5) -> requests.Response:
        current_url = url
        referer = f"{UIAS_BASE}/"
        response: requests.Response | None = None
        for _ in range(max_redirects + 1):
            response = self.session.get(
                current_url,
                headers=self._html_headers({"Referer": referer}),
                timeout=self.timeout,
                allow_redirects=False,
            )
            if response.status_code not in range(300, 400):
                return response
            location = response.headers.get("Location")
            if not location:
                return response
            referer = current_url
            current_url = urljoin(current_url, location)
        return response

    def get_wechat_client_id(self) -> requests.Response:
        return self.session.get(
            f"{QFHY_BASE}/edu/v2/weixin/getClientId",
            headers=self._json_headers({"Referer": QDDK_ADMIN_ENTRY}),
            timeout=self.timeout,
        )

    def get_wechat_qrcode_url(self, app_id: str, client_id: str) -> requests.Response:
        return self.session.post(
            f"{QFHY_BASE}/edu/v2/weixin/getQrCodeUrl",
            json={"app_id": app_id, "client_id": client_id},
            headers=self._json_headers({"Referer": QDDK_ADMIN_ENTRY, "Content-Type": "application/json"}),
            timeout=self.timeout,
        )

    def check_wechat_scan_status(self, client_id: str) -> requests.Response:
        sse_response = self._check_wechat_scan_status_sse(client_id)
        if sse_response is not None:
            return sse_response

        # Legacy fallback kept for older deployments and the original Kotlin flow.
        return self.session.post(
            f"{QFHY_BASE}/edu/v2/weixin/checkScan",
            json={"client_id": client_id},
            headers=self._json_headers({"Referer": QDDK_ADMIN_ENTRY, "Content-Type": "application/json"}),
            timeout=self.timeout,
        )

    def handle_wechat_callback(self, callback_url: str) -> requests.Response:
        return self.session.get(
            callback_url,
            headers=self._html_headers({"Accept-Language": "zh-CN,zh;q=0.9"}),
            timeout=self.timeout,
            allow_redirects=True,
        )

    def _check_wechat_scan_status_sse(self, client_id: str) -> Response | None:
        url = f"{QFHY_BASE}/edu/v1/wechat/stream"
        headers = {
            "Accept": "text/event-stream",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Referer": (
                f"{QFHY_BASE}/edu/v1/wechat/qrcodelogin?"
                f"appId={wechat_app_id()}&clientId={quote(client_id, safe='')}"
                f"&targetUrl={quote(WECHAT_CALLBACK_BASE, safe='')}"
            ),
        }
        try:
            with self.session.get(
                url,
                params={"clientId": client_id},
                headers=headers,
                timeout=(self.timeout, min(4, max(2, self.timeout))),
                stream=True,
            ) as response:
                if response.status_code == 404:
                    return None
                if response.status_code != 200:
                    synthetic = Response()
                    synthetic.status_code = response.status_code
                    synthetic._content = response.content
                    return synthetic
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    event = self._parse_sse_line(line)
                    if event:
                        return event.to_response(client_id)
        except ReadTimeout:
            return SseScanEvent(status=0).to_response(client_id)
        except requests.RequestException:
            return None
        return SseScanEvent(status=0).to_response(client_id)

    def _parse_sse_line(self, line: str) -> SseScanEvent | None:
        text = line.strip()
        if text.startswith("data:"):
            text = text[5:].strip()
        if not text:
            return None
        parts = text.split(",", 1)
        try:
            status = int(parts[0])
        except ValueError:
            return None
        return SseScanEvent(status=status, query=parts[1] if len(parts) > 1 else "")

    def complete_sso_with_sop_session(self, sop_session_cookie: str) -> str:
        sop_value = extract_cookie_value(sop_session_cookie, "_sop_session_")
        if not sop_value:
            raise RuntimeError("未找到 _sop_session_ Cookie")

        # A long-running desktop process can retain an expired qfhy SESSION in
        # requests' in-memory cookie jar.  Treating any non-empty value as a
        # successful refresh makes restart appear to fix the login, because a
        # fresh process starts with an empty jar.  A renewal must ignore both
        # persisted and in-memory SESSION values and accept only one issued by
        # the SSO flow below.
        renewal_cookies = remove_cookie(sop_session_cookie, "SESSION")
        self._clear_session_cookies()

        payload = self._decode_sop_payload(sop_value)
        extra = payload.get("extra") or "{}"
        if isinstance(extra, str):
            try:
                extra_payload = json.loads(extra)
            except json.JSONDecodeError:
                extra_payload = {}
        else:
            extra_payload = extra if isinstance(extra, dict) else {}

        open_id = extra_payload.get("openId") or extra_payload.get("open_id")
        ticket = payload.get("ticket")
        session_value = None

        if not session_value and open_id:
            session_value = self._try_access_xg_page(renewal_cookies, open_id)
        if not session_value and ticket:
            session_value = self._try_ticket_sso(renewal_cookies, ticket)
        if not session_value and open_id:
            session_value = self._try_init_site_session(renewal_cookies, open_id)
        if not session_value:
            session_value = self._find_session_cookie()
        if not session_value:
            raise RuntimeError("所有方法都未能获取 SESSION Cookie")

        return merge_cookie_strings(renewal_cookies, cookie_jar_to_string(self.session.cookies), f"SESSION={session_value}")

    def get_task_list(self, status: int = 1, cookies: str | None = None) -> requests.Response:
        headers = self._qddk_headers(cookies)
        return self.session.get(
            f"{TASK_LIST_BASE_URL}?status={status}",
            headers=headers,
            timeout=self.timeout,
        )

    def get_task_detail(self, task_id: int, cookies: str | None = None) -> requests.Response:
        headers = self._qddk_headers(cookies)
        return self.session.get(
            f"{TASK_DETAIL_URL}?qdrwId={task_id}",
            headers=headers,
            timeout=self.timeout,
        )

    def submit_location_checkin(self, request_body: dict | str, cookies: str | None = None) -> requests.Response:
        headers = self._qddk_headers(cookies, {"Content-Type": "application/json"})
        body = json.dumps(request_body, ensure_ascii=False, separators=(",", ":")) if isinstance(request_body, dict) else request_body
        return self.session.post(
            CHECKIN_LOCATION_URL,
            data=body.encode("utf-8"),
            headers=headers,
            timeout=self.timeout,
        )

    def _try_access_xg_page(self, sop_session_cookie: str, open_id: str) -> str | None:
        current_cookies = sop_session_cookie
        url = f"{QFHY_BASE}/xg/app/qddk/admin?open_id={quote(open_id, safe='')}"
        response = self.session.get(
            url,
            headers=self._html_headers({"Cookie": current_cookies, "Referer": f"{QFHY_BASE}/edu/"}),
            timeout=self.timeout,
            allow_redirects=False,
        )
        current_cookies = merge_cookie_strings(current_cookies, set_cookie_headers_to_string(response_set_cookie_headers(response)))
        for _ in range(5):
            session_value = self._session_from_response(response) or self._find_session_cookie()
            if session_value:
                return session_value
            location = response.headers.get("Location")
            if response.status_code not in range(300, 400) or not location:
                break
            url = urljoin(url, location)
            response = self.session.get(
                url,
                headers=self._html_headers({"Cookie": current_cookies, "Referer": QDDK_ADMIN_ENTRY}),
                timeout=self.timeout,
                allow_redirects=False,
            )
            current_cookies = merge_cookie_strings(current_cookies, set_cookie_headers_to_string(response_set_cookie_headers(response)))
        return self._find_session_cookie()

    def _try_ticket_sso(self, sop_session_cookie: str, ticket: str) -> str | None:
        response = self.session.get(
            f"{QFHY_BASE}/site/appware/system/sso/login",
            params={"ticket": ticket, "target": QDDK_ADMIN_ENTRY},
            headers=self._html_headers({"Cookie": sop_session_cookie, "Referer": f"{QFHY_BASE}/edu/"}),
            timeout=self.timeout,
            allow_redirects=False,
        )
        return self._session_from_response(response) or self._find_session_cookie()

    def _try_init_site_session(self, sop_session_cookie: str, open_id: str) -> str | None:
        response = self.session.get(
            f"{QFHY_BASE}/site/app/base/common/api/user/current.rst",
            headers=self._qddk_headers(sop_session_cookie, {"Referer": f"{QFHY_BASE}/xg/app/qddk/admin?open_id={open_id}"}),
            timeout=self.timeout,
            allow_redirects=False,
        )
        return self._session_from_response(response) or self._find_session_cookie()

    def _session_from_response(self, response: requests.Response) -> str | None:
        set_cookie = response.headers.get("Set-Cookie", "")
        if "SESSION=" in set_cookie:
            return set_cookie.split("SESSION=", 1)[1].split(";", 1)[0]
        return None

    def _find_session_cookie(self) -> str | None:
        for cookie in self.session.cookies:
            if cookie.name == "SESSION" and cookie.value:
                return cookie.value
        return None

    def _clear_session_cookies(self) -> None:
        for cookie in list(self.session.cookies):
            if cookie.name != "SESSION":
                continue
            try:
                self.session.cookies.clear(cookie.domain, cookie.path, cookie.name)
            except (KeyError, ValueError):
                # Custom CookieJar implementations used by callers may not
                # support domain/path clearing. Expiring the value still keeps
                # it from being accepted by _find_session_cookie().
                cookie.value = ""

    def _html_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if extra:
            headers.update(extra)
        return headers

    def _json_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if extra:
            headers.update(extra)
        return headers

    def _qddk_headers(self, cookies: str | None = None, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = self._json_headers({"Referer": QDDK_ADMIN_ENTRY, "appcode": "qddk"})
        if cookies:
            headers["Cookie"] = cookies
        if extra:
            headers.update(extra)
        return headers

    def _decode_sop_payload(self, sop_session_value: str) -> dict:
        parts = sop_session_value.split(".")
        if len(parts) != 3:
            raise ValueError("_sop_session_ 不是有效的 JWT")
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8")
        return json.loads(decoded)
