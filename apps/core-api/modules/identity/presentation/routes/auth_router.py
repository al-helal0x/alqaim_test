from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.identity.application.dto.identity_dto import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterCompanyRequest,
    TokenResponse,
)
from modules.identity.application.use_cases.auth_use_cases import (
    AccountLockedError,
    LoginUseCase,
    LogoutUseCase,
    RefreshTokenUseCase,
    RegisterCompanyUseCase,
)
from platform_core.database import get_db_session

router = APIRouter()


@router.post("/register-company", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_company(
    request: RegisterCompanyRequest, session: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    try:
        return await RegisterCompanyUseCase(session).execute(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    # عنوان IP يُستخرَج من الاتصال نفسه (server-side) وليس من الـ Body — نفس
    # مبدأ "لا يُقبل company_id من الـ Body" في auth_middleware.py، مطبَّق هنا
    # على معيار Rate Limiting كي لا يستطيع طالب الطلب انتحال IP مختلف لتفادي القفل.
    ip_address = http_request.client.host if http_request.client else None
    try:
        return await LoginUseCase(session).execute(request, ip_address=ip_address)
    except AccountLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: RefreshRequest, session: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    try:
        return await RefreshTokenUseCase(session).execute(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: LogoutRequest, session: AsyncSession = Depends(get_db_session)
) -> None:
    await LogoutUseCase(session).execute(request)
