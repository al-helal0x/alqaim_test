"""PKG-B1 — partners: is_system_managed + partial unique index (walk-in)

يضيف:
  1) عمود is_system_managed (boolean, NOT NULL, DEFAULT false) على partners.
  2) Partial Unique Index على (company_id) حيث is_system_managed = true —
     يمنع وجود أكثر من "عميل نقدي" واحد لكل شركة على مستوى قاعدة البيانات
     (وليس منطقاً تطبيقياً قابلاً للسباق). راجع 00_TASK_PACKAGE.md § PKG-B1.

⚠️ يتطلب Postgres حقيقياً (partial index / WHERE clause على CREATE UNIQUE INDEX
   غير مدعوم على SQLite في الذاكرة) — لا تُشغَّل الاختبارات الخاصة به على SQLite.

Revision ID: partners_20260816_0001
Revises: purchasing_20260815_0002 (رأس السلسلة الفعلي وقت الدمج — كانت
    الحزمة مسلَّمة معزولة بلا رؤية له، فتُرك `None` مؤقتاً هناك، مضبوط هنا
    فعلياً عند الدمج في الشجرة الكاملة)
Create Date: 2026-08-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "partners_20260816_0001"
down_revision: str | None = "purchasing_20260815_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_partners_company_system_managed"


def upgrade() -> None:
    op.add_column(
        "partners",
        sa.Column(
            "is_system_managed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # server_default كان مطلوباً فقط لملء الصفوف الحالية أثناء الـALTER TABLE.
    # نزيله بعد الترحيل حتى لا يعتمد التطبيق على DEFAULT ضمني في DB لاحقاً —
    # القيمة الافتراضية مسؤولية طبقة التطبيق (partner_models.py: default=False).
    op.alter_column("partners", "is_system_managed", server_default=None)

    op.create_index(
        INDEX_NAME,
        "partners",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("is_system_managed = true"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="partners")
    op.drop_column("partners", "is_system_managed")
