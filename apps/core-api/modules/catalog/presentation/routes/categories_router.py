from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.application.dto.catalog_dto import CategoryCreateRequest, CategoryResponse
from modules.catalog.application.use_cases.catalog_use_cases import (
    CreateCategoryUseCase,
    ListCategoriesUseCase,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("catalog.category.create"))],
)
async def create_category(
    request: CategoryCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> CategoryResponse:
    try:
        category = await CreateCategoryUseCase(session).execute(ctx, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CategoryResponse.model_validate(category)


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[CategoryResponse]:
    categories = await ListCategoriesUseCase(session).execute(ctx)
    return [CategoryResponse.model_validate(c) for c in categories]
