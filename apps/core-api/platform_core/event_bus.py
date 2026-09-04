"""Event Bus داخلي (In-process) مع نمط Outbox — القسم 6.6 من الوثيقة.

- المرحلة الحالية (Modular Monolith): نشر داخل نفس العملية.
- الأحداث تُكتب أولاً في جدول outbox_events ضمن نفس معاملة قاعدة البيانات
  (لضمان عدم فقدان الحدث)، ثم تُنشر لاحقاً للمشتركين.
- عند الانتقال مستقبلاً لـ Microservices: يُستبدل الناقل الداخلي بـ
  Message Broker خارجي (RabbitMQ/Kafka) دون تغيير منطق الوحدات نفسها.

── Task #6-S1 — Event Bus Lifecycle & Dependency Injection ─────────────────
`EventBus` لم يعد Singleton عالمي يُنشأ عند وقت الاستيراد (كان هذا سبب
تسرّب المشتركين بين الاختبارات — راجع README_المهمة.md وADR-001 القرار 6).

الملكية أصبحت صريحة (Dependency Injection):
  • الإنتاج: `main.py` ينشئ EventBus واحد Application-scoped داخل `lifespan`
    ويربطه بالسياق عبر `set_event_bus()` قبل تسجيل أي اشتراك.
  • الاختبارات: fixture في `conftest.py` تنشئ EventBus جديد تماماً لكل
    اختبار وتربطه بنفس الآلية، ثم تُعيد ضبط السياق عند الانتهاء — بلا أي
    state مشترك بين اختبار وآخر، بصرف النظر عن ترتيب التشغيل.

`event_bus` (الاسم المُصدَّر أسفل الملف) بقي متاحاً للاستيراد المباشر
(`from platform_core.event_bus import event_bus`) حفاظاً على كل نقاط
الاستدعاء الحالية في `modules/*` (خارج حدود هذه المهمة، راجع README) —
لكنه الآن Facade خفيف يُفوِّض كل استدعاء إلى الـ EventBus الفعّال في
السياق الحالي (Context-scoped عبر `contextvars`)، وليس كائناً عالمياً
واحداً تتراكم عليه الاشتراكات إلى الأبد. لا حاجة لتعديل أي ملف من
`modules/*` كي تعمل هذه الآلية.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Coroutine
from contextvars import ContextVar, Token
from typing import Any

EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    """Skeleton أولي — يُستكمل بآلية Outbox الفعلية قبل نهاية المرحلة 0.

    سلوك الصنف نفسه (subscribe/publish) لم يتغيّر إطلاقاً عن النسخة
    السابقة — التعديل الوحيد في هذه المهمة هو **كيف تُصنَع وتُملَك
    النسخة (instance)**، وليس ما تفعله.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._subscribers[event_name].append(handler)

    async def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        # TODO: كتابة الحدث في outbox_events ضمن نفس المعاملة قبل النشر الفعلي.
        for handler in self._subscribers.get(event_name, []):
            await handler(payload)


# ── Dependency Injection: مُزوِّد الـ EventBus الفعّال للسياق الحالي ──────
#
# لماذا ContextVar وليس متغيّر global عادي؟ لأن `event_bus` (الـ Facade
# أسفل الملف) يُستورَد مرة واحدة فقط في كل عملية Python (تخزين الاستيراد
# المعتاد)، لكن الكائن الذي يُفوَّض إليه فعلياً يجب أن يختلف باختلاف
# السياق: طلب HTTP واحد في الإنتاج يستخدم EventBus التطبيق، بينما كل
# اختبار (قد يعمل بالتوازي مستقبلاً عبر pytest-xdist) يحتاج EventBus خاصاً
# به فقط. ContextVar يعطي هذا العزل تلقائياً بلا قفل (lock) وبلا حالة
# عالمية متبقية بعد انتهاء السياق.
_current_event_bus: ContextVar[EventBus | None] = ContextVar(
    "_current_event_bus", default=None
)


def set_event_bus(bus: EventBus) -> Token:
    """يربط `bus` كـ EventBus الفعّال للسياق الحالي.

    يُستدعى مرة واحدة عند بداية السياق (Application lifespan في main.py،
    أو fixture لكل اختبار في conftest.py). يُعيد Token يُستخدم مع
    `reset_event_bus()` لإنهاء السياق بنظافة (اختبار → اختبار آخر، أو
    إيقاف التطبيق).
    """
    return _current_event_bus.set(bus)


def reset_event_bus(token: Token) -> None:
    """يُلغي ربط EventBus عند نهاية السياق (teardown)."""
    _current_event_bus.reset(token)


def get_event_bus() -> EventBus:
    """المُزوِّد (Provider) الرسمي — نقطة الحقن الوحيدة. تُستخدم من:
    - `main.py` عند تسجيل الاشتراكات (Wiring) في الإنتاج.
    - أي Use Case/Route يريد الاعتماد على الحقن الصريح (`Depends(get_event_bus)`
      في FastAPI) بدل الاستيراد المباشر لـ `event_bus` أدناه.

    يرفع RuntimeError صريحاً إن لم يُربَط أي EventBus بعد بالسياق الحالي —
    فشل سريع وواضح بدل نشر أحداث بصمت إلى لا مكان (سلوك خطير أسوأ من
    استثناء صريح عند الإقلاع الخاطئ).
    """
    bus = _current_event_bus.get()
    if bus is None:
        raise RuntimeError(
            "لا يوجد EventBus فعّال لهذا السياق. يجب استدعاء set_event_bus() "
            "أولاً — في main.py (lifespan التطبيق) للإنتاج، أو عبر fixture "
            "الاختبارات (conftest.py) لبيئة الاختبار."
        )
    return bus


class _EventBusFacade:
    """Facade يحافظ على توافق كل استيراد قديم لـ `event_bus` دون تعديل أي
    ملف استهلاك (`modules/*` خارج حدود هذه المهمة) — كل استدعاء يُفوَّض
    فعلياً إلى `get_event_bus()`، أي إلى نسخة EventBus المرتبطة بالسياق
    الحالي فقط، وليس إلى كائن عالمي واحد ثابت طوال عمر العملية."""

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        get_event_bus().subscribe(event_name, handler)

    async def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        await get_event_bus().publish(event_name, payload)


# يبقى قابلاً للاستيراد كما كان: `from platform_core.event_bus import event_bus`
# — لكنه الآن Facade خفيف (انظر أعلاه)، وليس Singleton عالمي مُنشأ عند وقت
# الاستيراد. لا يوجد أي استدعاء subscribe()/publish() يُنفَّذ هنا عند
# الاستيراد بعد الآن.
event_bus = _EventBusFacade()

# أمثلة أسماء أحداث مثبَّتة من "يوم العقود" (انظر docs/architecture/contracts.md):
# - "InvoicePosted"           {invoice_id, total, currency, partner_id}
# - "InvoiceDraftReady"       (من ai-platform إلى Purchasing)
# - "AccountSettingsChanged"  (يُبطل كاش الإعدادات)
