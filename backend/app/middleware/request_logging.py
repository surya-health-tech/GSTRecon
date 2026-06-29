"""HTTP request logging with correlation id (``X-Request-ID``)."""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import clear_request_context, set_request_context

log = logging.getLogger("app.http")

_SKIP_PATHS = frozenset({"/health", "/openapi.json", "/docs", "/redoc"})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = (request.headers.get("x-request-id") or "").strip() or uuid.uuid4().hex[:16]
        set_request_context(request_id=request_id)

        tenant_hint = request.headers.get("x-tenant-id")
        if tenant_hint:
            set_request_context(tenant_id=tenant_hint)

        path = request.url.path
        skip_body = path in _SKIP_PATHS or path.startswith("/docs")

        started = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - started) * 1000
            response.headers["X-Request-ID"] = request_id
            if not skip_body:
                level = logging.INFO
                if response.status_code >= 500:
                    level = logging.ERROR
                elif response.status_code >= 400:
                    level = logging.WARNING
                log.log(
                    level,
                    "%s %s -> %s %.0fms",
                    request.method,
                    path,
                    response.status_code,
                    elapsed_ms,
                )
            return response
        except Exception:
            elapsed_ms = (time.perf_counter() - started) * 1000
            log.exception(
                "%s %s failed after %.0fms",
                request.method,
                path,
                elapsed_ms,
            )
            raise
        finally:
            clear_request_context()
