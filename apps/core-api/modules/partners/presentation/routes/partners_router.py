from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.partners.application.dto.partner_dto import (
    PartnerCreateRequest,
    PartnerResponse,
    PartnerUpdateRequest,
)
from modules.partners.application.use_cases.partner_use_cases import (
    CreatePartnerUseCase,
    GetPartnerUseCase,
    ListPartnersPageUseCase,
    PartnerNotFoundError,
    UpdatePartnerUseCase,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session
from shared_kernel.pagination import Page, PageParams, page_params

router = APIRouter()


@router.post(
    "",
    response_model=PartnerResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("partners.partner.create"))],
)
async def create_partner(
    request: PartnerCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PartnerResponse:
    try:
        partner = await CreatePartnerUseCase(session).execute(ctx, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PartnerResponse.model_validate(partner)


@router.get("", response_model=Page[PartnerResponse])
async def list_partners(
    partner_type: str | None = Query(default=None),
    params: PageParams = Depends(page_params),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> Page[PartnerResponse]:
    partners, total = await ListPartnersPageUseCase(session).execute(
        ctx, params, partner_type=partner_type
    )
    return Page(
        items=[PartnerResponse.model_validate(p) for p in partners],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{partner_id}", response_model=PartnerResponse)
async def get_partner(
    partner_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PartnerResponse:
    try:
        partner = await GetPartnerUseCase(session).execute(ctx, partner_id)
    except PartnerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PartnerResponse.model_validate(partner)


@router.patch(
    "/{partner_id}",
    response_model=PartnerResponse,
    dependencies=[Depends(require_permission("partners.partner.update"))],
)
async def update_partner(
    partner_id: str,
    request: PartnerUpdateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PartnerResponse:
    try:
        partner = await UpdatePartnerUseCase(session).execute(ctx, partner_id, request)
    except PartnerNotFoundError as exc:
        # ⚠️ إصلاح حقيقي: قبله، هذه الحالة (نفس فحص العزل الذي يعمل بشكل
        # صحيح فعلاً في GetPartnerUseCase) كانت تسقط في except ValueError
        # أدناه وتُرجع 400 بدل 404 — تناقض اصطلاحي مع GET المجاور، اكتُشِف
        # فقط بتشغيل test_idor_partners.py::test_partner_update_is_isolated
        # حقيقياً هنا. لا علاقة له بتسريب بيانات (العزل نفسه سليم).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PartnerResponse.model_validate(partner)
