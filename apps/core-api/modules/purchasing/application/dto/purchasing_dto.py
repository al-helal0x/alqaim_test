from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from shared_kernel.pydantic_types import UUIDStr


class PurchaseOrderLineRequest(BaseModel):
    product_id: str
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)


class PurchaseOrderCreateRequest(BaseModel):
    branch_id: str
    supplier_id: str
    currency_code: str = Field(default="IQD", min_length=3, max_length=3)
    tax_amount: Decimal = Field(default=Decimal(0), ge=0)
    discount_amount: Decimal = Field(default=Decimal(0), ge=0)
    lines: list[PurchaseOrderLineRequest] = Field(min_length=1)

    @field_validator("lines")
    @classmethod
    def _at_least_one_line(cls, v):
        if not v:
            raise ValueError("يجب أن يحتوي أمر الشراء على بند واحد على الأقل")
        return v


class PurchaseOrderLineResponse(BaseModel):
    id: UUIDStr
    product_id: UUIDStr
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class PurchaseOrderResponse(BaseModel):
    id: UUIDStr
    order_number: str
    status: str
    supplier_id: UUIDStr
    currency_code: str
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    lines: list[PurchaseOrderLineResponse]

    model_config = {"from_attributes": True}


class PurchaseInvoiceFromOrderRequest(BaseModel):
    purchase_order_id: str


class PurchaseInvoiceFromAiDraftRequest(BaseModel):
    """جزء من TASK-AI-01 — طلب تحويل مسودة AI معتمَدة إلى فاتورة شراء.
    `branch_id` صريح من المُستدعي (المسودة لا تحتوي فرعاً — القرار خارج
    نطاق ai-platform تماماً)."""

    draft_id: str
    branch_id: str


class PurchaseInvoiceCreateRequest(BaseModel):
    """فاتورة شراء مستقلة (بلا أمر شراء سابق)."""

    branch_id: str
    supplier_id: str
    currency_code: str = Field(default="IQD", min_length=3, max_length=3)
    tax_amount: Decimal = Field(default=Decimal(0), ge=0)
    discount_amount: Decimal = Field(default=Decimal(0), ge=0)
    lines: list[PurchaseOrderLineRequest] = Field(min_length=1)


class PurchaseInvoiceResponse(BaseModel):
    id: UUIDStr
    invoice_number: str
    status: str
    supplier_id: UUIDStr
    purchase_order_id: UUIDStr | None
    total_amount: Decimal
    paid_amount: Decimal
    journal_entry_ref: str | None
    # TASK-AI-02b — NULL إن لم تُستلَم بضاعة الفاتورة بعد (أو إن كانت
    # مرتبطة بأمر شراء، حيث تُستلَم عبر مسار الأمر نفسه لا هنا).
    inventory_received_at: datetime | None

    model_config = {"from_attributes": True}
