"""Seed the 4 missing `accounting.*` permissions + backfill existing Owner roles.

**فجوة حقيقية مؤكَّدة من الكود (QA_FINDINGS_apps_web_manual_test.md #1):**
أربع صلاحيات مُستخدَمة فعلياً في `require_permission(...)` عبر راوترات
المحاسبة:
  - `accounting.account.create`      (accounts_router.py:31,45)
  - `accounting.fiscal_year.create`  (fiscal_periods_router.py:36)
  - `accounting.fiscal_period.close` (fiscal_periods_router.py:49)
  - `accounting.journal_entry.post`  (journal_entries_router.py:41)
لم تكن مزروعة في **أي** migration من الـ9 ملفات التي تلمس جدول
`permissions` (تحقَّقت بـ`grep -rn "accounting\\." migrations/versions/*.py`
→ صفر نتائج قبل هذا الملف). النتيجة: لا يوجد أي دور — ولا حتى Owner —
يملك هذه الصلاحيات فعلياً، فوحدة المحاسبة معطَّلة بالكامل عن الاستخدام.

**الفجوة الثانية الأخطر المكتشَفة أثناء هذا الإصلاح (لم يذكرها التقرير
الأصلي صراحة لكنها نفس الجذر):** كل ملفات seed الصلاحيات السابقة
(`purchasing_20260815_0002`, `pos_20260816_0001`, وغيرها) تُدخِل الصلاحية
الجديدة في جدول `permissions` فقط — ولا تمنحها لأدوار Owner **الموجودة
مسبقاً**. `RegisterCompanyUseCase` (auth_use_cases.py:95) يمنح دور Owner
كل الصلاحيات الموجودة في `permissions` **وقت التسجيل فقط** (`select(Permission)`
لحظي، ليس اشتراكاً مستقبلياً) — فأي شركة سُجِّلت قبل seed معيّن لن تحصل
على الصلاحية الجديدة تلقائياً أبداً، إلى الأبد، حتى لو كانت Owner. حتى
`pos_20260816_0001` وثَّق هذا الخطر صراحة في docstring الخاص به لكن لم
يُصلِحه. هذه الـmigration تُصلِح كلا الأمرين معاً: تزرع الصلاحيات الأربع
**و**تمنحها فوراً لكل دور Owner (`is_system_role=True, code='owner'`)
موجود حالياً في قاعدة البيانات — بدل ترك نفس الفخ يتكرر.

نفس نمط bulk_insert للصلاحيات (`purchasing_20260815_0002` حرفياً)، مع
خطوة INSERT إضافية لـ`role_permissions` عبر SELECT مباشر (لا حاجة لجلب
كل الصفوف لبايثون ثم bulk_insert — عدد أدوار Owner قد يكبر مستقبلاً،
وهذا نمط SQL-side قياسي وآمن من التكرار بفضل `ON CONFLICT DO NOTHING`
على `uq_role_permission`).

Revision ID: accounting_20260817_0001
Revises: pos_20260816_0001
Create Date: 2026-08-17
"""
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

revision = "accounting_20260817_0001"
down_revision = "pos_20260816_0001"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = [
    ("accounting.account.create", "إنشاء حساب في شجرة الحسابات (يشمل زرع الشجرة الافتراضية)"),
    ("accounting.fiscal_year.create", "إنشاء سنة مالية جديدة"),
    ("accounting.fiscal_period.close", "إغلاق فترة محاسبية"),
    ("accounting.journal_entry.post", "ترحيل قيد يومية يدوي"),
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
    new_ids = {code: str(uuid.uuid4()) for code, _ in NEW_PERMISSIONS}

    op.bulk_insert(
        _permissions_table,
        [
            {
                "id": new_ids[code], "code": code, "description": desc,
                "created_at": _seeded_at, "updated_at": _seeded_at,
            }
            for code, desc in NEW_PERMISSIONS
        ],
    )

    # Backfill: منح الصلاحيات الأربع الجديدة لكل دور Owner موجود مسبقاً —
    # يسدّ نفس الفجوة التي وثَّقها pos_20260816_0001 بلا إصلاح. ON CONFLICT
    # DO NOTHING يحمي uq_role_permission لو أُعيد تشغيل upgrade (لا يُفترَض
    # عملياً، لكن آمن بلا كلفة). role_id/permission_id بالفعل NOT NULL على
    # جدول role_permissions، فلا حاجة لتصفية NULL هنا.
    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions (id, role_id, permission_id, created_at, updated_at)
            SELECT gen_random_uuid(), r.id, p.id, :seeded_at, :seeded_at
            FROM roles r
            CROSS JOIN permissions p
            WHERE r.code = 'owner'
              AND r.is_system_role = true
              AND p.code = ANY(:codes)
            ON CONFLICT ON CONSTRAINT uq_role_permission DO NOTHING
            """
        ).bindparams(seeded_at=_seeded_at, codes=list(new_ids.keys()))
    )


def downgrade() -> None:
    codes = tuple(code for code, _ in NEW_PERMISSIONS)
    # role_permissions ← FK إلى permissions بلا CASCADE معرَّف صراحة هنا؛
    # نحذف صفوف role_permissions أولاً صراحة بدل الاعتماد على سلوك FK
    # ضمني قد يختلف بين بيئات القاعدة.
    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (SELECT id FROM permissions WHERE code = ANY(:codes))
            """
        ).bindparams(codes=list(codes))
    )
    op.execute(_permissions_table.delete().where(_permissions_table.c.code.in_(codes)))
