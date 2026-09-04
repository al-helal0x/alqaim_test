"""Documents + Integrations modules (العضو 13): documents, webhook_subscriptions,
webhook_deliveries. platform_admin لا يحتاج جدولاً جديداً — يعيد استخدام
companies.is_active الموجود أصلاً منذ platform_20260804_0001.

Revision ID: docs_integr_20260807_0001
Revises: platform_20260806_0005
Create Date: 2026-08-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "docs_integr_20260807_0001"
down_revision = "platform_20260806_0005"
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
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_documents_company_id", "documents", ["company_id"])
    op.create_index("ix_documents_entity_type", "documents", ["entity_type"])
    op.create_index("ix_documents_entity_id", "documents", ["entity_id"])

    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("target_url", sa.String(2048), nullable=False),
        sa.Column("secret", sa.String(128), nullable=False),
        sa.Column("event_types", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
    )
    op.create_index("ix_webhook_subscriptions_company_id", "webhook_subscriptions", ["company_id"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column(
            "subscription_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("webhook_subscriptions.id"), nullable=False,
        ),
        sa.Column("event_name", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_webhook_deliveries_company_id", "webhook_deliveries", ["company_id"])
    op.create_index("ix_webhook_deliveries_subscription_id", "webhook_deliveries", ["subscription_id"])


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_subscriptions")
    op.drop_table("documents")
