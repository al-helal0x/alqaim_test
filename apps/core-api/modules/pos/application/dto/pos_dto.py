from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from modules.pos.domain.rules import PosSessionStatus, PosSyncItemStatus
from modules.sales.application.dto.sales_dto import LineItemRequest
from shared_kernel.pydantic_types import UUIDStr


class OpenSessionRequest(BaseModel):
    warehouse_id: str
    opening_cash: Decimal = Field(default=Decimal(0), ge=0)


class CloseSessionRequest(BaseModel):
    closing_cash: Decimal = Field(ge=0)


class SessionResponse(BaseModel):
    id: UUIDStr
    company_id: UUIDStr
    warehouse_id: UUIDStr
    opened_by: UUIDStr
    opening_cash: Decimal
    closing_cash: Decimal | None
    status: PosSessionStatus
    opened_at: datetime
    closed_at: datetime | None

    model_config = {"from_attributes": True}


class PosSaleRequest(BaseModel):
    """عملية بيع واحدة من الجهاز — client_reference يولّده الجهاز نفسه ويبقى
    ثابتاً عبر إعادة المحاولة بعد انقطاع الاتصال (Idempotency Key)."""

    client_reference: str = Field(min_length=1, max_length=128)
    partner_id: str
    currency: str = Field(default="IQD", min_length=3, max_length=3)
    discount_amount: Decimal = Field(default=Decimal(0), ge=0)
    lines: list[LineItemRequest] = Field(min_length=1)


class PosSyncRequest(BaseModel):
    session_id: str
    sales: list[PosSaleRequest] = Field(min_length=1)


class PosSyncResultItem(BaseModel):
    client_reference: str
    status: PosSyncItemStatus
    sales_invoice_id: UUIDStr | None = None
    invoice_number: str | None = None
    error: str | None = None


class PosSyncResponse(BaseModel):
    results: list[PosSyncResultItem]
