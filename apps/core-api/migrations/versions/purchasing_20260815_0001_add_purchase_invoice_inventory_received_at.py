"""Add inventory_received_at to purchase_invoices (TASK-AI-02b — خطوة
استلام صريحة لفواتير شراء بلا أمر شراء، خصوصاً فواتير AI).

نفس درس `purchasing_20260813_0001` صراحة: اختبارات SQLite في الذاكرة تبني
الجدول من تعريف ORM مباشرة، فلا تكشف غياب migration حقيقية. هذا الملف
إلزامي بالتوازي مع تعديل `purchasing_models.py`.

العمود قابل لـNULL (لا حارس UNIQUE هنا — الحارس هو فحص "هل القيمة NULL؟"
داخل `ReceivePurchaseInvoiceInventoryUseCase` نفسه قبل أي `increase_stock`،
بنفس نمط `status != 'confirmed'` في `ReceivePurchaseOrderUseCase`).

Revision ID: purchasing_20260815_0001
Revises: purchasing_20260813_0001
Create Date: 2026-08-15
"""
import sqlalchemy as sa
from alembic import op

revision = "purchasing_20260815_0001"
down_revision = "purchasing_20260813_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_invoices",
        sa.Column("inventory_received_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("purchase_invoices", "inventory_received_at")
