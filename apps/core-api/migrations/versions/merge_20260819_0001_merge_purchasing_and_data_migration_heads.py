"""Merge revision: يوحّد فرعي الـmigrations اللي انفصلوا بلا قصد.

**المشكلة المكتشَفة (فحص يدوي 19 أغسطس 2026):** سلسلة الـmigrations فيها
فرعان منفصلان تمامًا، بلا merge revision بينهما:

  purchasing_20260815_0002  (ينتهي عند purchasing_20260815_0001)
  data_migration_20260818_0002  (يمر عبر accounting_20260817_0001 ←
                                  الذي يصلح صلاحيات المحاسبة الحرجة)

بلا هذا الملف، `alembic upgrade head` يرفض العمل على أي قاعدة بيانات
جديدة برسالة `Multiple heads are present` — يمنع أي بيئة جديدة (تطوير/
CI/staging) من التهيئة من الصفر، ويمنع بالتبعية اختبار trial-balance
(PKG-C3) الذي يعتمد على صلاحيات المحاسبة المصلَحة في نفس الفرع الآخر.

لا تغيير فعلي على البيانات هنا — دمج تاريخي بحت.

Revision ID: merge_20260819_0001
Revises: purchasing_20260815_0002, data_migration_20260818_0002
Create Date: 2026-08-19
"""

revision = "merge_20260819_0001"
down_revision = ("purchasing_20260815_0002", "data_migration_20260818_0002")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass