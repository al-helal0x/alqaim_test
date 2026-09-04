"""Auth hardening: refresh_tokens (hash-only, revocable) + login_attempts
(Rate Limiting / قفل حساب مؤقت على /auth/login — 5 محاولات فاشلة/15 دقيقة).

Revision ID: identity_20260808_0003
Revises: wfna_20260808_0002
Create Date: 2026-08-08
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "identity_20260808_0003"
down_revision = "wfna_20260808_0002"
branch_labels = None
depends_on = None


def _audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        # SHA-256 hex digest — لا نص صريح للتوكن يُخزَّن إطلاقاً (راجع
        # platform_core/security.py::hash_refresh_token).
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "login_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_login_attempts_email", "login_attempts", ["email"])
    op.create_index("ix_login_attempts_ip_address", "login_attempts", ["ip_address"])
    op.create_index("ix_login_attempts_created_at", "login_attempts", ["created_at"])


def downgrade() -> None:
    op.drop_table("login_attempts")
    op.drop_table("refresh_tokens")
