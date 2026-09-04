from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.inventory.application.dto.inventory_dto import (
    RecordMovementRequest,
    StockMovementResponse,
)
from modules.inventory.application.ports.inventory_port import InsufficientStockError
from modules.inventory.application.use_cases.inventory_use_cases import (
    ListMovementsUseCase,
    RecordMovementUseCase,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session
from shared_kernel.pagination import Page, PageParams, page_params

router = APIRouter()


@router.post(
    "",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("inventory.movement.create"))],
)
async def record_movement(
    request: RecordMovementRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> StockMovementResponse:
    try:
        movement = await RecordMovementUseCase(session).execute(ctx, request)
    except (ValueError, InsufficientStockError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return StockMovementResponse.model_validate(movement)


@router.get("", response_model=Page[StockMovementResponse])
async def list_movements(
    product_id: str | None = Query(default=None),
    warehouse_id: str | None = Query(default=None),
    params: PageParams = Depends(page_params),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> Page[StockMovementResponse]:
    movements, total = await ListMovementsUseCase(session).execute(
        ctx, params, product_id=product_id, warehouse_id=warehouse_id
    )
    return Page(
        items=[StockMovementResponse.model_validate(m) for m in movements],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )
