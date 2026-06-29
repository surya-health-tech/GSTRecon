"""Shared HTTP helpers for OAuth token exchange (Google / Microsoft)."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import get_settings

_ERR_MSG_MAX = 1500


def http_ssl_context() -> ssl.SSLContext:
    if get_settings().http_verify_ssl:
        return ssl.create_default_context()
    return ssl._create_unverified_context()


def format_http_error(exc: BaseException) -> str:
    """Prefer JSON error_description from token endpoints over generic 'HTTP Error 400'."""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        if raw.strip():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return raw.strip()[:_ERR_MSG_MAX]
            desc = data.get("error_description") or data.get("error")
            if isinstance(desc, str) and desc.strip():
                return desc.strip()[:_ERR_MSG_MAX]
            return raw.strip()[:_ERR_MSG_MAX]
        return f"HTTP {exc.code}: {exc.reason or 'request failed'}".strip()[:_ERR_MSG_MAX]
    return str(exc)[:_ERR_MSG_MAX]


def http_post_form(url: str, form: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30, context=http_ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(format_http_error(exc)) from exc
    except Exception as exc:
        raise RuntimeError(format_http_error(exc)) from exc
    if isinstance(data, dict) and data.get("error"):
        desc = data.get("error_description") or data.get("error")
        raise RuntimeError(str(desc).strip() if desc else "token endpoint error")
    return data


def http_post_json(url: str, payload: dict, *, bearer_token: str) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {bearer_token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60, context=http_ssl_context()) as resp:
            raw = resp.read().decode("utf-8")
            if not raw.strip():
                return {}
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(format_http_error(exc)) from exc
    except Exception as exc:
        raise RuntimeError(format_http_error(exc)) from exc


def http_json_get(url: str, *, bearer_token: str) -> dict:
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {bearer_token}")
    try:
        with urllib.request.urlopen(req, timeout=30, context=http_ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(format_http_error(exc)) from exc
    except Exception as exc:
        raise RuntimeError(format_http_error(exc)) from exc
