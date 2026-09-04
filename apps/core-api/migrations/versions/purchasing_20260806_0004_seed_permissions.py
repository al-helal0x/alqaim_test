"""Seed permissions for purchasing/payments (العضو 5).

Revision ID: purchasing_20260806_0004
Revises: purchasing_20260806_0003
Create Date: 2026-08-06
"""
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

revision = "purchasing_20260806_0004"
down_revision = "purchasing_20260806_0003"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = [
    ("purchasing.order.create", "إنشاء أمر شراء"),
    ("purchasing.order.confirm", "تأكيد/إلغاء أمر شراء"),
    ("purchasing.order.receive", "استلام أمر شراء (يزيد المخزون)"),
    ("purchasing.invoice.create", "إنشاء فاتورة شراء"),
    ("purchasing.invoice.post", "ترحيل فاتورة شراء محاسبياً"),
    ("payments.bank_account.create", "إنشاء حساب بنكي"),
    ("payments.payment.create", "تسجيل سند صرف"),
    ("payments.receipt.create", "تسجيل سند قبض"),
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
                "id": str(uuid.uuid4()), "code": code, "description": desc,
                "created_at": _seeded_at, "updated_at": _seeded_at,
            }
            for code, desc in NEW_PERMISSIONS
        ],
    )


def downgrade() -> None:
    codes = tuple(code for code, _ in NEW_PERMISSIONS)
    op.execute(_permissions_table.delete().where(_permissions_table.c.code.in_(codes)))
