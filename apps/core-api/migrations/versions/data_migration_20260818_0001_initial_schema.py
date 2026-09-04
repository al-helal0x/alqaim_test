"""data_migration module: import jobs, batches, row errors.

Revision ID: data_migration_20260818_0001
Revises: pos_20260816_0001
Create Date: 2026-08-18
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "data_migration_20260818_0001"
down_revision = "accounting_20260817_0001"
# ⚠️ إصلاح أثناء الدمج: كانت down_revision تشير إلى pos_20260816_0001 (الرأس
# الحقيقي وقت بناء هذه الحزمة). أُعيد ربطها بـaccounting_20260817_0001 لأنه
# الرأس الفعلي الحالي في المستودع بعد إصلاح صلاحيات المحاسبة (QA_FINDINGS #1).
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
        "data_migration_import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False
        ),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="connected"),
        # راجع ملاحظة أمنية في modules/data_migration/README.md: هذا مرجع
        # اتصال، والقرار النهائي بشأن تشفيره/تخزينه في Vault لم يُحسَم بعد
        # (TASK-MIG-02) — العمود هنا نص عادي مؤقتاً.
        sa.Column("connection_ref", sa.String(512), nullable=False),
        sa.Column("mappings", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_rows", sa.Integer(), nullable=False, server_default="0"),
        *_audit_columns(),
    )
    op.create_index(
        "ix_data_migration_import_jobs_company_id", "data_migration_import_jobs", ["company_id"]
    )

    op.create_table(
        "data_migration_import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_migration_import_jobs.id"),
            nullable=False,
        ),
        sa.Column("target_entity", sa.String(64), nullable=False),
        sa.Column("offset", sa.Integer(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_audit_columns(),
    )
    op.create_index(
        "ix_data_migration_import_batches_job_id", "data_migration_import_batches", ["job_id"]
    )

    op.create_table(
        "data_migration_import_row_errors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_migration_import_jobs.id"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("table_name", sa.String(128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("raw_row", postgresql.JSONB(), nullable=False),
        *_audit_columns(),
    )
    op.create_index(
        "ix_data_migration_import_row_errors_job_id",
        "data_migration_import_row_errors",
        ["job_id"],
    )


def downgrade() -> None:
    op.drop_table("data_migration_import_row_errors")
    op.drop_table("data_migration_import_batches")
    op.drop_table("data_migration_import_jobs")
