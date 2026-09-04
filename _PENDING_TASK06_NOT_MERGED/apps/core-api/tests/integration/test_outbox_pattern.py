"""اختبارات تكامل لمهمة 6 — Outbox Pattern لـ event_bus (القسم 6.6).

تغطي معيار القبول الثلاثة المذكورة في خطة الإغلاق حرفياً:
1. جدول outbox_events موجود ويُكتَب إليه.
2. الأحداث تُكتَب ضمن نفس معاملة قاعدة البيانات (لا تُفقَد عند rollback،
   ولا تُحفَظ لو فشلت العملية التجارية نفسها).
3. Worker/مسار إعادة المحاولة يُسلِّم الأحداث غير المُسلَّمة (retry + backoff
   + وسم "failed" بعد تجاوز الحد الأقصى).
"""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from platform_core.event_bus import EventBus
from platform_core.outbox_models import OutboxEvent, OutboxEventStatus

pytestmark = pytest.mark.asyncio


async def test_publish_writes_outbox_row_without_dispatching_immediately(db_session):
    """publish() وحدها لا تُسلِّم للمشتركين — فقط dispatch_pending تفعل ذلك.
    هذا يثبت الفصل بين "الكتابة الذرّية" و"التسليم الفعلي" الذي يقوم عليه
    كل ضمان Outbox."""
    bus = EventBus()
    received: list[dict] = []

    async def _handler(payload: dict) -> None:
        received.append(payload)

    bus.subscribe("InvoicePosted", _handler)

    await bus.publish(db_session, "InvoicePosted", {"invoice_id": "inv-1"})
    await db_session.commit()

    rows = (await db_session.execute(select(OutboxEvent))).scalars().all()
    assert len(rows) == 1
    assert rows[0].event_name == "InvoicePosted"
    assert rows[0].payload == {"invoice_id": "inv-1"}
    assert rows[0].status == OutboxEventStatus.PENDING.value
    assert received == []  # لم يُسلَّم بعد


async def test_event_is_part_of_same_transaction_and_lost_on_rollback(db_session):
    """يثبت الذرّية الفعلية: كتابة outbox_events ضمن نفس معاملة تغيير أعمال،
    فإذا فشلت/تم التراجع عن المعاملة (rollback) قبل commit، يختفي الحدث تماماً
    كما يختفي التغيير التجاري نفسه — لا "نصف حفظ" ممكن."""
    bus = EventBus()

    await bus.publish(db_session, "InvoicePosted", {"invoice_id": "inv-rollback"})
    # التحقق أن السطر مرئي داخل المعاملة الحالية (flush بلا commit)
    pending_in_txn = (await db_session.execute(select(OutboxEvent))).scalars().all()
    assert len(pending_in_txn) == 1

    await db_session.rollback()

    rows_after_rollback = (await db_session.execute(select(OutboxEvent))).scalars().all()
    assert rows_after_rollback == []


async def test_dispatch_pending_delivers_and_marks_dispatched(db_session):
    bus = EventBus()
    received: list[dict] = []

    async def _handler(payload: dict) -> None:
        received.append(payload)

    bus.subscribe("PaymentRecorded", _handler)

    await bus.publish(db_session, "PaymentRecorded", {"payment_id": "p-1"})
    await db_session.commit()

    dispatched_count = await bus.dispatch_pending(db_session)

    assert dispatched_count == 1
    assert received == [{"payment_id": "p-1"}]

    row = (await db_session.execute(select(OutboxEvent))).scalar_one()
    assert row.status == OutboxEventStatus.DISPATCHED.value
    assert row.dispatched_at is not None

    # استدعاء ثانٍ لا يُعيد التسليم (الحدث لم يعد pending)
    received.clear()
    dispatched_again = await bus.dispatch_pending(db_session)
    assert dispatched_again == 0
    assert received == []


async def test_dispatch_pending_retries_failed_handler_with_backoff(db_session):
    """مشترك يفشل في أول محاولة فقط — الحدث يبقى pending مع attempts=1 و
    next_attempt_at مؤجَّل للمستقبل (لا إعادة محاولة فورية عشوائية)، ثم
    ينجح عند دفع next_attempt_at للماضي يدوياً (محاكاة مرور الوقت)."""
    bus = EventBus()
    call_count = {"n": 0}
    received: list[dict] = []

    async def _flaky_handler(payload: dict) -> None:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("فشل مؤقت في المشترك")
        received.append(payload)

    bus.subscribe("StockLevelLow", _flaky_handler)

    await bus.publish(db_session, "StockLevelLow", {"product_id": "sku-1"})
    await db_session.commit()

    dispatched_count = await bus.dispatch_pending(db_session)
    assert dispatched_count == 0

    row = (await db_session.execute(select(OutboxEvent))).scalar_one()
    assert row.status == OutboxEventStatus.PENDING.value
    assert row.attempts == 1
    assert row.last_error is not None
    assert row.next_attempt_at > datetime.now(UTC)

    # لا تُعاد المحاولة قبل موعدها
    assert await bus.dispatch_pending(db_session) == 0
    assert received == []

    # نحاكي مرور الوقت: ندفع next_attempt_at للماضي يدوياً
    row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()

    dispatched_count = await bus.dispatch_pending(db_session)
    assert dispatched_count == 1
    assert received == [{"product_id": "sku-1"}]

    row = (await db_session.execute(select(OutboxEvent))).scalar_one()
    assert row.status == OutboxEventStatus.DISPATCHED.value


async def test_dispatch_pending_marks_failed_after_max_attempts(db_session):
    """مشترك يفشل دائماً — بعد تجاوز max_attempts يتوقف الحدث عن إعادة
    المحاولة تلقائياً ويُوسَم "failed" (يحتاج تدخلاً يدوياً) بدل إعادة
    المحاولة إلى ما لا نهاية."""
    bus = EventBus()

    async def _always_failing_handler(payload: dict) -> None:
        raise RuntimeError("خطأ دائم")

    bus.subscribe("AccountSettingsChanged", _always_failing_handler)

    await bus.publish(db_session, "AccountSettingsChanged", {"company_id": "c-1"})
    await db_session.commit()

    for _ in range(3):
        row = (await db_session.execute(select(OutboxEvent))).scalar_one()
        row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        await db_session.commit()
        await bus.dispatch_pending(db_session, max_attempts=3)

    row = (await db_session.execute(select(OutboxEvent))).scalar_one()
    assert row.status == OutboxEventStatus.FAILED.value
    assert row.attempts == 3


async def test_dispatch_pending_ignores_events_from_other_event_names(db_session):
    """حدث بلا أي مشترك مسجَّل (event_name غير معروف لهذا bus) يُسلَّم فوراً
    بنجاح (لا مشتركين = لا فشل) — يثبت أن الغياب التام لمشترك ليس خطأ."""
    bus = EventBus()

    await bus.publish(db_session, "SomeUnsubscribedEvent", {"x": 1})
    await db_session.commit()

    dispatched_count = await bus.dispatch_pending(db_session)
    assert dispatched_count == 1

    row = (await db_session.execute(select(OutboxEvent))).scalar_one()
    assert row.status == OutboxEventStatus.DISPATCHED.value
