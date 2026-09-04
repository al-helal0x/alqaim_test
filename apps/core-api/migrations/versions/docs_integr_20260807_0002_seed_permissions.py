"""Seed permissions for documents/integrations/platform_admin (العضو 13).

Revision ID: docs_integr_20260807_0002
Revises: docs_integr_20260807_0001
Create Date: 2026-08-07
"""
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

revision = "docs_integr_20260807_0002"
down_revision = "docs_integr_20260807_0001"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = [
    ("documents.upload", "رفع مرفق لأي كيان"),
    ("documents.delete", "حذف مرفق"),
    ("integrations.webhook.manage", "إنشاء/إلغاء اشتراكات Webhook"),
    (
        "platform_admin.company.manage",
        "إدارة كل الشركات على المنصة (صلاحية عابرة للشركات — استثناء متعمَّد، راجع"
        " platform_admin_use_cases.py)",
    ),
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
