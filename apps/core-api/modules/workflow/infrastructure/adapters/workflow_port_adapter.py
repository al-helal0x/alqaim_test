"""WorkflowPortAdapter — التنفيذ الفعلي لـ IWorkflowPort (مهمة #12). يعيد
استخدام Use Cases/Repositories الموجودة في هذه الوحدة نفسها حصراً — لا
استيراد لأي شيء من موديول آخر هنا، وهو الاتجاه الصحيح للاعتماديات (القسم
11.2: الوحدة المزوِّدة تستورد فقط من نفسها؛ الوحدة المستهلِكة تستورد فقط من
`application/ports` الخاص بالمزوِّد — راجع نمط
`modules/accounting/infrastructure/adapters/accounting_port_adapter.py`).

يُحقَن هذا الـ Adapter من نقطة التوصيل (Composition Root): إما راوتر presentation
(كما في `invoices_router.py` مع IAccountingPort/IInventoryPort) أو `main.py`
عند تسجيل معالِج حدث Event Bus — وليس من داخل infrastructure الخاصة بموديول
آخر مباشرة.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from modules.workflow.application.dto.workflow_dto import (
    WorkflowDefinitionCreateRequest,
    WorkflowInstanceStartRequest,
)
from modules.workflow.application.ports.workflow_port import (
    ApprovalWorkflowRequest,
    WorkflowInstanceRef,
)
from modules.workflow.application.use_cases.workflow_use_cases import (
    CreateWorkflowDefinitionUseCase,
    StartWorkflowInstanceUseCase,
)
from modules.workflow.infrastructure.repositories.workflow_repository import (
    WorkflowDefinitionRepository,
    WorkflowInstanceRepository,
)
from platform_core.auth_middleware import TenantContext


class WorkflowPortAdapter:
    """`user_id="system"`: هذا البدء مُشغَّل تلقائياً من Event Handler، وليس
    من طلب مستخدم مباشر مصادَق عليه. TenantContext هنا حاوية بيانات فقط —
    CreateWorkflowDefinitionUseCase وStartWorkflowInstanceUseCase (المُستدعاتان
    هنا) تستخدمان `ctx.company_id` حصراً، بلا أي فحص صلاحية RBAC مرتبط
    بـ user_id، فالقيمة الوهمية آمنة تماماً لهذا الاستخدام."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_approval_started(
        self, request: ApprovalWorkflowRequest
    ) -> WorkflowInstanceRef:
        instance_repo = WorkflowInstanceRepository(self._session)

        existing_instances = await instance_repo.list_for_company(
            company_id=request.company_id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
        )
        if existing_instances:
            latest = existing_instances[-1]
            return WorkflowInstanceRef(
                instance_id=str(latest.id), current_state=latest.current_state
            )

        ctx = TenantContext(company_id=request.company_id, user_id="system")
        definition_repo = WorkflowDefinitionRepository(self._session)
        definitions = await definition_repo.list_for_company(
            company_id=request.company_id, entity_type=request.entity_type
        )
        definition = next(
            (d for d in definitions if d.name == request.definition_name and d.is_active),
            None,
        )
        if definition is None:
            definition = await CreateWorkflowDefinitionUseCase(self._session).execute(
                ctx,
                WorkflowDefinitionCreateRequest(
                    entity_type=request.entity_type,
                    name=request.definition_name,
                    states=request.states,
                    transitions=[
                        {"name": t["name"], "from": t["from"], "to": t["to"]}
                        for t in request.transitions
                    ],
                ),
            )

        instance = await StartWorkflowInstanceUseCase(self._session).execute(
            ctx,
            WorkflowInstanceStartRequest(
                definition_id=str(definition.id),
                entity_type=request.entity_type,
                entity_id=request.entity_id,
            ),
        )
        return WorkflowInstanceRef(
            instance_id=str(instance.id), current_state=instance.current_state
        )

    async def get_latest_instance_state(
        self, *, company_id: str, entity_type: str, entity_id: str
    ) -> str | None:
        instance_repo = WorkflowInstanceRepository(self._session)
        existing_instances = await instance_repo.list_for_company(
            company_id=company_id, entity_type=entity_type, entity_id=entity_id
        )
        if not existing_instances:
            return None
        return existing_instances[-1].current_state
