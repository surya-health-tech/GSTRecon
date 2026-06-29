import os
from functools import lru_cache
from typing import Any, Self
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLATFORM_EMAIL_OAUTH_CALLBACK_PATH = "/api/v1/platform/email/oauth/callback"
DEFAULT_API_PORT = 8002


def public_api_base_url(frontend_app_url: str, api_port: int = DEFAULT_API_PORT) -> str:
    """Derive public API origin from the SPA URL.

    - Production HTTPS (nginx): https://domain → https://domain (/api on 443, not :8001).
    - Local Vite: http://localhost:5174 → http://localhost:8001.
    - HTTP + IP: http://206.x.x.x:5174 → http://206.x.x.x:8001.
    """
    p = urlparse(frontend_app_url.strip())
    scheme = p.scheme or "http"
    host = p.hostname or "localhost"
    port = p.port

    if port is None or port in (80, 443):
        return f"{scheme}://{host}"
    if scheme == "https":
        return f"{scheme}://{host}"
    if port in (5173, 5174):
        return f"{scheme}://{host}:{api_port}"
    return f"{scheme}://{host}:{port}"


class Settings(BaseSettings):
    # In Docker, compose injects env from host backend/.env; do not bake .env into the image.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    app_name: str = "GSTRecon API"
    debug: bool = False
    log_level: str = "INFO"

    # Playwright / local E2E only — never enable on production.
    e2e_test_hooks_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("E2E_TEST_HOOKS", "E2E_TEST_HOOKS_ENABLED"),
    )
    e2e_hooks_secret: str = Field(
        default="local-e2e-only",
        validation_alias=AliasChoices("E2E_HOOKS_SECRET"),
    )

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5433/gstrecon"

    jwt_secret_key: str = "change-me-in-production-use-long-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    cors_origins: str = "http://localhost:5175,http://127.0.0.1:5175"

    invitation_expire_days: int = 7

    frontend_app_url: str = "http://localhost:5175"

    # Outbound HTTPS (OAuth token refresh, Gmail API). Set false behind TLS-inspecting proxies (dev only).
    http_verify_ssl: bool = Field(
        default=True,
        validation_alias=AliasChoices("HTTP_VERIFY_SSL", "PLATFORM_SMTP_VERIFY_SSL"),
    )

    # Platform admin SMTP (new-tenant / firm-admin invites from the platform console).
    platform_smtp_host: str = ""
    platform_smtp_port: int = 587
    platform_smtp_user: str = ""
    platform_smtp_password: str = ""
    platform_smtp_use_tls: bool = True
    platform_email_from: str = ""
    platform_email_from_name: str = "GSTRecon"

    # Optional firm transactional SMTP when Gmail is not connected (team + portal invites).
    firm_invite_smtp_host: str = ""
    firm_invite_smtp_port: int = 587
    firm_invite_smtp_user: str = ""
    firm_invite_smtp_password: str = ""
    firm_invite_smtp_use_tls: bool = True
    firm_invite_smtp_verify_ssl: bool = True
    firm_invite_email_from: str = ""
    firm_invite_email_from_name: str = ""

    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    # Always derived from FRONTEND_APP_URL in derive_oauth_redirect_uris (env values ignored).
    google_oauth_redirect_uri: str = ""

    microsoft_oauth_client_id: str = ""
    microsoft_oauth_client_secret: str = ""
    microsoft_oauth_tenant_id: str = "common"
    microsoft_oauth_redirect_uri: str = ""

    platform_admin_email: str = "admin@localhost"
    platform_admin_password: str = "Accsys2026$"
    platform_admin_name: str = "Platform Admin"
    # Platform invite OAuth reuses the redirect URIs above (same Entra / Google app registration).

    # outlook: https://outlook.office.com/IMAP... (Microsoft Learn scope table).
    # office365: https://outlook.office365.com/IMAP... (some tenants align better with the IMAP hostname).
    # graph: https://graph.microsoft.com/IMAP... when Entra only lists IMAP under Microsoft Graph.
    microsoft365_oauth_token_resource: str = "outlook"

    file_storage_dir: str = "data/uploads"
    triage_attachment_max_bytes: int = 25 * 1024 * 1024

    @model_validator(mode="before")
    @classmethod
    def coalesce_ssl_verify_env(cls, data: Any) -> Any:
        """Honor PLATFORM_SMTP_VERIFY_SSL / HTTP_VERIFY_SSL for http_verify_ssl (pydantic env alias gap)."""
        merged: dict[str, Any] = dict(data) if isinstance(data, dict) else {}
        for key in ("HTTP_VERIFY_SSL", "PLATFORM_SMTP_VERIFY_SSL"):
            if key not in merged and key in os.environ:
                merged[key] = os.environ[key]
        for key in ("HTTP_VERIFY_SSL", "PLATFORM_SMTP_VERIFY_SSL"):
            if key in merged and "http_verify_ssl" not in merged:
                merged["http_verify_ssl"] = merged[key]
        return merged

    @field_validator("http_verify_ssl", mode="before")
    @classmethod
    def parse_bool_env(cls, value: Any) -> Any:
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("0", "false", "no", "off"):
                return False
            if v in ("1", "true", "yes", "on"):
                return True
        return value

    @model_validator(mode="after")
    def derive_oauth_redirect_uris(self) -> Self:
        api_base = public_api_base_url(self.frontend_app_url)
        callback = f"{api_base.rstrip('/')}{PLATFORM_EMAIL_OAUTH_CALLBACK_PATH}"
        object.__setattr__(self, "google_oauth_redirect_uri", callback)
        object.__setattr__(self, "microsoft_oauth_redirect_uri", callback)
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
