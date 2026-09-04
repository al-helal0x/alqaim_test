from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from modules.inventory.application.dto.inventory_dto import StockBalanceResponse
from modules.inventory.application.use_cases.inventory_use_cases import (
    GetProductBalanceUseCase,
    ListBalancesUseCase,
)
from platform_core.auth_middleware import TenantContext, get_current_context
from platform_core.database import get_db_session
from shared_kernel.pagination import Page, PageParams, page_params

router = APIRouter()


@router.get("", response_model=Page[StockBalanceResponse])
async def list_balances(
    warehouse_id: str | None = Query(default=None),
    params: PageParams = Depends(page_params),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> Page[StockBalanceResponse]:
    balances, total = await ListBalancesUseCase(session).execute(
        ctx, params, warehouse_id=warehouse_id
    )
    return Page(
        items=[StockBalanceResponse.model_validate(b) for b in balances],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{product_id}", response_model=list[StockBalanceResponse])
async def get_product_balance(
    product_id: str,
    warehouse_id: str | None = Query(default=None),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[StockBalanceResponse]:
    balances = await GetProductBalanceUseCase(session).execute(
        ctx, product_id, warehouse_id=warehouse_id
    )
    return [StockBalanceResponse.model_validate(b) for b in balances]
