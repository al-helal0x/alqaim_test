"""جسر Redis Pub/Sub — يلتقط الأحداث المنشورة من `ai-platform` (عملية
منفصلة فيزيائياً، القسم 6.12/7.10) على القناة المشتركة `alqaim:events`،
ويُعيد بثّها محلياً عبر `event_bus` الداخلي (platform_core/event_bus.py).

**هذا يُغلق فعلياً** الفجوة الموثَّقة منذ عدة دفعات في
`docs/architecture/contracts.md` §4 و`apps/ai-platform/workers/tasks.py`:
"آلية نشر InvoiceDraftReady بين العمليتين لا تزال TODO".

القرار المُتخَذ (بالتنسيق مع العضو 8 — انظر
`apps/ai-platform/platform_core/redis_events.py` للطرف الناشر): قناة واحدة
بمغلَّف JSON `{"event": ..., "payload": ..., "source": "ai-platform"}`،
بدل قناة منفصلة لكل نوع حدث — أبسط للاستماع، وتُبقي كل منطق التوجيه
(Routing) في نقطة واحدة هنا بدل تفريقه بين عدة قنوات.

بعد إعادة البث محلياً: أي Module يشترك بالطريقة المعتادة
(`event_bus.subscribe("InvoiceDraftReady", handler)`) دون أي معرفة بوجود
Redis أو ai-platform كعملية منفصلة أصلاً — التماثل الكامل مع الأحداث
المحلية الأخرى (مثل PaymentRecorded) مقصود ومطلوب (القسم 6.6).
"""
import asyncio
import json
import logging

import redis.asyncio as aioredis

from platform_core.config import get_settings
from platform_core.event_bus import event_bus

logger = logging.getLogger("platform_core.redis_bridge")

EVENTS_CHANNEL = "alqaim:events"

_listener_task: asyncio.Task | None = None
_redis_client: aioredis.Redis | None = None


async def _dispatch_envelope(raw_message: bytes | str) -> None:
    try:
        envelope = json.loads(raw_message)
        event_name = envelope["event"]
        payload = envelope["payload"]
    except (KeyError, TypeError, ValueError):
        logger.warning("رسالة مشوَّهة على قناة %s تم تجاهلها: %r", EVENTS_CHANNEL, raw_message)
        return

    logger.info(
        "استُلِم حدث عبر Redis Bridge: %s (source=%s)", event_name, envelope.get("source")
    )
    try:
        await event_bus.publish(event_name, payload)
    except Exception:
        logger.exception("فشل معالج محلي لحدث '%s' القادم عبر Redis", event_name)


async def _listen_loop() -> None:
    settings = get_settings()
    global _redis_client
    _redis_client = aioredis.from_url(settings.redis_url)
    pubsub = _redis_client.pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)
    logger.info("Redis event bridge مُشترِك فعلياً في القناة '%s'", EVENTS_CHANNEL)

    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue  # يتجاهل رسالة تأكيد الاشتراك نفسها
            await _dispatch_envelope(message["data"])
    except asyncio.CancelledError:
        pass  # إيقاف عادي عند إغلاق التطبيق — ليس خطأً
    finally:
        await pubsub.unsubscribe(EVENTS_CHANNEL)
        await pubsub.aclose()
        await _redis_client.aclose()


def start_redis_bridge() -> None:
    """يُستدعى عند إقلاع FastAPI (startup event في main.py)."""
    global _listener_task
    _listener_task = asyncio.create_task(_listen_loop())


async def stop_redis_bridge() -> None:
    """يُستدعى عند إغلاق FastAPI (shutdown event) — إغلاق نظيف بدل قتل فوري."""
    global _listener_task
    if _listener_task is not None:
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
        _listener_task = None
