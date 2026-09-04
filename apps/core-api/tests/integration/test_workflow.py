import uuid

import pytest

from modules.workflow.application.dto.workflow_dto import (
    WorkflowDefinitionCreateRequest,
    WorkflowInstanceStartRequest,
)
from modules.workflow.application.use_cases.workflow_use_cases import (
    CreateWorkflowDefinitionUseCase,
    StartWorkflowInstanceUseCase,
    TransitionWorkflowInstanceUseCase,
)
from platform_core.auth_middleware import TenantContext


def _make_ctx() -> TenantContext:
    return TenantContext(company_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_create_definition_start_instance_and_transition_success(db_session):
    ctx = _make_ctx()
    definition = await CreateWorkflowDefinitionUseCase(db_session).execute(
        ctx,
        WorkflowDefinitionCreateRequest(
            entity_type="purchase_order",
            name="موافقة أمر شراء",
            states=["draft", "pending", "approved", "rejected"],
            transitions=[
                {"name": "submit", "from": "draft", "to": "pending"},
                {"name": "approve", "from": "pending", "to": "approved"},
                {"name": "reject", "from": "pending", "to": "rejected"},
            ],
        ),
    )
    assert definition.states == ["draft", "pending", "approved", "rejected"]

    instance = await StartWorkflowInstanceUseCase(db_session).execute(
        ctx,
        WorkflowInstanceStartRequest(
            definition_id=str(definition.id), entity_type="purchase_order", entity_id="po-1"
        ),
    )
    assert instance.current_state == "draft"
    assert instance.history == []

    submitted = await TransitionWorkflowInstanceUseCase(db_session).execute(
        ctx, str(instance.id), "submit"
    )
    assert submitted.current_state == "pending"
    assert len(submitted.history) == 1
    assert submitted.history[0]["from"] == "draft"
    assert submitted.history[0]["to"] == "pending"


@pytest.mark.asyncio
async def test_transition_undefined_for_current_state_raises_value_error(db_session):
    ctx = _make_ctx()
    definition = await CreateWorkflowDefinitionUseCase(db_session).execute(
        ctx,
        WorkflowDefinitionCreateRequest(
            entity_type="purchase_order",
            name="موافقة أمر شراء",
            states=["draft", "pending", "approved"],
            transitions=[
                {"name": "submit", "from": "draft", "to": "pending"},
                {"name": "approve", "from": "pending", "to": "approved"},
            ],
        ),
    )
    instance = await StartWorkflowInstanceUseCase(db_session).execute(
        ctx,
        WorkflowInstanceStartRequest(
            definition_id=str(definition.id), entity_type="purchase_order", entity_id="po-2"
        ),
    )

    # "approve" غير معرَّف من الحالة الحالية "draft" (معرَّف فقط من "pending")
    with pytest.raises(ValueError):
        await TransitionWorkflowInstanceUseCase(db_session).execute(
            ctx, str(instance.id), "approve"
        )


@pytest.mark.asyncio
async def test_definition_create_rejects_transition_referencing_unknown_state():
    with pytest.raises(ValueError):
        WorkflowDefinitionCreateRequest(
            entity_type="purchase_order",
            name="تعريف غير صالح",
            states=["draft", "pending"],
            transitions=[{"name": "approve", "from": "pending", "to": "approved"}],
        )
