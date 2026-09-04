import uuid

import pytest
from sqlalchemy import select

from modules.notifications.application.use_cases.notifications_use_cases import (
    CreateNotificationFromEventUseCase,
    ListNotificationsUseCase,
    MarkNotificationReadUseCase,
)
from modules.notifications.infrastructure.models.notifications_models import Notification
from platform_core.auth_middleware import TenantContext
from shared_kernel.pagination import PageParams


@pytest.mark.asyncio
async def test_invoice_posted_creates_notification_with_expected_text(db_session):
    company_id = str(uuid.uuid4())
    payload = {"company_id": company_id, "total": 250, "currency": "IQD"}

    await CreateNotificationFromEventUseCase(db_session).execute("InvoicePosted", payload)

    rows = (await db_session.execute(select(Notification))).scalars().all()
    assert len(rows) == 1
    assert rows[0].title == "فاتورة جديدة"
    assert "250" in rows[0].body and "IQD" in rows[0].body


@pytest.mark.asyncio
async def test_stock_level_low_creates_notification_with_expected_text(db_session):
    company_id = str(uuid.uuid4())
    payload = {
        "company_id": company_id, "product_id": "p1", "warehouse_id": "w1",
        "current_qty": 3, "threshold": 10,
    }

    await CreateNotificationFromEventUseCase(db_session).execute("StockLevelLow", payload)

    rows = (await db_session.execute(select(Notification))).scalars().all()
    assert len(rows) == 1
    assert rows[0].title == "مخزون منخفض"
    assert "3" in rows[0].body and "10" in rows[0].body


@pytest.mark.asyncio
async def test_unknown_event_does_not_create_notification(db_session):
    """تأكيد صريح أن لا اشتراك غير موثَّق: PaymentRecorded ليس في القائمة
    المُعلَنة في contracts.md §2 كمستهلِك لها من notifications."""
    await CreateNotificationFromEventUseCase(db_session).execute(
        "PaymentRecorded", {"company_id": str(uuid.uuid4()), "payment_id": "pay1"}
    )

    rows = (await db_session.execute(select(Notification))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_mark_notification_read(db_session):
    company_id = str(uuid.uuid4())
    await CreateNotificationFromEventUseCase(db_session).execute(
        "InvoicePosted", {"company_id": company_id, "total": 10, "currency": "IQD"}
    )
    ctx = TenantContext(company_id=company_id, user_id=str(uuid.uuid4()))
    rows, _ = await ListNotificationsUseCase(db_session).execute(
        ctx, None, PageParams(page=1, page_size=20)
    )
    notification_id = str(rows[0].id)

    updated = await MarkNotificationReadUseCase(db_session).execute(ctx, notification_id)

    assert updated.is_read is True


@pytest.mark.asyncio
async def test_mark_notification_read_unknown_id_raises(db_session):
    ctx = TenantContext(company_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()))
    with pytest.raises(ValueError):
        await MarkNotificationReadUseCase(db_session).execute(ctx, str(uuid.uuid4()))
