"""قوائم مالية مبنية فوق قيود accounting (نفس استثناء القراءة المباشرة
الموثَّق في trial_balance_use_case.py — العضو 6 يملك accounting وreporting معاً).

income-statement: يجمع Revenue/Expense ضمن مدى تاريخ سنة مالية واحدة (فترة
زمنية، وليس تراكمياً) — صافي الربح = إجمالي الإيرادات − إجمالي المصروفات.

balance-sheet: تراكمي حتى نهاية السنة المالية المطلوبة (Assets/Liabilities/
Equity منذ بداية التشغيل، وليس فقط سنة واحدة). حقوق الملكية تُقرَأ بالكامل
من الحسابات المُرحَّلة فعلياً — بما فيها "الأرباح المرحّلة" (كود 3200) التي
تتغذّى الآن من قيود الإقفال الفعلية (ClosePeriodUseCase، انظر
accounting/application/use_cases/fiscal_period_use_cases.py). لم يعد هناك
سطر "صافي ربح مؤقت" منفصل: أي فترة أُقفلت أصلاً انعكس صافي ربحها تلقائياً
ضمن رصيد الأرباح المرحّلة نفسه. `current_period_unclosed_net_income` يبقى
معروضاً بشكل منفصل فقط لتوضيح أثر الفترات **غير المُقفلة بعد** ضمن السنة
المالية الحالية (حتى لا يظهر التقرير غير متوازن مؤقتاً بسبب نشاط لم يُقفل
بعد) — وليس بديلاً عن قيد الإقفال.
"""
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.infrastructure.models.accounting_models import (
    Account,
    AccountType,
    FiscalYear,
    JournalEntry,
    JournalEntryLine,
)


class FiscalYearNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class StatementRow:
    account_id: str
    account_code: str
    account_name: str
    amount: Decimal


async def _get_fiscal_year(session: AsyncSession, company_id: str, fiscal_year_id: str) -> FiscalYear:
    stmt = select(FiscalYear).where(
        FiscalYear.id == fiscal_year_id, FiscalYear.company_id == company_id
    )
    fiscal_year = (await session.execute(stmt)).scalar_one_or_none()
    if fiscal_year is None:
        raise FiscalYearNotFoundError("السنة المالية غير موجودة لهذه الشركة")
    return fiscal_year


async def _sum_by_account(
    session: AsyncSession,
    *,
    company_id: str,
    account_types: list[AccountType],
    date_from,
    date_to,
    credit_positive: bool,
) -> list[StatementRow]:
    """يجمع صافي المبلغ لكل حساب ضمن الأنواع/المدى الزمني المعطى.
    credit_positive=True يعني net = credit - debit (طبيعي للإيرادات/الالتزامات/
    حقوق الملكية)، False يعني net = debit - credit (طبيعي للأصول/المصروفات)."""
    net_expr = (
        (func.sum(JournalEntryLine.credit) - func.sum(JournalEntryLine.debit))
        if credit_positive
        else (func.sum(JournalEntryLine.debit) - func.sum(JournalEntryLine.credit))
    )
    stmt = (
        select(Account.id, Account.code, Account.name, net_expr)
        .join(JournalEntryLine, JournalEntryLine.account_id == Account.id)
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .where(
            Account.company_id == company_id,
            Account.account_type.in_(account_types),
            JournalEntry.entry_date >= date_from,
            JournalEntry.entry_date <= date_to,
        )
        .group_by(Account.id, Account.code, Account.name)
        .order_by(Account.code)
    )
    rows = (await session.execute(stmt)).all()
    return [
        StatementRow(account_id=str(aid), account_code=code, account_name=name, amount=amount)
        for aid, code, name, amount in rows
    ]


class GetIncomeStatementUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, company_id: str, fiscal_year_id: str) -> dict:
        fiscal_year = await _get_fiscal_year(self._session, company_id, fiscal_year_id)

        revenue_rows = await _sum_by_account(
            self._session,
            company_id=company_id,
            account_types=[AccountType.REVENUE],
            date_from=fiscal_year.start_date,
            date_to=fiscal_year.end_date,
            credit_positive=True,
        )
        expense_rows = await _sum_by_account(
            self._session,
            company_id=company_id,
            account_types=[AccountType.EXPENSE],
            date_from=fiscal_year.start_date,
            date_to=fiscal_year.end_date,
            credit_positive=False,
        )

        total_revenue = sum((r.amount for r in revenue_rows), Decimal(0))
        total_expense = sum((r.amount for r in expense_rows), Decimal(0))

        return {
            "fiscal_year_id": str(fiscal_year.id),
            "revenue_rows": revenue_rows,
            "expense_rows": expense_rows,
            "total_revenue": total_revenue,
            "total_expense": total_expense,
            "net_income": total_revenue - total_expense,
        }


class GetBalanceSheetUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, company_id: str, fiscal_year_id: str) -> dict:
        fiscal_year = await _get_fiscal_year(self._session, company_id, fiscal_year_id)
        # التاريخ الأدنى المفتوح: تراكمي منذ بداية التشغيل، وليس منذ بداية
        # السنة المالية فقط — لهذا date_from بعيد جداً في الماضي عمداً.
        far_past = fiscal_year.start_date.replace(year=1970)

        asset_rows = await _sum_by_account(
            self._session,
            company_id=company_id,
            account_types=[AccountType.ASSET],
            date_from=far_past,
            date_to=fiscal_year.end_date,
            credit_positive=False,
        )
        liability_rows = await _sum_by_account(
            self._session,
            company_id=company_id,
            account_types=[AccountType.LIABILITY],
            date_from=far_past,
            date_to=fiscal_year.end_date,
            credit_positive=True,
        )
        equity_rows = await _sum_by_account(
            self._session,
            company_id=company_id,
            account_types=[AccountType.EQUITY],
            date_from=far_past,
            date_to=fiscal_year.end_date,
            credit_positive=True,
        )

        income_statement = await GetIncomeStatementUseCase(self._session).execute(
            company_id, fiscal_year_id
        )
        current_period_net_income = income_statement["net_income"]

        total_assets = sum((r.amount for r in asset_rows), Decimal(0))
        total_liabilities = sum((r.amount for r in liability_rows), Decimal(0))
        total_equity_posted = sum((r.amount for r in equity_rows), Decimal(0))
        total_equity = total_equity_posted + current_period_net_income

        return {
            "fiscal_year_id": str(fiscal_year.id),
            "asset_rows": asset_rows,
            "liability_rows": liability_rows,
            "equity_rows": equity_rows,
            "current_period_net_income": current_period_net_income,
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "total_equity": total_equity,
            "is_balanced": total_assets == (total_liabilities + total_equity),
        }
