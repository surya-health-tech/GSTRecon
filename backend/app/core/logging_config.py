"""Application-wide logging: format, levels, and per-request correlation id."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
tenant_id_ctx: ContextVar[str] = ContextVar("tenant_id", default="-")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="-")
platform_access_session_id_ctx: ContextVar[str] = ContextVar("platform_access_session_id", default="-")


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("-")
        record.tenant_id = tenant_id_ctx.get("-")
        record.user_id = user_id_ctx.get("-")
        record.platform_access_session_id = platform_access_session_id_ctx.get("-")
        return True


def set_request_context(
    *,
    request_id: str | None = None,
    tenant_id: int | str | None = None,
    user_id: int | str | None = None,
    platform_access_session_id: int | str | None = None,
) -> None:
    if request_id is not None:
        request_id_ctx.set(request_id)
    if tenant_id is not None:
        tenant_id_ctx.set(str(tenant_id))
    if user_id is not None:
        user_id_ctx.set(str(user_id))
    if platform_access_session_id is not None:
        platform_access_session_id_ctx.set(str(platform_access_session_id))


def clear_request_context() -> None:
    request_id_ctx.set("-")
    tenant_id_ctx.set("-")
    user_id_ctx.set("-")
    platform_access_session_id_ctx.set("-")


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once at process startup (Docker logs / Dozzle)."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    log_format = (
        "%(asctime)s %(levelname)s "
        "[req=%(request_id)s tenant=%(tenant_id)s user=%(user_id)s pf_access=%(platform_access_session_id)s] "
        "%(name)s: %(message)s"
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(log_format, datefmt="%Y-%m-%dT%H:%M:%S%z"))
    handler.addFilter(RequestContextFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric)

    for name, pkg_level in (
        ("uvicorn", numeric),
        ("uvicorn.error", numeric),
        ("uvicorn.access", logging.WARNING),
        ("app", numeric),
        ("sqlalchemy.engine", logging.WARNING),
    ):
        logging.getLogger(name).setLevel(pkg_level)


def log_startup_banner(*, app_name: str, debug: bool, frontend_app_url: str) -> None:
    log = logging.getLogger("app.startup")
    log.info("%s starting (debug=%s frontend_app_url=%s)", app_name, debug, frontend_app_url)
