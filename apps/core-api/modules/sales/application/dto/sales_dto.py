from decimal import Decimal

from pydantic import BaseModel, Field

from modules.sales.domain.rules import (
    CreditNoteStatus,
    QuotationStatus,
    SalesInvoiceStatus,
    SalesOrderStatus,
)
from shared_kernel.pydantic_types import UUIDStr


class LineItemRequest(BaseModel):
    product_id: str
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    tax_amount: Decimal = Field(default=Decimal(0), ge=0)


class LineItemResponse(BaseModel):
    product_id: UUIDStr
    quantity: Decimal
    unit_price: Decimal
    tax_amount: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


# ── Quotations ───────────────────────────────────────────────────────────


class QuotationCreateRequest(BaseModel):
    partner_id: str
    currency: str = Field(default="IQD", min_length=3, max_length=3)
    lines: list[LineItemRequest] = Field(min_length=1)


class QuotationResponse(BaseModel):
    id: UUIDStr
    company_id: UUIDStr
    partner_id: UUIDStr
    quotation_number: str
    status: QuotationStatus
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    lines: list[LineItemResponse]

    model_config = {"from_attributes": True}


class QuotationStatusUpdateRequest(BaseModel):
    status: QuotationStatus


# ── Sales Orders ─────────────────────────────────────────────────────────


class SalesOrderCreateRequest(BaseModel):
    partner_id: str
    quotation_id: str | None = None
    currency: str = Field(default="IQD", min_length=3, max_length=3)
    lines: list[LineItemRequest] = Field(min_length=1)


class SalesOrderResponse(BaseModel):
    id: UUIDStr
    company_id: UUIDStr
    partner_id: UUIDStr
    quotation_id: UUIDStr | None
    order_number: str
    status: SalesOrderStatus
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    lines: list[LineItemResponse]

    model_config = {"from_attributes": True}


# ── Sales Invoices ───────────────────────────────────────────────────────


class SalesInvoiceCreateRequest(BaseModel):
    partner_id: str
    warehouse_id: str
    sales_order_id: str | None = None
    currency: str = Field(default="IQD", min_length=3, max_length=3)
    discount_amount: Decimal = Field(default=Decimal(0), ge=0)
    lines: list[LineItemRequest] = Field(min_length=1)
    # مهمة #11: معرّف idempotency اختياري يولّده العميل لمرة واحدة لكل "نية
    # إنشاء" منطقية (مثال: uuid4). إعادة إرسال نفس الطلب بنفس المفتاح (بعد
    # timeout مثلاً) تُعيد نفس الفاتورة المُنشأة أول مرة بدل إنشاء فاتورة مكررة.
    # يمكن إرساله أيضاً عبر الترويسة `Idempotency-Key` (لها الأولوية إن وُجدت).
    idempotency_key: str | None = Field(default=None, max_length=128)


class SalesInvoiceResponse(BaseModel):
    id: UUIDStr
    company_id: UUIDStr
    warehouse_id: UUIDStr
    partner_id: UUIDStr
    sales_order_id: UUIDStr | None
    invoice_number: str
    status: SalesInvoiceStatus
    currency: str
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    journal_entry_id: str | None
    idempotency_key: str | None
    lines: list[LineItemResponse]

    model_config = {"from_attributes": True}


# ── Credit Notes ─────────────────────────────────────────────────────────


class CreditNoteCreateRequest(BaseModel):
    invoice_id: str
    lines: list[LineItemRequest] = Field(min_length=1)


class CreditNoteResponse(BaseModel):
    id: UUIDStr
    company_id: UUIDStr
    invoice_id: UUIDStr
    partner_id: UUIDStr
    credit_note_number: str
    status: CreditNoteStatus
    currency: str
    total_amount: Decimal

    model_config = {"from_attributes": True}
