"""Router لموديول notifications. لا صلاحية RBAC مخصَّصة: كل مستخدم مصادَق
عليه يرى إشعارات شركته فقط (ضمنياً عبر ctx.company_id من التوكن)."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.notifications.application.dto.notifications_dto import NotificationResponse
from modules.notifications.application.use_cases.notifications_use_cases import (
    ListNotificationsUseCase,
    MarkNotificationReadUseCase,
)
from platform_core.auth_middleware import TenantContext, get_current_context
from platform_core.database import get_db_session
from shared_kernel.pagination import Page, PageParams, page_params

router = APIRouter()


@router.get("", response_model=Page[NotificationResponse])
async def list_notifications(
    is_read: bool | None = Query(default=None),
    params: PageParams = Depends(page_params),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> Page[NotificationResponse]:
    rows, total = await ListNotificationsUseCase(session).execute(ctx, is_read, params)
    return Page[NotificationResponse](
        items=[NotificationResponse.model_validate(row) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> NotificationResponse:
    try:
        notification = await MarkNotificationReadUseCase(session).execute(ctx, notification_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return NotificationResponse.model_validate(notification)
