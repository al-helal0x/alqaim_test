"""معالج حدث `PaymentRecorded` من موديول payments — يحدّث `paid_amount` على
فاتورة الشراء المرجعية. هذا هو التطبيق الفعلي الأول لآلية الأحداث المُعلَنة
في docs/architecture/contracts.md، ويثبت أن التواصل بين payments وpurchasing
يمر فعلياً عبر Event Bus وليس استيراداً مباشراً بين الوحدتين (القسم 11.2).

يُسجَّل هذا المعالج في main.py عند إقلاع التطبيق:
    bus.subscribe("PaymentRecorded", _on_payment_recorded)

⚠️ ملاحظة اكتُشفت أثناء حسم تعارض #6×#10×#11×#12: هذا الملف كان **مفقوداً
فعلياً من شجرة main** رغم أن `main.py` يستورده صراحة (`from
modules.purchasing.infrastructure.event_handlers import
apply_payment_to_invoice`) — أي أن استيراد core-api كان سيفشل بـ
`ModuleNotFoundError` فوراً عند أي إقلاع فعلي، بصرف النظر عن هذا الدمج.
أُعيد إنشاؤه هنا من نسخة تسليم #6 المحفوظة في `_PENDING_TASK06_NOT_MERGED/`
(كانت تحمل هذا الملف أصلاً كجزء من تعديلاتها خارج الحدود المصرَّح بها،
الموثَّقة في DELIVERY_CARD_TASK_06.md) لأنه المصدر الوحيد المتاح لمنطقه.
"""
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.purchasing.infrastructure.models.purchasing_models import PurchaseInvoice


async def apply_payment_to_invoice(session: AsyncSession, payload: dict) -> None:
    invoice_id = payload.get("invoice_id")
    company_id = payload.get("company_id")
    raw_amount = payload.get("amount")
    if not invoice_id or not company_id or raw_amount is None:
        return  # حمولة غير مكتملة — تُهمَل بصمت (لا تُسقِط باقي المشتركين)

    try:
        # مهمة 6 (Outbox): الحمولة تُخزَّن كـ JSON في outbox_events، لذا قد
        # تصل amount كنص (str) وليس Decimal حسب الناشر — Decimal(str(...))
        # يتعامل بأمان مع الحالتين معاً.
        amount = Decimal(str(raw_amount))
    except InvalidOperation:
        return  # قيمة غير رقمية — تُهمَل بصمت بدل إسقاط باقي المشتركين

    stmt = select(PurchaseInvoice).where(
        PurchaseInvoice.id == invoice_id, PurchaseInvoice.company_id == company_id
    )
    invoice = (await session.execute(stmt)).scalar_one_or_none()
    if invoice is None:
        return  # قد يكون سند دفع لفاتورة بيع (sales) — ليس خطأً هنا

    invoice.paid_amount = (invoice.paid_amount or 0) + amount
    await session.commit()


def make_handler(session: AsyncSession):
    """مصنع Closure يربط المعالج بجلسة قاعدة بيانات محدَّدة — مفيد للاختبار
    (حقن جلسة SQLite) وللإنتاج (حقن جلسة حقيقية عبر AsyncSessionLocal)."""

    async def _handler(payload: dict) -> None:
        await apply_payment_to_invoice(session, payload)

    return _handler
