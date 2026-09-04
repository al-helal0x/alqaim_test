"""Use Cases لموديول notifications (العضو 12)."""
from collections.abc import Callable
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from modules.notifications.infrastructure.models.notifications_models import Notification
from modules.notifications.infrastructure.repositories.notifications_repository import (
    NotificationRepository,
)
from platform_core.auth_middleware import TenantContext
from shared_kernel.pagination import PageParams, paginate


class CreateNotificationFromEventUseCase:
    """المستهلِك الفعلي لأحداث Event Bus — يُسجَّل في main.py حصراً للحدثين
    المُعلَنين صراحة كمستهلِك لهما في docs/architecture/contracts.md §2:
    `InvoicePosted` و`StockLevelLow`. أي حدث آخر (أو غير معروف) يُتجاهَل بصمت
    عبر `_TEMPLATES.get(event_name)` — لا اشتراك غير موثَّق."""

    _TEMPLATES: ClassVar[dict[str, Callable[[dict], tuple[str, str]]]] = {
        "InvoicePosted": lambda p: (
            "فاتورة جديدة",
            f"تم ترحيل فاتورة بقيمة {p.get('total')} {p.get('currency')}",
        ),
        "StockLevelLow": lambda p: (
            "مخزون منخفض",
            f"الكمية الحالية {p.get('current_qty')} أقل من الحد الأدنى {p.get('threshold')}",
        ),
    }

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, event_name: str, payload: dict) -> None:
        company_id = payload.get("company_id")
        template = self._TEMPLATES.get(event_name)
        if not company_id or template is None:
            # ملاحظة صادقة: حمولة StockLevelLow الموثَّقة فعلياً في contracts.md §2
            # لا تتضمن company_id صراحة (على عكس InvoicePosted) — إن لم يُضفه
            # الناشر الفعلي (inventory) للحمولة، هذا الفرع سيتجاهل الحدث بصمت
            # بنفس آلية الفجوة الموثَّقة سابقاً لـ InvoiceDraftReady في integrations.
            return
        title, body = template(payload)
        self._session.add(
            Notification(
                company_id=company_id,
                event_name=event_name,
                title=title,
                body=body,
                payload=payload,
            )
        )
        await self._session.commit()


class ListNotificationsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, is_read: bool | None, params: PageParams
    ) -> tuple[list[Notification], int]:
        stmt = NotificationRepository(self._session).query_for_company(
            company_id=ctx.company_id, is_read=is_read
        )
        return await paginate(self._session, stmt, Notification, params)


class MarkNotificationReadUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, notification_id: str) -> Notification:
        repo = NotificationRepository(self._session)
        notification = await repo.get_by_id(notification_id, company_id=ctx.company_id)
        if notification is None:
            raise ValueError("الإشعار غير موجود")
        notification.is_read = True
        await self._session.commit()
        await self._session.refresh(notification)
        return notification
