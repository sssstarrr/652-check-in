from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Mapping, Sequence

from app.core.checkin_service import CheckinService
from app.core.location import default_location, fixed_location, location_summary, random_location_for_campus
from app.core.models import Account, CheckinLocation, LoginType
from app.utils.time_utils import future_time_string


class CliConfigError(ValueError):
    pass


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run(args, os.environ)
    except CliConfigError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return 2


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one headless 652 check-in.")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and print planned accounts without network requests.")
    parser.add_argument("--campus", default=os.getenv("CHECKIN_CAMPUS", "宜宾"), help="Default campus: 宜宾, 李白河, or 汇东.")
    parser.add_argument(
        "--location-mode",
        default=os.getenv("CHECKIN_LOCATION_MODE", "default"),
        choices=("default", "fixed", "random"),
        help="Location selection mode.",
    )
    parser.add_argument("--location-index", type=int, default=_env_int("CHECKIN_LOCATION_INDEX", 0), help="Fixed location index.")
    parser.add_argument(
        "--random-offset",
        action="store_true",
        default=_truthy(os.getenv("CHECKIN_RANDOM_OFFSET")),
        help="Add a small random offset when location mode is random.",
    )
    parser.add_argument("--max-offset-meters", type=float, default=_env_float("CHECKIN_MAX_OFFSET_METERS", 35.0))
    parser.add_argument("--timeout", type=int, default=_env_int("CHECKIN_TIMEOUT", 20))
    return parser.parse_args(argv)


def run(args: argparse.Namespace, environ: Mapping[str, str]) -> int:
    specs = load_account_specs(environ, default_campus=args.campus)
    accounts = [account_from_spec(spec, index) for index, spec in enumerate(specs)]

    print(f"准备执行 652 打卡：账号数 {len(accounts)}")
    for account, spec in zip(accounts, specs):
        location = location_from_spec(spec, args, account.selected_location)
        print(f"- {account.display_name} / {account.selected_location} / {location_summary(location)}")

    if args.dry_run:
        print("dry-run 已启用：未访问学校接口，未提交打卡。")
        return 0

    service = CheckinService()
    service.api.timeout = max(5, int(args.timeout or 20))
    failed: list[str] = []
    for account, spec in zip(accounts, specs):
        location = location_from_spec(spec, args, account.selected_location)
        result = service.perform_checkin_with_cookies(account.session_token, account, location)
        print(f"{account.display_name}: {result.message}")
        if result.task:
            print(f"  任务：{result.task.name or result.task.id}")
        if result.location:
            print(f"  位置：{location_summary(result.location)}")
        if not result.success:
            failed.append(account.display_name)

    if failed:
        print(f"打卡失败账号：{', '.join(failed)}", file=sys.stderr)
        return 1
    print("全部账号处理完成。")
    return 0


def load_account_specs(environ: Mapping[str, str], default_campus: str = "宜宾") -> list[dict[str, Any]]:
    raw_accounts = (environ.get("CHECKIN_ACCOUNTS_JSON") or "").strip()
    if raw_accounts:
        try:
            parsed = json.loads(raw_accounts)
        except json.JSONDecodeError as exc:
            raise CliConfigError(f"CHECKIN_ACCOUNTS_JSON 不是合法 JSON：{exc}") from exc
        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list) or not parsed:
            raise CliConfigError("CHECKIN_ACCOUNTS_JSON 必须是非空 JSON 数组或对象")
        return [_normalize_spec(item, default_campus) for item in parsed]

    session = (environ.get("QFHY_SESSION") or environ.get("CHECKIN_SESSION") or "").strip()
    if not session:
        raise CliConfigError("请设置 QFHY_SESSION，或设置 CHECKIN_ACCOUNTS_JSON")
    return [
        _normalize_spec(
            {
                "student_id": environ.get("CHECKIN_STUDENT_ID") or "github-actions",
                "name": environ.get("CHECKIN_NAME") or "",
                "campus": default_campus,
                "session": session,
                "address": environ.get("CHECKIN_ADDRESS") or "",
                "longitude": environ.get("CHECKIN_LONGITUDE") or "",
                "latitude": environ.get("CHECKIN_LATITUDE") or "",
            },
            default_campus,
        )
    ]


def account_from_spec(spec: Mapping[str, Any], index: int = 0) -> Account:
    session = str(spec.get("session") or "").strip()
    if not session:
        raise CliConfigError(f"第 {index + 1} 个账号缺少 session")
    student_id = str(spec.get("student_id") or f"github-actions-{index + 1}")
    name = str(spec.get("name") or "")
    campus = str(spec.get("campus") or "宜宾")
    return Account(
        id=f"gha-{index + 1}-{student_id}",
        student_id=student_id,
        name=name,
        login_type=LoginType.QR,
        selected_location=campus,
        session_token=session,
        session_expire_time=future_time_string(1),
    )


def location_from_spec(spec: Mapping[str, Any], args: argparse.Namespace, campus: str) -> CheckinLocation:
    address = str(spec.get("address") or "").strip()
    longitude = spec.get("longitude")
    latitude = spec.get("latitude")
    if address and str(longitude or "").strip() and str(latitude or "").strip():
        try:
            return CheckinLocation(campus=campus, address=address, longitude=float(longitude), latitude=float(latitude))
        except ValueError as exc:
            raise CliConfigError("自定义位置的 longitude/latitude 必须是数字") from exc

    mode = str(spec.get("location_mode") or args.location_mode or "default").lower()
    index = _coerce_int(spec.get("location_index"), args.location_index)
    random_offset = _truthy(spec.get("random_offset")) if "random_offset" in spec else bool(args.random_offset)
    max_meters = _coerce_float(spec.get("max_offset_meters"), args.max_offset_meters)

    if mode == "fixed":
        return fixed_location(campus, index)
    if mode == "random":
        return random_location_for_campus(campus, random_offset=random_offset, max_meters=max_meters)
    return default_location(campus)


def _normalize_spec(item: Any, default_campus: str) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise CliConfigError("账号配置项必须是 JSON 对象")
    data = dict(item)
    data["session"] = data.get("session") or data.get("cookies") or data.get("session_token") or data.get("qfhy_session")
    data["student_id"] = data.get("student_id") or data.get("studentId") or data.get("username")
    data["campus"] = data.get("campus") or data.get("selected_location") or default_campus
    return data


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "是", "启用"}


def _env_int(name: str, default: int) -> int:
    return _coerce_int(os.getenv(name), default)


def _env_float(name: str, default: float) -> float:
    return _coerce_float(os.getenv(name), default)


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    raise SystemExit(main())
