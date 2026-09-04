"""Use Cases لموديول payments — سندات الصرف (Payments).

⚠️ ملاحظة اكتُشفت أثناء إعادة التحقق الفعلي (`pytest`) على بيئة حقيقية: هذا
الملف كان **مفقوداً بالكامل** من الشجرة رغم أن كلاً من
`presentation/routes/payments_router.py` و
`tests/integration/test_purchasing_payments_flow.py` يستوردانه صراحة
(`from modules.payments.application.use_cases.payments_use_cases import
CreatePaymentUseCase`) — أي أن استيراد موديول payments، وبالتالي إقلاع
core-api بأكمله، كان سيفشل بـ `ModuleNotFoundError` فوراً عند أي تشغيل فعلي.
لم يكتشف هذا أحد سابقاً لأن كل عمليات التحقق حتى الآن كانت `py_compile` (لا
يتتبّع استيرادات وقت التشغيل عبر حدود الموديولات) وليس `pytest` فعلياً على
بيئة بها Postgres/Redis حقيقيين. هذا بالضبط نفس نمط الخطر الذي واجهته
`modules/purchasing/infrastructure/event_handlers.py` سابقاً (راجع تعليق
ذلك الملف).

أُعيد بناء `CreatePaymentUseCase` هنا من العقد الفعلي الوحيد المتاح: توقيع
الاستدعاء في `payments_router.py` (`CreatePaymentUseCase(session,
event_bus).execute(ctx, request)`)، حقول `PaymentCreateRequest`/
`PaymentResponse` في `payments_dto.py`، نموذج `Payment` في
`payments_models.py`، ومعيار التسليم الفعلي في
`test_purchasing_payments_flow.py` (ترقيم تسلسلي `000001` عبر
`SqlNumberingService`، ونشر حدث `PaymentRecorded` بحمولة
`{invoice_id, company_id, amount}` يلتقطه معالج purchasing
`apply_payment_to_invoice` عبر Event Bus — لا استيراد مباشر بين
الموديولين، القسم 11.2).

── نشر الحدث: EventBus مباشر، وليس Outbox (Track 1) ─────────────────────
هذا الملف **لا** يستخدم `platform_core.outbox.enqueue_event()`. عقد
`enqueue_event()` المجمَّد في `INTERFACE_CONTRACT_OUTBOX.md` مخصَّص فقط
لثلاث نقاط النشر التي بُنيت عليه صراحة (`SalesInvoiceCreated`،
`InvoicePosted`، `FiscalPeriodClosed` — راجع Track 2/Track 3). `PaymentRecorded`
لم يكن جزءاً من ذلك النطاق، والاختبار الفعلي القائم
(`test_purchasing_payments_flow.py`) يُنشئ `EventBus()` معزولاً محلياً،
يشترك فيه مباشرة، ثم يتوقّع أن يصل الحدث للمشترك *فوراً* ضمن نفس استدعاء
`execute()` — وهو بالضبط سلوك `EventBus.publish(event_name, payload)`
الفوري القديم غير المُعدَّل (نفس النمط المستخدَم في
`platform_core/redis_bridge.py` لأحداث `InvoiceDraftReady` الواردة من
Redis). استخدام `enqueue_event()` هنا كان سيؤجّل التسليم إلى دورة استطلاع
`outbox_worker.py` التالية (كل ثانيتين) بدل تسليم متزامن، فيكسر هذا
الاختبار بلا أي داعٍ معماري — `PaymentRecorded` لا يحتاج ضمان بقاء عبر
انهيار العملية بنفس درجة إلحاح فواتير البيع/إقفال الفترة.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from modules.payments.application.dto.payments_dto import (
    BankAccountCreateRequest,
    PaymentCreateRequest,
    ReceiptCreateRequest,
)
from modules.payments.infrastructure.models.payments_models import BankAccount, Payment, Receipt
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext
from platform_core.event_bus import event_bus as _default_event_bus

if TYPE_CHECKING:
    from platform_core.event_bus import EventBus, _EventBusFacade

DOCUMENT_TYPE_PAYMENT = "payment"


class CreatePaymentUseCase:
    """سند صرف لمورد. إن ارتبط بفاتورة شراء (`reference_invoice_id`)، ينشر
    `PaymentRecorded` ليحدّث `paid_amount` على تلك الفاتورة عبر معالج
    purchasing المشترك عبر Event Bus فقط (بلا استيراد مباشر للموديول).

    `bus` معامل اختياري صريح (وليس اعتماداً ضمنياً فقط على الـ Facade
    العالمي) حتى تستطيع الاختبارات حقن `EventBus()` معزول خاص بها — تماماً
    كما يفعل `test_purchasing_payments_flow.py`.
    """

    def __init__(
        self,
        session: AsyncSession,
        bus: EventBus | _EventBusFacade = _default_event_bus,
    ) -> None:
        self._session = session
        self._event_bus = bus

    async def execute(self, ctx: TenantContext, request: PaymentCreateRequest) -> Payment:
        payment_number = await SqlNumberingService(self._session).next_number(
            company_id=ctx.company_id, document_type=DOCUMENT_TYPE_PAYMENT
        )

        payment = Payment(
            company_id=ctx.company_id,
            bank_account_id=request.bank_account_id,
            supplier_id=request.supplier_id,
            payment_number=payment_number,
            reference_invoice_id=request.reference_invoice_id,
            amount=request.amount,
            currency_code=request.currency_code,
            method=request.method,
            status="confirmed",
        )
        self._session.add(payment)
        await self._session.commit()

        # نشر فوري (EventBus مباشر، ليس Outbox — راجع تعليق أعلى الملف). لا
        # يُنشَر حدث إن لم يكن السند مرتبطاً بفاتورة (لا شيء يُحدَّث في هذه
        # الحالة أصلاً).
        if request.reference_invoice_id:
            await self._event_bus.publish(
                "PaymentRecorded",
                {
                    "invoice_id": request.reference_invoice_id,
                    "company_id": ctx.company_id,
                    "amount": str(request.amount),
                },
            )

        return payment


class CreateBankAccountUseCase:
    """حساب بنكي/صندوق نقدي لشركة — لا نشر حدث هنا: لا يوجد أي معالج حدث آخر
    يهتم بإنشاء حساب بنكي بحد ذاته (فرق واضح عن `CreatePaymentUseCase` الذي
    يُحدِّث فاتورة شراء عبر حدث)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: BankAccountCreateRequest) -> BankAccount:
        account = BankAccount(
            company_id=ctx.company_id,
            name=request.name,
            bank_name=request.bank_name,
            account_number=request.account_number,
            currency_code=request.currency_code,
            opening_balance=request.opening_balance,
            is_active=True,
        )
        self._session.add(account)
        await self._session.commit()
        return account


class CreateReceiptUseCase:
    """سند قبض من عميل. `reference_invoice_id` مُخزَّن بلا نشر حدث حالياً —
    على عكس `CreatePaymentUseCase`/`PaymentRecorded`، لا يوجد بعد أي معالج
    مسجَّل في sales يستهلك حدث قبض مقابل — تحديث `paid_amount` على فاتورة
    البيع المرجعية خارج نطاق هذا الملف، ويُترَك كعمل لاحق صريح بدل نشر حدث
    بلا مستهلك."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: ReceiptCreateRequest) -> Receipt:
        receipt_number = await SqlNumberingService(self._session).next_number(
            company_id=ctx.company_id, document_type="receipt"
        )
        receipt = Receipt(
            company_id=ctx.company_id,
            bank_account_id=request.bank_account_id,
            customer_id=request.customer_id,
            receipt_number=receipt_number,
            reference_invoice_id=request.reference_invoice_id,
            amount=request.amount,
            currency_code=request.currency_code,
            method=request.method,
            status="confirmed",
        )
        self._session.add(receipt)
        await self._session.commit()
        return receipt
