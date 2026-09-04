"""Initial schema for ai-platform's own database (القسم 8.5).

Revision ID: ai_20260805_0001
Revises:
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "ai_20260805_0001"
down_revision = None
branch_labels = None
depends_on = None


def _audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "ocr_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attachment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("engine_used", sa.String(32), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("completed_at", sa.String(), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_ocr_jobs_company_id", "ocr_jobs", ["company_id"])

    op.create_table(
        "invoice_extraction_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ocr_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ocr_jobs.id"), nullable=False),
        sa.Column("extracted_payload", postgresql.JSONB(), nullable=False),
        sa.Column("matched_supplier_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending_review"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.String(), nullable=True),
        *_audit_columns(),
    )
    op.create_index(
        "ix_invoice_extraction_drafts_company_id", "invoice_extraction_drafts", ["company_id"]
    )

    op.create_table(
        "entity_match_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "extraction_draft_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoice_extraction_drafts.id"), nullable=False,
        ),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("extracted_text", sa.String(), nullable=False),
        sa.Column("matched_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("user_selected_alternative_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
    )
    op.create_index(
        "ix_entity_match_suggestions_draft_id", "entity_match_suggestions", ["extraction_draft_id"]
    )

    op.create_table(
        "ai_learning_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "extraction_draft_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoice_extraction_drafts.id"), nullable=False,
        ),
        sa.Column("field_name", sa.String(64), nullable=False),
        sa.Column("ai_predicted_value", sa.String(), nullable=True),
        sa.Column("user_corrected_value", sa.String(), nullable=False),
        sa.Column("corrected_by", postgresql.UUID(as_uuid=True), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_ai_learning_feedback_company_id", "ai_learning_feedback", ["company_id"])

    op.create_table(
        "entity_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_text", sa.String(), nullable=False),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        # ملاحظة إنتاج (القسم 8.5/7.12): يُستبدَل هذا العمود بـ VECTOR(768) عبر
        # امتداد pgvector + فهرس ivfflat/hnsw عند تفعيل مطابقة Embeddings الفعلية.
        *_audit_columns(),
    )
    op.create_index("ix_entity_embeddings_company_id", "entity_embeddings", ["company_id"])


def downgrade() -> None:
    op.drop_table("entity_embeddings")
    op.drop_table("ai_learning_feedback")
    op.drop_table("entity_match_suggestions")
    op.drop_table("invoice_extraction_drafts")
    op.drop_table("ocr_jobs")
