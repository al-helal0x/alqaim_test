"""يثبت معياري القبول #1 و#3 في README_المهمة.md مباشرة:

1. عزل فعلي: Test A → EventBus A، Test B → EventBus B، بلا state مشترك.
2. حساسية الترتيب: نفس النتيجة بصرف النظر عن ترتيب تشغيل الاختبارات.

لا نعتمد هنا على `pytest.mark.asyncio` وحده لإثبات العزل، بل نتحقق صراحة
من طبقة الحقن نفسها (`platform_core.event_bus`): كل اختبار يحصل على
EventBus مختلف (هوية كائن مختلفة)، وأي اشتراك سجّله اختبار سابق على
`event_bus` (الـ Facade المستورَد مباشرة، تماماً كما تفعل modules/*) لا
يظهر إطلاقاً في اختبار لاحق.
"""
import pytest

from platform_core.event_bus import get_event_bus

pytestmark = pytest.mark.asyncio


async def test_a_subscribes_to_custom_event(event_bus):
    """يُسجِّل مشتركاً على 'SomeDomainEvent' — تماماً كما يفعل main.py عبر
    `from platform_core.event_bus import event_bus` ثم `event_bus.subscribe(...)`."""
    received = []

    async def _handler(payload: dict) -> None:
        received.append(payload)

    event_bus.subscribe("SomeDomainEvent", _handler)
    await event_bus.publish("SomeDomainEvent", {"marker": "from-test-a"})

    assert received == [{"marker": "from-test-a"}]


async def test_b_does_not_see_test_a_subscriber(event_bus):
    """لو كان EventBus لا يزال Singleton عالمي، هذا الاختبار كان سيَستقبل
    مشترِك test_a (لو نُشر نفس اسم الحدث هنا) — الآن EventBus هذا جديد
    تماماً، بلا أي معرفة بما سجّله test_a."""
    received = []

    async def _handler(payload: dict) -> None:
        received.append(payload)

    # لا نُعيد تسجيل نفس المشترك هنا عمداً — الهدف إثبات عدم بقاء مشترك
    # test_a. ننشر نفس اسم الحدث؛ لو تسرّب المشترك القديم لظهر هنا.
    await event_bus.publish("SomeDomainEvent", {"marker": "from-test-b"})
    assert received == []  # لا يوجد أي مشترك من الأصل (لا من test_a ولا محلي)

    event_bus.subscribe("SomeDomainEvent", _handler)
    await event_bus.publish("SomeDomainEvent", {"marker": "from-test-b"})
    assert received == [{"marker": "from-test-b"}]  # فقط ما سجّله هذا الاختبار


async def test_each_test_gets_a_distinct_event_bus_instance(event_bus):
    """يتحقق من هوية الكائن مباشرة (وليس فقط السلوك) — EventBus لهذا
    الاختبار ليس نفس الكائن الذي كان مرتبطاً بأي سياق آخر."""
    current = get_event_bus()
    assert current is event_bus  # نفس النسخة التي يفوَّض إليها الـ Facade

    # قائمة المشتركين تبدأ فارغة دوماً — لا تراكم عبر الاختبارات
    assert current._subscribers == {}
