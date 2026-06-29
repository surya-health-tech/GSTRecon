"""Phone number normalization for client contacts."""

from __future__ import annotations

import re

DEFAULT_COUNTRY_CODE = "+1"
DEFAULT_FIRM_COUNTRY_CODE = "+91"

# Common dial codes for firm UI (not exhaustive).
COMMON_COUNTRY_CODES: tuple[str, ...] = (
    "+1",
    "+44",
    "+61",
    "+64",
    "+91",
    "+353",
    "+49",
    "+33",
    "+39",
    "+34",
    "+31",
    "+46",
    "+47",
    "+45",
    "+41",
    "+971",
    "+65",
    "+852",
    "+81",
    "+82",
    "+86",
)


def normalize_country_code(value: str | None) -> str | None:
    if value is None:
        return None
    s = value.strip()
    if not s:
        return None
    if not s.startswith("+"):
        s = f"+{s}"
    digits = re.sub(r"\D", "", s)
    if not digits or len(digits) > 4:
        return None
    return f"+{digits}"


def normalize_local_phone(value: str | None) -> str | None:
    if value is None:
        return None
    s = value.strip()
    if not s:
        return None
    cleaned = re.sub(r"[^\d\s().-]", "", s)
    return cleaned[:64] if cleaned else None


def format_phone_display(country_code: str | None, local: str | None) -> str | None:
    cc = normalize_country_code(country_code)
    loc = normalize_local_phone(local)
    if not loc:
        return None
    if cc:
        return f"{cc} {loc}"
    return loc


def merge_phone_fields(
    *,
    phone_country_code: str | None,
    phone: str | None,
) -> tuple[str | None, str | None]:
    return normalize_country_code(phone_country_code), normalize_local_phone(phone)


def phone_login_digits(country_code: str | None, local: str | None) -> str | None:
    """Digits entered at login (local number only, no country code)."""
    loc = normalize_local_phone(local)
    if not loc:
        return None
    digits = re.sub(r"\D", "", loc)
    if not digits:
        return None
    # Common leading trunk prefix when dialling locally (e.g. India 0).
    digits = digits.lstrip("0") or digits
    return digits[:32]


def is_valid_phone_pair(country_code: str | None, local: str | None) -> bool:
    cc = normalize_country_code(country_code)
    loc = normalize_local_phone(local)
    digits = phone_login_digits(cc, loc)
    if not cc or not loc or not digits:
        return False
    return len(digits) >= 6
