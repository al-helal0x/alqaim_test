from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from modules.taxation.infrastructure.models.taxation_models import EInvoiceSubmissionStatus


class TaxRateCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    rate_percent: Decimal = Field(ge=0, le=100)


class TaxRateResponse(BaseModel):
    id: str
    code: str
    name: str
    rate_percent: Decimal
    is_active: bool

    model_config = {"from_attributes": True}


class TaxCalculationRequest(BaseModel):
    base_amount: Decimal = Field(ge=0)
    tax_rate_id: str


class TaxCalculationResponse(BaseModel):
    base_amount: Decimal
    rate_percent: Decimal
    tax_amount: Decimal
    total_amount: Decimal


class EInvoiceSubmissionResponse(BaseModel):
    id: str
    source_document_type: str
    source_document_id: str
    status: EInvoiceSubmissionStatus
    provider_reference: str | None
    submitted_at: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}
