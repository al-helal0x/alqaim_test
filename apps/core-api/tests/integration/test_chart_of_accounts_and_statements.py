from datetime import date
from decimal import Decimal

import pytest

from modules.accounting.application.dto.accounting_dto import FiscalYearCreateRequest
from modules.accounting.application.ports.accounting_port import (
    DocumentPostingLine,
    DocumentPostingRequest,
)
from modules.accounting.application.use_cases.chart_of_accounts_seed_use_case import (
    ChartOfAccountsAlreadySeededError,
    SeedDefaultChartOfAccountsUseCase,
)
from modules.accounting.application.use_cases.fiscal_period_use_cases import CreateFiscalYearUseCase
from modules.accounting.application.use_cases.journal_use_cases import RecordDocumentPostingUseCase
from modules.reporting.application.use_cases.financial_statements_use_case import (
    GetBalanceSheetUseCase,
    GetIncomeStatementUseCase,
)
from modules.tenancy.infrastructure.models.tenancy_models import Company
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService

pytestmark = pytest.mark.asyncio


async def _seed_company(session):
    company = Company(name="شركة القائم", default_currency="IQD")
    session.add(company)
    await session.commit()
    await session.refresh(company)
    return company


async def test_seed_default_chart_of_accounts_creates_hierarchy(db_session):
    company = await _seed_company(db_session)
    accounts = await SeedDefaultChartOfAccountsUseCase(db_session).execute(str(company.id))

    codes = {a.code for a in accounts}
    assert "1101" in codes  # الصندوق
    assert "4100" in codes  # إيرادات المبيعات
    assert "5100" in codes  # تكلفة البضاعة المباعة

    cash = next(a for a in accounts if a.code == "1101")
    current_assets = next(a for a in accounts if a.code == "1100")
    assert cash.parent_id == current_assets.id


async def test_seed_default_chart_of_accounts_rejects_double_seed(db_session):
    company = await _seed_company(db_session)
    await SeedDefaultChartOfAccountsUseCase(db_session).execute(str(company.id))

    with pytest.raises(ChartOfAccountsAlreadySeededError):
        await SeedDefaultChartOfAccountsUseCase(db_session).execute(str(company.id))


async def test_income_statement_and_balance_sheet_are_consistent(db_session):
    company = await _seed_company(db_session)
    await SeedDefaultChartOfAccountsUseCase(db_session).execute(str(company.id))

    fiscal_year = await CreateFiscalYearUseCase(db_session).execute(
        str(company.id),
        FiscalYearCreateRequest(
            code="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)
        ),
    )

    numbering_service = SqlNumberingService(db_session)
    use_case = RecordDocumentPostingUseCase(db_session, numbering_service)

    # بيع نقدي 1000 (مدين الصندوق 1101 / دائن إيرادات المبيعات 4100)
    await use_case.execute(
        DocumentPostingRequest(
            company_id=str(company.id),
            entry_date="2026-08-04",
            source_document_type="sales_invoice",
            source_document_id="INV-0001",
            currency="IQD",
            lines=[
                DocumentPostingLine(account_code="1101", debit=Decimal(1000)),
                DocumentPostingLine(account_code="4100", credit=Decimal(1000)),
            ],
        )
    )
    # مصروف إيجار نقدي 200 (مدين مصروفات إيجار 5300 / دائن الصندوق 1101)
    await use_case.execute(
        DocumentPostingRequest(
            company_id=str(company.id),
            entry_date="2026-08-04",
            source_document_type="expense",
            source_document_id="EXP-0001",
            currency="IQD",
            lines=[
                DocumentPostingLine(account_code="5300", debit=Decimal(200)),
                DocumentPostingLine(account_code="1101", credit=Decimal(200)),
            ],
        )
    )

    income_statement = await GetIncomeStatementUseCase(db_session).execute(
        str(company.id), str(fiscal_year.id)
    )
    assert income_statement["total_revenue"] == Decimal(1000)
    assert income_statement["total_expense"] == Decimal(200)
    assert income_statement["net_income"] == Decimal(800)

    balance_sheet = await GetBalanceSheetUseCase(db_session).execute(
        str(company.id), str(fiscal_year.id)
    )
    # الصندوق: +1000 - 200 = 800 (وهو كل الأصول المرحَّلة هنا)
    assert balance_sheet["total_assets"] == Decimal(800)
    assert balance_sheet["current_period_net_income"] == Decimal(800)
    assert balance_sheet["is_balanced"] is True
