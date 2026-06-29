"""initial GST reconciliation platform schema

Revision ID: 0001
Revises:
Create Date: 2026-06-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("timezone", sa.String(length=64), server_default="Asia/Kolkata", nullable=False),
        sa.Column("plan_key", sa.String(length=32), server_default="starter", nullable=False),
        sa.Column("max_users", sa.Integer(), server_default="50", nullable=False),
        sa.Column("max_clients", sa.Integer(), server_default="500", nullable=False),
        sa.Column("storage_limit_mb", sa.Integer(), server_default="10240", nullable=False),
        sa.Column("max_email_accounts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tenants_slug"), "tenants", ["slug"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("phone_country_code", sa.String(length=8), nullable=True),
        sa.Column("phone_login_digits", sa.String(length=32), nullable=True),
        sa.Column("login_method", sa.String(length=32), server_default="email", nullable=False),
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_platform_super_admin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True, postgresql_where=sa.text("email IS NOT NULL"))
    op.create_index(op.f("ix_users_phone_login_digits"), "users", ["phone_login_digits"], unique=False)

    op.create_table(
        "invitations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_invitations_email"), "invitations", ["email"], unique=False)

    op.create_table(
        "tenant_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_membership_user_tenant"),
    )

    op.create_table(
        "tenant_role_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("permissions_json", JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "role", name="uq_tenant_role_permissions_tenant_role"),
    )
    op.create_index("ix_tenant_role_permissions_tenant_id", "tenant_role_permissions", ["tenant_id"])

    op.create_table(
        "platform_email_connection",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("account_email", sa.String(length=320), nullable=False),
        sa.Column("from_display_name", sa.String(length=255), server_default="GST Reconciliation", nullable=False),
        sa.Column("oauth_access_token", sa.Text(), nullable=True),
        sa.Column("oauth_refresh_token", sa.Text(), nullable=True),
        sa.Column("oauth_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "platform_tenant_access_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("platform_admin_user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["platform_admin_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_platform_tenant_access_sessions_platform_admin_user_id",
        "platform_tenant_access_sessions",
        ["platform_admin_user_id"],
    )
    op.create_index(
        "ix_platform_tenant_access_sessions_tenant_id",
        "platform_tenant_access_sessions",
        ["tenant_id"],
    )

    op.create_table(
        "platform_audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("platform_admin_user_id", sa.Integer(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("access_session_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["access_session_id"], ["platform_tenant_access_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["platform_admin_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_platform_audit_log_platform_admin_user_id", "platform_audit_log", ["platform_admin_user_id"])
    op.create_index("ix_platform_audit_log_tenant_id", "platform_audit_log", ["tenant_id"])
    op.create_index("ix_platform_audit_log_access_session_id", "platform_audit_log", ["access_session_id"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_platform_audit_log_access_session_id", table_name="platform_audit_log")
    op.drop_index("ix_platform_audit_log_tenant_id", table_name="platform_audit_log")
    op.drop_index("ix_platform_audit_log_platform_admin_user_id", table_name="platform_audit_log")
    op.drop_table("platform_audit_log")
    op.drop_index("ix_platform_tenant_access_sessions_tenant_id", table_name="platform_tenant_access_sessions")
    op.drop_index(
        "ix_platform_tenant_access_sessions_platform_admin_user_id",
        table_name="platform_tenant_access_sessions",
    )
    op.drop_table("platform_tenant_access_sessions")
    op.drop_table("platform_email_connection")
    op.drop_index("ix_tenant_role_permissions_tenant_id", table_name="tenant_role_permissions")
    op.drop_table("tenant_role_permissions")
    op.drop_table("tenant_memberships")
    op.drop_index(op.f("ix_invitations_email"), table_name="invitations")
    op.drop_table("invitations")
    op.drop_index(op.f("ix_users_phone_login_digits"), table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_tenants_slug"), table_name="tenants")
    op.drop_table("tenants")
