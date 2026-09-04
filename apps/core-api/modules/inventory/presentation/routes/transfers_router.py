from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.inventory.application.dto.inventory_dto import (
    StockTransferCreateRequest,
    StockTransferResponse,
)
from modules.inventory.application.ports.inventory_port import InsufficientStockError
from modules.inventory.application.use_cases.inventory_use_cases import CreateStockTransferUseCase
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "",
    response_model=StockTransferResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("inventory.transfer.create"))],
)
async def create_transfer(
    request: StockTransferCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> StockTransferResponse:
    try:
        transfer = await CreateStockTransferUseCase(session).execute(ctx, request)
    except (ValueError, InsufficientStockError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return StockTransferResponse.model_validate(transfer)
