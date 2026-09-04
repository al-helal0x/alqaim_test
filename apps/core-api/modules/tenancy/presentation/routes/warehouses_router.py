from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.tenancy.application.dto.tenancy_dto import WarehouseCreateRequest, WarehouseResponse
from modules.tenancy.application.use_cases.company_use_cases import (
    CreateWarehouseUseCase,
    ListWarehousesUseCase,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "",
    response_model=WarehouseResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("inventory.warehouse.create"))],
)
async def create_warehouse(
    request: WarehouseCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> WarehouseResponse:
    try:
        warehouse = await CreateWarehouseUseCase(session).execute(ctx, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WarehouseResponse.model_validate(warehouse)


@router.get("", response_model=list[WarehouseResponse])
async def list_warehouses(
    branch_id: str | None = None,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[WarehouseResponse]:
    warehouses = await ListWarehousesUseCase(session).execute(ctx, branch_id=branch_id)
    return [WarehouseResponse.model_validate(w) for w in warehouses]
