"""إنشاء السنوات/الفترات المالية وإقفالها.

إقفال فترة (ClosePeriodUseCase) لم يعد مجرد وضع علامة `is_closed=True` —
أصبح يبني ويرحّل **قيد إقفال فعلي** يُصفّر أرصدة حسابات الإيرادات
والمصروفات ضمن مدى الفترة، وينقل صافي الربح/الخسارة الناتج إلى حساب
"الأرباح المرحّلة" (كود `3200` في شجرة الحسابات الافتراضية — نفس أسلوب
الأكواد الثابتة المستخدَم في بقية الوحدات المستهلكة لـ IAccountingPort،
انظر modules/sales و modules/purchasing)، **ثم** يمنع أي قيد جديد على هذه
الفترة (`FiscalPeriod.is_closed=True` يُفحص في
`RecordDocumentPostingUseCase._find_open_period`، القيد الحاسم — دفاع
مضاعف مع منع الترحيل المباشر). أخيراً يُنشر حدث `FiscalPeriodClosed`
(contracts.md §2) عبر `enqueue_event()` (تنفيذ #6×#11×#12×#10 — Outbox
الحقيقي، راجع INTERFACE_CONTRACT_OUTBOX.md) بدل نشر مباشر عبر EventBus —
الحدث يُكتَب ضمن نفس معاملة الإقفال قبل commit()، والـ Worker المنفصل
(platform_core/outbox_worker.py) يتولى النشر الفعلي لاحقاً، فلا يُفقَد
حتى لو انهارت العملية مباشرة بعد commit() وقبل وصول النشر لأي مشترك.

هذا يُغلق الفجوة الموثَّقة سابقاً في
`modules/reporting/application/use_cases/financial_statements_use_case.py`
(كان تقرير الميزانية يعرض "صافي ربح الفترة الحالية" كحقوق ملكية مؤقتة
لعدم وجود آلية إقفال فعلية — أصبحت موجودة الآن، وتقرير الميزانية عُدِّل
ليقرأ رصيد الأرباح المرحّلة الفعلي بدلاً من حساب صافي الربح المؤقت في كل
مرة).
"""
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.accounting.application.dto.accounting_dto import FiscalYearCreateRequest
from modules.accounting.domain.rules.journal_balance_rule import (
    JournalLineAmounts,
    assert_balanced,
)
from modules.accounting.infrastructure.models.accounting_models import (
    Account,
    AccountType,
    FiscalPeriod,
    FiscalYear,
    JournalEntry,
    JournalEntryLine,
)
from modules.tenancy.application.ports.numbering_port import INumberingService
from platform_core.event_bus import EventBus
from platform_core.outbox import enqueue_event

RETAINED_EARNINGS_ACCOUNT_CODE = "3200"  # "الأرباح المرحّلة" في شجرة الحسابات الافتراضية


class FiscalPeriodNotFoundError(ValueError):
    pass


class FiscalPeriodAlreadyClosedError(ValueError):
    """محاولة إقفال فترة مُقفلة أصلاً — تُرفَض صراحةً بدل توليد قيد إقفال
    مكرَّر يُصفّر حسابات مُصفَّرة أصلاً."""


class RetainedEarningsAccountMissingError(ValueError):
    """حساب الأرباح المرحّلة (الكود أعلاه) غير موجود لهذه الشركة — لا يمكن
    إقفال فترة فيها نشاط إيرادات/مصروفات بدون وجهة يُنقَل إليها صافي الربح."""


def _add_one_month(d: date) -> date:
    """يضيف شهراً واحداً إلى تاريخ، معالجاً تدوير السنة يدوياً بلا اعتماديات
    خارجية إضافية (تفادي إضافة حزمة جديدة لـ pyproject.toml لأجل هذا فقط)."""
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1)
    return d.replace(month=d.month + 1)


async def _closing_net_by_account(
    session: AsyncSession,
    *,
    company_id: str,
    account_types: list[AccountType],
    date_from: date,
    date_to: date,
    credit_positive: bool,
) -> list[tuple[str, Decimal]]:
    """يحسب صافي رصيد كل حساب (إيراد أو مصروف) ضمن مدى الفترة المطلوب
    إقفالها. منطق الحساب مطابق لـ
    `reporting/financial_statements_use_case._sum_by_account` لكن مكرَّر
    محلياً عمداً بدل الاستيراد منه — الطبقات هنا تفترض أن `reporting` يعتمد
    على `accounting`، وليس العكس (لا يجوز لـ accounting الاستيراد من
    reporting). الحسابات ذات الرصيد الصفري ضمن المدى تُستبعَد لأنها لا
    تحتاج سطر إقفال أصلاً.
    """
    net_expr = (
        (func.sum(JournalEntryLine.credit) - func.sum(JournalEntryLine.debit))
        if credit_positive
        else (func.sum(JournalEntryLine.debit) - func.sum(JournalEntryLine.credit))
    )
    stmt = (
        select(Account.id, net_expr)
        .join(JournalEntryLine, JournalEntryLine.account_id == Account.id)
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .where(
            Account.company_id == company_id,
            Account.account_type.in_(account_types),
            JournalEntry.entry_date >= date_from,
            JournalEntry.entry_date <= date_to,
        )
        .group_by(Account.id)
    )
    rows = (await session.execute(stmt)).all()
    return [(str(account_id), amount) for account_id, amount in rows if amount != 0]


