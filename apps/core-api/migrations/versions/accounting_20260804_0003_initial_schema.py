"""Initial schema: accounting module (chart of accounts, journal entries,
fiscal years/periods, cost centers) — العضو 6.

Revision ID: accounting_20260804_0003
Revises: identity_20260804_0002
Create Date: 2026-08-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "accounting_20260804_0003"
down_revision = "identity_20260804_0002"
branch_labels = None
depends_on = None


ACCOUNT_TYPE_ENUM = postgresql.ENUM(
    "asset", "liability", "equity", "revenue", "expense",
    name="account_type",
    create_type=False,
)
NORMAL_BALANCE_ENUM = postgresql.ENUM(
    "debit", "credit", name="account_normal_balance", create_type=False
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
    ACCOUNT_TYPE_ENUM.create(bind, checkfirst=True)
    NORMAL_BALANCE_ENUM.create(bind, checkfirst=True)

    op.create_table(
        "cost_centers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "code", name="uq_cost_centers_company_code"),
    )
    op.create_index("ix_cost_centers_company_id", "cost_centers", ["company_id"])

    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("account_type", ACCOUNT_TYPE_ENUM, nullable=False),
        sa.Column("normal_balance", NORMAL_BALANCE_ENUM, nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("is_postable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "code", name="uq_accounts_company_code"),
    )
    op.create_index("ix_accounts_company_id", "accounts", ["company_id"])

    op.create_table(
        "fiscal_years",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "code", name="uq_fiscal_years_company_code"),
    )
    op.create_index("ix_fiscal_years_company_id", "fiscal_years", ["company_id"])

    op.create_table(
        "fiscal_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("fiscal_year_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fiscal_years.id"), nullable=False),
        sa.Column("period_number", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("closed_at", sa.Date(), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("fiscal_year_id", "period_number", name="uq_fiscal_period_number"),
    )
    op.create_index("ix_fiscal_periods_company_id", "fiscal_periods", ["company_id"])
    op.create_index("ix_fiscal_periods_fiscal_year_id", "fiscal_periods", ["fiscal_year_id"])

    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("fiscal_period_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fiscal_periods.id"), nullable=False),
        sa.Column("entry_number", sa.String(64), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("source_document_type", sa.String(64), nullable=True),
        sa.Column("source_document_id", sa.String(64), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IQD"),
        sa.Column("is_reversed", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "entry_number", name="uq_journal_entries_number"),
    )
    op.create_index("ix_journal_entries_company_id", "journal_entries", ["company_id"])
    op.create_index("ix_journal_entries_fiscal_period_id", "journal_entries", ["fiscal_period_id"])

    op.create_table(
        "journal_entry_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("cost_center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cost_centers.id"), nullable=True),
        sa.Column("debit", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("description", sa.String(255), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_journal_entry_lines_company_id", "journal_entry_lines", ["company_id"])
    op.create_index("ix_journal_entry_lines_journal_entry_id", "journal_entry_lines", ["journal_entry_id"])
    op.create_index("ix_journal_entry_lines_account_id", "journal_entry_lines", ["account_id"])


def downgrade() -> None:
    op.drop_table("journal_entry_lines")
    op.drop_table("journal_entries")
    op.drop_table("fiscal_periods")
    op.drop_table("fiscal_years")
    op.drop_table("accounts")
    op.drop_table("cost_centers")
    bind = op.get_bind()
    ACCOUNT_TYPE_ENUM.drop(bind, checkfirst=True)
    NORMAL_BALANCE_ENUM.drop(bind, checkfirst=True)
