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


PGUUID.__init__ = lambda self, as_uuid=True: None  # no-op, we swap compile below


@pytest_asyncio.fixture
async def db_session():
    from modules.accounting.infrastructure.models import accounting_models  # noqa: F401

    # ▲▲▲ نهاية إضافة مهمة 6 ▲▲▲
    # ▼▼▼ العضو 12: إضافة مطلوبة ▼▼▼
    from modules.audit.infrastructure.models import audit_models  # noqa: F401
    from modules.catalog.infrastructure.models import catalog_models  # noqa: F401
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

    # نستبدل تعريف نوع العمود لكل الجداول بنوع متوافق مع SQLite قبل create_all
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PGUUID) or type(col.type).__name__ == "UUID":
                col.type = _SQLiteUUID()
            elif isinstance(col.type, JSONB):
                col.type = JSON()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()
