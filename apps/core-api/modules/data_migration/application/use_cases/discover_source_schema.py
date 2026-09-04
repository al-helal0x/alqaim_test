from sqlalchemy.ext.asyncio import AsyncSession

from modules.data_migration.application.ports.source_connector import SourceConnector
from modules.data_migration.domain.entities.import_job import TableDescriptor
from modules.data_migration.domain.rules.import_status_transitions import assert_valid_transition
from modules.data_migration.domain.value_objects.enums import ImportStatus
from modules.data_migration.infrastructure.repositories.data_migration_repository import (
    ImportJobRepository,
)
from platform_core.auth_middleware import TenantContext


class DiscoverSourceSchemaUseCase:
    """المرحلة 2 (§4.3). يستقبل connector جاهزاً (يُبنى في presentation عبر
    factory بسيطة حسب source_type — راجع TASK-MIG-02) بدل بنائه هنا، حتى يبقى
    use case بلا أي معرفة بأي مكتبة اتصال محدَّدة (pyodbc/pandas...)."""

    def __init__(self, session: AsyncSession, connector: SourceConnector) -> None:
        self._session = session
        self._connector = connector

    async def execute(self, ctx: TenantContext, job_id: str) -> list[TableDescriptor]:
        job = await ImportJobRepository(self._session).get_by_id(job_id, company_id=ctx.company_id)
        if job is None:
            raise ValueError("مهمة الاستيراد غير موجودة")

        assert_valid_transition(ImportStatus(job.status), ImportStatus.DISCOVERED)

        try:
            tables = await self._connector.discover_schema()
        finally:
            await self._connector.close()  # يُغلَق دائماً حتى عند فشل الاكتشاف

        job.status = ImportStatus.DISCOVERED.value
        await self._session.commit()
        return tables
