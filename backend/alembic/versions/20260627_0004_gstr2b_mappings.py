"""gstr2b mappings

Revision ID: 0004
Revises: 0003
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gstr2b_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("mapping_name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("original_filename", sa.String(length=512), nullable=True),
        sa.Column("stored_file_path", sa.String(length=1024), nullable=True),
        sa.Column("sheet_mappings", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "mapping_name", "version", name="uq_gstr2b_mapping_tenant_name_version"),
    )
    op.create_index("ix_gstr2b_mappings_tenant_id", "gstr2b_mappings", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_gstr2b_mappings_tenant_id", table_name="gstr2b_mappings")
    op.drop_table("gstr2b_mappings")
