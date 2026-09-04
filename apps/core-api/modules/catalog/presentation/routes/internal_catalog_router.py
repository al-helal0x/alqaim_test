"""مسار داخلي (خدمة-لخدمة) — قراءة المنتجات المعروفة لصالح ai-platform فقط.

نفس مبدأ internal_partners_router.py (راجعه للتفاصيل الكاملة للقرار):
X-Service-Token عبر get_service_context، استجابة مبسّطة id/name، company_id
من Query صراحة. لا تعديل على products_router.py أو get_current_context.
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.application.use_cases.catalog_use_cases import ListProductsUseCase
from platform_core.auth_middleware import TenantContext, get_service_context
from platform_core.database import get_db_session

router = APIRouter()


class KnownEntityResponse(BaseModel):
    """حمولة مبسّطة — كل ما يحتاجه EntityMatcher في ai-platform (id/name)."""

    id: str
    name: str


@router.get(
    "/internal/catalog/known-products",
    response_model=list[KnownEntityResponse],
    include_in_schema=False,  # لا يظهر في أي مستند OpenAPI عام موجَّه للعميل النهائي
    dependencies=[Depends(get_service_context)],
)
async def list_known_products(
    company_id: str = Query(..., description="مطلوب صراحة — لا يوجد توكن مستخدم هنا (X-Service-Token فقط)"),
    session: AsyncSession = Depends(get_db_session),
) -> list[KnownEntityResponse]:
    # نفس قرار عزل tenant عبر company_id من Query الموضَّح في
    # internal_partners_router.py — محصور بمسار محمي بـget_service_context فقط.
    ctx = TenantContext(company_id=company_id, user_id="service:ai-platform")
    # ListProductsUseCase(ctx) بلا ترقيم صفحات — نفس النمط المستخدم فعلياً في
    # GET /products/export (products_router.py) — يعيد كل منتجات الشركة دفعة
    # واحدة. لا افتراض إضافي هنا (بعكس partners) لأن هذا الاستخدام موجود
    # ومُتحقَّق منه فعلاً في الكود الحالي.
    products = await ListProductsUseCase(session).execute(ctx)
    return [KnownEntityResponse(id=str(p.id), name=p.name) for p in products]
