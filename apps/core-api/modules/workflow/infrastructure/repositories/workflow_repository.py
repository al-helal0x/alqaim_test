from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.workflow.infrastructure.models.workflow_models import (
    WorkflowDefinition,
    WorkflowInstance,
)


class WorkflowDefinitionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, definition_id: str, *, company_id: str) -> WorkflowDefinition | None:
        stmt = select(WorkflowDefinition).where(
            WorkflowDefinition.id == definition_id,
            WorkflowDefinition.company_id == company_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_company(
        self, *, company_id: str, entity_type: str | None = None
    ) -> list[WorkflowDefinition]:
        stmt = select(WorkflowDefinition).where(
            WorkflowDefinition.company_id == company_id,
            WorkflowDefinition.deleted_at.is_(None),
        )
        if entity_type:
            stmt = stmt.where(WorkflowDefinition.entity_type == entity_type)
        return list((await self._session.execute(stmt)).scalars().all())


class WorkflowInstanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, instance_id: str, *, company_id: str) -> WorkflowInstance | None:
        stmt = select(WorkflowInstance).where(
            WorkflowInstance.id == instance_id, WorkflowInstance.company_id == company_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_company(
        self,
        *,
        company_id: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> list[WorkflowInstance]:
        stmt = select(WorkflowInstance).where(WorkflowInstance.company_id == company_id)
        if entity_type:
            stmt = stmt.where(WorkflowInstance.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(WorkflowInstance.entity_id == entity_id)
        return list((await self._session.execute(stmt)).scalars().all())
