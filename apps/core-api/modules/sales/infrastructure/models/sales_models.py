"""جداول sales (blueprint القسم 8 وسطر 696-697، والقسم 13 العضو 4).

ملاحظة تصميم: `partner_id`/`product_id` هنا FK مباشر على جداول partners/products
(نفس قاعدة بيانات واحدة في مرحلة Modular Monolith الحالية) رغم أن الوصول
المنطقي لهذه البيانات من كود التطبيق يمر حصراً عبر IPartnerLookup/IProductLookup
(القسم 11.2 يمنع استيراد infrastructure لموديول آخر في الكود، وليس Foreign Key
على مستوى قاعدة البيانات — نفس النمط المستخدم فعلياً في partners/catalog
وaccounting حالياً في هذه الحزمة).
"""
import uuid
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared_kernel.db_base import BaseModel


class Quotation(BaseModel):
    __tablename__ = "quotations"
    __table_args__ = (UniqueConstraint("company_id", "quotation_number", name="uq_quotation_number"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    quotation_number: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="IQD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    valid_until: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["QuotationLine"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan"
    )


class QuotationLine(BaseModel):
    __tablename__ = "quotation_lines"

    quotation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quotations.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    quotation: Mapped["Quotation"] = relationship(back_populates="lines")


class SalesOrder(BaseModel):
    __tablename__ = "sales_orders"
    __table_args__ = (UniqueConstraint("company_id", "order_number", name="uq_sales_order_number"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    quotation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quotations.id"), nullable=True
    )
    order_number: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="IQD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)

    lines: Mapped[list["SalesOrderLine"]] = relationship(
        back_populates="sales_order", cascade="all, delete-orphan"
    )


class SalesOrderLine(BaseModel):
    __tablename__ = "sales_order_lines"

    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_orders.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    sales_order: Mapped["SalesOrder"] = relationship(back_populates="lines")


class SalesInvoice(BaseModel):
    __tablename__ = "sales_invoices"
    __table_args__ = (
        UniqueConstraint("company_id", "invoice_number", name="uq_sales_invoice_number"),
        # مهمة #11: مفتاح idempotency اختياري على مستوى الطلب — يمنع إنشاء فاتورة
        # مكررة عند إعادة إرسال نفس طلب الإنشاء (timeout من العميل مثلاً) دون أن
        # يعرف هل نجح الطلب الأول أم لا. NULL لا يتعارض مع NULL آخر (سلوك
        # Postgres القياسي لـ UNIQUE)، لذا الفواتير التي أُنشئت بلا مفتاح لا تتأثر.
        UniqueConstraint("company_id", "idempotency_key", name="uq_sales_invoice_idempotency_key"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    sales_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_orders.id"), nullable=True
    )
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="IQD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    journal_entry_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # مهمة #11: راجع تعليق UniqueConstraint أعلاه.
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    lines: Mapped[list["SalesInvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class SalesInvoiceLine(BaseModel):
    __tablename__ = "sales_invoice_lines"

    sales_invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoices.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    invoice: Mapped["SalesInvoice"] = relationship(back_populates="lines")


class CreditNote(BaseModel):
    __tablename__ = "credit_notes"
    __table_args__ = (UniqueConstraint("company_id", "credit_note_number", name="uq_credit_note_number"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoices.id"), nullable=False, index=True
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    credit_note_number: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="IQD")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    journal_entry_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class CreditNoteLine(BaseModel):
    __tablename__ = "credit_note_lines"

    credit_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credit_notes.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
