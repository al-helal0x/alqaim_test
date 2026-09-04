from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.application.dto.catalog_dto import (
    PriceListCreateRequest,
    PriceListItemCreateRequest,
    PriceListItemResponse,
    PriceListResponse,
)
from modules.catalog.application.use_cases.catalog_use_cases import (
    AddPriceListItemUseCase,
    CreatePriceListUseCase,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "",
    response_model=PriceListResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("catalog.price_list.create"))],
)
async def create_price_list(
    request: PriceListCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PriceListResponse:
    price_list = await CreatePriceListUseCase(session).execute(ctx, request)
    return PriceListResponse.model_validate(price_list)


@router.post(
    "/{price_list_id}/items",
    response_model=PriceListItemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("catalog.price_list.update"))],
)
async def add_price_list_item(
    price_list_id: str,
    request: PriceListItemCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PriceListItemResponse:
    try:
        item = await AddPriceListItemUseCase(session).execute(ctx, price_list_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PriceListItemResponse.model_validate(item)
