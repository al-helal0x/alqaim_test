"""اختبارات تكامل تغطي معيار تسليم العضو 6 (القسم 13): أي حدث تشغيلي يولّد
قيداً متوازناً صحيحاً تلقائياً، ويُمنَع أي ترحيل على فترة مقفلة، وميزان
المراجعة يتوازن دائماً.
"""
from datetime import date
from decimal import Decimal

import pytest

from modules.accounting.application.ports.accounting_port import (
    DocumentPostingLine,
    DocumentPostingRequest,
)
from modules.accounting.application.use_cases.fiscal_period_use_cases import ClosePeriodUseCase
from modules.accounting.application.use_cases.journal_use_cases import (
    FiscalPeriodClosedError,
    RecordDocumentPostingUseCase,
)
from modules.accounting.domain.rules.journal_balance_rule import UnbalancedJournalEntryError
from modules.accounting.infrastructure.models.accounting_models import (
    Account,
    AccountNormalBalance,
    AccountType,
    FiscalPeriod,
    FiscalYear,
)
from modules.reporting.application.use_cases.trial_balance_use_case import GetTrialBalanceUseCase
from modules.tenancy.infrastructure.models.tenancy_models import Company
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.event_bus import EventBus

pytestmark = pytest.mark.asyncio


async def _seed_company_with_open_period(session):
    company = Company(name="شركة القائم", default_currency="IQD")
    session.add(company)
    await session.flush()

    fiscal_year = FiscalYear(
        company_id=company.id,
        code="2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    session.add(fiscal_year)
    await session.flush()

    period = FiscalPeriod(
        company_id=company.id,
        fiscal_year_id=fiscal_year.id,
        period_number=8,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
    )
    session.add(period)

    cash = Account(
        company_id=company.id,
        code="1100",
        name="النقدية",
        account_type=AccountType.ASSET,
        normal_balance=AccountNormalBalance.DEBIT,
    )
    revenue = Account(
        company_id=company.id,
        code="4000",
        name="إيرادات المبيعات",
        account_type=AccountType.REVENUE,
        normal_balance=AccountNormalBalance.CREDIT,
    )
    session.add_all([cash, revenue])
    await session.commit()
    await session.refresh(period)
    return company, period, cash, revenue


async def test_record_document_posting_creates_balanced_entry(db_session):
    company, _period, _cash, _revenue = await _seed_company_with_open_period(db_session)
    numbering_service = SqlNumberingService(db_session)
    use_case = RecordDocumentPostingUseCase(db_session, numbering_service)

    ref = await use_case.execute(
        DocumentPostingRequest(
            company_id=str(company.id),
            entry_date="2026-08-04",
            source_document_type="sales_invoice",
            source_document_id="INV-0001",
            currency="IQD",
            lines=[
                DocumentPostingLine(account_code="1100", debit=Decimal("1000.0000")),
                DocumentPostingLine(account_code="4000", credit=Decimal("1000.0000")),
            ],
        )
    )

    assert ref.journal_entry_id
    assert ref.entry_number


async def test_unbalanced_posting_is_rejected(db_session):
    company, _period, _cash, _revenue = await _seed_company_with_open_period(db_session)
    numbering_service = SqlNumberingService(db_session)
    use_case = RecordDocumentPostingUseCase(db_session, numbering_service)

    with pytest.raises(UnbalancedJournalEntryError):
        await use_case.execute(
            DocumentPostingRequest(
                company_id=str(company.id),
                entry_date="2026-08-04",
                source_document_type="sales_invoice",
                source_document_id="INV-0002",
                currency="IQD",
                lines=[
                    DocumentPostingLine(account_code="1100", debit=Decimal("1000.0000")),
                    DocumentPostingLine(account_code="4000", credit=Decimal("999.0000")),
                ],
            )
        )


async def test_posting_to_closed_period_is_rejected(db_session):
    company, period, _cash, _revenue = await _seed_company_with_open_period(db_session)
    numbering_service = SqlNumberingService(db_session)
    # ClosePeriodUseCase يحتاج الآن INumberingService لبناء قيد الإقفال
    # الفعلي، وEventBus محقون (وليس الـ Singleton العام) لتفادي تلوّث حالة
    # الاختبارات عبر ملفات أخرى تستورد main.py وتشترك في الـ Singleton
    # (انظر modules/accounting/application/use_cases/fiscal_period_use_cases.py)
    test_event_bus = EventBus()
    await ClosePeriodUseCase(db_session, numbering_service, test_event_bus).execute(
        str(company.id), str(period.id)
    )

    use_case = RecordDocumentPostingUseCase(db_session, numbering_service)

    with pytest.raises(FiscalPeriodClosedError):
        await use_case.execute(
            DocumentPostingRequest(
                company_id=str(company.id),
                entry_date="2026-08-04",
                source_document_type="sales_invoice",
                source_document_id="INV-0003",
                currency="IQD",
                lines=[
                    DocumentPostingLine(account_code="1100", debit=Decimal("500.0000")),
                    DocumentPostingLine(account_code="4000", credit=Decimal("500.0000")),
                ],
            )
        )


async def test_trial_balance_always_balances(db_session):
    company, period, _cash, _revenue = await _seed_company_with_open_period(db_session)
    numbering_service = SqlNumberingService(db_session)
    use_case = RecordDocumentPostingUseCase(db_session, numbering_service)

    for i in range(3):
        await use_case.execute(
            DocumentPostingRequest(
                company_id=str(company.id),
                entry_date="2026-08-04",
                source_document_type="sales_invoice",
                source_document_id=f"INV-{i:04d}",
                currency="IQD",
                lines=[
                    DocumentPostingLine(account_code="1100", debit=Decimal("100.0000")),
                    DocumentPostingLine(account_code="4000", credit=Decimal("100.0000")),
                ],
            )
        )

    rows = await GetTrialBalanceUseCase(db_session).execute(str(company.id), str(period.id))
    total_debit = sum((r.total_debit for r in rows), Decimal(0))
    total_credit = sum((r.total_credit for r in rows), Decimal(0))
    assert total_debit == total_credit == Decimal("300.0000")
