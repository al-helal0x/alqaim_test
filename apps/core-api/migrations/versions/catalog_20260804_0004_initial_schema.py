"""Catalog module: product_categories, units_of_measure, products, price_lists,
price_list_items.

Revision ID: catalog_20260804_0004
Revises: partners_20260804_0003
Create Date: 2026-08-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "catalog_20260804_0004"
down_revision = "partners_20260804_0003"
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
        "product_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_categories.id"), nullable=True
        ),
        *_audit_columns(),
    )
    op.create_index("ix_product_categories_company_id", "product_categories", ["company_id"])

    op.create_table(
        "units_of_measure",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False
        ),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "code", name="uq_uom_company_code"),
    )
    op.create_index("ix_units_of_measure_company_id", "units_of_measure", ["company_id"])

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False
        ),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("product_type", sa.String(16), nullable=False, server_default="product"),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_categories.id"),
            nullable=True,
        ),
        sa.Column(
            "base_uom_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("units_of_measure.id"),
            nullable=False,
        ),
        sa.Column("sale_price", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("purchase_price", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("track_inventory", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "sku", name="uq_products_company_sku"),
    )
    op.create_index("ix_products_company_id", "products", ["company_id"])

    op.create_table(
        "price_lists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IQD"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_audit_columns(),
    )
    op.create_index("ix_price_lists_company_id", "price_lists", ["company_id"])

    op.create_table(
        "price_list_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "price_list_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("price_lists.id"), nullable=False
        ),
        sa.Column(
            "product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False
        ),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        *_audit_columns(),
        sa.UniqueConstraint("price_list_id", "product_id", name="uq_price_list_item_product"),
    )
    op.create_index("ix_price_list_items_price_list_id", "price_list_items", ["price_list_id"])
    op.create_index("ix_price_list_items_product_id", "price_list_items", ["product_id"])


def downgrade() -> None:
    op.drop_table("price_list_items")
    op.drop_table("price_lists")
    op.drop_table("products")
    op.drop_table("units_of_measure")
    op.drop_table("product_categories")
