"""Seed the missing `data_migration.job.manage` permission + backfill Owner roles.

**فجوة اكتُشِفت أثناء دمج حزمة data_migration، لم تُذكَر في أي من مستنداتها
(README/DATA_MIGRATION_BUILD_PLAN.md/BUILD_VERIFICATION_LOG.md):**
`data_migration_router.py` يتطلب `data_migration.job.manage` عبر
`require_permission(...)` على كل مسار (إنشاء مهمة، اكتشاف مخطط، معاينة،
ترحيل)، لكن migration الجدول الأولية (`data_migration_20260818_0001`) تُنشئ
الجداول فقط ولا تزرع هذه الصلاحية إطلاقاً — **نفس فئة الخلل بالضبط** التي
وُثِّقت وأُصلِحت لصلاحيات المحاسبة في `accounting_20260817_0001` (راجع
QA_FINDINGS_apps_web_manual_test.md #1). بلا هذا الملف، لا يستطيع أي
مستخدم — ولا حتى Owner — استخدام موديول الاستيراد/التصدير إطلاقاً.

نفس الحل المُثبَت هناك بالضبط: تزرع الصلاحية **و**تمنحها فوراً (SQL-side
`INSERT ... ON CONFLICT DO NOTHING`) لكل دور Owner موجود حالياً، حتى لا
تتكرر مشكلة "شركة قديمة لن تحصل على الصلاحية الجديدة تلقائياً أبداً".

Revision ID: data_migration_20260818_0002
Revises: data_migration_20260818_0001
Create Date: 2026-08-18
"""
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

revision = "data_migration_20260818_0002"
down_revision = "data_migration_20260818_0001"
branch_labels = None
depends_on = None

PERMISSION_CODE = "data_migration.job.manage"
PERMISSION_DESC = "إدارة مهام استيراد/تصدير البيانات (اكتشاف مخطط، معاينة، ترحيل فعلي)"

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
    new_id = str(uuid.uuid4())

    op.bulk_insert(
        _permissions_table,
        [
            {
                "id": new_id, "code": PERMISSION_CODE, "description": PERMISSION_DESC,
                "created_at": _seeded_at, "updated_at": _seeded_at,
            }
        ],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions (id, role_id, permission_id, created_at, updated_at)
            SELECT gen_random_uuid(), r.id, p.id, :seeded_at, :seeded_at
            FROM roles r
            CROSS JOIN permissions p
            WHERE r.code = 'owner'
              AND r.is_system_role = true
              AND p.code = :code
            ON CONFLICT ON CONSTRAINT uq_role_permission DO NOTHING
            """
        ).bindparams(seeded_at=_seeded_at, code=PERMISSION_CODE)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE code = :code)"
        ).bindparams(code=PERMISSION_CODE)
    )
    op.execute(_permissions_table.delete().where(_permissions_table.c.code == PERMISSION_CODE))
