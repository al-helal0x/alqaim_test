"""PKG-B2 — Endpoint مخصَّص لطلب/إنشاء "العميل النقدي" (walk-in).

ملف منفصل تماماً عن partners_router.py عمداً — partners_router.py ممنوع لمسه
(00_TASK_PACKAGE.md § Files ممنوع لمسها: عقد `POST /partners` العام يبقى بلا
أي تغيير في صلاحيته أو سلوكه الحالي). هذا الملف لا يستورد منه ولا يعدّله.

القرار المعماري (متروك لمنفّذ المهمة بحسب نص PKG-B2): endpoint مستقل تحت
`/partners/walk-in` بدل معالجة ضمنية داخل `POST /pos/sales`، لأن:
  - الكاشير يحتاج هذا id *قبل* إتمام البيع (لعرضه/تخزينه محلياً في Flutter،
    راجع PKG-B3: "خزّن هذا id محلياً (cache) لتفادي استدعاء متكرر").
  - يفصل مسؤولية "الحصول على هوية العميل النقدي" عن مسؤولية "إنشاء فاتورة
    بيع" بشكل نظيف (Single Responsibility) — pos_router.py (خارج نطاق هذه
    الحزمة، REFERENCE_ONLY) يبقى بلا حاجة لأي تعديل.

⚠️ تسجيل هذا router: يُفترض تضمينه في تطبيق FastAPI الرئيسي (main.py — خارج
نطاق ملفات هذه الحزمة/OWNED) بنفس prefix المستخدَم لـpartners_router.py:

    app.include_router(partners_router, prefix="/partners", tags=["partners"])
    app.include_router(partners_walkin_router, prefix="/partners", tags=["partners"])

بحيث يصبح المسار الكامل النهائي: `POST /partners/walk-in`.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.partners.application.dto.partner_dto import WalkInPartnerResponse
from modules.partners.application.use_cases.partner_use_cases import (
    GetOrCreateWalkInPartnerUseCase,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "/walk-in",
    response_model=WalkInPartnerResponse,
    status_code=status.HTTP_200_OK,
    # عمداً pos.sale.create وليس partners.partner.create — الكاشير "يطلب"
    # العميل النقدي كجزء من إتمام بيع، لا "ينشئ" عميلاً (00_TASK_PACKAGE.md
    # § PKG-B2). هذا هو صلب الفرق عن `POST /partners` العام.
    dependencies=[Depends(require_permission("pos.sale.create"))],
)
async def get_or_create_walkin_partner(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> WalkInPartnerResponse:
    """Idempotent: أي عدد من الاستدعاءات لنفس الشركة يُعيد دائماً نفس هذا id —
    سواء كان الصف موجوداً مسبقاً، أُنشئ الآن، أو أنشأه طلب متزامن (race).
    لا فشل ظاهر للمستخدم النهائي (الكاشير) في أي من هذه الحالات؛ لذلك 200 لا
    201 — الدلالة "احصل على العميل النقدي" أقرب لِـGET-semantics منها لإنشاء
    مورد جديد بالمعنى التقليدي لِـPOST 201، رغم أن أول استدعاء لكل شركة قد
    يُنشئ الصف فعلياً خلف الكواليس.
    """
    partner = await GetOrCreateWalkInPartnerUseCase(session).execute(ctx)
    return WalkInPartnerResponse.model_validate(partner)
