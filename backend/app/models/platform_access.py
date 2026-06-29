"""Platform super-admin tenant portal access sessions and audit log."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlatformTenantAccessSession(Base):
    """Active or historical platform-admin access into a firm tenant portal."""

    __tablename__ = "platform_tenant_access_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform_admin_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)


class PlatformAuditLog(Base):
    """Append-only audit trail for platform-admin actions."""

    __tablename__ = "platform_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform_admin_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), index=True, nullable=True
    )
    access_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("platform_tenant_access_sessions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