class CreateFiscalYearUseCase:
    """ينشئ السنة المالية ويولّد فتراتها الشهرية تلقائياً (period_count فترة
    بالتساوي بين start_date و end_date)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, company_id: str, request: FiscalYearCreateRequest) -> FiscalYear:
        fiscal_year = FiscalYear(
            company_id=company_id,
            code=request.code,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        self._session.add(fiscal_year)
        await self._session.flush()

        period_start = request.start_date
        for period_number in range(1, request.period_count + 1):
            if period_number == request.period_count:
                period_end = request.end_date
            else:
                next_month_first_day = _add_one_month(
                    period_start.replace(day=1)
                )
                period_end = min(next_month_first_day - timedelta(days=1), request.end_date)
            self._session.add(
                FiscalPeriod(
                    company_id=company_id,
                    fiscal_year_id=fiscal_year.id,
                    period_number=period_number,
                    start_date=period_start,
                    end_date=period_end,
                )
            )
            period_start = period_end + timedelta(days=1)
            if period_start > request.end_date:
                break

        await self._session.commit()
        stmt = (
            select(FiscalYear)
            .where(FiscalYear.id == fiscal_year.id)
            .options(selectinload(FiscalYear.periods))
        )
        return (await self._session.execute(stmt)).scalar_one()


class ClosePeriodUseCase:
    """يبني قيد الإقفال (إن وُجد نشاط إيرادات/مصروفات ضمن مدى الفترة)،
    يرحّله بينما الفترة لا تزال مفتوحة تقنياً، ثم يقفل الفترة نفسها وينشر
    الحدث."""

    def __init__(
        self,
        session: AsyncSession,
        numbering_service: INumberingService,
        event_bus: EventBus,
    ) -> None:
        self._session = session
        self._numbering_service = numbering_service
        # ⚠️ تنفيذ #6×#11×#12×#10 (Track 3): النشر الفعلي انتقل إلى
        # enqueue_event() أدناه (Outbox حقيقي) — هذا المعامل لم يعد
        # مُستخدَماً داخلياً. أُبقي عليه بدل حذفه (README الحزمة يسمح
        # بالحذف صراحةً) لأن حذفه يكسر توقيع الاستدعاء في
        # fiscal_periods_router.py و8 مواضع في tests/integration/
        # (test_period_closing.py وtest_accounting_posting.py) — خارج
        # نطاق هذا الملف/هذه الحزمة تماماً، ولم يُتحقَّق من أن تلك
        # الاختبارات لا تفترض سلوك event_bus.publish() الفوري القديم في
        # مكان آخر. تحديثها بأمان يحتاج مراجعة كل اختبار على حدة، وليس مجرد
        # حذف معامل — تُرِك كفجوة موثَّقة بدل تعديل أعمى.
        self._event_bus = event_bus

    async def execute(self, company_id: str, period_id: str) -> FiscalPeriod:
        stmt = select(FiscalPeriod).where(
            FiscalPeriod.id == period_id, FiscalPeriod.company_id == company_id
        )
        period = (await self._session.execute(stmt)).scalar_one_or_none()
        if period is None:
            raise FiscalPeriodNotFoundError("الفترة المالية غير موجودة لهذه الشركة")
        if period.is_closed:
            raise FiscalPeriodAlreadyClosedError(
                "الفترة المالية مُقفلة أصلاً — لا يمكن إقفالها مرة أخرى"
            )

        closing_journal_entry_id = await self._post_closing_entry(
            company_id=company_id, period=period
        )

        period.is_closed = True
        period.closed_at = datetime.now(UTC).date()

        # تنفيذ #6×#11×#12×#10 (Track 3): enqueue_event() يحل محل نداء
        # event_bus.publish() المباشر — يُكتَب ضمن نفس معاملة الإقفال قبل
        # commit() (إما يُحفَظ إقفال الفترة + الحدث معاً ذرّياً أو لا شيء
        # منهما)، والـ Worker المنفصل يتولى النشر الفعلي لاحقاً. نفس حقول
        # الحمولة بالضبط المطابقة لِـ contracts.md §2.
        await enqueue_event(
            self._session,
            event_name="FiscalPeriodClosed",
            payload={
                "company_id": company_id,
                "period_id": str(period.id),
                "closed_at": period.closed_at.isoformat(),
                "closing_journal_entry_id": closing_journal_entry_id,
            },
            aggregate_id=str(period.id),
        )

        await self._session.commit()
        await self._session.refresh(period)
        return period

    async def _post_closing_entry(self, *, company_id: str, period: FiscalPeriod) -> str | None:
        """يبني قيد الإقفال ويرحّله. يُعيد معرّف القيد، أو `None` إن لم يكن
        هناك أي نشاط إيرادات/مصروفات ضمن الفترة (لا حاجة لقيد فارغ)."""
        revenue_rows = await _closing_net_by_account(
            self._session,
            company_id=company_id,
            account_types=[AccountType.REVENUE],
            date_from=period.start_date,
            date_to=period.end_date,
            credit_positive=True,
        )
        expense_rows = await _closing_net_by_account(
            self._session,
            company_id=company_id,
            account_types=[AccountType.EXPENSE],
            date_from=period.start_date,
            date_to=period.end_date,
            credit_positive=False,
        )

        if not revenue_rows and not expense_rows:
            return None

        total_revenue = sum((amount for _, amount in revenue_rows), Decimal(0))
        total_expense = sum((amount for _, amount in expense_rows), Decimal(0))
        net_income = total_revenue - total_expense

        re_stmt = select(Account).where(
            Account.company_id == company_id, Account.code == RETAINED_EARNINGS_ACCOUNT_CODE
        )
        retained_earnings = (await self._session.execute(re_stmt)).scalar_one_or_none()
        if retained_earnings is None:
            raise RetainedEarningsAccountMissingError(
                f"حساب الأرباح المرحّلة (كود {RETAINED_EARNINGS_ACCOUNT_CODE}) غير موجود "
                "لهذه الشركة — أضِفه إلى شجرة الحسابات قبل إقفال فترة فيها نشاط"
            )

        # 1) تجهيز أسطر القيد في الذاكرة أولاً للتحقق من التوازن قبل أي كتابة
        #    لقاعدة البيانات (نفس نهج RecordDocumentPostingUseCase).
        pending_lines: list[dict] = []
        for account_id, amount in revenue_rows:
            # حسابات الإيرادات دائنة بطبيعتها؛ تُصفَّر بترحيل مدين بمقدار رصيدها
            pending_lines.append(
                {
                    "account_id": account_id,
                    "debit": amount,
                    "credit": Decimal(0),
                    "description": "إقفال حساب إيراد إلى الأرباح المرحّلة",
                }
            )
        for account_id, amount in expense_rows:
            # حسابات المصروفات مدينة بطبيعتها؛ تُصفَّر بترحيل دائن بمقدار رصيدها
            pending_lines.append(
                {
                    "account_id": account_id,
                    "debit": Decimal(0),
                    "credit": amount,
                    "description": "إقفال حساب مصروف إلى الأرباح المرحّلة",
                }
            )
        if net_income >= 0:
            pending_lines.append(
                {
                    "account_id": str(retained_earnings.id),
                    "debit": Decimal(0),
                    "credit": net_income,
                    "description": "ترحيل صافي ربح الفترة إلى الأرباح المرحّلة",
                }
            )
        else:
            pending_lines.append(
                {
                    "account_id": str(retained_earnings.id),
                    "debit": -net_income,
                    "credit": Decimal(0),
                    "description": "ترحيل صافي خسارة الفترة من الأرباح المرحّلة",
                }
            )

        assert_balanced(
            [
                JournalLineAmounts(debit=line["debit"], credit=line["credit"])
                for line in pending_lines
            ]
        )

        # 2) الكتابة الفعلية: القيد يُرحَّل على نفس الفترة (fiscal_period_id)
        #    بينما is_closed لا يزال False في هذه اللحظة — يُقفَل بعد نجاح
        #    الترحيل مباشرة في execute().
        entry_number = await self._numbering_service.next_number(
            company_id=company_id, document_type="journal_entry"
        )
        closing_entry = JournalEntry(
            company_id=company_id,
            fiscal_period_id=period.id,
            entry_number=entry_number,
            entry_date=period.end_date,
            memo=f"قيد إقفال الفترة رقم {period.period_number}",
            source_document_type="period_closing",
            source_document_id=str(period.id),
            currency="IQD",
        )
        self._session.add(closing_entry)
        await self._session.flush()  # للحصول على closing_entry.id قبل إضافة الأسطر

        for line in pending_lines:
            self._session.add(
                JournalEntryLine(
                    company_id=company_id,
                    journal_entry_id=closing_entry.id,
                    account_id=line["account_id"],
                    debit=line["debit"],
                    credit=line["credit"],
                    description=line["description"],
                )
            )

        await self._session.flush()
        return str(closing_entry.id)


class ListFiscalYearsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, company_id: str) -> list[FiscalYear]:
        stmt = (
            select(FiscalYear)
            .where(FiscalYear.company_id == company_id, FiscalYear.deleted_at.is_(None))
            .options(selectinload(FiscalYear.periods))
            .order_by(FiscalYear.start_date)
        )
        return list((await self._session.execute(stmt)).scalars().all())
