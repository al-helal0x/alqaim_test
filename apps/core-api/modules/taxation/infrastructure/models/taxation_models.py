"""جداول taxation — ضرائب/فوترة إلكترونية (القسم 13 — العضو 6).

`e_invoice_submissions` تتبّع حالة إرسال الفاتورة الإلكترونية لجهة حكومية
خارجية (لم تُحدَّد في Blueprint أي بوابة تحديداً — لذا الحقول هنا عامة بما
يكفي لأي مزوّد لاحقاً: provider، حمولة الاستجابة الخام، الحالة).
"""
import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db_base import BaseModel


class EInvoiceSubmissionStatus(enum.StrEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


class TaxRate(BaseModel):
    __tablename__ = "tax_rates"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # نسبة مئوية بـ Decimal (مثال: 15.0000 تعني 15%) — لا Float إطلاقاً (القسم 17)
    rate_percent: Mapped["Numeric"] = mapped_column(Numeric(6, 4), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EInvoiceSubmission(BaseModel):
    __tablename__ = "e_invoice_submissions"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    source_document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_document_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # ⚠️ name= صريح إلزامي — نفس فئة الخلل المكتشَفة في accounting_models.py
    # (Account.account_type): بلا تحديده، SQLAlchemy يشتق اسم نوع Postgres
    # كـ"einvoicesubmissionstatus" من اسم الكلاس، بينما الـmigration
    # (taxation_20260804_0004) أنشأت النوع فعلياً باسم
    # "e_invoice_submission_status". أي INSERT/UPDATE فعلي على هذا الجدول
    # كان سيفشل بـ`UndefinedObjectError` بنفس الطريقة تماماً.
    # ⚠️ name= + values_callable إلزاميان معاً — نفس فئة الخلل المزدوجة
    # المكتشَفة في Account.account_type (accounting_models.py): (1) اسم نوع
    # Postgres المُشتَق تلقائياً من اسم الكلاس لا يطابق الاسم الفعلي الذي
    # أنشأته الـmigration، و(2) SQLAlchemy يخزّن .name لعضو الـPython enum
    # ("PENDING") بدل .value الفعلي ("pending") بشكل افتراضي، بينما نوع
    # Postgres يقبل فقط القيم الصغيرة المعرَّفة في الـmigration.
    status: Mapped[EInvoiceSubmissionStatus] = mapped_column(
        Enum(
            EInvoiceSubmissionStatus,
            name="e_invoice_submission_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=EInvoiceSubmissionStatus.PENDING,
        nullable=False,
    )
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitted_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)