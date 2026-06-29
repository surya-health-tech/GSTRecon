"""Forgot-password flow for firm users."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import PasswordResetToken, Tenant, TenantMembership, User
from app.services.firm_users import LOGIN_METHOD_EMAIL
from app.services.invite_emails import send_firm_password_reset_email

log = logging.getLogger(__name__)

RESET_TTL_MINUTES = 60

GENERIC_FIRM_MESSAGE = (
    "If an account with that email exists and uses password sign-in, "
    "we sent instructions to reset your password."
)


def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _expire_unconsumed_firm_tokens(db: Session, *, user_id: int) -> None:
    now = datetime.now(timezone.utc)
    rows = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.consumed_at.is_(None),
        )
        .all()
    )
    for row in rows:
        row.consumed_at = now


def _primary_tenant_for_user(db: Session, user: User) -> Tenant | None:
    m = (
        db.query(TenantMembership)
        .filter(
            TenantMembership.user_id == user.id,
            TenantMembership.is_active.is_(True),
        )
        .first()
    )
    if m is None:
        return None
    return db.get(Tenant, m.tenant_id)


def request_firm_password_reset(db: Session, *, email: str) -> None:
    """Issue reset email when eligible. Never raises for unknown emails."""
    e = (email or "").strip().lower()
    if not e or "@" not in e:
        return
    user = (
        db.query(User)
        .filter(User.email == e, User.is_active.is_(True))
        .first()
    )
    if user is None or not user.hashed_password:
        return
    if not user.is_platform_super_admin and user.login_method != LOGIN_METHOD_EMAIL:
        return
    if not user.email:
        return

    _expire_unconsumed_firm_tokens(db, user_id=user.id)
    raw = _new_token()
    row = PasswordResetToken(
        user_id=user.id,
        token_hash=_sha256(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=RESET_TTL_MINUTES),
    )
    db.add(row)
    db.flush()

    tenant = None if user.is_platform_super_admin else _primary_tenant_for_user(db, user)
    sent, err = send_firm_password_reset_email(
        db,
        user=user,
        tenant=tenant,
        raw_token=raw,
        ttl_minutes=RESET_TTL_MINUTES,
    )
    if not sent:
        log.warning("Firm password reset email not sent user_id=%s: %s", user.id, err)
    db.commit()


def confirm_firm_password_reset(
    db: Session, *, raw_token: str, new_password: str
) -> User | None:
    raw = (raw_token or "").strip()
    if len(raw) < 32:
        return None
    th = _sha256(raw)
    row = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == th,
            PasswordResetToken.consumed_at.is_(None),
        )
        .first()
    )
    if row is None:
        return None
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        return None
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        return None

    row.consumed_at = datetime.now(timezone.utc)
    user.hashed_password = hash_password(new_password)
    user.must_change_password = False
    db.commit()
    db.refresh(user)
    return user
