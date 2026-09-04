"""Initial schema: taxation module (tax_rates, e_invoice_submissions) — العضو 6.

Revision ID: taxation_20260804_0004
Revises: accounting_20260804_0003
Create Date: 2026-08-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "taxation_20260804_0004"
down_revision = "accounting_20260804_0003"
branch_labels = None
depends_on = None

SUBMISSION_STATUS_ENUM = postgresql.ENUM(
    "pending", "submitted", "accepted", "rejected", "failed",
    name="e_invoice_submission_status",
    create_type=False,
)


def _audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    SUBMISSION_STATUS_ENUM.create(bind, checkfirst=True)

    op.create_table(
        "tax_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("rate_percent", sa.Numeric(6, 4), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
    )
    op.create_index("ix_tax_rates_company_id", "tax_rates", ["company_id"])

    op.create_table(
        "e_invoice_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("source_document_type", sa.String(64), nullable=False),
        sa.Column("source_document_id", sa.String(64), nullable=False),
        sa.Column("status", SUBMISSION_STATUS_ENUM, nullable=False, server_default="pending"),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_e_invoice_submissions_company_id", "e_invoice_submissions", ["company_id"])
    op.create_index(
        "ix_e_invoice_submissions_source_document_id", "e_invoice_submissions", ["source_document_id"]
    )


def downgrade() -> None:
    op.drop_table("e_invoice_submissions")
    op.drop_table("tax_rates")
    bind = op.get_bind()
    SUBMISSION_STATUS_ENUM.drop(bind, checkfirst=True)
