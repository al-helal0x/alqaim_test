from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.infrastructure.repositories.product_lookup_repository import SqlProductLookup
from modules.partners.infrastructure.repositories.partner_lookup_repository import SqlPartnerLookup
from modules.sales.application.dto.sales_dto import (
    QuotationCreateRequest,
    QuotationResponse,
    QuotationStatusUpdateRequest,
)
from modules.sales.application.use_cases.sales_use_cases import (
    CreateQuotationUseCase,
    GetQuotationUseCase,
    ListQuotationsUseCase,
    PartnerNotFoundError,
    ProductNotFoundError,
    UpdateQuotationStatusUseCase,
)
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session
from shared_kernel.pagination import Page, PageParams, page_params

router = APIRouter()


@router.post(
    "",
    response_model=QuotationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("sales.quotation.create"))],
)
async def create_quotation(
    request: QuotationCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> QuotationResponse:
    use_case = CreateQuotationUseCase(
        session, SqlPartnerLookup(session), SqlProductLookup(session), SqlNumberingService(session)
    )
    try:
        quotation = await use_case.execute(ctx, request)
    except (PartnerNotFoundError, ProductNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return QuotationResponse.model_validate(quotation)


@router.get("", response_model=Page[QuotationResponse])
async def list_quotations(
    params: PageParams = Depends(page_params),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> Page[QuotationResponse]:
    quotations, total = await ListQuotationsUseCase(session).execute(ctx, params)
    return Page(
        items=[QuotationResponse.model_validate(q) for q in quotations],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{quotation_id}", response_model=QuotationResponse)
async def get_quotation(
    quotation_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> QuotationResponse:
    try:
        quotation = await GetQuotationUseCase(session).execute(ctx, quotation_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return QuotationResponse.model_validate(quotation)


@router.post(
    "/{quotation_id}/status",
    response_model=QuotationResponse,
    dependencies=[Depends(require_permission("sales.quotation.update"))],
)
async def update_quotation_status(
    quotation_id: str,
    request: QuotationStatusUpdateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> QuotationResponse:
    try:
        quotation = await UpdateQuotationStatusUseCase(session).execute(
            ctx, quotation_id, request.status
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return QuotationResponse.model_validate(quotation)
