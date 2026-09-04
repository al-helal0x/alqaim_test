from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.data_migration.infrastructure.models.data_migration_models import (
    ImportBatch,
    ImportJob,
    ImportRowError,
)


class ImportJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, job_id: str, *, company_id: str) -> ImportJob | None:
        stmt = select(ImportJob).where(
            ImportJob.id == job_id, ImportJob.company_id == company_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_company(self, *, company_id: str) -> list[ImportJob]:
        stmt = select(ImportJob).where(
            ImportJob.company_id == company_id, ImportJob.deleted_at.is_(None)
        )
        return list((await self._session.execute(stmt)).scalars().all())


class ImportBatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_job(self, *, job_id: str) -> list[ImportBatch]:
        stmt = select(ImportBatch).where(ImportBatch.job_id == job_id)
        return list((await self._session.execute(stmt)).scalars().all())


class ImportRowErrorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_job(self, *, job_id: str, limit: int = 100) -> list[ImportRowError]:
        stmt = (
            select(ImportRowError)
            .where(ImportRowError.job_id == job_id)
            .order_by(ImportRowError.row_number)
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())
