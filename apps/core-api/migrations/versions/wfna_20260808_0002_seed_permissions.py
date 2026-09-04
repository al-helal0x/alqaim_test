"""Seed permissions for workflow/audit (العضو 12).

notifications: لا صلاحية جديدة — كل مستخدم يرى إشعارات شركته فقط ضمنياً
عبر company_id، بلا حاجة لتحقق RBAC إضافي.

Revision ID: wfna_20260808_0002
Revises: wfna_20260808_0001
Create Date: 2026-08-08
"""
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

revision = "wfna_20260808_0002"
down_revision = "wfna_20260808_0001"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = [
    ("workflow.definition.manage", "إنشاء/تعديل تعريفات سير العمل"),
    ("workflow.instance.transition", "تنفيذ انتقال حالة على نسخة سير عمل"),
    ("audit.log.view", "عرض سجل التدقيق"),
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
