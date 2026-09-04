"""جزء آمن ثانٍ من `TASK-AI-01` — Idempotency (خطوة موصوفة حرفياً في الخطة:
"draft_id كـ idempotency_key — يمنع فاتورتين لنفس المسودة").

**لماذا use case منفصل، لا تعديل `CreatePurchaseInvoiceUseCase`:** لتفادي أي
أثر جانبي على مسار إنشاء فاتورة الشراء اليدوي/من أمر شراء الموجود فعلاً
ويعمل بلا مشاكل. هذا الملف **يستدعي** `_build_lines_and_totals` الموجودة
فعلاً (لا إعادة بناء منطق حساب الإجمالي) دون تعديل عليها.

**النمط متطابق تماماً مع `sales_use_cases.py` لمهمة #11:**
1. فحص مبكر بمفتاح idempotency (هنا: `source_ai_draft_id`) قبل أي عمل.
2. عند سباق حقيقي (طلبان شبه-متزامنين لنفس المسودة) → `IntegrityError` من
   قيد UNIQUE على مستوى القاعدة (`uq_purchase_invoice_ai_draft_id`،
   راجع `migrations/versions/purchasing_20260813_0001_*.py`) → rollback ثم
   إعادة نفس الفاتورة التي فازت بالسباق، بلا كسر الطلب الخاسر.

**ما هذا الملف لا يفعله عمداً (خارج نطاق هذا الجزء تحديداً):**
- لا Endpoint فعلي يستدعيه.
- لا استدعاء شبكي لـ`ai-platform`.
- لا نشر حدث Outbox (`CreatePurchaseInvoiceUseCase` الأصلية نفسها لا تنشر
  أي حدث حالياً — الحفاظ على نفس السلوك هنا، لا توسيع غير مطلوب).
- بناء `PurchaseInvoiceCreateRequest` نفسه من مخرجات AI متروك لـ
  `build_purchase_invoice_from_ai_draft.py` (الجزء الأول المُسلَّم سابقاً)
  — هذا الملف يستقبله جاهزاً فقط.
"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from modules.purchasing.application.dto.purchasing_dto import PurchaseInvoiceCreateRequest
from modules.purchasing.application.use_cases.purchase_invoice_use_cases import (
    DOCUMENT_TYPE_PURCHASE_INVOICE,
    _build_lines_and_totals,
)
from modules.purchasing.infrastructure.models.purchasing_models import PurchaseInvoice
from modules.purchasing.infrastructure.repositories.purchasing_repository import (
    PurchaseInvoiceRepository,
)
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext


class CreatePurchaseInvoiceFromAiDraftUseCase:
    """يُنشئ فاتورة شراء من طلب جاهز (مبني مسبقاً بواسطة
    `build_purchase_invoice_request_from_ai_draft`) مع idempotency صريح
    بـ`ai_draft_id` — لا فاتورتين لنفس المسودة، بلا سباق حقيقي."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = PurchaseInvoiceRepository(session)

    async def execute(
        self,
        ctx: TenantContext,
        request: PurchaseInvoiceCreateRequest,
        *,
        ai_draft_id: str,
    ) -> PurchaseInvoice:
        if not ai_draft_id:
            raise ValueError("ai_draft_id مطلوب لهذا الـuse case تحديداً")

        existing = await self._repo.get_by_ai_draft_id(
            company_id=ctx.company_id, source_ai_draft_id=ai_draft_id
        )
        if existing is not None:
            return existing

        numbering = SqlNumberingService(self._session)
        invoice_number = await numbering.next_number(
            company_id=ctx.company_id, document_type=DOCUMENT_TYPE_PURCHASE_INVOICE
        )

        lines, subtotal, total = _build_lines_and_totals(
            request.lines, request.tax_amount, request.discount_amount
        )

        invoice = PurchaseInvoice(
            company_id=ctx.company_id,
            branch_id=request.branch_id,
            supplier_id=request.supplier_id,
            purchase_order_id=None,
            invoice_number=invoice_number,
            status="draft",
            currency_code=request.currency_code,
            subtotal=subtotal,
            tax_amount=request.tax_amount,
            discount_amount=request.discount_amount,
            total_amount=total,
            lines=lines,
            source_ai_draft_id=ai_draft_id,
        )
        self._session.add(invoice)

        try:
            await self._session.commit()
        except IntegrityError:
            # سباق حقيقي: طلبان بنفس ai_draft_id وصلا شبه-متزامنين وكلاهما
            # اجتاز الفحص المبكر أعلاه قبل أن يُنشئ أي منهما السجل — قيد
            # UNIQUE على مستوى القاعدة هو خط الدفاع الحاسم (نفس نمط مهمة #11).
            await self._session.rollback()
            existing = await self._repo.get_by_ai_draft_id(
                company_id=ctx.company_id, source_ai_draft_id=ai_draft_id
            )
            if existing is not None:
                return existing
            raise

        await self._session.refresh(invoice, attribute_names=["lines"])
        return invoice
