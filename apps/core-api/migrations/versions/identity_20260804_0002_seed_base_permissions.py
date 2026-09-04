"""Seed base permission catalog needed by the Phase-0 skeleton.

كل عضو يضيف صلاحيات وحدته الخاصة في migration منفصلة عند بناء وحدته
(القسم 15.2 — تسمية `{module}_{timestamp}_{desc}.py`). هذا الملف يزرع فقط
الصلاحيات التي يعتمد عليها Skeleton العضو 1 نفسه.

Revision ID: identity_20260804_0002
Revises: platform_20260804_0001
Create Date: 2026-08-04
"""
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

revision = "identity_20260804_0002"
down_revision = "platform_20260804_0001"
branch_labels = None
depends_on = None

BASE_PERMISSIONS = [
    ("identity.user.create", "دعوة/إنشاء مستخدم جديد داخل الشركة"),
    ("identity.role.manage", "إنشاء/تعديل الأدوار وصلاحياتها"),
    ("tenancy.company.manage", "تعديل إعدادات الشركة"),
    ("tenancy.branch.create", "إنشاء فرع جديد"),
    ("inventory.warehouse.create", "إنشاء مستودع جديد"),
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
            for code, desc in BASE_PERMISSIONS
        ],
    )


def downgrade() -> None:
    codes = tuple(code for code, _ in BASE_PERMISSIONS)
    op.execute(
        _permissions_table.delete().where(_permissions_table.c.code.in_(codes))
    )
