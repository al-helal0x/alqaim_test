"""جداول purchasing — purchase_orders/purchase_order_lines/purchase_invoices/
purchase_invoice_lines (القسم 8.2/8.3). يملك هذا الـ Module جداوله بنفسه
(بدل الاعتماد على جدول `invoices` المشترك النظري في القسم 8.3) لأن sales
لم تُبنَ بعد، وهذا يطابق مبدأ استقلالية الوحدات في القسم 6.4/11.2.
"""
import uuid
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared_kernel.db_base import BaseModel


class PurchaseOrder(BaseModel):
    __tablename__ = "purchase_orders"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    order_number: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    # draft | confirmed | received | cancelled
    currency_code: Mapped[str] = mapped_column(String(3), default="IQD", nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(1), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0), nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)  # Optimistic Locking — القسم 8.2

    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )


class PurchaseOrderLine(BaseModel):
    __tablename__ = "purchase_order_lines"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="lines")


class PurchaseInvoice(BaseModel):
    __tablename__ = "purchase_invoices"
    __table_args__ = (
        # جزء من `TASK-AI-01` (خطوة Idempotency: "draft_id كـ idempotency_key
        # — يمنع فاتورتين لنفس المسودة") — يمنع فاتورتين لنفس مسودة AI لنفس
        # الشركة على مستوى القاعدة (خط الدفاع الحاسم، بنفس نمط
        # `uq_sales_invoice_idempotency_key` لمهمة #11). NULL لا يتعارض مع
        # NULL آخر ضمن UNIQUE القياسي في PostgreSQL، فالفواتير العادية
        # (بلا `source_ai_draft_id`) غير متأثرة إطلاقاً.
        UniqueConstraint(
            "company_id", "source_ai_draft_id", name="uq_purchase_invoice_ai_draft_id"
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    # draft | posted | cancelled
    currency_code: Mapped[str] = mapped_column(String(3), default="IQD", nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(1), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0), nullable=False)
    journal_entry_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    # جزء من TASK-AI-01 — NULL لكل الفواتير العادية (يدوية/من أمر شراء)،
    # ويُملأ فقط عند الإنشاء عبر CreatePurchaseInvoiceFromAiDraftUseCase.
    source_ai_draft_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # جزء من TASK-AI-02b — يُملأ فقط عبر ReceivePurchaseInvoiceInventoryUseCase
    # (خطوة "استلام" صريحة منفصلة، بنفس مفهوم ReceivePurchaseOrderUseCase
    # القائم). يبقى NULL لكل فاتورة لم تُستلَم بضاعتها بعد؛ يُستخدَم أيضاً
    # كحارس idempotency يمنع استلام الفاتورة نفسها مرتين (زيادة مخزون مزدوجة).
    # لا معنى له لفواتير مرتبطة بأمر شراء (purchase_order_id غير NULL) —
    # تلك تُستلَم عبر استلام أمر الشراء نفسه، لا هنا (انظر التحقق في Use Case).
    inventory_received_at: Mapped["DateTime | None"] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    lines: Mapped[list["PurchaseInvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class PurchaseInvoiceLine(BaseModel):
    __tablename__ = "purchase_invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_invoices.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    invoice: Mapped["PurchaseInvoice"] = relationship(back_populates="lines")
