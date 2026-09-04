"""Seed permission catalog entries for inventory, sales & pos modules (Members 3 & 4).

Revision ID: inv_sales_pos_20260805_0009
Revises: pos_20260805_0008
Create Date: 2026-08-05
"""
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

revision = "inv_sales_pos_20260805_0009"
down_revision = "pos_20260805_0008"
branch_labels = None
depends_on = None

MODULE_PERMISSIONS = [
    ("inventory.movement.create", "إدخال حركة مخزون يدوية"),
    ("inventory.transfer.create", "إنشاء تحويل مخزون بين مستودعين"),
    ("inventory.adjustment.create", "إنشاء تسوية جرد"),
    ("sales.quotation.create", "إنشاء عرض سعر"),
    ("sales.quotation.update", "تعديل حالة عرض سعر"),
    ("sales.order.create", "إنشاء أمر بيع"),
    ("sales.order.update", "تعديل حالة أمر بيع"),
    ("sales.invoice.create", "إنشاء فاتورة بيع"),
    ("sales.invoice.post", "ترحيل فاتورة بيع"),
    ("sales.invoice.update", "تعديل/إلغاء فاتورة بيع"),
    ("sales.credit_note.create", "إصدار إشعار دائن"),
    ("pos.session.open", "فتح جلسة نقطة بيع"),
    ("pos.session.close", "إغلاق جلسة نقطة بيع"),
    ("pos.sale.sync", "مزامنة مبيعات نقطة بيع"),
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
