"""Use Cases للمدفوعات — القسم 9. ربط السداد بفاتورة شراء يتم عبر حدث
`PaymentRecorded` (مُعلَن مسبقاً في docs/architecture/contracts.md) وليس عبر
استيراد مباشر لجداول purchasing — احتراماً لقاعدة عزل الوحدات (القسم 11.2:
"ممنوع استيراد infrastructure الخاص بـ module آخر مباشرة").
"""
from sqlalchemy.ext.asyncio import AsyncSession

from modules.payments.application.dto.payments_dto import (
    BankAccountCreateRequest,
    PaymentCreateRequest,
    ReceiptCreateRequest,
)
from modules.payments.infrastructure.models.payments_models import BankAccount, Payment, Receipt
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext
from platform_core.event_bus import EventBus

DOCUMENT_TYPE_PAYMENT = "payment"
DOCUMENT_TYPE_RECEIPT = "receipt"


class CreateBankAccountUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: BankAccountCreateRequest) -> BankAccount:
        account = BankAccount(
            company_id=ctx.company_id, name=request.name, bank_name=request.bank_name,
            account_number=request.account_number, currency_code=request.currency_code,
            opening_balance=request.opening_balance,
        )
        self._session.add(account)
        await self._session.commit()
        await self._session.refresh(account)
        return account


class CreatePaymentUseCase:
    """ينشئ سند صرف، ثم ينشر حدث `PaymentRecorded` عبر Outbox الفعلي (مهمة 6،
    القسم 6.6 — انظر platform_core/event_bus.py) ليُحدِّث موديول purchasing
    رصيد الفاتورة المرجعية دون أي اعتماد مباشر بين الوحدتين."""

    def __init__(self, session: AsyncSession, event_bus: EventBus) -> None:
        self._session = session
        self._event_bus = event_bus

    async def execute(self, ctx: TenantContext, request: PaymentCreateRequest) -> Payment:
        numbering = SqlNumberingService(self._session)
        payment_number = await numbering.next_number(
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

        if request.reference_invoice_id:
            # flush (وليس commit) فقط لتوليد payment.id قبل بناء حمولة الحدث —
            # يبقى ضمن نفس المعاملة المفتوحة، لا حفظ نهائي بعد.
            await self._session.flush()
            # مهمة 6 (Outbox): يُكتَب ضمن نفس معاملة إنشاء سند الصرف قبل
            # الـ commit — إما يُحفَظ الاثنان معاً أو لا شيء.
            await self._event_bus.publish(
                self._session,
                "PaymentRecorded",
                {
                    "payment_id": str(payment.id),
                    "invoice_id": request.reference_invoice_id,
                    "amount": str(request.amount),
                    "currency": request.currency_code,
                    "company_id": ctx.company_id,
                },
            )
        await self._session.commit()
        await self._session.refresh(payment)

        if request.reference_invoice_id:
            # محاولة تسليم فورية (best effort) — أي فشل يلتقطه outbox_worker لاحقاً
            await self._event_bus.dispatch_pending(self._session)
        return payment


class CreateReceiptUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: ReceiptCreateRequest) -> Receipt:
        numbering = SqlNumberingService(self._session)
        receipt_number = await numbering.next_number(
            company_id=ctx.company_id, document_type=DOCUMENT_TYPE_RECEIPT
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
        await self._session.refresh(receipt)
        return receipt
