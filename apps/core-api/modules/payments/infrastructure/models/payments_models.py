"""جداول payments — bank_accounts/payments/receipts (القسم 8.2)."""
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db_base import BaseModel


class BankAccount(BaseModel):
    __tablename__ = "bank_accounts"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="IQD", nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class Payment(BaseModel):
    """سند صرف — للموردين (يُنقِص رصيد فاتورة شراء)."""

    __tablename__ = "payments"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_accounts.id"), nullable=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    payment_number: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="IQD", nullable=False)
    method: Mapped[str] = mapped_column(String(16), default="cash", nullable=False)
    # cash | bank_transfer | check
    status: Mapped[str] = mapped_column(String(16), default="confirmed", nullable=False)
    # draft | confirmed | cancelled
    journal_entry_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Receipt(BaseModel):
    """سند قبض — من العملاء (يُنقِص رصيد فاتورة بيع — Sales لم تُبنَ بعد،
    يُخزَّن reference_invoice_id كنص حر مؤقتاً بلا FK صارم)."""

    __tablename__ = "receipts"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_accounts.id"), nullable=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    receipt_number: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="IQD", nullable=False)
    method: Mapped[str] = mapped_column(String(16), default="cash", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="confirmed", nullable=False)
    journal_entry_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
