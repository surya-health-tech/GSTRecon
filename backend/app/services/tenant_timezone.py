"""Tenant IANA timezone helpers used for calendar dates and local-day UTC ranges."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.models import Tenant

DEFAULT_TENANT_TIMEZONE = "Asia/Kolkata"

# Standard IANA zones offered in firm settings and reminder configuration UIs.
STANDARD_IANA_TIMEZONES: tuple[str, ...] = (
    "Asia/Kolkata",
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "Europe/London",
    "Europe/Berlin",
    "Asia/Singapore",
    "Asia/Tokyo",
    "Australia/Sydney",
)


def normalize_tenant_timezone(tz_name: str | None) -> str:
    raw = (tz_name or DEFAULT_TENANT_TIMEZONE).strip() or DEFAULT_TENANT_TIMEZONE
    if raw in STANDARD_IANA_TIMEZONES:
        return raw
    try:
        ZoneInfo(raw)
        return raw
    except Exception:
        return DEFAULT_TENANT_TIMEZONE


def validate_tenant_timezone(tz_name: str) -> str:
    """Validate a user-selected timezone; must be a known IANA id from the standard list."""
    raw = tz_name.strip()
    if raw not in STANDARD_IANA_TIMEZONES:
        try:
            ZoneInfo(raw)
        except Exception as exc:
            raise ValueError(
                f"Unknown timezone: {tz_name}. Choose one of: {', '.join(STANDARD_IANA_TIMEZONES)}"
            ) from exc
    return raw


def tenant_zone(db: Session, tenant_id: int) -> ZoneInfo:
    tenant = db.get(Tenant, tenant_id)
    tz_name = normalize_tenant_timezone(tenant.timezone if tenant else None)
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo(DEFAULT_TENANT_TIMEZONE)


def today_for_tenant(db: Session, tenant_id: int) -> date:
    """Calendar today in the firm's configured timezone."""
    tz = tenant_zone(db, tenant_id)
    return datetime.now(timezone.utc).astimezone(tz).date()


def utc_range_for_local_dates(tz_name: str, date_from: date, date_to: date) -> tuple[datetime, datetime]:
    """Inclusive local calendar [date_from, date_to] as UTC [start, end) for timestamptz filters."""
    tz = ZoneInfo(normalize_tenant_timezone(tz_name))
    start = datetime.combine(date_from, time.min, tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc)
    return start, end


def week_start_utc_for_tenant(db: Session, tenant_id: int) -> datetime:
    """Monday 00:00 in the firm timezone, as UTC."""
    tz = tenant_zone(db, tenant_id)
    now_local = datetime.now(timezone.utc).astimezone(tz)
    monday = now_local.date() - timedelta(days=now_local.weekday())
    start_local = datetime.combine(monday, time.min, tzinfo=tz)
    return start_local.astimezone(timezone.utc)
