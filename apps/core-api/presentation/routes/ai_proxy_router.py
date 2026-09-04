"""بوابة موحّدة لخدمة ai-platform المنفصلة (القسم 9.7/6.12) — تسدّ الفجوة
المُكتشَفة: "لا مسار /ai/* داخل core-api، ai-platform معزول خلف منفذه الخاص
(8100) دون بوابة". العميل الخارجي (Web/Mobile) لا يتصل بـ ai-platform مباشرة
أبداً — فقط عبر core-api، الذي يفرض المصادقة/RBAC المحلي الموحَّد أولاً ثم
يمرِّر الطلب.

**قاعدة صارمة (Zero Trust — القسم 6.10):** `company_id`/`corrected_by`/
`reviewer_user_id` تُحقَن هنا من `TenantContext` (المستخرَج من JWT) ولا
تُقبَل أبداً من مُدخلات العميل مباشرة — حتى لو أرسلها العميل، تُتجاهَل.
"""
import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from platform_core.ai_gateway_client import get_ai_platform_client
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission

router = APIRouter()


def _forward_error(exc: httpx.HTTPStatusError) -> None:
    raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)


@router.post(
    "/documents/analyze", status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permission("ai.document.analyze"))],
)
async def analyze_document(
    file: UploadFile = File(...),
    company_currency: str = "IQD",
    ctx: TenantContext = Depends(get_current_context),
) -> dict:
    file_bytes = await file.read()
    async with get_ai_platform_client() as client:
        try:
            response = await client.post(
                "/ai/documents/analyze",
                params={"company_id": ctx.company_id, "company_currency": company_currency},
                files={"file": (file.filename, file_bytes, file.content_type)},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _forward_error(exc)
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"تعذّر الوصول لخدمة ai-platform: {exc}",
            ) from exc
    return response.json()


@router.get("/documents/jobs/{job_id}")
async def get_job_status(job_id: str, ctx: TenantContext = Depends(get_current_context)) -> dict:
    async with get_ai_platform_client() as client:
        try:
            response = await client.get(f"/ai/documents/jobs/{job_id}")
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _forward_error(exc)
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"تعذّر الوصول لخدمة ai-platform: {exc}",
            ) from exc
    return response.json()


@router.get("/drafts/{draft_id}")
async def get_draft(draft_id: str, ctx: TenantContext = Depends(get_current_context)) -> dict:
    async with get_ai_platform_client() as client:
        try:
            response = await client.get(f"/ai/drafts/{draft_id}")
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _forward_error(exc)
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"تعذّر الوصول لخدمة ai-platform: {exc}",
            ) from exc
    return response.json()


@router.post(
    "/drafts/{draft_id}/confirm",
    dependencies=[Depends(require_permission("ai.draft.review"))],
)
async def confirm_draft(draft_id: str, ctx: TenantContext = Depends(get_current_context)) -> dict:
    async with get_ai_platform_client() as client:
        try:
            response = await client.post(
                f"/ai/drafts/{draft_id}/confirm", params={"reviewer_user_id": ctx.user_id}
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _forward_error(exc)
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"تعذّر الوصول لخدمة ai-platform: {exc}",
            ) from exc
    return response.json()


@router.post(
    "/drafts/{draft_id}/reject",
    dependencies=[Depends(require_permission("ai.draft.review"))],
)
async def reject_draft(draft_id: str, ctx: TenantContext = Depends(get_current_context)) -> dict:
    async with get_ai_platform_client() as client:
        try:
            response = await client.post(
                f"/ai/drafts/{draft_id}/reject", params={"reviewer_user_id": ctx.user_id}
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _forward_error(exc)
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"تعذّر الوصول لخدمة ai-platform: {exc}",
            ) from exc
    return response.json()


@router.post(
    "/drafts/{draft_id}/corrections", status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("ai.draft.review"))],
)
async def record_correction(
    draft_id: str, body: dict, ctx: TenantContext = Depends(get_current_context)
) -> dict:
    async with get_ai_platform_client() as client:
        try:
            response = await client.post(
                f"/ai/drafts/{draft_id}/corrections",
                params={"company_id": ctx.company_id, "corrected_by": ctx.user_id},
                json=body,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _forward_error(exc)
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"تعذّر الوصول لخدمة ai-platform: {exc}",
            ) from exc
    return response.json()


@router.get("/entities/{entity_type}/suggestions")
async def get_entity_suggestions(
    entity_type: str,
    text: str = Query(min_length=1),
    ctx: TenantContext = Depends(get_current_context),
) -> list:
    """ملاحظة: هذا الـ endpoint في ai-platform يتوقّع candidates عبر query
    params مباشرة (انظر apps/ai-platform/presentation/routes/entities_router.py)
    — في الاستخدام الفعلي عبر core-api، الأصح أن يجلب core-api المرشحين من
    catalog/partners داخلياً ويمرّرهم، لا أن يطلبهم من العميل الخارجي. تبسيط
    مؤقت هنا: تمرير مباشر بلا مرشحين (يُستكمَل عند دمج catalog/partners
    الفعلي مع هذه البوابة تحديداً)."""
    async with get_ai_platform_client() as client:
        try:
            response = await client.get(
                f"/ai/entities/{entity_type}/suggestions", params={"text": text}
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _forward_error(exc)
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"تعذّر الوصول لخدمة ai-platform: {exc}",
            ) from exc
    return response.json()
