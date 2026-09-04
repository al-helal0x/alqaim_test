from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.tenancy.application.dto.tenancy_dto import BranchCreateRequest, BranchResponse
from modules.tenancy.application.use_cases.company_use_cases import (
    CreateBranchUseCase,
    ListBranchesUseCase,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("tenancy.branch.create"))],
)
async def create_branch(
    request: BranchCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> BranchResponse:
    branch = await CreateBranchUseCase(session).execute(ctx, request)
    return BranchResponse.model_validate(branch)


@router.get("", response_model=list[BranchResponse])
async def list_branches(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[BranchResponse]:
    branches = await ListBranchesUseCase(session).execute(ctx)
    return [BranchResponse.model_validate(b) for b in branches]
