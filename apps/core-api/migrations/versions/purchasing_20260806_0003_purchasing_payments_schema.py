"""purchasing + payments tables (العضو 5).

Revision ID: purchasing_20260806_0003
Revises: inv_sales_pos_20260805_0009
Create Date: 2026-08-06
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "purchasing_20260806_0003"
down_revision = "inv_sales_pos_20260805_0009"
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
        "purchase_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_number", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="IQD"),
        sa.Column("exchange_rate", sa.Numeric(18, 6), nullable=False, server_default="1"),
        sa.Column("subtotal", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *_audit_columns(),
    )
    op.create_index("ix_purchase_orders_company_id", "purchase_orders", ["company_id"])
    op.create_index("ix_purchase_orders_supplier_id", "purchase_orders", ["supplier_id"])

    op.create_table(
        "purchase_order_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "purchase_order_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_orders.id"), nullable=False,
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 4), nullable=False),
        *_audit_columns(),
    )
    op.create_index(
        "ix_purchase_order_lines_order_id", "purchase_order_lines", ["purchase_order_id"]
    )

    op.create_table(
        "purchase_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "purchase_order_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_orders.id"), nullable=True,
        ),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_number", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="IQD"),
        sa.Column("exchange_rate", sa.Numeric(18, 6), nullable=False, server_default="1"),
        sa.Column("subtotal", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("paid_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("journal_entry_ref", sa.String(64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *_audit_columns(),
    )
    op.create_index("ix_purchase_invoices_company_id", "purchase_invoices", ["company_id"])
    op.create_index("ix_purchase_invoices_supplier_id", "purchase_invoices", ["supplier_id"])

    op.create_table(
        "purchase_invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_invoices.id"), nullable=False,
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 4), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_purchase_invoice_lines_invoice_id", "purchase_invoice_lines", ["invoice_id"])

    op.create_table(
        "bank_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("bank_name", sa.String(255), nullable=True),
        sa.Column("account_number", sa.String(64), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="IQD"),
        sa.Column("opening_balance", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
    )
    op.create_index("ix_bank_accounts_company_id", "bank_accounts", ["company_id"])

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "bank_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id"),
            nullable=True,
        ),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_number", sa.String(64), nullable=False),
        sa.Column("reference_invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="IQD"),
        sa.Column("method", sa.String(16), nullable=False, server_default="cash"),
        sa.Column("status", sa.String(16), nullable=False, server_default="confirmed"),
        sa.Column("journal_entry_ref", sa.String(64), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_payments_company_id", "payments", ["company_id"])
    op.create_index("ix_payments_supplier_id", "payments", ["supplier_id"])

    op.create_table(
        "receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "bank_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id"),
            nullable=True,
        ),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("receipt_number", sa.String(64), nullable=False),
        sa.Column("reference_invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="IQD"),
        sa.Column("method", sa.String(16), nullable=False, server_default="cash"),
        sa.Column("status", sa.String(16), nullable=False, server_default="confirmed"),
        sa.Column("journal_entry_ref", sa.String(64), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_receipts_company_id", "receipts", ["company_id"])
    op.create_index("ix_receipts_customer_id", "receipts", ["customer_id"])


def downgrade() -> None:
    op.drop_table("receipts")
    op.drop_table("payments")
    op.drop_table("bank_accounts")
    op.drop_table("purchase_invoice_lines")
    op.drop_table("purchase_invoices")
    op.drop_table("purchase_order_lines")
    op.drop_table("purchase_orders")
