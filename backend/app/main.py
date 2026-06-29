import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging, log_startup_banner
from app.middleware.request_logging import RequestLoggingMiddleware

settings = get_settings()
configure_logging(settings.log_level)
log = logging.getLogger("app.main")

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code >= 500:
        log.error(
            "HTTP %s %s %s: %s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
        )
    elif exc.status_code >= 400 and request.url.path not in ("/api/v1/auth/login",):
        log.warning(
            "HTTP %s %s %s: %s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    detail = "Internal server error"
    if settings.debug:
        detail = str(exc)
    return JSONResponse(status_code=500, content={"detail": detail})


@app.on_event("startup")
def _on_startup() -> None:
    log_startup_banner(
        app_name=settings.app_name,
        debug=settings.debug,
        frontend_app_url=settings.frontend_app_url,
    )
    log.info("Application startup complete")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
