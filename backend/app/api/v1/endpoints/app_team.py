from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_db, require_permission
from app.models import Invitation, TenantMembership, User
from app.schemas.tenant import InvitationCreatedResponse
from app.schemas.users import (
    CreateFirmUserRequest,
    CreateFirmUserResponse,
    FirmUserOut,
    MembershipRoleUpdate,
    MembershipStatusUpdate,
    TeamMemberRow,
    UpdateFirmUserRequest,
)
from app.services.firm_users import create_firm_user, firm_user_out, update_firm_user
from app.services.invitations import active_firm_member_exists, resend_invitation
from app.services.team import (
    FIRM_ROLES,
    count_active_admins,
    user_activity_blockers,
)

router = APIRouter()


def _assert_inviter_may_assign_role(ctx: TenantContext, role: str) -> None:
    if ctx.membership.role == "manager" and role != "staff":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Managers can only invite staff members.",
        )


def _get_membership(
    db: Session, ctx: TenantContext, user_id: int
) -> tuple[TenantMembership, User]:
    row = (
        db.query(TenantMembership, User)
        .join(User, User.id == TenantMembership.user_id)
        .filter(
            TenantMembership.tenant_id == ctx.tenant.id,
            TenantMembership.user_id == user_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not in this firm")
    return row


@router.get("/users", response_model=list[TeamMemberRow])
def list_firm_users(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("team.view")),
) -> list[TeamMemberRow]:
    tid = ctx.tenant.id
    out: list[TeamMemberRow] = []

    member_rows = (
        db.query(TenantMembership, User)
        .join(User, User.id == TenantMembership.user_id)
        .filter(TenantMembership.tenant_id == tid)
        .order_by(User.full_name, User.id)
        .all()
    )
    for m, u in member_rows:
        member_status = "active" if m.is_active else "inactive"
        out.append(
            TeamMemberRow(
                kind="member",
                status=member_status,
                user_id=u.id,
                full_name=u.full_name,
                email=u.email,
                role=m.role,
                membership_active=m.is_active,
                login_method=u.login_method,
                phone=u.phone,
                phone_country_code=u.phone_country_code,
            )
        )

    now = datetime.now(timezone.utc)
    pending_invites = (
        db.query(Invitation)
        .filter(Invitation.tenant_id == tid, Invitation.accepted_at.is_(None))
        .order_by(Invitation.full_name, Invitation.id)
        .all()
    )
    for inv in pending_invites:
        if active_firm_member_exists(db, tid, inv.email):
            continue
        invite_status = "invited" if inv.expires_at > now else "expired"
        out.append(
            TeamMemberRow(
                kind="invitation",
                status=invite_status,
                invitation_id=inv.id,
                full_name=inv.full_name,
                email=inv.email,
                role=inv.role,
                login_method="email",
                invitation_expires_at=inv.expires_at,
            )
        )

    out.sort(key=lambda r: (r.full_name or "").casefold())
    return out


@router.post("/users", response_model=CreateFirmUserResponse, status_code=status.HTTP_201_CREATED)
def create_firm_team_member(
    body: CreateFirmUserRequest,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("team.add")),
) -> CreateFirmUserResponse:
    _assert_inviter_may_assign_role(ctx, body.role)
    return create_firm_user(
        db, tenant_id=ctx.tenant.id, body=body, actor_user_id=ctx.membership.user_id
    )


@router.patch("/users/{user_id}/profile", response_model=FirmUserOut)
def update_firm_team_member(
    user_id: int,
    body: UpdateFirmUserRequest,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("team.edit")),
) -> FirmUserOut:
    if user_id == ctx.membership.user_id and body.role is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role from this screen.",
        )
    return update_firm_user(
        db,
        tenant_id=ctx.tenant.id,
        user_id=user_id,
        body=body,
        actor_user_id=ctx.membership.user_id,
    )


@router.patch("/users/{user_id}", response_model=FirmUserOut)
def set_user_membership_status(
    user_id: int,
    body: MembershipStatusUpdate,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("team.edit")),
) -> FirmUserOut:
    if user_id == ctx.membership.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own membership from this screen.",
        )
    m, u = _get_membership(db, ctx, user_id)
    if not body.membership_active and m.role == "tenant_admin":
        if count_active_admins(db, ctx.tenant.id, exclude_user_id=user_id) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last firm administrator.",
            )
    m.is_active = body.membership_active
    db.commit()
    return firm_user_out(m, u)


@router.patch("/users/{user_id}/role", response_model=FirmUserOut)
def set_user_role(
    user_id: int,
    body: MembershipRoleUpdate,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("team.assign_roles")),
) -> FirmUserOut:
    if body.role not in FIRM_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    if user_id == ctx.membership.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role from this screen.",
        )
    m, u = _get_membership(db, ctx, user_id)
    if m.role == "tenant_admin" and body.role != "tenant_admin":
        if count_active_admins(db, ctx.tenant.id, exclude_user_id=user_id) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change the role of the last firm administrator.",
            )
    m.role = body.role
    db.commit()
    return firm_user_out(m, u)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_firm_user(
    user_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("team.remove")),
) -> None:
    if user_id == ctx.membership.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove yourself from the firm.",
        )
    m, u = _get_membership(db, ctx, user_id)
    if m.role == "tenant_admin" and count_active_admins(db, ctx.tenant.id, exclude_user_id=user_id) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last firm administrator.",
        )
    blockers = user_activity_blockers(db, ctx.tenant.id, user_id)
    if blockers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cannot remove this user because they have linked activity: "
                + ", ".join(blockers)
                + ". Deactivate the user instead."
            ),
        )
    db.delete(m)
    other_memberships = (
        db.query(TenantMembership).filter(TenantMembership.user_id == user_id).count()
    )
    if other_memberships == 0:
        u.is_active = False
    db.commit()


@router.post(
    "/invitations/{invitation_id}/resend",
    response_model=InvitationCreatedResponse,
)
def resend_firm_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("team.add")),
) -> InvitationCreatedResponse:
    return resend_invitation(db, ctx.tenant.id, invitation_id)
