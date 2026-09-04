from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from modules.inventory.domain.rules import MovementType
from shared_kernel.pydantic_types import UUIDStr


class StockMovementResponse(BaseModel):
    id: UUIDStr
    company_id: UUIDStr
    warehouse_id: UUIDStr
    product_id: UUIDStr
    movement_type: MovementType
    quantity: Decimal
    unit_cost: Decimal | None
    source_type: str
    source_id: str
    movement_date: datetime

    model_config = {"from_attributes": True}


class StockBalanceResponse(BaseModel):
    warehouse_id: UUIDStr
    product_id: UUIDStr
    quantity: Decimal

    model_config = {"from_attributes": True}


class RecordMovementRequest(BaseModel):
    """إدخال حركة يدوية مباشرة (استلام بضاعة بلا فاتورة شراء بعد — الوحدة
    purchasing لم تُبنَ بعد؛ هذا المسار يسدّ الفجوة مؤقتاً لإدخال رصيد ابتدائي)."""

    warehouse_id: str
    product_id: str
    movement_type: MovementType
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class StockTransferCreateRequest(BaseModel):
    from_warehouse_id: str
    to_warehouse_id: str
    product_id: str
    quantity: Decimal = Field(gt=0)
    notes: str | None = None


class StockTransferResponse(BaseModel):
    id: UUIDStr
    company_id: UUIDStr
    from_warehouse_id: UUIDStr
    to_warehouse_id: UUIDStr
    product_id: UUIDStr
    quantity: Decimal
    transfer_date: datetime
    notes: str | None

    model_config = {"from_attributes": True}


class StockAdjustmentCreateRequest(BaseModel):
    warehouse_id: str
    product_id: str
    quantity_delta: Decimal = Field(description="موجب = زيادة مكتشَفة، سالب = نقص")
    reason: str = Field(min_length=3, max_length=500)


class StockAdjustmentResponse(BaseModel):
    id: UUIDStr
    company_id: UUIDStr
    warehouse_id: UUIDStr
    product_id: UUIDStr
    quantity_delta: Decimal
    reason: str
    adjustment_date: datetime

    model_config = {"from_attributes": True}
