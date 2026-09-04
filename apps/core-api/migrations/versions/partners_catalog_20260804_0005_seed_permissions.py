"""Seed permission catalog entries for partners & catalog modules (Member 2).

Revision ID: partners_catalog_20260804_0005
Revises: catalog_20260804_0004
Create Date: 2026-08-04
"""
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

revision = "partners_catalog_20260804_0005"
down_revision = "catalog_20260804_0004"
branch_labels = None
depends_on = None

MODULE_PERMISSIONS = [
    ("partners.partner.create", "إنشاء عميل/مورد جديد"),
    ("partners.partner.update", "تعديل بيانات عميل/مورد"),
    ("catalog.category.create", "إنشاء تصنيف منتجات"),
    ("catalog.uom.create", "إنشاء وحدة قياس"),
    ("catalog.product.create", "إنشاء منتج/خدمة جديدة"),
    ("catalog.product.update", "تعديل منتج/خدمة"),
    ("catalog.price_list.create", "إنشاء قائمة أسعار"),
    ("catalog.price_list.update", "تعديل بنود قائمة أسعار"),
]

_permissions_table = table(
    "permissions",
    column("id", postgresql.UUID(as_uuid=True)),
    column("code", sa.String),
    column("description", sa.String),
    column("created_at", sa.DateTime(timezone=True)),
    column("updated_at", sa.DateTime(timezone=True)),
)


# asyncpg + bulk_insert لا يقبل sa.func.now() كقيمة Python فعلية عبر
# executemany (خطأ حقيقي مكتشَف بالتشغيل الفعلي ضد Postgres — وليس نظرياً):
# "expected a datetime.date or datetime.datetime instance, got 'now'".
# الحل: قيمة Python فعلية محسوبة مرة واحدة عند تنفيذ الهجرة.
_seeded_at = datetime.now(UTC)


def upgrade() -> None:
    op.bulk_insert(
        _permissions_table,
        [
            {
                "id": str(uuid.uuid4()),
                "code": code,
                "description": desc,
                "created_at": _seeded_at,
                "updated_at": _seeded_at,
            }
            for code, desc in MODULE_PERMISSIONS
        ],
    )


def downgrade() -> None:
    codes = tuple(code for code, _ in MODULE_PERMISSIONS)
    op.execute(_permissions_table.delete().where(_permissions_table.c.code.in_(codes)))
