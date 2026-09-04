"""Event Bus داخلي (In-process) مع نمط Outbox — القسم 6.6 من الوثيقة، مهمة 6.

- المرحلة الحالية (Modular Monolith): نشر داخل نفس العملية.
- كل حدث يُكتَب أولاً في جدول outbox_events (platform_core/outbox_models.py)
  ضمن **نفس معاملة قاعدة البيانات** التي أنتجته: EventBus.publish لا يعمل
  commit بنفسه، بل session.add + flush فقط — على المستدعي أن يستدعيها *قبل*
  commit العملية التجارية (نفس الجلسة/session)، ثم commit العادي يحفظ الاثنين
  معاً بشكل ذرّي (إما كلاهما يُحفَظ أو لا شيء).
- بعد الـ commit: محاولة تسليم فورية (best effort) عبر dispatch_pending، ثم
  Worker دوري (platform_core/outbox_worker.py) كشبكة أمان لأي حدث لم يُسلَّم
  (فشل مؤقت في أحد المشتركين، أو تعطّل العملية قبل المحاولة الفورية).
- عند الانتقال مستقبلاً لـ Microservices: يُستبدل التسليم المحلي بـ
  Message Broker خارجي (RabbitMQ/Kafka)، لكن جدول outbox_events والمعاملة
  الذرّية يبقيان كما هما — هذا بالضبط ما يجعل Outbox مستقلاً عن ناقل النقل.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.outbox_models import OutboxEvent, OutboxEventStatus

logger = logging.getLogger("platform_core.event_bus")

EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]

# سقف عدد المحاولات قبل أن يُعتبَر الحدث "failed" ويتوقف عن إعادة المحاولة
# التلقائية (يبقى مسجّلاً في outbox_events لتدخّل يدوي/تنبيه لاحقاً).
DEFAULT_MAX_ATTEMPTS = 8
# سقف Backoff الأسّي بين المحاولات (لا يتجاوز ساعة واحدة بين محاولتين).
MAX_BACKOFF_SECONDS = 3600


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._subscribers[event_name].append(handler)

    async def publish(
        self, session: AsyncSession, event_name: str, payload: dict[str, Any]
    ) -> OutboxEvent:
        """يكتب سطر outbox_events ضمن الجلسة المُمرَّرة **دون** commit — يجب
        استدعاؤها قبل commit عملية الأعمال في نفس الـ use case، حتى يُحفَظ
        الحدث ذرّياً مع التغيير الذي أنتجه. لا تستدعِ هذه الدالة بعد commit؛
        عندها لا ضمان للذرّية (بالضبط ما كان يحدث قبل مهمة 6)."""
        event = OutboxEvent(event_name=event_name, payload=payload)
        session.add(event)
        await session.flush()
        return event

    async def dispatch_pending(
        self,
        session: AsyncSession,
        *,
        batch_size: int = 100,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> int:
        """تُقرأ الأحداث pending المستحقة (next_attempt_at <= الآن)، تُحاوَل
        تسليمها للمشتركين المحليين، ويُحدَّث status/attempts/last_error حسب
        النتيجة، ثم commit على نفس الجلسة. تُستدعى مرتين:
        1) فوراً بعد commit عملية الأعمال (محاولة تسليم بأقل تأخير ممكن).
        2) من outbox_worker.py دورياً كشبكة أمان لأي حدث لم يُسلَّم.
        تُعيد عدد الأحداث التي تم تسليمها بنجاح في هذه الدفعة."""
        now = datetime.now(UTC)
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.status == OutboxEventStatus.PENDING.value)
            .where(OutboxEvent.next_attempt_at <= now)
            .order_by(OutboxEvent.created_at)
            .limit(batch_size)
        )
        events = (await session.execute(stmt)).scalars().all()

        dispatched_count = 0
        for event in events:
            handlers = self._subscribers.get(event.event_name, [])
            try:
                for handler in handlers:
                    await handler(event.payload)
            except Exception as exc:  # noqa: BLE001 — فشل مشترك واحد لا يُسقط الدفعة كلها
                event.attempts += 1
                event.last_error = str(exc)[:2000]
                if event.attempts >= max_attempts:
                    event.status = OutboxEventStatus.FAILED.value
                    logger.error(
                        "حدث outbox %s ('%s') تجاوز الحد الأقصى للمحاولات (%s): %s",
                        event.id, event.event_name, max_attempts, exc,
                    )
                else:
                    backoff = min(30 * (2 ** event.attempts), MAX_BACKOFF_SECONDS)
                    event.next_attempt_at = now + timedelta(seconds=backoff)
                    logger.warning(
                        "فشل تسليم حدث outbox %s ('%s') — محاولة %s/%s، إعادة بعد %ss: %s",
                        event.id, event.event_name, event.attempts, max_attempts, backoff, exc,
                    )
            else:
                event.status = OutboxEventStatus.DISPATCHED.value
                event.dispatched_at = now
                dispatched_count += 1

        if events:
            await session.commit()
        return dispatched_count


event_bus = EventBus()

# أمثلة أسماء أحداث مثبَّتة من "يوم العقود" (انظر docs/architecture/contracts.md):
# - "InvoicePosted"           {invoice_id, total, currency, partner_id, company_id}
# - "InvoiceDraftReady"       (من ai-platform إلى Purchasing، عبر redis_bridge.py)
# - "AccountSettingsChanged"  (يُبطل كاش الإعدادات)
# - "PaymentRecorded"
# - "FiscalPeriodClosed"
