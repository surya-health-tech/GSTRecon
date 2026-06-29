from datetime import datetime

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_cases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("case_name", sa.String(length=255), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("tax_period_month", sa.Integer(), nullable=False),
        sa.Column("tax_period_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("gstr2b_original_filename", sa.String(length=512), nullable=True),
        sa.Column("gstr2b_stored_path", sa.String(length=1024), nullable=True),
        sa.Column("pr_original_filename", sa.String(length=512), nullable=True),
        sa.Column("pr_stored_path", sa.String(length=1024), nullable=True),
        sa.Column("gstr2b_mapping_id", sa.Integer(), nullable=True),
        sa.Column("pr_mapping_id", sa.Integer(), nullable=True),
        sa.Column("gstr2b_mapping_name", sa.String(length=255), nullable=True),
        sa.Column("pr_mapping_name", sa.String(length=255), nullable=True),
        sa.Column("summary_counts", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["gstr2b_mapping_id"], ["gstr2b_mappings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pr_mapping_id"], ["purchase_register_mappings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reconciliation_cases_tenant_id", "reconciliation_cases", ["tenant_id"])
    op.create_index("ix_reconciliation_cases_client_id", "reconciliation_cases", ["client_id"])

    op.create_table(
        "reconciliation_case_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("match_status", sa.String(length=64), nullable=True),
        sa.Column("remarks", sa.String(length=512), nullable=True),
        sa.Column("portal_data", postgresql.JSONB(), nullable=True),
        sa.Column("book_data", postgresql.JSONB(), nullable=True),
        sa.Column("normalized", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["reconciliation_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reconciliation_case_records_case_id", "reconciliation_case_records", ["case_id"])
    op.create_index("ix_reconciliation_case_records_category", "reconciliation_case_records", ["category"])


def downgrade() -> None:
    op.drop_index("ix_reconciliation_case_records_category", table_name="reconciliation_case_records")
    op.drop_index("ix_reconciliation_case_records_case_id", table_name="reconciliation_case_records")
    op.drop_table("reconciliation_case_records")
    op.drop_index("ix_reconciliation_cases_client_id", table_name="reconciliation_cases")
    op.drop_index("ix_reconciliation_cases_tenant_id", table_name="reconciliation_cases")
    op.drop_table("reconciliation_cases")
