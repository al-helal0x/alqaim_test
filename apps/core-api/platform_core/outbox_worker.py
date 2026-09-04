"""Outbox Worker — تنفيذ #6×#11×#12×#10، Track 1.

Task طويل الأمد (asyncio) يُشغَّل من `lifespan` في `main.py` (نفس نمط
`start_redis_bridge()`/`stop_redis_bridge()` الموجود مسبقاً): يستطلع
(poll) صفوف `outbox_events` بحالة `pending` كل ثانيتين، لكل صف يستدعي
`EventBus.publish(event_name, payload)` الفعلي (عبر `get_event_bus()` —
نفس نقطة الحقن التي أرساها Task #6-S1)، ثم يُحدِّث الصف لحالة `dispatched`
مع `dispatched_at`. عند فشل أي معالج: زيادة `attempts`، تسجيل `last_error`،
وإعادة جدولة عبر `next_attempt_at` بـ Exponential Backoff
(`min(30 * 2**attempts, 3600)` ثانية — مطابق حرفياً لِـ§9.1 من
`ALQAIM_V2_MASTER_EXECUTION_PLAN.md`). بعد `MAX_ATTEMPTS=8` محاولات فاشلة:
الصف يتحوّل نهائياً لحالة `failed` ويتوقف عن إعادة المحاولة — يبقى في
الجدول (لا حذف) لتدخل يدوي، بدل الاستطلاع الصامت إلى الأبد.

⚠️ لا يعدّل `event_bus.py` — يستهلكه فقط عبر `get_event_bus()` (أُغلق هذا
الملف في Task #6-S1، لا يُعاد فتحه هنا).

── TASK-06-02 (تصحيح، 2026-08-13) ──────────────────────────────────────────
النسخة السابقة من هذا الملف كانت تستخدم `min(2**attempts, 300)` بلا أي حد
لعدد المحاولات — الصف يبقى `pending` ويُعاد استطلاعه إلى الأبد حتى لو كان
فشله دائمياً (payload تالف مثلاً)، بمخالفة صريحة لبند "Failure handling" في
§9.1 من الخطة الرئيسية. صُحِّح هنا لصيغة العقد الحرفية: backoff
`min(30 * 2**attempts, 3600)`، وحد أقصى `MAX_ATTEMPTS=8` محاولات ثم
`status="failed"` نهائياً. لم يُغيَّر `POLL_INTERVAL_SECONDS` (لا يزال
ثانيتين لا 15 كما ورد في الخطة) — فرق استطلاع أسرع فقط، غير مرتبط بمشكلة
الموثوقية المُصلَحة هنا، تُرِك كقرار منفصل غير محسوم عمداً.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from platform_core.database import AsyncSessionLocal
from platform_core.event_bus import get_event_bus
from platform_core.outbox_models import OutboxEvent

logger = logging.getLogger("platform_core.outbox_worker")

POLL_INTERVAL_SECONDS = 2
MAX_ATTEMPTS = 8  # §9.1: بعد هذا العدد من المحاولات الفاشلة → status="failed" نهائياً
BASE_BACKOFF_SECONDS = 30
MAX_BACKOFF_SECONDS = 3600  # ساعة — سقف §9.1 الحرفي (30 * 2**attempts, حتى 3600)

_worker_task: asyncio.Task | None = None


async def _dispatch_one(session, row: OutboxEvent) -> None:
    """يحاول تسليم صف واحد. أي استثناء من أي معالج مشترك يُعامَل كفشل
    تسليم كامل للصف (نفس دلالة `EventBus.publish` التي تُشغّل كل المشتركين
    تباعاً) — لا تسليم جزئي مُسجَّل كـ dispatched.

    عند الفشل: `attempts += 1`، ثم إما إعادة جدولة (`pending` +
    `next_attempt_at`) إن لم يبلغ `MAX_ATTEMPTS` بعد، أو `status="failed"`
    نهائياً إن بلغه — الصف يبقى في الجدول (لا حذف) لتدخل يدوي، ولا يُعاد
    استطلاعه بعدها (`_poll_once` يُصفّي على `status == "pending"` فقط)."""
    try:
        await get_event_bus().publish(row.event_name, row.payload)
    except Exception as exc:  # noqa: BLE001 — نلتقط أي فشل من أي معالج مشترك عمداً
        row.attempts += 1
        row.last_error = str(exc)[:2000]
        if row.attempts >= MAX_ATTEMPTS:
            row.status = "failed"
            logger.error(
                "توقف تسليم حدث outbox '%s' (id=%s) نهائياً بعد %d محاولة فاشلة — "
                "يحتاج تدخلاً يدوياً: %s",
                row.event_name, row.id, row.attempts, exc,
            )
        else:
            backoff = min(BASE_BACKOFF_SECONDS * 2**row.attempts, MAX_BACKOFF_SECONDS)
            row.next_attempt_at = datetime.now(UTC) + timedelta(seconds=backoff)
            logger.warning(
                "فشل تسليم حدث outbox '%s' (id=%s, المحاولة #%d/%d): %s",
                row.event_name, row.id, row.attempts, MAX_ATTEMPTS, exc,
            )
    else:
        row.status = "dispatched"
        row.dispatched_at = datetime.now(UTC)
    await session.commit()


async def _poll_once() -> None:
    async with AsyncSessionLocal() as session:
        now = datetime.now(UTC)
        stmt = (
            select(OutboxEvent)
            .where(
                OutboxEvent.status == "pending",
                (OutboxEvent.next_attempt_at.is_(None)) | (OutboxEvent.next_attempt_at <= now),
            )
            .order_by(OutboxEvent.created_at)
        )
        rows = (await session.execute(stmt)).scalars().all()
        for row in rows:
            await _dispatch_one(session, row)


async def _run_loop() -> None:
    while True:
        try:
            await _poll_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("عطل غير متوقَّع في دورة استطلاع outbox_worker")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def start_outbox_worker() -> None:
    """يُستدعى عند إقلاع FastAPI (`lifespan` في main.py)."""
    global _worker_task
    _worker_task = asyncio.create_task(_run_loop())


async def stop_outbox_worker() -> None:
    """يُستدعى عند إغلاق FastAPI — إغلاق نظيف بدل قتل فوري."""
    global _worker_task
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
