from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.workflow.application.dto.workflow_dto import (
    WorkflowDefinitionCreateRequest,
    WorkflowDefinitionResponse,
    WorkflowInstanceResponse,
    WorkflowInstanceStartRequest,
    WorkflowInstanceTransitionRequest,
)
from modules.workflow.application.use_cases.workflow_use_cases import (
    CreateWorkflowDefinitionUseCase,
    ListWorkflowDefinitionsUseCase,
    ListWorkflowInstancesUseCase,
    StartWorkflowInstanceUseCase,
    TransitionWorkflowInstanceUseCase,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "/definitions",
    response_model=WorkflowDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("workflow.definition.manage"))],
)
async def create_workflow_definition(
    request: WorkflowDefinitionCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> WorkflowDefinitionResponse:
    definition = await CreateWorkflowDefinitionUseCase(session).execute(ctx, request)
    return WorkflowDefinitionResponse.model_validate(definition)


@router.get("/definitions", response_model=list[WorkflowDefinitionResponse])
async def list_workflow_definitions(
    entity_type: str | None = Query(default=None),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[WorkflowDefinitionResponse]:
    definitions = await ListWorkflowDefinitionsUseCase(session).execute(ctx, entity_type)
    return [WorkflowDefinitionResponse.model_validate(d) for d in definitions]


@router.post(
    "/instances",
    response_model=WorkflowInstanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_workflow_instance(
    request: WorkflowInstanceStartRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> WorkflowInstanceResponse:
    try:
        instance = await StartWorkflowInstanceUseCase(session).execute(ctx, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WorkflowInstanceResponse.model_validate(instance)


@router.get("/instances", response_model=list[WorkflowInstanceResponse])
async def list_workflow_instances(
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[WorkflowInstanceResponse]:
    instances = await ListWorkflowInstancesUseCase(session).execute(ctx, entity_type, entity_id)
    return [WorkflowInstanceResponse.model_validate(i) for i in instances]


@router.post(
    "/instances/{instance_id}/transition",
    response_model=WorkflowInstanceResponse,
    dependencies=[Depends(require_permission("workflow.instance.transition"))],
)
async def transition_workflow_instance(
    instance_id: str,
    request: WorkflowInstanceTransitionRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> WorkflowInstanceResponse:
    try:
        instance = await TransitionWorkflowInstanceUseCase(session).execute(
            ctx, instance_id, request.transition_name
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WorkflowInstanceResponse.model_validate(instance)
