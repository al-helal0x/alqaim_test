"""Sales module: quotations, quotation_lines, sales_orders, sales_order_lines,
sales_invoices, sales_invoice_lines, credit_notes, credit_note_lines.

Revision ID: sales_20260805_0007
Revises: inventory_20260805_0006
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "sales_20260805_0007"
down_revision = "inventory_20260805_0006"
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


def _money():
    return sa.Numeric(18, 4)


def upgrade() -> None:
    op.create_table(
        "quotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quotation_number", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IQD"),
        sa.Column("subtotal", _money(), nullable=False, server_default="0"),
        sa.Column("tax_amount", _money(), nullable=False, server_default="0"),
        sa.Column("total_amount", _money(), nullable=False, server_default="0"),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "quotation_number", name="uq_quotation_number"),
    )
    op.create_index("ix_quotations_company_id", "quotations", ["company_id"])
    op.create_index("ix_quotations_partner_id", "quotations", ["partner_id"])

    op.create_table(
        "quotation_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("quotation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quotations.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", _money(), nullable=False),
        sa.Column("unit_price", _money(), nullable=False),
        sa.Column("tax_amount", _money(), nullable=False, server_default="0"),
        sa.Column("line_total", _money(), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_quotation_lines_quotation_id", "quotation_lines", ["quotation_id"])

    op.create_table(
        "sales_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quotation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quotations.id"), nullable=True),
        sa.Column("order_number", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IQD"),
        sa.Column("subtotal", _money(), nullable=False, server_default="0"),
        sa.Column("tax_amount", _money(), nullable=False, server_default="0"),
        sa.Column("total_amount", _money(), nullable=False, server_default="0"),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "order_number", name="uq_sales_order_number"),
    )
    op.create_index("ix_sales_orders_company_id", "sales_orders", ["company_id"])
    op.create_index("ix_sales_orders_partner_id", "sales_orders", ["partner_id"])

    op.create_table(
        "sales_order_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", _money(), nullable=False),
        sa.Column("unit_price", _money(), nullable=False),
        sa.Column("tax_amount", _money(), nullable=False, server_default="0"),
        sa.Column("line_total", _money(), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_sales_order_lines_sales_order_id", "sales_order_lines", ["sales_order_id"])

    op.create_table(
        "sales_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id"), nullable=True),
        sa.Column("invoice_number", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IQD"),
        sa.Column("subtotal", _money(), nullable=False, server_default="0"),
        sa.Column("discount_amount", _money(), nullable=False, server_default="0"),
        sa.Column("tax_amount", _money(), nullable=False, server_default="0"),
        sa.Column("total_amount", _money(), nullable=False, server_default="0"),
        sa.Column("journal_entry_id", sa.String(64), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "invoice_number", name="uq_sales_invoice_number"),
    )
    op.create_index("ix_sales_invoices_company_id", "sales_invoices", ["company_id"])
    op.create_index("ix_sales_invoices_partner_id", "sales_invoices", ["partner_id"])

    op.create_table(
        "sales_invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "sales_invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_invoices.id"), nullable=False
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", _money(), nullable=False),
        sa.Column("unit_price", _money(), nullable=False),
        sa.Column("tax_amount", _money(), nullable=False, server_default="0"),
        sa.Column("line_total", _money(), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_sales_invoice_lines_sales_invoice_id", "sales_invoice_lines", ["sales_invoice_id"])

    op.create_table(
        "credit_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column(
            "invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_invoices.id"), nullable=False
        ),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credit_note_number", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IQD"),
        sa.Column("total_amount", _money(), nullable=False),
        sa.Column("journal_entry_id", sa.String(64), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "credit_note_number", name="uq_credit_note_number"),
    )
    op.create_index("ix_credit_notes_company_id", "credit_notes", ["company_id"])
    op.create_index("ix_credit_notes_invoice_id", "credit_notes", ["invoice_id"])

    op.create_table(
        "credit_note_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "credit_note_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("credit_notes.id"), nullable=False
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", _money(), nullable=False),
        sa.Column("unit_price", _money(), nullable=False),
        sa.Column("line_total", _money(), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_credit_note_lines_credit_note_id", "credit_note_lines", ["credit_note_id"])


def downgrade() -> None:
    op.drop_table("credit_note_lines")
    op.drop_table("credit_notes")
    op.drop_table("sales_invoice_lines")
    op.drop_table("sales_invoices")
    op.drop_table("sales_order_lines")
    op.drop_table("sales_orders")
    op.drop_table("quotation_lines")
    op.drop_table("quotations")
