"""Partners module: partners table (customers/suppliers unified entity).

Revision ID: partners_20260804_0003
Revises: identity_20260804_0002
Create Date: 2026-08-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "partners_20260804_0003"
down_revision = "taxation_20260804_0004"
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
        "partners",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("partner_type", sa.String(16), nullable=False, server_default="customer"),
        sa.Column("tax_number", sa.String(64), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("credit_limit", sa.Numeric(18, 4), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "tax_number", name="uq_partners_company_tax_number"),
    )
    op.create_index("ix_partners_company_id", "partners", ["company_id"])


def downgrade() -> None:
    op.drop_table("partners")
