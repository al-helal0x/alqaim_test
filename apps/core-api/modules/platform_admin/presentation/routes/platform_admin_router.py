from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.platform_admin.application.dto.platform_admin_dto import (
    CompanyAdminSummaryResponse,
)
from modules.platform_admin.application.use_cases.platform_admin_use_cases import (
    ListAllCompaniesUseCase,
    SetCompanyActiveStatusUseCase,
)
from platform_core.auth_middleware import require_permission
from platform_core.database import get_db_session

router = APIRouter()

_REQUIRE_PLATFORM_ADMIN = Depends(require_permission("platform_admin.company.manage"))


@router.get(
    "/companies",
    response_model=list[CompanyAdminSummaryResponse],
    dependencies=[_REQUIRE_PLATFORM_ADMIN],
)
async def list_all_companies(
    session: AsyncSession = Depends(get_db_session),
) -> list[CompanyAdminSummaryResponse]:
    """يسرد **كل** الشركات على المنصة بغض النظر عن هوية طالِب الطلب —
    الاستثناء المتعمَّد الوحيد لعزل Multi-Tenancy، انظر التوثيق في
    application/use_cases/platform_admin_use_cases.py."""
    rows = await ListAllCompaniesUseCase().execute(session)
    return [
        CompanyAdminSummaryResponse(
            id=str(company.id),
            name=company.name,
            default_currency=company.default_currency,
            is_active=company.is_active,
            branch_count=branch_count,
            created_at=company.created_at,
        )
        for company, branch_count in rows
    ]


@router.post(
    "/companies/{company_id}/suspend",
    response_model=CompanyAdminSummaryResponse,
    dependencies=[_REQUIRE_PLATFORM_ADMIN],
)
async def suspend_company(
    company_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> CompanyAdminSummaryResponse:
    try:
        company = await SetCompanyActiveStatusUseCase().execute(
            session, company_id, is_active=False
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CompanyAdminSummaryResponse(
        id=str(company.id), name=company.name, default_currency=company.default_currency,
        is_active=company.is_active, branch_count=0, created_at=company.created_at,
    )


@router.post(
    "/companies/{company_id}/activate",
    response_model=CompanyAdminSummaryResponse,
    dependencies=[_REQUIRE_PLATFORM_ADMIN],
)
async def activate_company(
    company_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> CompanyAdminSummaryResponse:
    try:
        company = await SetCompanyActiveStatusUseCase().execute(
            session, company_id, is_active=True
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CompanyAdminSummaryResponse(
        id=str(company.id), name=company.name, default_currency=company.default_currency,
        is_active=company.is_active, branch_count=0, created_at=company.created_at,
    )
