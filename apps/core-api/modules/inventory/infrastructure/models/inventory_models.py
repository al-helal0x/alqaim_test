"""جداول inventory (blueprint القسم 8، سطر 693 والقسم 13 العضو 3).

مصدر الحقيقة الوحيد للأرصدة هو `stock_movements` (Event Sourced جزئياً) —
`stock_balances` جدول ملخّص (Materialized) يُحدَّث ضمن نفس معاملة قاعدة
البيانات مع كل حركة (وليس عبر DB Trigger في هذه المرحلة — قرار عملي موثَّق:
التحديث يحدث دائماً من نفس Use Case الذي يكتب الحركة، فلا يوجد مسار كتابة
آخر لـ stock_movements يتجاوز هذا المنطق طالما كل الكتابة تمر عبر
application/use_cases في هذه الوحدة فقط).
"""
import uuid
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db_base import BaseModel


class StockMovement(BaseModel):
    """سجل غير قابل للتعديل (Append-only) لكل حركة مخزون فعلية."""

    __tablename__ = "stock_movements"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True
    )
    movement_type: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    movement_date: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)


class StockBalance(BaseModel):
    """جدول ملخّص (رصيد حالي) لكل (شركة، مستودع، منتج) — القسم 8، سطر 694."""

    __tablename__ = "stock_balances"
    __table_args__ = (
        UniqueConstraint("company_id", "warehouse_id", "product_id", name="uq_stock_balance_wh_product"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)


class StockTransfer(BaseModel):
    """تحويل بضاعة بين مستودعين — ينتج حركتين (out من المصدر + in للوجهة)."""

    __tablename__ = "stock_transfers"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    from_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False
    )
    to_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    transfer_date: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


class StockAdjustment(BaseModel):
    """تسوية جرد — قد تكون الكمية موجبة (زيادة مكتشَفة) أو سالبة (نقص)."""

    __tablename__ = "stock_adjustments"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    adjustment_date: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)


class StockReservation(BaseModel):
    """حجز مؤقت لكمية (يُنشأ من IInventoryPort.reserve_stock) — لا يخصم الرصيد
    الفعلي بل يقلّل "المتاح" (quantity - حجوزات نشطة) حتى يُستهلك عبر
    deduct_stock أو يُلغى/ينتهي.
    """

    __tablename__ = "stock_reservations"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    expires_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)
