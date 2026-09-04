"""يثبت أن publish_event الحقيقية تنشر فعلياً على Redis بالشكل الذي يتوقّعه
جسر core-api (نفس القناة، نفس بنية المغلَّف JSON) — طرف النشر من نفس زوج
الاختبارات الذي يغطي جسر core-api في apps/core-api/tests/integration/
test_redis_bridge_real_modules.py (الطرف المستقبِل)."""
import json

import pytest
import redis.asyncio as aioredis

from platform_core.redis_events import EVENTS_CHANNEL, publish_event

pytestmark = pytest.mark.asyncio


async def _redis_available() -> bool:
    try:
        client = aioredis.from_url("redis://localhost:6379/1")
        await client.ping()
        await client.aclose()
        return True
    except Exception:  # noqa: BLE001 — فحص توفّر Redis فقط: أي فشل يعني "تخطَّ الاختبار"
        return False


async def test_publish_event_sends_correct_envelope_on_shared_channel():
    if not await _redis_available():
        pytest.skip("Redis غير متاح في بيئة التشغيل الحالية")

    subscriber = aioredis.from_url("redis://localhost:6379/1")
    pubsub = subscriber.pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)

    # نستهلك رسالة الاشتراك الأولى (confirmation) قبل النشر
    await pubsub.get_message(timeout=1.0)

    await publish_event("InvoiceDraftReady", {"draft_id": "unit-test-001", "confidence": 0.9})

    message = await pubsub.get_message(timeout=3.0)
    while message is not None and message.get("type") != "message":
        message = await pubsub.get_message(timeout=3.0)

    await pubsub.unsubscribe(EVENTS_CHANNEL)
    await pubsub.aclose()
    await subscriber.aclose()

    assert message is not None, "لم تصل أي رسالة عبر Redis خلال المهلة"
    envelope = json.loads(message["data"])
    assert envelope["event"] == "InvoiceDraftReady"
    assert envelope["payload"]["draft_id"] == "unit-test-001"
    assert envelope["source"] == "ai-platform"
