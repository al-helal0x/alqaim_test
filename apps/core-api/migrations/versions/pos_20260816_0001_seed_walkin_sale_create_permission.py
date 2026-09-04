"""Seed `pos.sale.create` permission (PKG-B2 — walk-in customer).

**فجوة حقيقية اكتُشِفت عند الدمج:** `partners_walkin_router.py` (PKG-B2) يحمي
`POST /partners/walk-in` بصلاحية `pos.sale.create` عمداً (لا
`partners.partner.create` — الكاشير "يطلب" عميلاً نقدياً ضمنياً أثناء
البيع، لا يُدير شركاء بالمعنى الكامل). لكن هذه الصلاحية **لم تكن مزروعة
إطلاقاً** في `inv_sales_pos_20260805_0009_seed_permissions.py` — الموجود
هناك فقط `pos.session.open`/`pos.session.close`/`pos.sale.sync`. بلا هذا
الملف، أي دور يُبنى عبر seed الصلاحيات القياسي (مثل `RegisterCompanyUseCase`
الذي يمنح دور Owner كل الصلاحيات الموجودة في جدول `permissions`) لن يملك
هذه الصلاحية الجديدة إطلاقاً.

نفس نمط `purchasing_20260815_0002_seed_receive_inventory_permission.py`
حرفياً (bulk_insert بقيمة `created_at`/`updated_at` بايثونية فعلية).

Revision ID: pos_20260816_0001
Revises: partners_20260816_0001
Create Date: 2026-08-15
"""
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

revision = "pos_20260816_0001"
down_revision = "partners_20260816_0001"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = [
    (
        "pos.sale.create",
        "إنشاء بيع من نقطة البيع (يشمل طلب عميل نقدي ضمنياً) — PKG-B2",
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
