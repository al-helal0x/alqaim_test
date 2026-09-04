"""إعداد بيئة اختبار عبر SQLite في الذاكرة (aiosqlite) بدلاً من Postgres —
للتحقق السريع من منطق الأعمال محلياً دون حاجة لبنية تحتية. الإنتاج يستخدم
Postgres حصراً كما في platform_core/database.py.
"""
import uuid

import pytest_asyncio
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.types import CHAR, TypeDecorator


# SQLite لا يدعم UUID/asyncpg-only features — نستبدل نوع العمود وقت الاختبار فقط
class _SQLiteUUID(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None


def _swap_pg_only_types_for_sqlite() -> None:
    """يستبدل UUID/JSONB بنوعين متوافقين مع SQLite على *كل* عمود مسجَّل حالياً
    في `Base.metadata` — عبر `with_variant()` (وليس استبدال `col.type` مباشرة).

    ── ثلاثة إصلاحات حقيقية هنا (كلها اكتُشفت بتشغيل pytest فعلياً على بيئة
    حقيقية، لا بالقراءة) ─────────────────────────────────────────────────

    1) استبدال `PGUUID.__init__` بدالة no-op على مستوى الـ *class* بأكمله
       يجعل أي `UUID(as_uuid=True)` جديد يُنشَأ لاحقاً في نفس العملية يفتقد
       `native_uuid`، فيفشل بـ `AttributeError` عند أول compile. **لا حاجة
       لمس __init__ إطلاقاً.**

    2) استبدال `Uuid.bind_processor` على مستوى الـ class تساهلاً مع IDs
       كنصوص خام يُصلِح مشاكل UUID الفردية، لكنه يُفسِد صفوفاً كاملة تحت
       `insertmanyvalues` (قيم تنتقل لأعمدة خاطئة).

    3) استبدال `col.type` مباشرة (`col.type = _SQLiteUUID()`) يُغيِّر كائن
       العمود المشترك في `Base.metadata` *بشكل دائم لعمر العملية بأكملها*،
       وليس فقط لمحرك SQLite المحلي. كل الاختبارات هنا تستخدم SQLite
       في-الذاكرة فقط، ما عدا `test_redis_bridge_real_modules.py` الذي يفتح
       جلسة حقيقية على Postgres الفعلي عبر
       `platform_core.database.AsyncSessionLocal` — وهذا الاختبار كان يفشل
       بـ `DatatypeMismatchError: column "id" is of type uuid but expression
       is of type character varying` لأن عمود UUID كان قد استُبدل مسبقاً
       بنوع SQLite بمجرد تشغيل أي اختبار SQLite آخر في نفس العملية، فبقي
       "عالقاً" هكذا حتى عند الاتصال بـ Postgres الحقيقي لاحقاً.
       `with_variant("sqlite")` يحل هذا جذرياً: يبقي تصريف Postgres كما هو
       تماماً (UUID/JSONB أصليين)، ويستبدل فقط عند التصريف لـ SQLite
       تحديداً — بلا أي تسريب بين المحركين. هذا نفس الأسلوب الذي يستخدمه
       `OutboxEvent.payload` أصلاً (`JSONB().with_variant(JSON(), "sqlite")`،
       راجع `outbox_models.py`).
    """
    from shared_kernel.db_base import Base

    for table in Base.metadata.tables.values():
        for col in table.columns:
            # with_variant في SQLAlchemy 2.0 يُعدِّل نوع العمود في مكانه (لا
            # يُغلِّفه بكائن منفصل) — استدعاء ثانٍ على نفس العمود يفشل بـ
            # `ArgumentError: Dialect 'sqlite' is already present`. الفحص هنا
            # لكل عمود على حدة (لا علم عام لمرة واحدة فقط) يضمن أن أي
            # عمود/جدول جديد يُسجَّل لاحقاً في `Base.metadata` يُستبدَل نوعه
            # أيضاً، بلا محاولة استبدال عمود سبق استبداله فعلاً.
            already_swapped = "sqlite" in getattr(col.type, "_variant_mapping", {})
            if already_swapped:
                continue
            if isinstance(col.type, PGUUID) or type(col.type).__name__ == "UUID":
                col.type = col.type.with_variant(_SQLiteUUID(), "sqlite")
            elif isinstance(col.type, JSONB):
                col.type = col.type.with_variant(JSON(), "sqlite")


# ── Task #6-S1 — Event Bus Lifecycle & Dependency Injection ────────────────
# EventBus جديد تماماً لكل اختبار — بلا تسريب state (مشتركين) بين
# الاختبارات، وبلا حساسية لترتيب التشغيل (معيار القبول #1 و#3 في
# README_المهمة.md). `autouse=True` عمداً: عزل EventBus يجب أن يكون
# خاصية بيئة الاختبار نفسها، وليس شيئاً يعتمد على أن يطلبه كل اختبار
# صراحةً — فهذا بالضبط ما كان مفقوداً سابقاً (main.py كان يُسجِّل
# مشتركين دائمين على event_bus عالمي بمجرد أن يستورده أي اختبار، مباشرة
# أو عبر سلسلة استيراد).
@pytest_asyncio.fixture(autouse=True)
async def _isolated_event_bus():
    from platform_core.event_bus import EventBus, reset_event_bus, set_event_bus

    bus = EventBus()
    token = set_event_bus(bus)
    try:
        yield bus
    finally:
        reset_event_bus(token)


@pytest_asyncio.fixture
async def event_bus(_isolated_event_bus):
    """اسم صريح لأي اختبار يريد الوصول لنفس EventBus المعزول لهذا الاختبار
    (مثلاً للتحقق من أن حدثاً مُعيَّناً نُشر فعلاً). نفس الكائن الذي
    `_isolated_event_bus` (autouse) أنشأه وربطه بالسياق — هذا الاسم بديل
    مقروء فقط، لا ينشئ EventBus ثانياً."""
    return _isolated_event_bus


@pytest_asyncio.fixture
async def db_session():
    from modules.accounting.infrastructure.models import accounting_models  # noqa: F401

    # ▲▲▲ نهاية إضافة مهمة 6 ▲▲▲
    # ▼▼▼ العضو 12: إضافة مطلوبة ▼▼▼
    from modules.audit.infrastructure.models import audit_models  # noqa: F401
    from modules.catalog.infrastructure.models import catalog_models  # noqa: F401
    from modules.data_migration.infrastructure.models import data_migration_models  # noqa: F401
    from modules.documents.infrastructure.models import documents_models  # noqa: F401
    from modules.identity.infrastructure.models import identity_models  # noqa: F401
    from modules.integrations.infrastructure.models import integrations_models  # noqa: F401
    from modules.inventory.infrastructure.models import inventory_models  # noqa: F401
    from modules.notifications.infrastructure.models import notifications_models  # noqa: F401
    from modules.partners.infrastructure.models import partner_models  # noqa: F401
    from modules.payments.infrastructure.models import payments_models  # noqa: F401
    from modules.pos.infrastructure.models import pos_models  # noqa: F401
    from modules.purchasing.infrastructure.models import purchasing_models  # noqa: F401
    from modules.sales.infrastructure.models import sales_models  # noqa: F401
    from modules.taxation.infrastructure.models import taxation_models  # noqa: F401
    from modules.tenancy.infrastructure.models import tenancy_models  # noqa: F401
    from modules.workflow.infrastructure.models import workflow_models  # noqa: F401

    # ▼▼▼ مهمة 6: إضافة مطلوبة (Outbox Pattern) ▼▼▼
    from platform_core import outbox_models  # noqa: F401

    # ▲▲▲ نهاية إضافة العضو 12 ▲▲▲
    from shared_kernel.db_base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    _swap_pg_only_types_for_sqlite()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()
