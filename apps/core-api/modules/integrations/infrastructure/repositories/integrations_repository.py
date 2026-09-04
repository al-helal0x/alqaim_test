from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.integrations.infrastructure.models.integrations_models import (
    WebhookDelivery,
    WebhookSubscription,
)


class WebhookSubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, subscription_id: str, *, company_id: str) -> WebhookSubscription | None:
        stmt = select(WebhookSubscription).where(
            WebhookSubscription.id == subscription_id,
            WebhookSubscription.company_id == company_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_company(self, *, company_id: str) -> list[WebhookSubscription]:
        stmt = select(WebhookSubscription).where(
            WebhookSubscription.company_id == company_id,
            WebhookSubscription.deleted_at.is_(None),
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_active_for_event(
        self, *, company_id: str, event_name: str
    ) -> list[WebhookSubscription]:
        subscriptions = await self.list_for_company(company_id=company_id)
        return [s for s in subscriptions if s.is_active and event_name in s.event_types]

    async def list_active_for_event_all_companies(
        self, *, event_name: str
    ) -> list[WebhookSubscription]:
        """يُستخدَم من مُوزِّع الأحداث (Dispatcher) الذي يستقبل حدثاً بلا معرفة
        مسبقة بأي شركة — عكس بقية الاستعلامات هنا (كل شيء آخر يُقيَّد
        بـ ctx.company_id قادماً من الطلب المصادَق عليه)."""
        stmt = select(WebhookSubscription).where(
            WebhookSubscription.deleted_at.is_(None), WebhookSubscription.is_active.is_(True)
        )
        subscriptions = list((await self._session.execute(stmt)).scalars().all())
        return [s for s in subscriptions if event_name in s.event_types]


class WebhookDeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_subscription(
        self, *, company_id: str, subscription_id: str, limit: int = 50
    ) -> list[WebhookDelivery]:
        stmt = (
            select(WebhookDelivery)
            .where(
                WebhookDelivery.company_id == company_id,
                WebhookDelivery.subscription_id == subscription_id,
            )
            .order_by(WebhookDelivery.created_at.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())
