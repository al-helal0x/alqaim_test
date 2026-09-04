"""جزء صغير وآمن من `TASK-AI-01` (راجع `ALQAIM_V2_MASTER_EXECUTION_PLAN.md`
القسم الخاص بـ`TASK-AI-01`، خطوة التنفيذ #3: "تحويل حقول المسودة لـ
`PurchaseInvoiceCreateRequest` الحالي، استدعاء use case الموجود (لا إعادة
بناء)").

**ما يفعله هذا الملف فقط:** دالة تحويل صرفة (pure mapping) من
`extracted_payload` (حقل في `DraftResponse` القادم من `ai-platform` بعد
اعتماد المسودة بشرياً — انظر `apps/ai-platform/application/dto/ai_dto.py`)
إلى `PurchaseInvoiceCreateRequest` الحالي في هذه الوحدة. لا شبكة، لا
`session`، لا أثر جانبي — قابلة للاختبار بالكامل بمعزل.

**ما لا يفعله عمداً (خارج نطاق هذا الجزء تحديداً):**
- لا Endpoint فعلي (`POST /purchasing/invoices/ai-upload`) — يبقى مفتوحاً.
- لا استدعاء شبكي لـ`ai-platform` لجلب المسودة.
- لا Idempotency بـ`draft_id` (يحتاج تخزين/فحص مسبق قبل الاستدعاء).
- **لا قرار سياسة حول حدّ الثقة (confidence threshold) لمطابقة المنتج/المورد
  تلقائياً.** هذا قرار عمل مفتوح تماماً كقرار backoff formula/`redis_bridge.py`
  المؤجَّلين في `تسليم_TASK-06-05.md` — لا "تنفيذ" تقني وحيد صحيح له بلا
  صاحب قرار. لذلك تستقبل هذه الدالة `supplier_id` ومعرّفات المنتج **جاهزة
  ومحسومة مسبقاً** من طرف الاستدعاء (الـ endpoint المستقبلي)، ولا تقرر هي
  نفسها أي عتبة ثقة.
"""
from decimal import Decimal, InvalidOperation

from modules.purchasing.application.dto.purchasing_dto import (
    PurchaseInvoiceCreateRequest,
    PurchaseOrderLineRequest,
)


class DraftMappingError(ValueError):
    """يُترجَم لـ 422 صريح في الـ endpoint النهائي لـ`TASK-AI-01` — لا إنشاء
    فاتورة جزئية أبداً (مطابقة لمتطلب الخطة الرئيسية حرفياً)."""


def build_purchase_invoice_request_from_ai_draft(
    *,
    extracted_payload: dict,
    branch_id: str,
    supplier_id: str | None,
    product_id_by_line_index: dict[int, str],
) -> PurchaseInvoiceCreateRequest:
    """يحوّل `extracted_payload` لمسودة AI معتمَدة إلى
    `PurchaseInvoiceCreateRequest` جاهز للتمرير إلى use case الفاتورة
    الموجود فعلاً (`purchase_invoice_use_cases.py`) — بلا تعديل عليه.

    `product_id_by_line_index`: قرار مطابقة كل بند (index في `lines`) بمنتج
    فعلي — محسوم مسبقاً من طرف الاستدعاء، وليس هنا (راجع تحذير الملف أعلاه).
    """
    if not branch_id:
        raise DraftMappingError("branch_id مطلوب لإنشاء فاتورة الشراء")

    if not supplier_id:
        raise DraftMappingError(
            "لا يوجد مورد مطابَق بثقة كافية لهذه المسودة — يحتاج مطابقة يدوية "
            "قبل التحويل لفاتورة شراء"
        )

    raw_lines = extracted_payload.get("lines") or []
    if not raw_lines:
        raise DraftMappingError("المسودة لا تحتوي أي بند فاتورة قابل للتحويل")

    lines: list[PurchaseOrderLineRequest] = []
    for index, raw_line in enumerate(raw_lines):
        product_id = product_id_by_line_index.get(index)
        if not product_id:
            description = (raw_line.get("description") or "").strip()
            raise DraftMappingError(
                f"البند رقم {index + 1} ('{description}') بلا منتج مطابَق — "
                "لا إنشاء فاتورة جزئية"
            )

        quantity = raw_line.get("quantity")
        unit_price = raw_line.get("unit_price")
        if quantity is None or unit_price is None:
            raise DraftMappingError(f"البند رقم {index + 1} ناقص الكمية أو السعر")

        try:
            quantity_decimal = Decimal(str(quantity))
            unit_price_decimal = Decimal(str(unit_price))
        except InvalidOperation as exc:
            raise DraftMappingError(
                f"البند رقم {index + 1}: قيمة كمية/سعر غير رقمية صالحة"
            ) from exc

        if quantity_decimal <= 0 or unit_price_decimal < 0:
            raise DraftMappingError(
                f"البند رقم {index + 1}: كمية يجب أن تكون أكبر من صفر وسعر لا يكون سالباً"
            )

        lines.append(
            PurchaseOrderLineRequest(
                product_id=product_id,
                description=(raw_line.get("description") or "").strip() or "بند بلا وصف من AI",
                quantity=quantity_decimal,
                unit_price=unit_price_decimal,
            )
        )

    currency_code = (extracted_payload.get("currency_guess") or "IQD").upper()

    def _decimal_or_zero(value) -> Decimal:
        if value is None:
            return Decimal(0)
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return Decimal(0)

    return PurchaseInvoiceCreateRequest(
        branch_id=branch_id,
        supplier_id=supplier_id,
        currency_code=currency_code,
        tax_amount=_decimal_or_zero(extracted_payload.get("tax_guess")),
        discount_amount=_decimal_or_zero(extracted_payload.get("discount_guess")),
        lines=lines,
    )
