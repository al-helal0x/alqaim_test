from decimal import Decimal

from pydantic import BaseModel, Field


class BankAccountCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    bank_name: str | None = None
    account_number: str | None = None
    currency_code: str = Field(default="IQD", min_length=3, max_length=3)
    opening_balance: Decimal = Field(default=Decimal(0))


class BankAccountResponse(BaseModel):
    id: str
    name: str
    bank_name: str | None
    currency_code: str
    opening_balance: Decimal
    is_active: bool

    model_config = {"from_attributes": True}


class PaymentCreateRequest(BaseModel):
    supplier_id: str
    amount: Decimal = Field(gt=0)
    currency_code: str = Field(default="IQD", min_length=3, max_length=3)
    method: str = Field(default="cash")
    bank_account_id: str | None = None
    reference_invoice_id: str | None = None


class PaymentResponse(BaseModel):
    id: str
    payment_number: str
    supplier_id: str
    amount: Decimal
    method: str
    status: str
    reference_invoice_id: str | None
    journal_entry_ref: str | None

    model_config = {"from_attributes": True}


class ReceiptCreateRequest(BaseModel):
    customer_id: str
    amount: Decimal = Field(gt=0)
    currency_code: str = Field(default="IQD", min_length=3, max_length=3)
    method: str = Field(default="cash")
    bank_account_id: str | None = None
    reference_invoice_id: str | None = None


class ReceiptResponse(BaseModel):
    id: str
    receipt_number: str
    customer_id: str
    amount: Decimal
    method: str
    status: str
    reference_invoice_id: str | None
    journal_entry_ref: str | None

    model_config = {"from_attributes": True}
