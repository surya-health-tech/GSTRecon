from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReconciliationCase(Base):
    __tablename__ = "reconciliation_cases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tax_period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    gstr2b_original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    gstr2b_stored_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    pr_original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pr_stored_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    gstr2b_mapping_id: Mapped[int | None] = mapped_column(
        ForeignKey("gstr2b_mappings.id", ondelete="SET NULL"), nullable=True
    )
    pr_mapping_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_register_mappings.id", ondelete="SET NULL"), nullable=True
    )
    gstr2b_mapping_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pr_mapping_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary_counts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReconciliationCaseRecord(Base):
    __tablename__ = "reconciliation_case_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("reconciliation_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    match_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remarks: Mapped[str | None] = mapped_column(String(512), nullable=True)
    portal_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    book_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    normalized: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
