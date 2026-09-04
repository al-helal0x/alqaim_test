"""Inventory module: stock_movements, stock_balances, stock_transfers,
stock_adjustments, stock_reservations.

Revision ID: inventory_20260805_0006
Revises: partners_catalog_20260804_0005
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "inventory_20260805_0006"
down_revision = "partners_catalog_20260804_0005"
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
        "stock_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("movement_type", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("movement_date", sa.DateTime(timezone=True), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_stock_movements_company_id", "stock_movements", ["company_id"])
    op.create_index("ix_stock_movements_warehouse_id", "stock_movements", ["warehouse_id"])
    op.create_index("ix_stock_movements_product_id", "stock_movements", ["product_id"])
    op.create_index("ix_stock_movements_source_id", "stock_movements", ["source_id"])

    op.create_table(
        "stock_balances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "warehouse_id", "product_id", name="uq_stock_balance_wh_product"),
    )
    op.create_index("ix_stock_balances_company_id", "stock_balances", ["company_id"])
    op.create_index("ix_stock_balances_warehouse_id", "stock_balances", ["warehouse_id"])
    op.create_index("ix_stock_balances_product_id", "stock_balances", ["product_id"])

    op.create_table(
        "stock_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("from_warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("to_warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("transfer_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_stock_transfers_company_id", "stock_transfers", ["company_id"])

    op.create_table(
        "stock_adjustments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(18, 4), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("adjustment_date", sa.DateTime(timezone=True), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_stock_adjustments_company_id", "stock_adjustments", ["company_id"])

    op.create_table(
        "stock_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_stock_reservations_company_id", "stock_reservations", ["company_id"])
    op.create_index("ix_stock_reservations_warehouse_id", "stock_reservations", ["warehouse_id"])
    op.create_index("ix_stock_reservations_product_id", "stock_reservations", ["product_id"])


def downgrade() -> None:
    op.drop_table("stock_reservations")
    op.drop_table("stock_adjustments")
    op.drop_table("stock_transfers")
    op.drop_table("stock_balances")
    op.drop_table("stock_movements")
