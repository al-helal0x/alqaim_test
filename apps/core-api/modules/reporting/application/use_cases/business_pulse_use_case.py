"""لوحة "نبض الشركة اليومي" — TASK-BI-01، أول Vertical Slice لميزة الرسوم
البيانية الحية (راجع الدراسة والبطاقة المرفقتين لهذه المهمة).

قواعد التصميم الملزمة من بطاقة المهمة (لا اجتهاد هنا، تطبيق حرفي):

1. لا استعلام SQL خام جديد خارج repositories/use cases القائمة فعلاً في
   sales/inventory/payments — هذا الملف يستدعيها فقط، ويجمّع (aggregate)
   النتائج في بايثون. هذا يضمن أن فلترة company_id/tenant تمر دائماً عبر
   نفس الكود المُختبَر فعلياً في تلك الوحدات، لا استعلاماً موازياً قد ينسى
   الفلترة.
2. استثناء واحد فقط: `modules.accounting` — مسموح لـ `reporting` قراءتها
   مباشرة عبر SQLAlchemy (نفس نمط `trial_balance_use_case.py` الموثَّق:
   "نفس المالك"). غير مُستخدَم فعلياً في هذه النسخة الأولى لأن أعمار الذمم
   تُحسَب من sales+payments مباشرة، لا accounting.
3. لا Materialized View ولا جدول تجميع في هذه النسخة (مستوى 1 فقط: استعلام
   مباشر عند الفتح). هذا يعني تجميعاً في الذاكرة (O(n) على فواتير/حركات
   الشركة) — قيد معروف وموثَّق، لا يُحسَّن إلا بعد قياس بطء فعلي (TASK-BI-02
   المستقبلية، غير مفتوحة الآن).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from modules.inventory.application.use_cases.inventory_use_cases import ListBalancesUseCase
from modules.payments.infrastructure.repositories.payments_repository import (
    BankAccountRepository,
    PaymentRepository,
    ReceiptRepository,
)
from modules.reporting.application.dto.business_pulse_dto import (
    BusinessPulseResponse,
    CashAccountBalance,
    LowStockItem,
    ReceivablesAging,
    SalesTrendPoint,
    TopProductRow,
)
from modules.sales.application.use_cases.sales_use_cases import ListSalesInvoicesUseCase
from modules.sales.domain.rules import SalesInvoiceStatus
from platform_core.auth_middleware import TenantContext
from shared_kernel.pagination import PageParams

# سقف تجميع داخلي للنسخة الأولى (استعلام مباشر عند الفتح، بلا Materialized
# View) — ليس حد صفحات API للمستخدم، بل حد أمان داخلي بحت كي لا يجلب هذا
# الاستخدام الداخلي كل سجل فاتورة/رصيد للشركة بلا سقف مطلقاً. يُعاد تقييمه
# عند فتح TASK-BI-02 (تحسين الأداء) لا قبل ذلك.
_INTERNAL_AGGREGATION_PAGE_SIZE = 2000

_LOW_STOCK_TOP_N = 5
_TOP_PRODUCTS_TOP_N = 5


class BusinessPulseUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, *, period_days: int = 7) -> BusinessPulseResponse:
        if period_days < 1:
            raise ValueError("period_days يجب أن يكون 1 على الأقل")

        now = datetime.now(UTC)
        posted_invoices = await self._load_posted_invoices(ctx)

        sales_trend, sales_current, sales_previous = self._compute_sales_trend(
            posted_invoices, now=now, period_days=period_days
        )
        top_products = self._compute_top_products(
            posted_invoices, now=now, period_days=period_days
        )
        cash_accounts, cash_total = await self._compute_cash_position(ctx)
        low_stock_items = await self._compute_low_stock(ctx)
        receivables_aging = await self._compute_receivables_aging(ctx, posted_invoices, now=now)

        return BusinessPulseResponse(
            company_id=ctx.company_id,
            period_days=period_days,
            generated_at=now.isoformat(),
            sales_trend=sales_trend,
            sales_total_current_period=sales_current,
            sales_total_previous_period=sales_previous,
            top_products=top_products,
            cash_accounts=cash_accounts,
            cash_total=cash_total,
            low_stock_items=low_stock_items,
            receivables_aging=receivables_aging,
        )

    # ── مؤشر 1+2: اتجاه المبيعات + أعلى 5 منتجات ───────────────────────────

    async def _load_posted_invoices(self, ctx: TenantContext):
        """فواتير البيع المرحَّلة فقط (لا مسودات) — عبر ListSalesInvoicesUseCase
        القائم فعلاً، الذي يضمن فلترة company_id (لا استعلام موازٍ)."""
        params = PageParams(page=1, page_size=_INTERNAL_AGGREGATION_PAGE_SIZE)
        invoices, _total = await ListSalesInvoicesUseCase(self._session).execute(ctx, params)
        return [inv for inv in invoices if inv.status == SalesInvoiceStatus.POSTED.value]

    def _compute_sales_trend(self, posted_invoices, *, now: datetime, period_days: int):
        current_start = now - timedelta(days=period_days)
        previous_start = now - timedelta(days=period_days * 2)

        by_day: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
        current_total = Decimal(0)
        previous_total = Decimal(0)

        for inv in posted_invoices:
            created = inv.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)

            if current_start <= created <= now:
                by_day[created.date().isoformat()] += inv.total_amount
                current_total += inv.total_amount
            elif previous_start <= created < current_start:
                previous_total += inv.total_amount

        # كل أيام الفترة تظهر بالترتيب حتى لو صفر مبيعات (خط زمني متصل للرسم،
        # لا فجوات صامتة تبدو كخطأ في الواجهة)
        trend: list[SalesTrendPoint] = []
        for offset in range(period_days - 1, -1, -1):
            day = (now - timedelta(days=offset)).date().isoformat()
            trend.append(SalesTrendPoint(day=day, total_amount=by_day.get(day, Decimal(0))))

        return trend, current_total, previous_total

    def _compute_top_products(self, posted_invoices, *, now: datetime, period_days: int):
        current_start = now - timedelta(days=period_days)
        totals: dict[str, dict[str, Decimal]] = defaultdict(
            lambda: {"quantity": Decimal(0), "amount": Decimal(0)}
        )

        for inv in posted_invoices:
            created = inv.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if not (current_start <= created <= now):
                continue
            for line in inv.lines:
                key = str(line.product_id)
                totals[key]["quantity"] += line.quantity
                totals[key]["amount"] += line.line_total

        ranked = sorted(totals.items(), key=lambda kv: kv[1]["amount"], reverse=True)
        return [
            TopProductRow(product_id=pid, total_quantity=vals["quantity"], total_amount=vals["amount"])
            for pid, vals in ranked[:_TOP_PRODUCTS_TOP_N]
        ]

    # ── مؤشر 3: الصندوق والحسابات البنكية ───────────────────────────────────

    async def _compute_cash_position(self, ctx: TenantContext):
        bank_accounts = await BankAccountRepository(self._session).list_for_company(
            company_id=ctx.company_id
        )
        receipts = await ReceiptRepository(self._session).list_for_company(company_id=ctx.company_id)
        payments = await PaymentRepository(self._session).list_for_company(company_id=ctx.company_id)

        receipts_by_account: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
        for r in receipts:
            if r.status == "confirmed" and r.bank_account_id is not None:
                receipts_by_account[str(r.bank_account_id)] += r.amount

        payments_by_account: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
        for p in payments:
            if p.status == "confirmed" and p.bank_account_id is not None:
                payments_by_account[str(p.bank_account_id)] += p.amount

        rows: list[CashAccountBalance] = []
        total = Decimal(0)
        for acc in bank_accounts:
            acc_id = str(acc.id)
            balance = (
                acc.opening_balance
                + receipts_by_account.get(acc_id, Decimal(0))
                - payments_by_account.get(acc_id, Decimal(0))
            )
            rows.append(
                CashAccountBalance(
                    bank_account_id=acc_id,
                    name=acc.name,
                    currency_code=acc.currency_code,
                    balance=balance,
                )
            )
            total += balance

        return rows, total

    # ── مؤشر 4: أدنى 5 عناصر مخزوناً ────────────────────────────────────────

    async def _compute_low_stock(self, ctx: TenantContext):
        params = PageParams(page=1, page_size=_INTERNAL_AGGREGATION_PAGE_SIZE)
        balances, _total = await ListBalancesUseCase(self._session).execute(ctx, params)
        ranked = sorted(balances, key=lambda b: b.quantity)
        return [
            LowStockItem(
                product_id=str(b.product_id),
                warehouse_id=str(b.warehouse_id),
                quantity=b.quantity,
            )
            for b in ranked[:_LOW_STOCK_TOP_N]
        ]

    # ── مؤشر 5: أعمار الذمم المدينة ─────────────────────────────────────────

    async def _compute_receivables_aging(self, ctx: TenantContext, posted_invoices, *, now: datetime):
        receipts = await ReceiptRepository(self._session).list_for_company(company_id=ctx.company_id)
        paid_by_invoice: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
        for r in receipts:
            if r.status == "confirmed" and r.reference_invoice_id is not None:
                paid_by_invoice[str(r.reference_invoice_id)] += r.amount

        bucket_0_30 = Decimal(0)
        bucket_31_60 = Decimal(0)
        bucket_61_plus = Decimal(0)

        for inv in posted_invoices:
            outstanding = inv.total_amount - paid_by_invoice.get(str(inv.id), Decimal(0))
            if outstanding <= 0:
                continue
            created = inv.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            age_days = (now - created).days
            if age_days <= 30:
                bucket_0_30 += outstanding
            elif age_days <= 60:
                bucket_31_60 += outstanding
            else:
                bucket_61_plus += outstanding

        return ReceivablesAging(
            bucket_0_30=bucket_0_30, bucket_31_60=bucket_31_60, bucket_61_plus=bucket_61_plus
        )
