"""مسار داخلي (خدمة-لخدمة) — قراءة الموردين المعروفين لصالح ai-platform فقط.

منفصل تماماً عن partners_router.py العام:
- مصادقة مختلفة: X-Service-Token عبر get_service_context، وليس get_current_context.
- استجابة مبسّطة (id/name فقط) بدل PartnerResponse الكامل.
- company_id يأتي صراحة من Query (لا يوجد توكن مستخدم لاستخراجه منه هنا) —
  مقبول فقط لأن المتصل موثوق عبر X-Service-Token (راجع get_service_context).

لا تعديل على partners_router.py أو get_current_context. راجع
README_عضو-1.md §4 للعقد الكامل المتفق عليه مع العضو 2 (ai-platform).
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from modules.partners.application.use_cases.partner_use_cases import ListPartnersPageUseCase
from platform_core.auth_middleware import TenantContext, get_service_context
from platform_core.database import get_db_session
from shared_kernel.pagination import PageParams

router = APIRouter()

# حجم الصفحة أثناء التجميع الداخلي الكامل (وليس عقد GET /partners العام).
# ⚠️ افتراض غير مُتحقَّق منه مقابل التعريف الحقيقي لـ PageParams — ملف
# shared_kernel/pagination.py لم يكن ضمن حزمة الملفات المرفقة لهذه المهمة،
# فقط استُدل على أن PageParams(page=.., page_size=..) واستخدام
# params.page/params.page_size (كما في partners_router.py الحالي). يجب
# التأكد من هذا عند الدمج مع الشيفرة الحقيقية (انظر ملاحظات التحقق في
# رسالة التسليم).
_INTERNAL_PAGE_SIZE = 200


class KnownEntityResponse(BaseModel):
    """حمولة مبسّطة — كل ما يحتاجه EntityMatcher في ai-platform (id/name)."""

    id: str
    name: str


async def _collect_all_pages(use_case: ListPartnersPageUseCase, ctx: TenantContext, **filters):
    """يجمع كل صفحات نتيجة use case مُرقَّم إلى قائمة واحدة كاملة — العقد
    الداخلي يعيد القائمة الكاملة دفعة واحدة (لا ترقيم صفحات في الاستجابة)،
    بعكس GET /partners العام.
    """
    collected = []
    page = 1
    while True:
        params = PageParams(page=page, page_size=_INTERNAL_PAGE_SIZE)
        items, total = await use_case.execute(ctx, params, **filters)
        collected.extend(items)
        if not items or len(collected) >= total:
            break
        page += 1
    return collected


@router.get(
    "/internal/partners/known-suppliers",
    response_model=list[KnownEntityResponse],
    include_in_schema=False,  # لا يظهر في أي مستند OpenAPI عام موجَّه للعميل النهائي
    dependencies=[Depends(get_service_context)],
)
async def list_known_suppliers(
    company_id: str = Query(..., description="مطلوب صراحة — لا يوجد توكن مستخدم هنا (X-Service-Token فقط)"),
    session: AsyncSession = Depends(get_db_session),
) -> list[KnownEntityResponse]:
    # عزل tenant هنا يعتمد على company_id القادم من Query صراحةً (وليس من
    # توكن موقَّع) — هذا مقبول فقط ضمن حدود هذا المسار المحمي بـ
    # get_service_context (متصل خدمة داخلية موثوقة)، ولا يُستخدم هذا النمط
    # أبداً على أي مسار محمي بـget_current_context. القرار موثَّق في
    # README_عضو-1.md §3.2.
    ctx = TenantContext(company_id=company_id, user_id="service:ai-platform")
    partners = await _collect_all_pages(
        ListPartnersPageUseCase(session), ctx, partner_type="supplier"
    )
    return [KnownEntityResponse(id=str(p.id), name=p.name) for p in partners]
