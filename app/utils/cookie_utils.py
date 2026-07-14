from __future__ import annotations

from http.cookies import SimpleCookie
from typing import Iterable


def cookie_jar_to_string(cookie_jar) -> str:
    pairs = []
    for cookie in cookie_jar:
        if cookie.name and cookie.value:
            pairs.append(f"{cookie.name}={cookie.value}")
    return "; ".join(pairs)


def parse_cookie_pairs(cookie_string: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    if not cookie_string:
        return result
    for part in cookie_string.split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue
        name, value = item.split("=", 1)
        if name and value:
            result[name.strip()] = value.strip()
    return result


def merge_cookie_strings(*cookie_strings: str | None) -> str:
    merged: dict[str, str] = {}
    for cookie_string in cookie_strings:
        merged.update(parse_cookie_pairs(cookie_string))
    return "; ".join(f"{name}={value}" for name, value in merged.items())


def extract_cookie_value(cookie_string: str | None, name: str) -> str | None:
    return parse_cookie_pairs(cookie_string).get(name)


def remove_cookie(cookie_string: str | None, name: str) -> str:
    pairs = parse_cookie_pairs(cookie_string)
    pairs.pop(name, None)
    return "; ".join(f"{key}={value}" for key, value in pairs.items())


def set_cookie_headers_to_string(headers: Iterable[str] | None) -> str:
    if not headers:
        return ""
    pairs: list[str] = []
    for header in headers:
        cookie = SimpleCookie()
        try:
            cookie.load(header)
        except Exception:
            continue
        for key, morsel in cookie.items():
            if morsel.value:
                pairs.append(f"{key}={morsel.value}")
    return "; ".join(pairs)


def response_set_cookie_headers(response) -> list[str]:
    raw_headers = getattr(getattr(response, "raw", None), "headers", None)
    if raw_headers is not None:
        if hasattr(raw_headers, "getlist"):
            values = raw_headers.getlist("Set-Cookie")
            if values:
                return values
        if hasattr(raw_headers, "get_all"):
            values = raw_headers.get_all("Set-Cookie")
            if values:
                return list(values)
    value = response.headers.get("Set-Cookie", "")
    return [value] if value else []
