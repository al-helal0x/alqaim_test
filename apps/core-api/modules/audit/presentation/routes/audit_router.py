"""Router لموديول audit — GET فقط. لا POST/DELETE: السجل يُكتَب حصراً عبر
Event Bus (`RecordAuditLogUseCase`)، لا عبر API مباشرة — وإلا فقد سجل
التدقيق مصداقيته كمصدر موثوق."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from modules.audit.application.dto.audit_dto import AuditLogEntryResponse
from modules.audit.application.use_cases.audit_use_cases import ListAuditLogsUseCase
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session
from shared_kernel.pagination import Page, PageParams, page_params

router = APIRouter()


@router.get(
    "/logs",
    response_model=Page[AuditLogEntryResponse],
    dependencies=[Depends(require_permission("audit.log.view"))],
)
async def list_audit_logs(
    event_name: str | None = Query(default=None),
    params: PageParams = Depends(page_params),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> Page[AuditLogEntryResponse]:
    rows, total = await ListAuditLogsUseCase(session).execute(ctx, event_name, params)
    return Page[AuditLogEntryResponse](
        items=[AuditLogEntryResponse.model_validate(row) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )
