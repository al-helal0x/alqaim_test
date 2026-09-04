from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from modules.tenancy.application.dto.tenancy_dto import NextNumberResponse
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext, get_current_context
from platform_core.database import get_db_session

router = APIRouter()


@router.post("/{document_type}/next", response_model=NextNumberResponse)
async def next_number(
    document_type: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> NextNumberResponse:
    """يُستهلك داخلياً من الوحدات الأخرى (sales/purchasing/accounting...) وليس
    عادة من الواجهة مباشرة — معروض هنا كـ endpoint اختباري لهذا الـ Port."""
    service = SqlNumberingService(session)
    number = await service.next_number(company_id=ctx.company_id, document_type=document_type)
    return NextNumberResponse(document_type=document_type, number=number)
