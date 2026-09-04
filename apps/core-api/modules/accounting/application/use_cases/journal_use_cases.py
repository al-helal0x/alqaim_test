"""حالات استخدام القيود وشجرة الحسابات.

RecordDocumentPostingUseCase هو التنفيذ الفعلي لـ IAccountingPort
(application/ports/accounting_port.py). يعتمد فقط على INumberingService
(Protocol من tenancy) — لا يستورد infrastructure الخاصة بوحدة tenancy
مباشرة (القسم 11.2)؛ التنفيذ الفعلي (SqlNumberingService) يُحقَن من طبقة
التوصيل (Router) وليس هنا.
"""
from datetime import date as date_type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.accounting.application.dto.accounting_dto import AccountCreateRequest
from modules.accounting.application.ports.accounting_port import (
    DocumentPostingRequest,
    JournalEntryRef,
)
from modules.accounting.domain.rules.journal_balance_rule import (
    JournalLineAmounts,
    assert_balanced,
    assert_line_amount_valid,
)
from modules.accounting.infrastructure.models.accounting_models import (
    Account,
    FiscalPeriod,
    JournalEntry,
    JournalEntryLine,
)
from modules.tenancy.application.ports.numbering_port import INumberingService


class FiscalPeriodClosedError(ValueError):
    """محاولة ترحيل على فترة مالية مقفلة — ممنوعة إطلاقاً (معيار تسليم العضو 6)."""


class NoOpenFiscalPeriodError(ValueError):
    """لا توجد فترة مالية مفتوحة تغطي تاريخ الترحيل المطلوب."""


class AccountNotFoundError(ValueError):
    pass


async def _reload_with_lines(session: AsyncSession, journal_entry_id) -> JournalEntry:
    """يعيد تحميل القيد مع أسطره محمّلة صراحة (selectinload) — Lazy-load عادي
    غير آمن مع AsyncSession خارج نفس الـ await الأصلي."""
    stmt = (
        select(JournalEntry)
        .where(JournalEntry.id == journal_entry_id)
        .options(selectinload(JournalEntry.lines))
    )
    return (await session.execute(stmt)).scalar_one()


async def _find_open_period(
    session: AsyncSession, *, company_id: str, entry_date: date_type
) -> FiscalPeriod:
    stmt = select(FiscalPeriod).where(
        FiscalPeriod.company_id == company_id,
        FiscalPeriod.start_date <= entry_date,
        FiscalPeriod.end_date >= entry_date,
    )
    period = (await session.execute(stmt)).scalar_one_or_none()
    if period is None:
        raise NoOpenFiscalPeriodError(
            f"لا توجد فترة مالية معرَّفة تغطي تاريخ {entry_date} لهذه الشركة"
        )
    if period.is_closed:
        raise FiscalPeriodClosedError(
            f"الفترة المالية المغطية لتاريخ {entry_date} مقفلة — لا يُسمح بترحيل قيود جديدة عليها"
        )
    return period


async def _get_account_by_code(session: AsyncSession, *, company_id: str, code: str) -> Account:
    stmt = select(Account).where(Account.company_id == company_id, Account.code == code)
    account = (await session.execute(stmt)).scalar_one_or_none()
    if account is None:
        raise AccountNotFoundError(f"لا يوجد حساب بالكود {code} لهذه الشركة")
    if not account.is_postable:
        raise ValueError(f"الحساب {code} حساب تجميعي (parent) — لا يُسمح بالترحيل عليه مباشرة")
    return account


