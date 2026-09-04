"""اختبارات تكامل لمهمة #10 (إقفال الفترة المالية + تحديث الميزانية):

1. إقفال فترة فيها نشاط إيرادات/مصروفات يُنتج قيد إقفال فعلي متوازن يُصفّر
   حسابات الإيرادات/المصروفات وينقل صافي الربح إلى "الأرباح المرحّلة".
2. لا يمكن ترحيل أي قيد جديد على فترة مُقفلة (تغطية إضافية —
   test_accounting_posting.py يغطي هذا أيضاً من زاوية RecordDocumentPostingUseCase).
3. لا يمكن إقفال فترة مُقفلة أصلاً مرتين.
4. تقرير الميزانية بعد الإقفال يعكس رصيد الأرباح المرحّلة الفعلي — وليس
   حساباً مؤقتاً لصافي الربح — لفترة أُقفلت، بينما يستمر بعرض صافي الربح
   غير المُقفل لفترة لاحقة مفتوحة ضمن نفس السنة المالية.
5. إقفال فترة بلا أي نشاط إيرادات/مصروفات لا يُنشئ قيد إقفال (لا حاجة له).
6. غياب حساب "الأرباح المرحّلة" في شجرة الحسابات يمنع الإقفال بخطأ واضح.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from modules.accounting.application.dto.accounting_dto import FiscalYearCreateRequest
from modules.accounting.application.ports.accounting_port import (
    DocumentPostingLine,
    DocumentPostingRequest,
)
from modules.accounting.application.use_cases.chart_of_accounts_seed_use_case import (
    SeedDefaultChartOfAccountsUseCase,
)
from modules.accounting.application.use_cases.fiscal_period_use_cases import (
    RETAINED_EARNINGS_ACCOUNT_CODE,
    ClosePeriodUseCase,
    CreateFiscalYearUseCase,
    FiscalPeriodAlreadyClosedError,
    RetainedEarningsAccountMissingError,
)
from modules.accounting.application.use_cases.journal_use_cases import (
    FiscalPeriodClosedError,
    RecordDocumentPostingUseCase,
)
from modules.accounting.infrastructure.models.accounting_models import (
    Account,
    AccountNormalBalance,
    AccountType,
    JournalEntry,
    JournalEntryLine,
)
from modules.reporting.application.use_cases.financial_statements_use_case import (
    GetBalanceSheetUseCase,
)
from modules.tenancy.infrastructure.models.tenancy_models import Company
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.event_bus import EventBus
from platform_core.outbox_models import OutboxEvent

pytestmark = pytest.mark.asyncio


async def _seed_company_with_chart_and_two_periods(session):
    """شركة بشجرة حسابات افتراضية كاملة (فيها 3200 الأرباح المرحّلة) وسنة
    مالية 2026 مقسَّمة على فترتين شهريتين فقط (يناير/فبراير) لتبسيط الاختبار."""
    company = Company(name="شركة القائم", default_currency="IQD")
    session.add(company)
    await session.commit()
    await session.refresh(company)

    await SeedDefaultChartOfAccountsUseCase(session).execute(str(company.id))

    fiscal_year = await CreateFiscalYearUseCase(session).execute(
        str(company.id),
        FiscalYearCreateRequest(
            code="2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 28),
            period_count=2,
        ),
    )
    jan, feb = sorted(fiscal_year.periods, key=lambda p: p.period_number)
    return company, fiscal_year, jan, feb


async def test_closing_period_posts_balanced_closing_entry_to_retained_earnings(db_session):
    company, _fiscal_year, jan, _feb = await _seed_company_with_chart_and_two_periods(db_session)
    numbering_service = SqlNumberingService(db_session)
    # EventBus محلي معزول لتفادي تلوّث الـ Singleton العام بين ملفات
    # الاختبار (نفس تحذير test_redis_event_bridge.py)
    test_event_bus = EventBus()
    posting = RecordDocumentPostingUseCase(db_session, numbering_service)

    # بيع نقدي 1000 (مدين الصندوق 1101 / دائن إيرادات المبيعات 4100)
    await posting.execute(
        DocumentPostingRequest(
            company_id=str(company.id),
            entry_date="2026-01-10",
            source_document_type="sales_invoice",
            source_document_id="INV-0001",
            currency="IQD",
            lines=[
                DocumentPostingLine(account_code="1101", debit=Decimal(1000)),
                DocumentPostingLine(account_code="4100", credit=Decimal(1000)),
            ],
        )
    )
    # مصروف إيجار نقدي 300 (مدين مصروفات إيجار 5300 / دائن الصندوق 1101)
    await posting.execute(
        DocumentPostingRequest(
            company_id=str(company.id),
            entry_date="2026-01-15",
            source_document_type="expense",
            source_document_id="EXP-0001",
            currency="IQD",
            lines=[
                DocumentPostingLine(account_code="5300", debit=Decimal(300)),
                DocumentPostingLine(account_code="1101", credit=Decimal(300)),
            ],
        )
    )

    period = await ClosePeriodUseCase(db_session, numbering_service, test_event_bus).execute(
        str(company.id), str(jan.id)
    )
    assert period.is_closed is True

    # قيد الإقفال نفسه: متوازن، مرتبط بالفترة، ونوعه period_closing
    stmt = select(JournalEntry).where(JournalEntry.source_document_type == "period_closing")
    closing_entries = (await db_session.execute(stmt)).scalars().all()
    assert len(closing_entries) == 1
    closing_entry = closing_entries[0]
    assert closing_entry.fiscal_period_id == jan.id

    lines_stmt = select(JournalEntryLine).where(
        JournalEntryLine.journal_entry_id == closing_entry.id
    )
    lines = (await db_session.execute(lines_stmt)).scalars().all()
    total_debit = sum((ln.debit for ln in lines), Decimal(0))
    total_credit = sum((ln.credit for ln in lines), Decimal(0))
    assert total_debit == total_credit  # القيد متوازن

    # الأرباح المرحّلة استلمت صافي الربح فعلياً: 1000 - 300 = 700
    re_stmt = select(Account).where(
        Account.company_id == company.id, Account.code == RETAINED_EARNINGS_ACCOUNT_CODE
    )
    retained_earnings = (await db_session.execute(re_stmt)).scalar_one()
    re_line_stmt = select(JournalEntryLine).where(
        JournalEntryLine.journal_entry_id == closing_entry.id,
        JournalEntryLine.account_id == retained_earnings.id,
    )
    re_line = (await db_session.execute(re_line_stmt)).scalar_one()
    assert re_line.credit == Decimal(700)
    assert re_line.debit == Decimal(0)


async def test_closing_period_enqueues_fiscal_period_closed_outbox_event(db_session):
    """TASK-10-01 — بند اختبار مطلوب صراحة في `ALQAIM_V2_MASTER_EXECUTION_PLAN.md`
    ("صف outbox_events بحالة pending لـFiscalPeriodClosed موجود بعد
    الإقفال") لم يكن مغطى بأي اختبار حتى هذا التسليم — `ClosePeriodUseCase`
    تكتب الحدث فعلياً عبر `enqueue_event()` (راجع `fiscal_period_use_cases.py`)،
    لكن لا شيء كان يتحقق من ذلك فعلياً."""
    company, _fiscal_year, jan, _feb = await _seed_company_with_chart_and_two_periods(db_session)
    numbering_service = SqlNumberingService(db_session)
    test_event_bus = EventBus()

    period = await ClosePeriodUseCase(db_session, numbering_service, test_event_bus).execute(
        str(company.id), str(jan.id)
    )

    rows = (
        await db_session.execute(
            select(OutboxEvent).where(OutboxEvent.event_name == "FiscalPeriodClosed")
        )
    ).scalars().all()
    assert len(rows) == 1, "يجب أن يُكتَب صف outbox واحد بالضبط عند الإقفال — لا صفر، لا تكرار"
    row = rows[0]
    assert row.status == "pending"
    assert row.aggregate_id == str(period.id)
    assert row.payload["period_id"] == str(period.id)
    assert row.payload["company_id"] == str(company.id)


async def test_posting_after_close_is_rejected_even_with_retroactive_date(db_session):
    company, _fy, jan, _feb = await _seed_company_with_chart_and_two_periods(db_session)
    numbering_service = SqlNumberingService(db_session)
    # EventBus محلي معزول لتفادي تلوّث الـ Singleton العام بين ملفات
    # الاختبار (نفس تحذير test_redis_event_bridge.py)
    test_event_bus = EventBus()
    posting = RecordDocumentPostingUseCase(db_session, numbering_service)

    await posting.execute(
        DocumentPostingRequest(
            company_id=str(company.id),
            entry_date="2026-01-05",
            source_document_type="sales_invoice",
            source_document_id="INV-0002",
            currency="IQD",
            lines=[
                DocumentPostingLine(account_code="1101", debit=Decimal(500)),
                DocumentPostingLine(account_code="4100", credit=Decimal(500)),
            ],
        )
    )
    await ClosePeriodUseCase(db_session, numbering_service, test_event_bus).execute(str(company.id), str(jan.id))

    with pytest.raises(FiscalPeriodClosedError):
        await posting.execute(
            DocumentPostingRequest(
                company_id=str(company.id),
                entry_date="2026-01-20",
                source_document_type="sales_invoice",
                source_document_id="INV-0003",
                currency="IQD",
                lines=[
                    DocumentPostingLine(account_code="1101", debit=Decimal(100)),
                    DocumentPostingLine(account_code="4100", credit=Decimal(100)),
                ],
            )
        )


async def test_closing_an_already_closed_period_is_rejected(db_session):
    company, _fy, jan, _feb = await _seed_company_with_chart_and_two_periods(db_session)
    numbering_service = SqlNumberingService(db_session)
    # EventBus محلي معزول لتفادي تلوّث الـ Singleton العام بين ملفات
    # الاختبار (نفس تحذير test_redis_event_bridge.py)
    test_event_bus = EventBus()
    await ClosePeriodUseCase(db_session, numbering_service, test_event_bus).execute(str(company.id), str(jan.id))

    with pytest.raises(FiscalPeriodAlreadyClosedError):
        await ClosePeriodUseCase(db_session, numbering_service, test_event_bus).execute(
            str(company.id), str(jan.id)
        )


async def test_closing_period_with_no_activity_creates_no_closing_entry(db_session):
    company, _fy, jan, _feb = await _seed_company_with_chart_and_two_periods(db_session)
    numbering_service = SqlNumberingService(db_session)
    # EventBus محلي معزول لتفادي تلوّث الـ Singleton العام بين ملفات
    # الاختبار (نفس تحذير test_redis_event_bridge.py)
    test_event_bus = EventBus()

    period = await ClosePeriodUseCase(db_session, numbering_service, test_event_bus).execute(
        str(company.id), str(jan.id)
    )
    assert period.is_closed is True

    stmt = select(JournalEntry).where(JournalEntry.source_document_type == "period_closing")
    closing_entries = (await db_session.execute(stmt)).scalars().all()
    assert closing_entries == []


async def test_closing_without_retained_earnings_account_is_rejected(db_session):
    company = Company(name="شركة بلا أرباح مرحّلة", default_currency="IQD")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    # شجرة حسابات يدوية ناقصة عمداً: بلا حساب 3200
    cash = Account(
        company_id=company.id, code="1101", name="الصندوق",
        account_type=AccountType.ASSET, normal_balance=AccountNormalBalance.DEBIT,
    )
    revenue = Account(
        company_id=company.id, code="4100", name="إيرادات المبيعات",
        account_type=AccountType.REVENUE, normal_balance=AccountNormalBalance.CREDIT,
    )
    db_session.add_all([cash, revenue])
    await db_session.commit()

    fiscal_year = await CreateFiscalYearUseCase(db_session).execute(
        str(company.id),
        FiscalYearCreateRequest(
            code="2026", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31), period_count=1
        ),
    )
    period = fiscal_year.periods[0]

    numbering_service = SqlNumberingService(db_session)
    # EventBus محلي معزول لتفادي تلوّث الـ Singleton العام بين ملفات
    # الاختبار (نفس تحذير test_redis_event_bridge.py)
    test_event_bus = EventBus()
    posting = RecordDocumentPostingUseCase(db_session, numbering_service)
    await posting.execute(
        DocumentPostingRequest(
            company_id=str(company.id),
            entry_date="2026-01-10",
            source_document_type="sales_invoice",
            source_document_id="INV-0001",
            currency="IQD",
            lines=[
                DocumentPostingLine(account_code="1101", debit=Decimal(400)),
                DocumentPostingLine(account_code="4100", credit=Decimal(400)),
            ],
        )
    )

    with pytest.raises(RetainedEarningsAccountMissingError):
        await ClosePeriodUseCase(db_session, numbering_service, test_event_bus).execute(
            str(company.id), str(period.id)
        )


async def test_balance_sheet_reflects_actual_retained_earnings_after_closing(db_session):
    company, fiscal_year, jan, _feb = await _seed_company_with_chart_and_two_periods(db_session)
    numbering_service = SqlNumberingService(db_session)
    # EventBus محلي معزول لتفادي تلوّث الـ Singleton العام بين ملفات
    # الاختبار (نفس تحذير test_redis_event_bridge.py)
    test_event_bus = EventBus()
    posting = RecordDocumentPostingUseCase(db_session, numbering_service)

    # فترة يناير: ربح 700 (1000 إيراد - 300 مصروف) — تُقفَل
    await posting.execute(
        DocumentPostingRequest(
            company_id=str(company.id), entry_date="2026-01-10",
            source_document_type="sales_invoice", source_document_id="INV-0001",
            currency="IQD",
            lines=[
                DocumentPostingLine(account_code="1101", debit=Decimal(1000)),
                DocumentPostingLine(account_code="4100", credit=Decimal(1000)),
            ],
        )
    )
    await posting.execute(
        DocumentPostingRequest(
            company_id=str(company.id), entry_date="2026-01-15",
            source_document_type="expense", source_document_id="EXP-0001",
            currency="IQD",
            lines=[
                DocumentPostingLine(account_code="5300", debit=Decimal(300)),
                DocumentPostingLine(account_code="1101", credit=Decimal(300)),
            ],
        )
    )
    await ClosePeriodUseCase(db_session, numbering_service, test_event_bus).execute(str(company.id), str(jan.id))

    # فترة فبراير: نشاط جديد لم يُقفل بعد (ربح 150)
    await posting.execute(
        DocumentPostingRequest(
            company_id=str(company.id), entry_date="2026-02-05",
            source_document_type="sales_invoice", source_document_id="INV-0002",
            currency="IQD",
            lines=[
                DocumentPostingLine(account_code="1101", debit=Decimal(150)),
                DocumentPostingLine(account_code="4100", credit=Decimal(150)),
            ],
        )
    )

    balance_sheet = await GetBalanceSheetUseCase(db_session).execute(
        str(company.id), str(fiscal_year.id)
    )

    # الأرباح المرحّلة الفعلية (كود 3200) تظهر ضمن equity_rows بقيمة 700 —
    # هذه قراءة فعلية من رصيد الحساب بعد قيد الإقفال، وليست حساباً مؤقتاً.
    retained_earnings_row = next(
        r for r in balance_sheet["equity_rows"] if r.account_code == RETAINED_EARNINGS_ACCOUNT_CODE
    )
    assert retained_earnings_row.amount == Decimal(700)

    # الفترة المفتوحة (فبراير) ما زال ربحها يظهر كصافي ربح غير مُقفل بعد
    assert balance_sheet["current_period_net_income"] == Decimal(150)

    # الميزانية متوازنة: الأصول = 1000-300+150 = 850؛ حقوق الملكية = 700 (مرحّلة) + 150 (غير مُقفل) = 850
    assert balance_sheet["total_assets"] == Decimal(850)
    assert balance_sheet["total_equity"] == Decimal(850)
    assert balance_sheet["is_balanced"] is True
