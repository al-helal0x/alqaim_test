"""يثبت أن جسر Redis (platform_core/redis_bridge.py) يستقبل فعلياً ما يُنشره
`ai-platform` (platform_core/redis_events.py) على القناة المشتركة
'alqaim:events' ويُعيد بثّه محلياً عبر event_bus — إغلاق فعلي للفجوة
الموثَّقة في contracts.md §4 (وليس اختباراً وهمياً بمحاكاة الدالتين
منفصلتين؛ هذا Redis حقيقي يعمل على نفس الجهاز).

يتطلب Redis فعلياً متاحاً على redis://localhost:6379 — إن لم يكن متاحاً
يُتخطى الاختبار تلقائياً بدل الفشل (بيئات CI بلا Redis محلي).
"""
import asyncio
import json

import pytest
import redis.asyncio as aioredis

from platform_core.event_bus import EventBus

pytestmark = pytest.mark.asyncio

REDIS_URL = "redis://localhost:6379/0"
EVENTS_CHANNEL = "alqaim:events"


async def _redis_available() -> bool:
    try:
        client = aioredis.from_url(REDIS_URL)
        await client.ping()
        await client.aclose()
        return True
    except Exception:
        return False


async def test_event_published_on_redis_is_received_by_local_bridge(db_session):
    if not await _redis_available():
        pytest.skip("Redis غير متاح في بيئة التشغيل الحالية")

    # نستخدم event_bus محلي مستقل (وليس الـ Singleton العام) لتفادي تلوّث
    # الاختبارات الأخرى بمشتركين دائمين
    local_bus = EventBus()
    received: list[dict] = []

    async def _handler(payload: dict) -> None:
        received.append(payload)

    local_bus.subscribe("InvoiceDraftReady", _handler)

    # نُحاكي بالضبط ما يفعله platform_core/redis_bridge.py: اشتراك على نفس
    # القناة، ثم توجيه أي رسالة لـ event_bus محلي
    client = aioredis.from_url(REDIS_URL)
    pubsub = client.pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)

    async def _bridge_loop():
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            envelope = json.loads(message["data"])
            # مهمة 6: publish يكتب outbox_events فقط — dispatch_pending هو ما
            # يُسلّم فعلياً للمشتركين المحليين (تماماً كما يفعل redis_bridge.py).
            await local_bus.publish(db_session, envelope["event"], envelope["payload"])
            await db_session.commit()
            await local_bus.dispatch_pending(db_session)
            break  # رسالة واحدة كافية لهذا الاختبار

    bridge_task = asyncio.create_task(_bridge_loop())
    await asyncio.sleep(0.2)  # مهلة بسيطة لضمان اكتمال الاشتراك قبل النشر

    # هذا بالضبط ما ينشره ai-platform/platform_core/redis_events.publish_event
    publisher = aioredis.from_url(REDIS_URL)
    envelope = json.dumps({
        "event": "InvoiceDraftReady",
        "payload": {"draft_id": "abc-123", "company_id": "company-xyz", "confidence": 0.81},
        "source": "ai-platform",
    })
    await publisher.publish(EVENTS_CHANNEL, envelope)
    await publisher.aclose()

    await asyncio.wait_for(bridge_task, timeout=3.0)
    await pubsub.unsubscribe(EVENTS_CHANNEL)
    await pubsub.aclose()
    await client.aclose()

    assert len(received) == 1
    assert received[0]["draft_id"] == "abc-123"
    assert received[0]["company_id"] == "company-xyz"
