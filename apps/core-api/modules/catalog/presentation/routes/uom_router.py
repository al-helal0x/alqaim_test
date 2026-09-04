from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.application.dto.catalog_dto import UomCreateRequest, UomResponse
from modules.catalog.application.use_cases.catalog_use_cases import (
    CreateUomUseCase,
    ListUomsUseCase,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "",
    response_model=UomResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("catalog.uom.create"))],
)
async def create_uom(
    request: UomCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> UomResponse:
    try:
        uom = await CreateUomUseCase(session).execute(ctx, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UomResponse.model_validate(uom)


@router.get("", response_model=list[UomResponse])
async def list_uoms(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[UomResponse]:
    uoms = await ListUomsUseCase(session).execute(ctx)
    return [UomResponse.model_validate(u) for u in uoms]
