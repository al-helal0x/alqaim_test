"""Seed `purchasing.invoice.receive_inventory` permission (TASK-AI-02b).

نفس نمط `purchasing_20260806_0004_seed_permissions.py` حرفياً (bulk_insert
بقيمة `created_at`/`updated_at` بايثونية فعلية — asyncpg لا يقبل `sa.func.now()`
عبر executemany، درس مُستفاد موثَّق هناك).

Revision ID: purchasing_20260815_0002
Revises: purchasing_20260815_0001
Create Date: 2026-08-15
"""
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

revision = "purchasing_20260815_0002"
down_revision = "purchasing_20260815_0001"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = [
    (
        "purchasing.invoice.receive_inventory",
        "استلام بضاعة فاتورة شراء بلا أمر شراء (يزيد المخزون) — TASK-AI-02b",
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
