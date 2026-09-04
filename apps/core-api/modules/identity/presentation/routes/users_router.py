from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.identity.application.dto.identity_dto import CreateUserRequest, UserResponse
from modules.identity.application.use_cases.user_use_cases import CreateUserUseCase
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("identity.user.create"))],
)
async def create_user(
    request: CreateUserRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    try:
        user = await CreateUserUseCase(session).execute(ctx, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse)
async def get_me(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    from modules.identity.infrastructure.repositories.user_repository import UserRepository

    user = await UserRepository(session).get_by_id(ctx.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مستخدم غير موجود")
    return UserResponse.model_validate(user)
