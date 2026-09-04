"""ناشر أحداث عبر Redis Pub/Sub — الجسر الفعلي بين عمليتي `ai-platform`
و`core-api` المنفصلتين فيزيائياً (القسم 6.6/7.10).

هذا يُغلق فعلياً الفجوة الموثَّقة سابقاً في `workers/tasks.py` وفي
`docs/architecture/contracts.md` §4: "آلية نشر حدث InvoiceDraftReady...
لا تزال TODO". القرار المُتخَذ الآن (بالتنسيق مع العضو 1 عبر
`core-api/platform_core/redis_bridge.py`): **قناة Redis Pub/Sub واحدة
مشتركة** (`alqaim:events`) تحمل مغلَّفاً JSON بالشكل:

    {"event": "<اسم الحدث>", "payload": {...}, "published_at": "...", "source": "ai-platform"}

يستمع `core-api` لهذه القناة في الخلفية (Background Task عند الإقلاع)
ويُعيد بثّها محلياً عبر `event_bus` الداخلي — بحيث تبقى بقية الوحدات
(purchasing لاحقاً) تشترك بنفس الطريقة المعتادة (`event_bus.subscribe`)
دون أي معرفة بوجود Redis أصلاً خلف الكواليس.

**لماذا Pub/Sub وليس Celery/طابور مهام:** الأحداث هنا إشعارات "حدث شيء"
(Fire-and-forget, لا يحتاج المُرسِل تأكيد استلام) وليست مهام يجب ضمان
تنفيذها حتى لو كان المستهلك غير متصل حالياً — ذلك ما يُستخدَم من أجله
Celery أصلاً في `workers/tasks.py` لمهمة OCR نفسها. عند الحاجة لضمان
تسليم أقوى مستقبلاً (لا فقدان حدث حتى لو كان core-api متوقفاً وقت النشر)
يُستبدَل هذا بـ Redis Streams أو ناقل رسائل حقيقي (RabbitMQ/Kafka) دون
تغيير واجهة `publish_event` نفسها.
"""
import json
import logging
from datetime import UTC, datetime

import redis.asyncio as aioredis

from platform_core.config import get_settings

logger = logging.getLogger("ai_platform.redis_events")

EVENTS_CHANNEL = "alqaim:events"


def _serialize(event_name: str, payload: dict) -> str:
    return json.dumps(
        {
            "event": event_name,
            "payload": payload,
            "published_at": datetime.now(UTC).isoformat(),
            "source": "ai-platform",
        },
        default=str,  # UUID/Decimal في الحمولة تُحوَّل لنص تلقائياً
    )


async def publish_event(event_name: str, payload: dict) -> None:
    """ينشر حدثاً على القناة المشتركة. فشل النشر (Redis غير متاح مثلاً) يُسجَّل
    في اللوق ولا يُسقِط خط أنابيب OCR نفسه — استخراج الفاتورة نجح فعلياً
    بصرف النظر عن نجاح إشعار core-api به (فصل صريح بين الاثنين)."""
    settings = get_settings()
    client = aioredis.from_url(settings.redis_url)
    try:
        await client.publish(EVENTS_CHANNEL, _serialize(event_name, payload))
    except Exception:
        logger.exception("فشل نشر الحدث '%s' على Redis — العملية الأساسية غير متأثرة", event_name)
    finally:
        await client.aclose()
