"""Outbox Pattern لـ event_bus: جدول outbox_events (مهمة 6، القسم 6.6).

Revision ID: platform_20260808_0003
Revises: wfna_20260808_0002
Create Date: 2026-08-08
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "platform_20260808_0003"
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
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_name", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        *_audit_columns(),
    )
    op.create_index("ix_outbox_events_event_name", "outbox_events", ["event_name"])
    op.create_index(
        "ix_outbox_events_status_next_attempt",
        "outbox_events",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_status_next_attempt", table_name="outbox_events")
    op.drop_index("ix_outbox_events_event_name", table_name="outbox_events")
    op.drop_table("outbox_events")