class RecordDocumentPostingUseCase:
    """تنفيذ IAccountingPort.record_document_posting — أهم Use Case في النظام.

    يُستدعى من: sales/purchasing/payments/inventory عند وقوع حدث تشغيلي
    (فاتورة، دفعة...) لتحويله تلقائياً إلى قيد محاسبي متوازن.
    """

    def __init__(self, session: AsyncSession, numbering_service: INumberingService) -> None:
        self._session = session
        self._numbering_service = numbering_service

    async def execute(self, document_dto: DocumentPostingRequest) -> JournalEntryRef:
        entry_date = date_type.fromisoformat(document_dto.entry_date)
        period = await _find_open_period(
            self._session, company_id=document_dto.company_id, entry_date=entry_date
        )

        # 1) تحقّق توازن القيد في طبقة Domain الصِرفة قبل أي كتابة لقاعدة البيانات
        for line in document_dto.lines:
            assert_line_amount_valid(line.debit, line.credit)
        assert_balanced(
            [JournalLineAmounts(debit=line.debit, credit=line.credit) for line in document_dto.lines]
        )

        entry_number = await self._numbering_service.next_number(
            company_id=document_dto.company_id, document_type="journal_entry"
        )

        journal_entry = JournalEntry(
            company_id=document_dto.company_id,
            fiscal_period_id=period.id,
            entry_number=entry_number,
            entry_date=entry_date,
            memo=document_dto.memo,
            source_document_type=document_dto.source_document_type,
            source_document_id=document_dto.source_document_id,
            currency=document_dto.currency,
        )
        self._session.add(journal_entry)
        await self._session.flush()  # للحصول على journal_entry.id قبل إضافة الأسطر

        for line in document_dto.lines:
            account = await _get_account_by_code(
                self._session, company_id=document_dto.company_id, code=line.account_code
            )
            cost_center_id = None
            if line.cost_center_code:
                from modules.accounting.infrastructure.models.accounting_models import CostCenter

                cc_stmt = select(CostCenter).where(
                    CostCenter.company_id == document_dto.company_id,
                    CostCenter.code == line.cost_center_code,
                )
                cost_center = (await self._session.execute(cc_stmt)).scalar_one_or_none()
                cost_center_id = cost_center.id if cost_center else None

            self._session.add(
                JournalEntryLine(
                    company_id=document_dto.company_id,
                    journal_entry_id=journal_entry.id,
                    account_id=account.id,
                    cost_center_id=cost_center_id,
                    debit=line.debit,
                    credit=line.credit,
                    description=line.description,
                )
            )

        await self._session.commit()
        await self._session.refresh(journal_entry)

        return JournalEntryRef(
            journal_entry_id=str(journal_entry.id), entry_number=journal_entry.entry_number
        )


class PostManualJournalEntryUseCase:
    """ترحيل يدوي من واجهة المحاسب مباشرة (account_id بدل account_code، ولا
    يمر عبر IAccountingPort لأنه لا يمثّل حدثاً تشغيلياً من وحدة أخرى)."""

    def __init__(self, session: AsyncSession, numbering_service: INumberingService) -> None:
        self._session = session
        self._numbering_service = numbering_service

    async def execute(self, *, company_id: str, entry_date, memo, currency, lines) -> JournalEntry:
        period = await _find_open_period(self._session, company_id=company_id, entry_date=entry_date)

        for line in lines:
            assert_line_amount_valid(line.debit, line.credit)
        assert_balanced(
            [JournalLineAmounts(debit=line.debit, credit=line.credit) for line in lines]
        )

        entry_number = await self._numbering_service.next_number(
            company_id=company_id, document_type="journal_entry"
        )
        journal_entry = JournalEntry(
            company_id=company_id,
            fiscal_period_id=period.id,
            entry_number=entry_number,
            entry_date=entry_date,
            memo=memo,
            currency=currency,
        )
        self._session.add(journal_entry)
        await self._session.flush()

        for line in lines:
            stmt = select(Account).where(
                Account.id == line.account_id, Account.company_id == company_id
            )
            account = (await self._session.execute(stmt)).scalar_one_or_none()
            if account is None:
                raise AccountNotFoundError(f"الحساب {line.account_id} غير موجود لهذه الشركة")
            if not account.is_postable:
                raise ValueError(f"الحساب {account.code} حساب تجميعي — لا يُسمح بالترحيل عليه")

            self._session.add(
                JournalEntryLine(
                    company_id=company_id,
                    journal_entry_id=journal_entry.id,
                    account_id=account.id,
                    cost_center_id=line.cost_center_id,
                    debit=line.debit,
                    credit=line.credit,
                    description=line.description,
                )
            )

        await self._session.commit()
        return await _reload_with_lines(self._session, journal_entry.id)


class CreateAccountUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, company_id: str, request: AccountCreateRequest) -> Account:
        account = Account(
            company_id=company_id,
            code=request.code,
            name=request.name,
            account_type=request.account_type,
            normal_balance=request.normal_balance,
            parent_id=request.parent_id,
            is_postable=request.is_postable,
        )
        self._session.add(account)
        await self._session.commit()
        await self._session.refresh(account)
        return account


class ListAccountsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, company_id: str) -> list[Account]:
        stmt = select(Account).where(
            Account.company_id == company_id, Account.deleted_at.is_(None)
        ).order_by(Account.code)
        return list((await self._session.execute(stmt)).scalars().all())


class ListJournalEntriesUseCase:
    """يعرض قيود اليومية لشركة معيّنة، الأحدث أولاً، مع تحميل بنودها
    (selectinload) لأن JournalEntryResponse يتطلب lines — بنفس نمط
    get_journal_entry في الراوتر لتفادي lazy-load غير متزامن."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, company_id: str) -> list[JournalEntry]:
        stmt = (
            select(JournalEntry)
            .where(JournalEntry.company_id == company_id)
            .options(selectinload(JournalEntry.lines))
            .order_by(JournalEntry.entry_date.desc(), JournalEntry.entry_number.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())
