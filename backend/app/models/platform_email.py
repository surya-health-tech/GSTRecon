from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlatformEmailConnection(Base):
    """Singleton platform outbound mail (tenant invites). OAuth preferred over env SMTP."""

    __tablename__ = "platform_email_connection"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # gmail | microsoft365
    account_email: Mapped[str] = mapped_column(String(320), nullable=False)
    from_display_name: Mapped[str] = mapped_column(String(255), default="FinTaskFlow", nullable=False)
    oauth_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
