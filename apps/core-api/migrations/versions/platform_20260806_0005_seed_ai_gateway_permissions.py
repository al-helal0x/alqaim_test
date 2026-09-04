"""Seed permissions for the /ai/* gateway (العضو 1 + العضو 8 — بوابة ai-platform).

Revision ID: platform_20260806_0005
Revises: purchasing_20260806_0004
Create Date: 2026-08-06
"""
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

revision = "platform_20260806_0005"
down_revision = "purchasing_20260806_0004"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = [
    ("ai.document.analyze", "رفع مستند لتحليله عبر ai-platform (OCR/استخراج)"),
    ("ai.draft.review", "اعتماد/رفض/تصحيح مسودة استخراج فاتورة من ai-platform"),
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
