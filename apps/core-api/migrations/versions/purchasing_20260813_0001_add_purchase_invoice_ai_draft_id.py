"""Add source_ai_draft_id to purchase_invoices (TASK-AI-01 — idempotency:
"draft_id كـ idempotency_key — يمنع فاتورتين لنفس المسودة").

يمنع إنشاء فاتورتي شراء لنفس مسودة AI (draft_id) لنفس الشركة، بنفس نمط
`sales_20260809_0001_add_invoice_idempotency_key.py` لمهمة #11 تماماً —
عمود قابل لـNULL + قيد UNIQUE مركّب على (company_id, source_ai_draft_id).

**درس مُستفاد من `sales_20260809_0001` صراحة (نفس الملاحظة تنطبق هنا):**
اختبارات SQLite في الذاكرة تُنشئ الجدول من تعريف الـORM مباشرة، فلا تكشف
غياب migration حقيقية. لذلك هذا الملف **إلزامي** بالتوازي مع تعديل
`purchasing_models.py` — لا يكفي تعديل الـORM وحده.

NULL لا يتعارض مع NULL آخر ضمن UNIQUE القياسي في PostgreSQL، فكل فواتير
الشراء العادية (اليدوية/من أمر شراء — بلا `source_ai_draft_id`) غير متأثرة
إطلاقاً بهذا القيد.

Revision ID: purchasing_20260813_0001
Revises: platform_20260812_0003
Create Date: 2026-08-13
"""
import sqlalchemy as sa
from alembic import op

revision = "purchasing_20260813_0001"
down_revision = "platform_20260812_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_invoices",
        sa.Column("source_ai_draft_id", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_purchase_invoice_ai_draft_id",
        "purchase_invoices",
        ["company_id", "source_ai_draft_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_purchase_invoice_ai_draft_id", "purchase_invoices", type_="unique"
    )
    op.drop_column("purchase_invoices", "source_ai_draft_id")
