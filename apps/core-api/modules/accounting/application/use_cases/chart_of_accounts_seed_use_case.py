"""زرع شجرة حسابات افتراضية لشركة جديدة — Use Case مستقل يُستدعى صراحةً بعد
إنشاء الشركة (من واجهة الويب أو مباشرة)، وليس مربوطاً بمسار Bootstrap الخاص
بالعضو 1 (`RegisterCompanyUseCase`) عمداً: `identity`/`tenancy` ملك العضو 1
حصرياً (القسم 15.2) ولا يجوز لي تعديلهما. هذا التصميم يبقي الوحدتين منفصلتين
تماماً — لو أراد العضو 1 لاحقاً استدعاء هذا الـ Use Case من مسار Bootstrap
فهو يفعل ذلك عبر IAccountingPort أو Event جديد يُتَّفق عليه، وليس استيراداً
مباشراً.

الشجرة أدناه مبسّطة ومناسبة لتاجر/شركة صغيرة عامة (ليست قطاعية) — نقطة بداية
معقولة يمكن للمحاسب تعديلها لاحقاً عبر /accounts، وليست معياراً محاسبياً
رسمياً (لا IFRS ولا معيار عراقي موحّد محدَّد في Blueprint).
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.infrastructure.models.accounting_models import (
    Account,
    AccountNormalBalance,
    AccountType,
)


@dataclass(frozen=True)
class _AccountSeed:
    code: str
    name: str
    account_type: AccountType
    normal_balance: AccountNormalBalance
    parent_code: str | None = None
    is_postable: bool = True


_DEFAULT_CHART: list[_AccountSeed] = [
    # ── الأصول (Assets) ──────────────────────────────────────────────
    _AccountSeed("1000", "الأصول", AccountType.ASSET, AccountNormalBalance.DEBIT, is_postable=False),
    _AccountSeed("1100", "الأصول المتداولة", AccountType.ASSET, AccountNormalBalance.DEBIT, "1000", is_postable=False),
    _AccountSeed("1101", "الصندوق (النقدية)", AccountType.ASSET, AccountNormalBalance.DEBIT, "1100"),
    _AccountSeed("1102", "البنك", AccountType.ASSET, AccountNormalBalance.DEBIT, "1100"),
    _AccountSeed("1110", "الذمم المدينة (العملاء)", AccountType.ASSET, AccountNormalBalance.DEBIT, "1100"),
    _AccountSeed("1120", "المخزون", AccountType.ASSET, AccountNormalBalance.DEBIT, "1100"),
    _AccountSeed("1130", "ضريبة مدخلات مستحقة", AccountType.ASSET, AccountNormalBalance.DEBIT, "1100"),
    _AccountSeed("1200", "الأصول الثابتة", AccountType.ASSET, AccountNormalBalance.DEBIT, "1000", is_postable=False),
    _AccountSeed("1210", "أثاث ومعدات", AccountType.ASSET, AccountNormalBalance.DEBIT, "1200"),
    _AccountSeed("1220", "مجمّع إهلاك الأصول الثابتة", AccountType.ASSET, AccountNormalBalance.CREDIT, "1200"),
    # ── الالتزامات (Liabilities) ─────────────────────────────────────
    _AccountSeed("2000", "الالتزامات", AccountType.LIABILITY, AccountNormalBalance.CREDIT, is_postable=False),
    _AccountSeed("2100", "الذمم الدائنة (الموردون)", AccountType.LIABILITY, AccountNormalBalance.CREDIT, "2000"),
    _AccountSeed("2200", "ضريبة مخرجات مستحقة", AccountType.LIABILITY, AccountNormalBalance.CREDIT, "2000"),
    _AccountSeed("2300", "رواتب مستحقة الدفع", AccountType.LIABILITY, AccountNormalBalance.CREDIT, "2000"),
    # ── حقوق الملكية (Equity) ────────────────────────────────────────
    _AccountSeed("3000", "حقوق الملكية", AccountType.EQUITY, AccountNormalBalance.CREDIT, is_postable=False),
    _AccountSeed("3100", "رأس المال", AccountType.EQUITY, AccountNormalBalance.CREDIT, "3000"),
    _AccountSeed("3200", "الأرباح المرحّلة", AccountType.EQUITY, AccountNormalBalance.CREDIT, "3000"),
    # ── الإيرادات (Revenue) ──────────────────────────────────────────
    _AccountSeed("4000", "الإيرادات", AccountType.REVENUE, AccountNormalBalance.CREDIT, is_postable=False),
    _AccountSeed("4100", "إيرادات المبيعات", AccountType.REVENUE, AccountNormalBalance.CREDIT, "4000"),
    _AccountSeed("4200", "مردودات ومسموحات المبيعات", AccountType.REVENUE, AccountNormalBalance.DEBIT, "4000"),
    # ── المصروفات (Expenses) ─────────────────────────────────────────
    _AccountSeed("5000", "المصروفات", AccountType.EXPENSE, AccountNormalBalance.DEBIT, is_postable=False),
    _AccountSeed("5100", "تكلفة البضاعة المباعة", AccountType.EXPENSE, AccountNormalBalance.DEBIT, "5000"),
    _AccountSeed("5200", "مصروفات الرواتب", AccountType.EXPENSE, AccountNormalBalance.DEBIT, "5000"),
    _AccountSeed("5300", "مصروفات إيجار", AccountType.EXPENSE, AccountNormalBalance.DEBIT, "5000"),
    _AccountSeed("5400", "مصروفات عمومية وإدارية", AccountType.EXPENSE, AccountNormalBalance.DEBIT, "5000"),
]


class ChartOfAccountsAlreadySeededError(ValueError):
    pass


class SeedDefaultChartOfAccountsUseCase:
    """عملية Idempotent: تفشل صراحةً إن كانت الشركة تملك حسابات مسبقاً بدل أن
    تُنشئ تكراراً صامتاً (Fail Fast أوضح من UniqueConstraint خام للمستخدم)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, company_id: str) -> list[Account]:
        existing_stmt = select(Account.id).where(Account.company_id == company_id).limit(1)
        if (await self._session.execute(existing_stmt)).first() is not None:
            raise ChartOfAccountsAlreadySeededError(
                "هذه الشركة تملك حسابات مسبقاً — استخدم /accounts لإضافة حسابات يدوياً بدل إعادة الزرع"
            )

        code_to_id: dict[str, Account] = {}
        created: list[Account] = []

        for seed in _DEFAULT_CHART:
            parent_id = code_to_id[seed.parent_code].id if seed.parent_code else None
            account = Account(
                company_id=company_id,
                code=seed.code,
                name=seed.name,
                account_type=seed.account_type,
                normal_balance=seed.normal_balance,
                parent_id=parent_id,
                is_postable=seed.is_postable,
            )
            self._session.add(account)
            await self._session.flush()  # نحتاج account.id فوراً كـ parent للأسطر التالية
            code_to_id[seed.code] = account
            created.append(account)

        await self._session.commit()
        for account in created:
            await self._session.refresh(account)
        return created
