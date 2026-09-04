from decimal import Decimal

import pytest

from modules.taxation.application.dto.taxation_dto import TaxRateCreateRequest
from modules.taxation.application.use_cases.tax_use_cases import (
    CalculateTaxUseCase,
    CreateTaxRateUseCase,
    SubmitEInvoiceUseCase,
    TaxRateNotFoundError,
)
from modules.taxation.infrastructure.models.taxation_models import EInvoiceSubmissionStatus
from modules.tenancy.infrastructure.models.tenancy_models import Company

pytestmark = pytest.mark.asyncio


async def _seed_company(session):
    company = Company(name="شركة القائم", default_currency="IQD")
    session.add(company)
    await session.commit()
    await session.refresh(company)
    return company


async def test_calculate_tax_uses_registered_rate(db_session):
    company = await _seed_company(db_session)
    tax_rate = await CreateTaxRateUseCase(db_session).execute(
        str(company.id),
        TaxRateCreateRequest(code="VAT15", name="ضريبة القيمة المضافة 15%", rate_percent=Decimal(15)),
    )

    result = await CalculateTaxUseCase(db_session).execute(
        str(company.id), str(tax_rate.id), Decimal(1000)
    )

    assert result["tax_amount"] == Decimal("150.0000")
    assert result["total_amount"] == Decimal("1150.0000")


async def test_calculate_tax_rejects_unknown_rate(db_session):
    company = await _seed_company(db_session)
    with pytest.raises(TaxRateNotFoundError):
        await CalculateTaxUseCase(db_session).execute(
            str(company.id), "00000000-0000-0000-0000-000000000000", Decimal(100)
        )


async def test_submit_einvoice_starts_pending(db_session):
    company = await _seed_company(db_session)
    submission = await SubmitEInvoiceUseCase(db_session).execute(
        str(company.id), "sales_invoice", "INV-0001"
    )
    assert submission.status == EInvoiceSubmissionStatus.PENDING
