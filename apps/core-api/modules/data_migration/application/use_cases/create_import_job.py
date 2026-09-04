from sqlalchemy.ext.asyncio import AsyncSession

from modules.data_migration.application.dto.data_migration_dto import CreateImportJobRequest
from modules.data_migration.infrastructure.models.data_migration_models import ImportJob
from platform_core.auth_middleware import TenantContext


class CreateImportJobUseCase:
    """المرحلة 1 من خط السير (§4.3): تسجيل مصدر فقط — لا اتصال فعلي ولا قراءة
    بيانات بعد. نفس نمط CreateWebhookSubscriptionUseCase في modules.integrations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: CreateImportJobRequest) -> ImportJob:
        job = ImportJob(
            company_id=ctx.company_id,
            source_type=request.source_type.value,
            status="connected",
            connection_ref=request.connection_ref,
        )
        self._session.add(job)
        await self._session.commit()
        await self._session.refresh(job)
        return job
