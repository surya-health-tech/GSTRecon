import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings

log = logging.getLogger(__name__)
from app.models import Invitation, Tenant, TenantMembership, User
from app.schemas.tenant import InvitationCreate, InvitationCreatedResponse
from app.services.invite_emails import InviteChannel, build_accept_invite_url, send_team_invitation_email


def _hash_invite_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def active_firm_member_exists(db: Session, tenant_id: int, email: str) -> bool:
    normalized = email.strip().lower()
    if not normalized:
        return False
    row = (
        db.query(TenantMembership.id)
        .join(User, User.id == TenantMembership.user_id)
        .filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.is_active.is_(True),
            User.email == normalized,
        )
        .first()
    )
    return row is not None


def find_pending_invitation(db: Session, tenant_id: int, email: str) -> Invitation | None:
    now = datetime.now(timezone.utc)
    return (
        db.query(Invitation)
        .filter(
            Invitation.tenant_id == tenant_id,
            Invitation.email == email.lower(),
            Invitation.accepted_at.is_(None),
            Invitation.expires_at > now,
        )
        .order_by(Invitation.id.desc())
        .first()
    )


def _send_invitation_email(
    db: Session,
    *,
    tenant_id: int,
    inv: Invitation,
    raw_token: str,
    invite_channel: InviteChannel,
) -> tuple[bool, str | None]:
    tenant = db.get(Tenant, tenant_id)
    tenant_name = tenant.name if tenant else "your firm"
    return send_team_invitation_email(
        db,
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        to_email=inv.email,
        to_name=inv.full_name,
        role=inv.role,
        raw_token=raw_token,
        channel=invite_channel,
    )


def resend_invitation(
    db: Session,
    tenant_id: int,
    invitation_id: int,
    *,
    invite_channel: InviteChannel = "firm",
) -> InvitationCreatedResponse:
    inv = (
        db.query(Invitation)
        .filter(Invitation.id == invitation_id, Invitation.tenant_id == tenant_id)
        .first()
    )
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    if inv.accepted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation was already accepted.",
        )
    settings = get_settings()
    raw_token = secrets.token_urlsafe(32)
    inv.token_hash = _hash_invite_token(raw_token)
    inv.expires_at = datetime.now(timezone.utc) + timedelta(days=settings.invitation_expire_days)
    db.commit()
    db.refresh(inv)

    invite_url = build_accept_invite_url(raw_token)
    email_sent, email_error = _send_invitation_email(
        db, tenant_id=tenant_id, inv=inv, raw_token=raw_token, invite_channel=invite_channel
    )
    return InvitationCreatedResponse(
        invitation_id=inv.id,
        email=inv.email,
        expires_at=inv.expires_at.isoformat(),
        invite_token=raw_token,
        invite_url=invite_url,
        email_sent=email_sent,
        email_error=email_error,
        resent=True,
    )


def create_invitation(
    db: Session,
    tenant_id: int,
    body: InvitationCreate,
    *,
    invite_channel: InviteChannel = "firm",
) -> InvitationCreatedResponse:
    pending = find_pending_invitation(db, tenant_id, body.email)
    if pending is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A pending invitation already exists for this email. "
                "Use Resend invitation instead of creating a new one."
            ),
        )

    if active_firm_member_exists(db, tenant_id, body.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already on your team. Edit their role on the Team page instead of inviting again.",
        )

    settings = get_settings()
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_invite_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.invitation_expire_days)

    inv = Invitation(
        tenant_id=tenant_id,
        email=body.email.lower(),
        full_name=body.full_name,
        role=body.role,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)

    invite_url = build_accept_invite_url(raw_token)
    email_sent, email_error = _send_invitation_email(
        db, tenant_id=tenant_id, inv=inv, raw_token=raw_token, invite_channel=invite_channel
    )
    if email_sent:
        log.info(
            "Team invitation email sent tenant_id=%s channel=%s to=%s role=%s",
            tenant_id,
            invite_channel,
            inv.email,
            inv.role,
        )
    else:
        log.warning(
            "Team invitation email not sent tenant_id=%s channel=%s to=%s: %s",
            tenant_id,
            invite_channel,
            inv.email,
            email_error or "unknown",
        )

    return InvitationCreatedResponse(
        invitation_id=inv.id,
        email=inv.email,
        expires_at=inv.expires_at.isoformat(),
        invite_token=raw_token,
        invite_url=invite_url,
        email_sent=email_sent,
        email_error=email_error,
    )
