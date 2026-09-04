from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.data_migration.application.dto.data_migration_dto import (
    CreateImportJobRequest,
    ImportJobResponse,
    TableDescriptorResponse,
)
from modules.data_migration.application.use_cases.create_import_job import (
    CreateImportJobUseCase,
)
from modules.data_migration.application.use_cases.discover_source_schema import (
    DiscoverSourceSchemaUseCase,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


def _build_connector(source_type: str, connection_ref: str):
    """Factory بسيطة: source_type → SourceConnector. هذا هو المكان الوحيد في
    الموديول الذي "يعرف" أسماء الموصلات المحدَّدة — use_cases لا تعرفها.
    TODO (TASK-MIG-02): استيراد فعلي لـ MssqlConnector/CsvExcelConnector هنا."""
    raise NotImplementedError


@router.post(
    "",
    response_model=ImportJobResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("data_migration.job.manage"))],
)
async def create_import_job(
    request: CreateImportJobRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> ImportJobResponse:
    job = await CreateImportJobUseCase(session).execute(ctx, request)
    return ImportJobResponse.model_validate(job)


@router.post(
    "/{job_id}/discover",
    response_model=list[TableDescriptorResponse],
    dependencies=[Depends(require_permission("data_migration.job.manage"))],
)
async def discover_source_schema(
    job_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[TableDescriptorResponse]:
    # TODO (TASK-MIG-02): جلب job.source_type/connection_ref فعلياً ثم بناء
    # connector عبر _build_connector قبل استدعاء use case — محذوف مؤقتاً هنا
    # لإبقاء هذا الملف قابلاً للاستيراد (import) بلا أخطاء أثناء البناء التدريجي.
    try:
        connector = _build_connector("", "")
        tables = await DiscoverSourceSchemaUseCase(session, connector).execute(ctx, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [TableDescriptorResponse(**t.__dict__) for t in tables]


# TODO (TASK-MIG-03 وما بعدها): إضافة نقاط النهاية التالية بنفس النمط:
#   POST /{job_id}/mapping           → SetMappingRequest → mapped
#   POST /{job_id}/preview           → PreviewResultResponse → previewed
#   POST /{job_id}/commit            → CommitResultResponse → committing/completed
#   GET  /{job_id}                   → ImportJobResponse
#   GET  /{job_id}/errors            → قائمة ImportRowError (بحد أقصى، مع pagination)
#   GET  /export?entity=...&format=xlsx|pdf
