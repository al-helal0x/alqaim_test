"""ميزان المراجعة (Trial Balance) — أول تقرير مالي حقيقي، ويُستخدم كإثبات
مباشر لمعيار تسليم العضو 6: "ميزان المراجعة يتوازن دائماً" (لأن كل قيد
مُدخَل عبر accounting مضمون التوازن مسبقاً، مجموع كل الأعمدة هنا يجب أن يخرج
متساوياً رياضياً بشكل حتمي، وليس صدفة).

ملاحظة حدود الوحدات (القسم 11.2): reporting يقرأ مباشرة من جداول accounting
عبر SQLAlchemy لأنهما مملوكتان لنفس العضو (6) — هذا استثناء موثّق فقط بين
وحدتين لنفس المالك، وليس نمطاً عاماً لبقية الوحدات.
"""
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.infrastructure.models.accounting_models import Account, JournalEntryLine


class TrialBalanceRow:
    def __init__(self, account_id, account_code, account_name, total_debit, total_credit):
        self.account_id = account_id
        self.account_code = account_code
        self.account_name = account_name
        self.total_debit = total_debit
        self.total_credit = total_credit
        self.balance = total_debit - total_credit


class GetTrialBalanceUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, company_id: str, fiscal_period_id: str) -> list[TrialBalanceRow]:
        from modules.accounting.infrastructure.models.accounting_models import JournalEntry

        stmt = (
            select(
                Account.id,
                Account.code,
                Account.name,
                func.coalesce(func.sum(JournalEntryLine.debit), Decimal(0)),
                func.coalesce(func.sum(JournalEntryLine.credit), Decimal(0)),
            )
            .join(JournalEntryLine, JournalEntryLine.account_id == Account.id)
            .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .where(
                Account.company_id == company_id,
                JournalEntry.fiscal_period_id == fiscal_period_id,
            )
            .group_by(Account.id, Account.code, Account.name)
            .order_by(Account.code)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            TrialBalanceRow(account_id, code, name, debit, credit)
            for account_id, code, name, debit, credit in rows
        ]
