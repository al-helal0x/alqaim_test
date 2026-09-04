"""POS module: pos_sessions, pos_sync_queue.

Revision ID: pos_20260805_0008
Revises: sales_20260805_0007
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "pos_20260805_0008"
down_revision = "sales_20260805_0007"
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
        "pos_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("opened_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opening_cash", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("closing_cash", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_pos_sessions_company_id", "pos_sessions", ["company_id"])

    op.create_table(
        "pos_sync_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pos_sessions.id"), nullable=False),
        sa.Column("client_reference", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("sales_invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "client_reference", name="uq_pos_sync_client_reference"),
    )
    op.create_index("ix_pos_sync_queue_company_id", "pos_sync_queue", ["company_id"])
    op.create_index("ix_pos_sync_queue_session_id", "pos_sync_queue", ["session_id"])


def downgrade() -> None:
    op.drop_table("pos_sync_queue")
    op.drop_table("pos_sessions")
