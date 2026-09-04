"""أقوى من test_redis_event_bridge.py: يستخدم فعلياً `start_redis_bridge`/
`stop_redis_bridge` الحقيقيتين من platform_core/redis_bridge.py (نفس الكود
المُشغَّل في main.py)، وينشر الحدث عبر **عملية Python منفصلة فعلياً** تُشغِّل
`ai-platform/platform_core/redis_events.publish_event` الحقيقية — محاكاة
حقيقية لواقع الإنتاج (عمليتان منفصلتان)، وليس استيراداً وهمياً داخل نفس
المُفسِّر (وهو مستحيل فعلياً هنا لأن كلا الخدمتين تُسمّيان حزمتهما الداخلية
`platform_core` بنفس الاسم — تعارض أسماء حقيقي لا يظهر إلا بمحاكاة عمليتين
منفصلتين كما في الإنتاج الفعلي)."""
import asyncio
import subprocess
import sys
from pathlib import Path

import pytest

from platform_core.event_bus import event_bus
from platform_core.redis_bridge import start_redis_bridge, stop_redis_bridge

pytestmark = pytest.mark.asyncio

AI_PLATFORM_PATH = Path(__file__).resolve().parents[3] / "ai-platform"

_PUBLISHER_SCRIPT = """
import asyncio, sys
sys.path.insert(0, {ai_platform_path!r})
from platform_core.redis_events import publish_event

asyncio.run(publish_event("InvoiceDraftReady", {{
    "draft_id": "subprocess-draft-001",
    "company_id": "subprocess-company-001",
    "confidence": 0.66,
}}))
"""


async def _redis_available() -> bool:
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url("redis://localhost:6379/0")
        await client.ping()
        await client.aclose()
        return True
    except Exception:
        return False


async def _database_available() -> bool:
    """مهمة 6: redis_bridge يكتب الحدث الوارد عبر outbox_events (نفس ضمانات
    Outbox) قبل تسليمه — أصبح هذا الاختبار يحتاج Postgres حقيقياً متاحاً على
    settings.database_url، وليس Redis فقط."""
    try:
        from sqlalchemy import text

        from platform_core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def test_real_bridge_receives_event_from_separate_ai_platform_process():
    if not await _redis_available():
        pytest.skip("Redis غير متاح في بيئة التشغيل الحالية")
    if not AI_PLATFORM_PATH.exists():
        pytest.skip("مجلد apps/ai-platform غير موجود بجانب core-api في هذه البيئة")

    received: list[dict] = []

    async def _handler(payload: dict) -> None:
        received.append(payload)

    event_bus.subscribe("InvoiceDraftReady", _handler)
    start_redis_bridge()
    await asyncio.sleep(0.3)  # مهلة اشتراك الجسر فعلياً على القناة قبل النشر

    try:
        script = _PUBLISHER_SCRIPT.format(ai_platform_path=str(AI_PLATFORM_PATH))
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"فشل سكربت النشر: {result.stderr}"

        for _ in range(30):  # حتى 3 ثوانٍ انتظار — استلام غير متزامن عبر Pub/Sub
            if received:
                break
            await asyncio.sleep(0.1)
    finally:
        await stop_redis_bridge()

    assert len(received) == 1
    assert received[0]["draft_id"] == "subprocess-draft-001"
    assert received[0]["company_id"] == "subprocess-company-001"
