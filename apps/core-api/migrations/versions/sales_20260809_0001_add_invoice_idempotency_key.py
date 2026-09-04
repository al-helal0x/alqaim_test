"""Add idempotency_key to sales_invoices (مهمة #11 — أمان معاملة إنشاء→ترحيل فاتورة البيع).

هذه الـ migration كانت مفقودة من تسليم مهمة #11 الأصلي رغم أن الكود
(`infrastructure/models/sales_models.py`) يفترض وجود العمود والقيد فعليًا.
أُضيفت أثناء دمج الدفعة الثالثة (integration lead) لأن `SalesInvoice.idempotency_key`
لن يعمل بدون عمود فعلي في قاعدة البيانات — هذا يعني أن مهمة #11 كانت ستفشل
عند أول تشغيل فعلي رغم نجاح اختباراتها محليًا (SQLite في-الذاكرة تُنشئ
الجدول من تعريف الـ ORM مباشرة، فلا تكشف غياب الـ migration الحقيقية).

NULL لا يتعارض مع NULL آخر ضمن UNIQUE القياسي في PostgreSQL، فالفواتير
القديمة (بلا idempotency_key) غير متأثرة إطلاقًا بهذا القيد.

Revision ID: sales_20260809_0001
Revises: identity_20260808_0003
Create Date: 2026-08-09
"""
import sqlalchemy as sa
from alembic import op

revision = "sales_20260809_0001"
down_revision = "identity_20260808_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_invoices",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_unique_constraint(
        "uq_sales_invoice_idempotency_key",
        "sales_invoices",
        ["company_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_sales_invoice_idempotency_key", "sales_invoices", type_="unique"
    )
    op.drop_column("sales_invoices", "idempotency_key")
