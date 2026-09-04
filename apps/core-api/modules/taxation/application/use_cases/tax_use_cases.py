
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.taxation.application.dto.taxation_dto import TaxRateCreateRequest
from modules.taxation.domain.rules.tax_calculation_rule import calculate_tax_amount
from modules.taxation.infrastructure.models.taxation_models import (
    EInvoiceSubmission,
    EInvoiceSubmissionStatus,
    TaxRate,
)


class TaxRateNotFoundError(ValueError):
    pass


class CreateTaxRateUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, company_id: str, request: TaxRateCreateRequest) -> TaxRate:
        tax_rate = TaxRate(
            company_id=company_id,
            code=request.code,
            name=request.name,
            rate_percent=request.rate_percent,
        )
        self._session.add(tax_rate)
        await self._session.commit()
        await self._session.refresh(tax_rate)
        return tax_rate


class ListTaxRatesUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, company_id: str) -> list[TaxRate]:
        stmt = select(TaxRate).where(
            TaxRate.company_id == company_id, TaxRate.deleted_at.is_(None)
        ).order_by(TaxRate.code)
        return list((await self._session.execute(stmt)).scalars().all())


class CalculateTaxUseCase:
    """يحسب الضريبة لمبلغ أساسي معطى استناداً لسعر ضريبة مسجَّل — يُستهلك من
    Sales/Purchasing عند بناء الفاتورة (لا يوجد Port رسمي بعد في contracts.md
    لهذا — يُستدعى حالياً فقط عبر REST من الواجهة، وليس Port بين الوحدات)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, company_id: str, tax_rate_id: str, base_amount):
        stmt = select(TaxRate).where(
            TaxRate.id == tax_rate_id, TaxRate.company_id == company_id
        )
        tax_rate = (await self._session.execute(stmt)).scalar_one_or_none()
        if tax_rate is None:
            raise TaxRateNotFoundError("نسبة الضريبة غير موجودة لهذه الشركة")

        tax_amount = calculate_tax_amount(base_amount, tax_rate.rate_percent)
        return {
            "base_amount": base_amount,
            "rate_percent": tax_rate.rate_percent,
            "tax_amount": tax_amount,
            "total_amount": base_amount + tax_amount,
        }


class SubmitEInvoiceUseCase:
    """يسجّل محاولة إرسال فاتورة إلكترونية ويضعها بحالة `pending`.

    ملاحظة صريحة: الإرسال الفعلي لبوابة حكومية خارجية غير منفَّذ هنا — لم
    يحدَّد Blueprint أي مزوّد/بروتوكول محدد لهذا (لا يوجد اسم بوابة أو Spec
    API في القسم 13/6.6). هذا الـ Use Case يوفّر فقط سجل التتبّع (الجدول +
    الحالات) الذي ستُبنى فوقه عملية الإرسال الفعلية لاحقاً بعد تحديد المزوّد.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, company_id: str, source_document_type: str, source_document_id: str
    ) -> EInvoiceSubmission:
        submission = EInvoiceSubmission(
            company_id=company_id,
            source_document_type=source_document_type,
            source_document_id=source_document_id,
            status=EInvoiceSubmissionStatus.PENDING,
        )
        self._session.add(submission)
        await self._session.commit()
        await self._session.refresh(submission)
        return submission
