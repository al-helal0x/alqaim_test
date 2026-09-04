"""Worker دوري لإعادة محاولة أحداث outbox_events غير المُسلَّمة (مهمة 6،
القسم 6.6). شبكة أمان فقط: المسار السعيد هو تسليم فوري مباشرةً بعد commit
عملية الأعمال (event_bus.dispatch_pending المُستدعاة من use case نفسه) —
هذا Worker يلتقط ما تبقّى فقط: فشل مؤقت في مشترك، أو تعطّل العملية بين
commit التغيير التجاري وتنفيذ محاولة التسليم الفورية.

Modular Monolith حالياً → asyncio task بسيط داخل نفس عملية FastAPI (متماثل
مع نمط platform_core/redis_bridge.py: start/stop عبر lifespan في main.py).
عند الانتقال لـ Microservices يصبح Worker/Job منفصلاً (Celery beat أو
Kubernetes CronJob) دون تغيير منطق dispatch_pending نفسه.
"""
import asyncio
import logging

from platform_core.database import AsyncSessionLocal
from platform_core.event_bus import event_bus

logger = logging.getLogger("platform_core.outbox_worker")

# فاصل الاستطلاع بين كل دفعة ومحاولة الدفعة التالية.
POLL_INTERVAL_SECONDS = 15

_worker_task: asyncio.Task | None = None


async def _run_once() -> None:
    async with AsyncSessionLocal() as session:
        dispatched = await event_bus.dispatch_pending(session)
        if dispatched:
            logger.info("outbox worker: تم تسليم %s حدث(اً) متأخر(اً)", dispatched)


async def _poll_loop() -> None:
    while True:
        try:
            await _run_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("outbox worker: فشلت دورة استطلاع واحدة، سيُعاد المحاولة")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def start_outbox_worker() -> None:
    """يُستدعى عند إقلاع FastAPI (lifespan في main.py) — نفس نمط
    platform_core/redis_bridge.start_redis_bridge."""
    global _worker_task
    _worker_task = asyncio.create_task(_poll_loop())


async def stop_outbox_worker() -> None:
    """يُستدعى عند إغلاق FastAPI — إيقاف نظيف بدل قتل فوري."""
    global _worker_task
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
