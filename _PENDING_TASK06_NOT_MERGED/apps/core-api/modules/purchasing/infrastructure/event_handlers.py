"""معالج حدث `PaymentRecorded` من موديول payments — يحدّث `paid_amount` على
فاتورة الشراء المرجعية. هذا هو التطبيق الفعلي الأول لآلية الأحداث المُعلَنة
في docs/architecture/contracts.md، ويثبت أن التواصل بين payments وpurchasing
يمر فعلياً عبر Event Bus وليس استيراداً مباشراً بين الوحدتين (القسم 11.2).

يُسجَّل هذا المعالج في main.py عند إقلاع التطبيق:
    event_bus.subscribe("PaymentRecorded", handle_payment_recorded)
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
        # مهمة 6 (Outbox): الحمولة تُخزَّن كـ JSON في outbox_events، لذا تصل
        # amount كنص (str) وليس Decimal — راجع payments_use_cases.py.
        amount = Decimal(str(raw_amount))
    except InvalidOperation:
        return  # قيمة غير رقمية — تُهمَل بصمت بدل إسقاط باقي المشتركين

    stmt = select(PurchaseInvoice).where(
        PurchaseInvoice.id == invoice_id, PurchaseInvoice.company_id == company_id
    )
    invoice = (await session.execute(stmt)).scalar_one_or_none()
    if invoice is None:
        return  # قد يكون سند دفع لفاتورة بيع (sales) لاحقاً — ليس خطأً هنا

    invoice.paid_amount = (invoice.paid_amount or 0) + amount
    await session.commit()


def make_handler(session: AsyncSession):
    """مصنع Closure يربط المعالج بجلسة قاعدة بيانات محدَّدة — مفيد للاختبار
    (حقن جلسة SQLite) وللإنتاج (حقن جلسة حقيقية عبر AsyncSessionLocal)."""

    async def _handler(payload: dict) -> None:
        await apply_payment_to_invoice(session, payload)

    return _handler
