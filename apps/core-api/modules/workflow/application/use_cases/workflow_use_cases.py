"""Use Cases لموديول workflow (Approval Engine العام — العضو 12).

نطاق هذه الجولة محدود عمداً لمحرك حالات عام قابل للربط بأي كيان، بلا أي
اشتراك في Event Bus (workflow لا تستهلك أحداث الوحدات الأخرى هذه الجولة —
راجع README)."""
from sqlalchemy.ext.asyncio import AsyncSession

from modules.workflow.application.dto.workflow_dto import (
    WorkflowDefinitionCreateRequest,
    WorkflowInstanceStartRequest,
)
from modules.workflow.infrastructure.models.workflow_models import (
    WorkflowDefinition,
    WorkflowInstance,
)
from modules.workflow.infrastructure.repositories.workflow_repository import (
    WorkflowDefinitionRepository,
    WorkflowInstanceRepository,
)
from platform_core.auth_middleware import TenantContext
from shared_kernel.db_base import utcnow


class CreateWorkflowDefinitionUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, request: WorkflowDefinitionCreateRequest
    ) -> WorkflowDefinition:
        definition = WorkflowDefinition(
            company_id=ctx.company_id,
            entity_type=request.entity_type,
            name=request.name,
            states=request.states,
            transitions=[t.model_dump(by_alias=True) for t in request.transitions],
        )
        self._session.add(definition)
        await self._session.commit()
        await self._session.refresh(definition)
        return definition


class ListWorkflowDefinitionsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, entity_type: str | None
    ) -> list[WorkflowDefinition]:
        return await WorkflowDefinitionRepository(self._session).list_for_company(
            company_id=ctx.company_id, entity_type=entity_type
        )


class StartWorkflowInstanceUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, request: WorkflowInstanceStartRequest
    ) -> WorkflowInstance:
        definition = await WorkflowDefinitionRepository(self._session).get_by_id(
            request.definition_id, company_id=ctx.company_id
        )
        if definition is None:
            raise ValueError("تعريف سير العمل غير موجود")
        if not definition.is_active:
            raise ValueError("تعريف سير العمل غير مُفعَّل")
        if not definition.states:
            raise ValueError("تعريف سير العمل بلا حالات")

        instance = WorkflowInstance(
            company_id=ctx.company_id,
            definition_id=definition.id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            current_state=definition.states[0],
            history=[],
        )
        self._session.add(instance)
        await self._session.commit()
        await self._session.refresh(instance)
        return instance


class ListWorkflowInstancesUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, entity_type: str | None, entity_id: str | None
    ) -> list[WorkflowInstance]:
        return await WorkflowInstanceRepository(self._session).list_for_company(
            company_id=ctx.company_id, entity_type=entity_type, entity_id=entity_id
        )


class TransitionWorkflowInstanceUseCase:
    """قاعدة تحقق إلزامية: أي انتقال غير معرَّف في `definition.transitions`
    لحالة الـ instance الحالية → `ValueError` واضح (400 على مستوى الـ Router)،
    لا فشل صامت."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, instance_id: str, transition_name: str
    ) -> WorkflowInstance:
        instance = await WorkflowInstanceRepository(self._session).get_by_id(
            instance_id, company_id=ctx.company_id
        )
        if instance is None:
            raise ValueError("نسخة سير العمل غير موجودة")

        definition = await WorkflowDefinitionRepository(self._session).get_by_id(
            str(instance.definition_id), company_id=ctx.company_id
        )
        if definition is None:
            raise ValueError("تعريف سير العمل غير موجود")

        transition = next(
            (
                t
                for t in definition.transitions
                if t["name"] == transition_name and t["from"] == instance.current_state
            ),
            None,
        )
        if transition is None:
            raise ValueError(
                f"انتقال غير مسموح: {transition_name} من الحالة {instance.current_state}"
            )

        instance.history = [
            *instance.history,
            {
                "from": instance.current_state,
                "to": transition["to"],
                "at": utcnow().isoformat(),
            },
        ]
        instance.current_state = transition["to"]
        await self._session.commit()
        await self._session.refresh(instance)
        return instance
