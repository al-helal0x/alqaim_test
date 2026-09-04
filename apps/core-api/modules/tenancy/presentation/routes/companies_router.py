from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from modules.tenancy.application.dto.tenancy_dto import CompanyResponse
from platform_core.auth_middleware import TenantContext, get_current_context
from platform_core.database import get_db_session

router = APIRouter()


@router.get("/current", response_model=CompanyResponse)
async def get_current_company(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> CompanyResponse:
    from sqlalchemy import select

    from modules.tenancy.infrastructure.models.tenancy_models import Company

    stmt = select(Company).where(Company.id == ctx.company_id)
    company = (await session.execute(stmt)).scalar_one()
    return CompanyResponse.model_validate(company)
