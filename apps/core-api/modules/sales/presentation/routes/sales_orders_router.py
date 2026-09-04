from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.infrastructure.repositories.product_lookup_repository import SqlProductLookup
from modules.partners.infrastructure.repositories.partner_lookup_repository import SqlPartnerLookup
from modules.sales.application.dto.sales_dto import (
    SalesOrderCreateRequest,
    SalesOrderResponse,
)
from modules.sales.application.use_cases.sales_use_cases import (
    CreateSalesOrderUseCase,
    ListSalesOrdersUseCase,
    PartnerNotFoundError,
    ProductNotFoundError,
    QuotationNotAcceptedError,
    UpdateSalesOrderStatusUseCase,
)
from modules.sales.domain.rules import SalesOrderStatus
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session
from shared_kernel.pagination import Page, PageParams, page_params

router = APIRouter()


@router.post(
    "",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("sales.order.create"))],
)
async def create_sales_order(
    request: SalesOrderCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> SalesOrderResponse:
    use_case = CreateSalesOrderUseCase(
        session, SqlPartnerLookup(session), SqlProductLookup(session), SqlNumberingService(session)
    )
    try:
        order = await use_case.execute(ctx, request)
    except (PartnerNotFoundError, ProductNotFoundError, QuotationNotAcceptedError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SalesOrderResponse.model_validate(order)


@router.get("", response_model=Page[SalesOrderResponse])
async def list_sales_orders(
    params: PageParams = Depends(page_params),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> Page[SalesOrderResponse]:
    orders, total = await ListSalesOrdersUseCase(session).execute(ctx, params)
    return Page(
        items=[SalesOrderResponse.model_validate(o) for o in orders],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post(
    "/{order_id}/confirm",
    response_model=SalesOrderResponse,
    dependencies=[Depends(require_permission("sales.order.update"))],
)
async def confirm_sales_order(
    order_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> SalesOrderResponse:
    try:
        order = await UpdateSalesOrderStatusUseCase(session).execute(
            ctx, order_id, SalesOrderStatus.CONFIRMED
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SalesOrderResponse.model_validate(order)


@router.post(
    "/{order_id}/cancel",
    response_model=SalesOrderResponse,
    dependencies=[Depends(require_permission("sales.order.update"))],
)
async def cancel_sales_order(
    order_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> SalesOrderResponse:
    try:
        order = await UpdateSalesOrderStatusUseCase(session).execute(
            ctx, order_id, SalesOrderStatus.CANCELLED
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SalesOrderResponse.model_validate(order)
