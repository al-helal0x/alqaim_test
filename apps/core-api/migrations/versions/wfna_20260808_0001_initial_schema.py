"""Workflow + Notifications + Audit modules (العضو 12): audit_log_entries,
notifications, workflow_definitions, workflow_instances.

Revision ID: wfna_20260808_0001
Revises: docs_integr_20260807_0002
Create Date: 2026-08-08

⚠️ تحقق من `down_revision` قبل التطبيق: هذا صحيح وقت تجهيز هذا الملف فقط.
إن دُمجت حزمة أخرى (مثل العضو 11) قبل هذا الملف في فرع `integration`، حدِّث
`down_revision` ليطابق الرأس الفعلي وقت الدمج — لا وقت الكتابة.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "wfna_20260808_0001"
down_revision = "docs_integr_20260807_0002"
branch_labels = None
depends_on = None


def _audit_columns():
    # نفس تعريف _audit_columns() المستخدم في migrations العضو 13
    # (docs_integr_20260807_0001_initial_schema.py) حرفياً — لا صيغة جديدة.
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "audit_log_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("event_name", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_audit_log_entries_company_id", "audit_log_entries", ["company_id"])
    op.create_index("ix_audit_log_entries_event_name", "audit_log_entries", ["event_name"])

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("event_name", sa.String(128), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_audit_columns(),
    )
    op.create_index("ix_notifications_company_id", "notifications", ["company_id"])

    op.create_table(
        "workflow_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("states", postgresql.JSONB(), nullable=False),
        sa.Column("transitions", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
    )
    op.create_index("ix_workflow_definitions_company_id", "workflow_definitions", ["company_id"])

    op.create_table(
        "workflow_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column(
            "definition_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_definitions.id"), nullable=False,
        ),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=False),
        sa.Column("current_state", sa.String(64), nullable=False),
        sa.Column("history", postgresql.JSONB(), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_workflow_instances_company_id", "workflow_instances", ["company_id"])
    op.create_index(
        "ix_workflow_instances_entity", "workflow_instances", ["entity_type", "entity_id"]
    )


def downgrade() -> None:
    op.drop_table("workflow_instances")
    op.drop_table("workflow_definitions")
    op.drop_table("notifications")
    op.drop_table("audit_log_entries")
