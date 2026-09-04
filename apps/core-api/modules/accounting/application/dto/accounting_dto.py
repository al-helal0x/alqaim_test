from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from modules.accounting.infrastructure.models.accounting_models import (
    AccountNormalBalance,
    AccountType,
)
from shared_kernel.pydantic_types import UUIDStr


class AccountCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    account_type: AccountType
    normal_balance: AccountNormalBalance
    parent_id: str | None = None
    is_postable: bool = True


class AccountResponse(BaseModel):
    id: UUIDStr
    code: str
    name: str
    account_type: AccountType
    normal_balance: AccountNormalBalance
    parent_id: UUIDStr | None
    is_postable: bool
    is_active: bool

    model_config = {"from_attributes": True}


class FiscalYearCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    start_date: date
    end_date: date
    period_count: int = Field(default=12, ge=1, le=13)


class FiscalPeriodResponse(BaseModel):
    id: UUIDStr
    period_number: int
    start_date: date
    end_date: date
    is_closed: bool

    model_config = {"from_attributes": True}


class FiscalYearResponse(BaseModel):
    id: UUIDStr
    code: str
    start_date: date
    end_date: date
    is_closed: bool
    periods: list[FiscalPeriodResponse] = []

    model_config = {"from_attributes": True}


class JournalEntryLineRequest(BaseModel):
    account_id: str
    debit: Decimal = Decimal(0)
    credit: Decimal = Decimal(0)
    description: str | None = None
    cost_center_id: str | None = None


class JournalEntryCreateRequest(BaseModel):
    """لترحيل يدوي مباشر من واجهة المحاسب (مختلف عن IAccountingPort الذي
    تستخدمه الوحدات الأخرى تلقائياً)."""

    entry_date: date
    memo: str | None = None
    currency: str = Field(default="IQD", min_length=3, max_length=3)
    lines: list[JournalEntryLineRequest]

    @model_validator(mode="after")
    def _at_least_two_lines(self) -> "JournalEntryCreateRequest":
        if len(self.lines) < 2:
            raise ValueError("القيد يحتاج سطرين على الأقل (مدين ودائن)")
        return self


class JournalEntryLineResponse(BaseModel):
    id: UUIDStr
    account_id: UUIDStr
    debit: Decimal
    credit: Decimal
    description: str | None

    model_config = {"from_attributes": True}


class JournalEntryResponse(BaseModel):
    id: UUIDStr
    entry_number: str
    entry_date: date
    memo: str | None
    currency: str
    source_document_type: str | None
    source_document_id: UUIDStr | None
    lines: list[JournalEntryLineResponse] = []

    model_config = {"from_attributes": True}


class TrialBalanceRow(BaseModel):
    account_id: str
    account_code: str
    account_name: str
    total_debit: Decimal
    total_credit: Decimal
    balance: Decimal


class TrialBalanceResponse(BaseModel):
    fiscal_period_id: str
    rows: list[TrialBalanceRow]
    is_balanced: bool


class StatementRowResponse(BaseModel):
    account_id: str
    account_code: str
    account_name: str
    amount: Decimal


class IncomeStatementResponse(BaseModel):
    fiscal_year_id: str
    revenue_rows: list[StatementRowResponse]
    expense_rows: list[StatementRowResponse]
    total_revenue: Decimal
    total_expense: Decimal
    net_income: Decimal


class BalanceSheetResponse(BaseModel):
    fiscal_year_id: str
    asset_rows: list[StatementRowResponse]
    liability_rows: list[StatementRowResponse]
    equity_rows: list[StatementRowResponse]
    current_period_net_income: Decimal
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    is_balanced: bool
