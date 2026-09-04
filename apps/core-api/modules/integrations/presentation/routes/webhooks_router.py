from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.integrations.application.dto.integrations_dto import (
    WebhookDeliveryResponse,
    WebhookSubscriptionCreatedResponse,
    WebhookSubscriptionCreateRequest,
    WebhookSubscriptionResponse,
)
from modules.integrations.application.use_cases.integrations_use_cases import (
    CreateWebhookSubscriptionUseCase,
    DeactivateWebhookSubscriptionUseCase,
    ListWebhookDeliveriesUseCase,
    ListWebhookSubscriptionsUseCase,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "",
    response_model=WebhookSubscriptionCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("integrations.webhook.manage"))],
)
async def create_webhook_subscription(
    request: WebhookSubscriptionCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> WebhookSubscriptionCreatedResponse:
    subscription = await CreateWebhookSubscriptionUseCase(session).execute(ctx, request)
    return WebhookSubscriptionCreatedResponse.model_validate(subscription)


@router.get("", response_model=list[WebhookSubscriptionResponse])
async def list_webhook_subscriptions(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[WebhookSubscriptionResponse]:
    subscriptions = await ListWebhookSubscriptionsUseCase(session).execute(ctx)
    return [WebhookSubscriptionResponse.model_validate(s) for s in subscriptions]


@router.delete(
    "/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("integrations.webhook.manage"))],
)
async def deactivate_webhook_subscription(
    subscription_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    try:
        await DeactivateWebhookSubscriptionUseCase(session).execute(ctx, subscription_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{subscription_id}/deliveries", response_model=list[WebhookDeliveryResponse])
async def list_webhook_deliveries(
    subscription_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[WebhookDeliveryResponse]:
    try:
        deliveries = await ListWebhookDeliveriesUseCase(session).execute(ctx, subscription_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [WebhookDeliveryResponse.model_validate(d) for d in deliveries]
