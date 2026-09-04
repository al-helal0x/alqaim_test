"""TASK-06-05 — يغلق فجوة GATE-01 الموثَّقة في
`ALQAIM_V2_PACKAGE_MERGE_PLAN_REVISED.md §3.4/§5`: لا وجود سابقاً لملف
يختبر `outbox.py`/`outbox_worker.py` بمعزل عن أي use case تجاري (التغطية
الوحيدة السابقة كانت غير مباشرة عبر `test_sales_invoice_idempotent_posting.py`).

يغطي السيناريوهات الأربعة الإلزامية من `ALQAIM_V2_MASTER_EXECUTION_PLAN.md §13`
حرفياً، بنفس ترتيبها:

1. Transaction succeeds → Event exists
2. Transaction fails    → Event does not exist
3. Worker fails         → Event remains retryable (حتى `MAX_ATTEMPTS`، ثم `failed`)
4. Event delivered twice → Consumer remains safe (at-least-once، لا exactly-once)

لا يلمس هذا الملف `platform_core/outbox.py` أو `outbox_worker.py` — الكود
الفعلي (بما فيه إصلاح `MAX_ATTEMPTS=8 → status="failed"` الموثَّق في تعليق
TASK-06-02 أعلى `outbox_worker.py`) موجود ومطابق للعقد مسبقاً؛ هذا الملف
فقط يثبت ذلك باختبار مباشر بدل تركه بلا تغطية.

نستخدم `db_session`/`event_bus` من `conftest.py` (SQLite في-الذاكرة +
EventBus معزول لكل اختبار) — لا حاجة لبنية تحتية حقيقية.

ملاحظة على قابلية الاختبار: `_poll_once()` في `outbox_worker.py` يفتح
جلسته الخاصة عبر `AsyncSessionLocal` من `platform_core.database` (اتصال
Postgres حقيقي حسب `settings.database_url`) — غير مناسب مباشرة لبيئة
SQLite هنا. لذلك تُختبَر `_dispatch_one()` (تأخذ `session`/`row` كوسيطين
صريحين، قابلة للحقن بالكامل) بدل `_poll_once()`/`_run_loop()` — وهي
الدالة التي تحوي فعلياً منطق backoff/`MAX_ATTEMPTS` محل الاختبار، بينما
`_poll_once` مجرد استعلام + حلقة استدعاء لا منطق قرار فيه.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from platform_core import outbox
from platform_core.outbox_models import OutboxEvent
from platform_core.outbox_worker import MAX_ATTEMPTS, _dispatch_one

pytestmark = pytest.mark.asyncio


def _row_of(session_result) -> OutboxEvent:
    return session_result.scalar_one()


async def _all_outbox_rows(db_session) -> list[OutboxEvent]:
    result = await db_session.execute(select(OutboxEvent))
    return list(result.scalars().all())


# ── 1. Transaction succeeds → Event exists ─────────────────────────────────


async def test_transaction_succeeds_event_exists(db_session):
    """محاكاة use case تجاري ناجح: enqueue_event ثم commit ضمن نفس معاملة
    العمل التجاري (تماماً كنمط sales_use_cases.py/fiscal_period_use_cases.py)
    — الصف يجب أن يكون موجوداً وبحالة 'pending' بعد الـ commit."""
    aggregate_id = str(uuid.uuid4())

    await outbox.enqueue_event(
        db_session,
        event_name="TestBusinessEventHappened",
        payload={"marker": "success-path"},
        aggregate_id=aggregate_id,
    )
    await db_session.commit()

    rows = await _all_outbox_rows(db_session)
    assert len(rows) == 1
    assert rows[0].event_name == "TestBusinessEventHappened"
    assert rows[0].aggregate_id == aggregate_id
    assert rows[0].status == "pending"
    assert rows[0].attempts == 0


# ── 2. Transaction fails → Event does not exist ────────────────────────────


async def test_transaction_fails_event_does_not_exist(db_session):
    """`enqueue_event()` عمداً بلا `commit()` داخلي (موثَّق في docstring
    الدالة نفسها) — لو فشلت العملية التجارية بعد enqueue_event وقبل أي
    commit (مثلاً exception في خطوة لاحقة من نفس use case)، `rollback()`
    يُلغي صف outbox معها ذرّياً، بنفس معاملة قاعدة البيانات تماماً. هذا هو
    الضمان الجوهري لكون Outbox 'ذرّياً' مع التغيير التجاري، لا نشراً منفصلاً
    قد يتيتم لو فشلت المعاملة."""
    await outbox.enqueue_event(
        db_session,
        event_name="TestEventThatShouldVanish",
        payload={"marker": "will-be-rolled-back"},
        aggregate_id=str(uuid.uuid4()),
    )
    # محاكاة فشل use case تجاري بعد enqueue_event مباشرة — rollback بدل commit
    await db_session.rollback()

    rows = await _all_outbox_rows(db_session)
    assert rows == []


# ── 3. Worker fails → Event remains retryable (حتى MAX_ATTEMPTS ثم failed) ─


async def test_worker_failure_reschedules_row_as_retryable(db_session, event_bus):
    """معالج فاشل مسجَّل على الحدث → `_dispatch_one` يجب أن يزيد `attempts`،
    يُبقي `status='pending'` (قابل لإعادة المحاولة، ليس 'failed' بعد)،
    ويحدِّد `next_attempt_at` مستقبلياً — الصف *لم* يُفقَد ولم يُعلَّم
    dispatched رغم الفشل."""

    async def _always_fails(payload: dict) -> None:
        raise RuntimeError("فشل معالج متعمَّد لأغراض الاختبار")

    event_bus.subscribe("TestFailingEvent", _always_fails)

    row = OutboxEvent(
        id=uuid.uuid4(),
        event_name="TestFailingEvent",
        payload={"marker": "will-fail"},
        aggregate_id=str(uuid.uuid4()),
        status="pending",
        attempts=0,
    )
    db_session.add(row)
    await db_session.commit()

    await _dispatch_one(db_session, row)

    assert row.status == "pending"  # لا يزال قابلاً لإعادة المحاولة
    assert row.attempts == 1
    assert row.next_attempt_at is not None  # أُعيدت جدولته، لا استطلاع فوري لا نهائي
    assert row.last_error is not None
    assert row.dispatched_at is None


async def test_worker_failure_exhausted_attempts_marks_row_failed(db_session, event_bus):
    """هذا الشق تحديداً هو ما كان مفقوداً في النسخة السابقة من
    `outbox_worker.py` (موثَّق كالانحراف 3.1 في خطة الدمج): بعد بلوغ
    `MAX_ATTEMPTS` محاولات فاشلة، الصف يجب أن يتحوّل نهائياً لحالة
    'failed' ويتوقف عن إعادة الجدولة — لا يبقى 'pending' إلى الأبد."""

    async def _always_fails(payload: dict) -> None:
        raise RuntimeError("فشل معالج متعمَّد لأغراض الاختبار")

    event_bus.subscribe("TestPermanentlyFailingEvent", _always_fails)

    row = OutboxEvent(
        id=uuid.uuid4(),
        event_name="TestPermanentlyFailingEvent",
        payload={"marker": "will-permanently-fail"},
        aggregate_id=str(uuid.uuid4()),
        status="pending",
        attempts=MAX_ATTEMPTS - 1,  # المحاولة القادمة هي الأخيرة المسموحة
    )
    db_session.add(row)
    await db_session.commit()

    await _dispatch_one(db_session, row)

    assert row.attempts == MAX_ATTEMPTS
    assert row.status == "failed"  # توقف نهائي — لا next_attempt_at جديد بعدها
    assert row.dispatched_at is None

    # صف 'failed' لا يُستطلَع مجدداً — هذا هو الفلتر الفعلي في _poll_once()
    stmt = select(OutboxEvent).where(OutboxEvent.status == "pending")
    still_pending = (await db_session.execute(stmt)).scalars().all()
    assert row not in still_pending


# ── 4. Event delivered twice → Consumer remains safe (at-least-once) ───────


async def test_worker_never_redelivers_a_dispatched_row(db_session, event_bus):
    """نصف ضمان at-least-once من جهة الـ Worker نفسه: صف 'dispatched'
    فعلياً لا يُعاد استطلاعه أبداً — نفس فلتر `status == 'pending'` الذي
    يستخدمه `_poll_once()` الحقيقي. الـ Worker لا يُسبِّب تكراراً من
    تلقاء نفسه في المسار السعيد."""
    received: list[dict] = []

    async def _record(payload: dict) -> None:
        received.append(payload)

    event_bus.subscribe("TestDeliverOnceEvent", _record)

    row = OutboxEvent(
        id=uuid.uuid4(),
        event_name="TestDeliverOnceEvent",
        payload={"marker": "deliver-once"},
        aggregate_id=str(uuid.uuid4()),
        status="pending",
        attempts=0,
    )
    db_session.add(row)
    await db_session.commit()

    await _dispatch_one(db_session, row)
    assert row.status == "dispatched"
    assert len(received) == 1

    # محاكاة دورة استطلاع تالية: فلتر _poll_once الفعلي (status == 'pending')
    stmt = select(OutboxEvent).where(OutboxEvent.status == "pending")
    picked_up_again = (await db_session.execute(stmt)).scalars().all()
    assert row not in picked_up_again  # لن يُعاد إرساله من الـ Worker


async def test_duplicate_delivery_requires_idempotent_consumer(db_session, event_bus):
    """النصف الآخر من ضمان at-least-once — وهو تصميمي لا آلي: النظام
    **لا** يضمن exactly-once. لو انهار `core-api` بعد نجاح `publish()`
    داخل `_dispatch_one` وقبل اكتمال `session.commit()` (نافذة حقيقية،
    راجع docstring الملف)، إعادة تشغيل الـ Worker تُعيد تسليم *نفس* الحدث
    لأن الصف بقي 'pending'. هذا الاختبار يثبت أن الاستدعاء المزدوج للمعالج
    نفسه **لا يكسر شيئاً على مستوى EventBus/Outbox** — عبء ضمان
    idempotency يقع على المعالج التجاري نفسه (كما فعلت مهمة #11 فعلياً
    لفاتورة البيع)، وليس على طبقة Outbox، تماماً كما ينص §9.1 من الخطة
    الرئيسية بخصوص at-least-once."""
    received: list[dict] = []

    async def _record(payload: dict) -> None:
        received.append(payload)

    event_bus.subscribe("TestDuplicateDeliveryEvent", _record)

    payload = {"marker": "duplicate-delivery", "invoice_id": str(uuid.uuid4())}

    # استدعاء publish() مباشرة مرتين متتاليتين — يحاكي إعادة التسليم بعد
    # انهيار افتراضي بين publish() الأول ونجاح تعليم الصف dispatched
    await event_bus.publish("TestDuplicateDeliveryEvent", payload)
    await event_bus.publish("TestDuplicateDeliveryEvent", payload)

    assert received == [payload, payload]  # كلا الاستدعاءين نجح بلا استثناء
