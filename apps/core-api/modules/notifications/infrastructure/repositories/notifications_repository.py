from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.notifications.infrastructure.models.notifications_models import Notification


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def query_for_company(self, *, company_id: str, is_read: bool | None = None):
        stmt = select(Notification).where(Notification.company_id == company_id)
        if is_read is not None:
            stmt = stmt.where(Notification.is_read == is_read)
        return stmt

    async def get_by_id(self, notification_id: str, *, company_id: str) -> Notification | None:
        stmt = select(Notification).where(
            Notification.id == notification_id, Notification.company_id == company_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
