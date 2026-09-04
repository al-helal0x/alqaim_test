"""Use Cases لموديول integrations (Webhooks الصادرة — العضو 13)."""
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from modules.integrations.application.dto.integrations_dto import (
    WebhookSubscriptionCreateRequest,
)
from modules.integrations.application.ports.webhook_sender_port import IWebhookSender
from modules.integrations.infrastructure.models.integrations_models import (
    WebhookDelivery,
    WebhookSubscription,
)
from modules.integrations.infrastructure.repositories.integrations_repository import (
    WebhookDeliveryRepository,
    WebhookSubscriptionRepository,
)
from platform_core.auth_middleware import TenantContext


class CreateWebhookSubscriptionUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, request: WebhookSubscriptionCreateRequest
    ) -> WebhookSubscription:
        subscription = WebhookSubscription(
            company_id=ctx.company_id,
            target_url=request.target_url,
            secret=secrets.token_hex(32),
            event_types=request.event_types,
        )
        self._session.add(subscription)
        await self._session.commit()
        await self._session.refresh(subscription)
        return subscription


class ListWebhookSubscriptionsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext) -> list[WebhookSubscription]:
        return await WebhookSubscriptionRepository(self._session).list_for_company(
            company_id=ctx.company_id
        )


class DeactivateWebhookSubscriptionUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, subscription_id: str) -> None:
        subscription = await WebhookSubscriptionRepository(self._session).get_by_id(
            subscription_id, company_id=ctx.company_id
        )
        if subscription is None:
            raise ValueError("الاشتراك غير موجود")
        subscription.is_active = False
        await self._session.commit()


class ListWebhookDeliveriesUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, subscription_id: str) -> list[WebhookDelivery]:
        subscription = await WebhookSubscriptionRepository(self._session).get_by_id(
            subscription_id, company_id=ctx.company_id
        )
        if subscription is None:
            raise ValueError("الاشتراك غير موجود")
        return await WebhookDeliveryRepository(self._session).list_for_subscription(
            company_id=ctx.company_id, subscription_id=subscription_id
        )


class DispatchEventToWebhooksUseCase:
    """المستهلِك الفعلي لأحداث Event Bus — يُسجَّل في main.py لكل اسم حدث
    نريد بثّه خارجياً (القسم 6.6). لا يعرف شيئاً عن الوحدة الناشرة (sales/
    purchasing/payments/...)، فقط يستقبل (event_name, payload) عاماً —
    بالضبط نمط الفصل الذي تفرضه المادة 11.2."""

    def __init__(self, session: AsyncSession, sender: IWebhookSender) -> None:
        self._session = session
        self._sender = sender

    async def execute(self, event_name: str, payload: dict) -> None:
        company_id = payload.get("company_id")
        if not company_id:
            return  # حمولة بلا company_id لا يمكن نطاقها لأي اشتراك — تُهمَل بصمت

        repo = WebhookSubscriptionRepository(self._session)
        subscriptions = await repo.list_active_for_event(
            company_id=str(company_id), event_name=event_name
        )
        for subscription in subscriptions:
            success, status_code, error = await self._sender.send(
                url=subscription.target_url, payload=payload, secret=subscription.secret
            )
            self._session.add(
                WebhookDelivery(
                    company_id=subscription.company_id,
                    subscription_id=subscription.id,
                    event_name=event_name,
                    payload=payload,
                    success=success,
                    status_code=status_code,
                    error_message=error,
                )
            )
        if subscriptions:
            await self._session.commit()
