"""جزء آمن ثالث من `TASK-AI-01` — تجميع (orchestration) الجزأين السابقين
(`build_purchase_invoice_from_ai_draft.py` + `create_purchase_invoice_from_ai_draft_use_case.py`)
فوق مسودة **مُستقبَلة جاهزة** (dict بشكل `DraftResponse` من `ai-platform` —
`id`, `status`, `extracted_payload`, `matched_supplier_id`). لا يجلب المسودة
بنفسه (ذلك في الـ endpoint فقط، يستخدم `platform_core.ai_gateway_client`
الموجود فعلاً — راجع تحذير النطاق أدناه).

**لماذا دالة منفصلة عن الـ endpoint:** لتبقى قابلة للاختبار الكامل محلياً
بلا شبكة، بنفس فلسفة بقية اختبارات هذا المشروع (`db_session` على SQLite في
الذاكرة). استدعاء `ai-platform` الفعلي (خارج نطاق هذا الجزء) موجود ومُختبَر
مسبقاً وبمعزل في `platform_core/ai_gateway_client.py` +
`presentation/routes/ai_proxy_router.py` — **تصحيح لملاحظة سابقة في بطاقات
تسليم `TASK-AI-01` الأولى/الثانية**: ذُكِر وقتها أن "قرارات البنية التحتية
(Base URL، مصادقة بين الخدمتين) غير محسومة" — تبيَّن عند الفحص الفعلي هنا
أن هذا **غير دقيق**: البوابة موجودة ومُطبَّقة بالفعل (`ai_proxy_router.py`)
وتُستخدَم لمسارات أخرى مماثلة (`GET /ai/drafts/{draft_id}` تحديداً).
التصحيح مذكور صراحة بدل السكوت عنه.

## قرار عتبة الثقة لمطابقة المنتج — إعادة استخدام قرار موجود، لا قرار جديد

بطاقتا التسليم السابقتان ذكرتا أن عتبة الثقة قرار سياسة مؤجَّل بلا صاحب
قرار. **هذا لا يزال صحيحاً كسياسة عامة رسمية**، لكن هذا الجزء يتجنّب
اختراع رقم جديد: يُعيد استخدام **نفس** الرقم `0.92` المستخدَم فعلياً وحرفياً
في `apps/ai-platform/application/use_cases/process_document_pipeline.py`
لمطابقة المورد تلقائياً (`if supplier_matches[0].confidence >= 0.92`).
تطبيقه هنا على مطابقة المنتج أيضاً هو **اتساق مع سابقة قائمة فعلاً في
نفس الكودبيس**، وليس قراراً معمارياً جديداً من طرف واحد — لكنه يبقى
تقنياً غير موثَّق كسياسة رسمية معلَنة، لذا هذا التوضيح مكتوب صراحة هنا.

## فجوة اكتُشفت أثناء الفحص (توثيق، لا افتراض)

`extracted_payload["line_matches"]` تُبنى في `process_document_pipeline.py`
**فقط إن كان `known_products` غير فارغ** عند وقت معالجة المستند — إن كان
فارغاً، `line_matches` تبقى `[]` بالكامل، **بينما `lines` تبقى ممتلئة
بكل البنود المُستخرَجة**. أي: لا ضمان أن `len(line_matches) == len(lines)`،
ولا ضمان محاذاة index-بـ-index بينهما في هذه الحالة. القرار المتَّبع هنا
**متحفِّظ عمداً**: لو لم يتطابق الطولان، تُعامَل كل البنود كبلا مطابقة
منتج إطلاقاً (بدل تخمين محاذاة قد تكون خاطئة) — يؤدي هذا لرفض 422 صريح
بدل فاتورة خاطئة صامتة، وهو نفس مبدأ "لا إنشاء جزئي" المُلزَم في الخطة.
"""
from modules.purchasing.application.use_cases.build_purchase_invoice_from_ai_draft import (
    DraftMappingError,
    build_purchase_invoice_request_from_ai_draft,
)
from modules.purchasing.application.use_cases.create_purchase_invoice_from_ai_draft_use_case import (
    CreatePurchaseInvoiceFromAiDraftUseCase,
)
from modules.purchasing.infrastructure.models.purchasing_models import PurchaseInvoice
from platform_core.auth_middleware import TenantContext

# راجع التوثيق أعلى الملف — نفس الرقم المستخدَم فعلياً في ai-platform
# لمطابقة المورد، مُعاد استخدامه هنا للمنتج باتساق، وليس قراراً جديداً.
_REUSED_AUTO_MATCH_CONFIDENCE_THRESHOLD = 0.92


def _resolve_product_id_by_line_index(extracted_payload: dict) -> dict[int, str]:
    lines = extracted_payload.get("lines") or []
    line_matches = extracted_payload.get("line_matches") or []

    if len(line_matches) != len(lines):
        # فجوة محاذاة مكتشَفة (راجع التوثيق أعلى الملف) — لا تخمين، لا مطابقات.
        return {}

    resolved: dict[int, str] = {}
    for index, entry in enumerate(line_matches):
        candidates = entry.get("matches") or []
        if not candidates:
            continue
        top = candidates[0]
        if top.get("confidence", 0) >= _REUSED_AUTO_MATCH_CONFIDENCE_THRESHOLD:
            entity_id = top.get("entity_id")
            if entity_id:
                resolved[index] = entity_id
    return resolved


async def create_purchase_invoice_from_approved_draft(
    session,
    ctx: TenantContext,
    *,
    draft: dict,
    branch_id: str,
) -> PurchaseInvoice:
    """`draft`: dict بشكل `DraftResponse` (`id`, `status`, `extracted_payload`,
    `matched_supplier_id`) — مُستقبَل جاهزاً من طرف المُستدعي (الـ endpoint).

    يرفع `DraftMappingError` (422 صريح في الـ endpoint) لأي حالة غير صالحة
    — بلا إنشاء فاتورة جزئية أبداً، مطابقةً لمتطلب الخطة الرئيسية حرفياً.
    """
    status_value = draft.get("status")
    if status_value != "approved":
        raise DraftMappingError(
            f"لا يمكن تحويل مسودة بحالة '{status_value}' — يجب اعتمادها أولاً عبر ai-platform"
        )

    extracted_payload = draft.get("extracted_payload") or {}
    matched_supplier_id = draft.get("matched_supplier_id")
    product_id_by_line_index = _resolve_product_id_by_line_index(extracted_payload)

    request = build_purchase_invoice_request_from_ai_draft(
        extracted_payload=extracted_payload,
        branch_id=branch_id,
        supplier_id=matched_supplier_id,
        product_id_by_line_index=product_id_by_line_index,
    )

    draft_id = draft.get("id")
    return await CreatePurchaseInvoiceFromAiDraftUseCase(session).execute(
        ctx, request, ai_draft_id=draft_id
    )
