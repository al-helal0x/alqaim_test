"""PKG-B2 — Tests Required (00_TASK_PACKAGE.md § PKG-B2), مستوى use case.

يبني على نفس بنية اختبار PKG-B1 (`test_walkin_partial_unique_index.py`):
يتطلب Postgres حقيقياً (`TEST_DATABASE_URL`) لأن استرداد السباق يعتمد فعلياً
على الفهرس الجزئي الفريد من PKG-B1، وليس على منطق تطبيقي وحده.

يغطي السيناريوهات الثلاثة من GATE-WI/PKG-B2 على مستوى use case مباشرة
(دون المرور بطبقة HTTP/auth — ذلك مغطّى في test_walkin_router.py):
  1) نداء متكرر لنفس الشركة → نفس هذا id دائماً، لا سجل جديد.
  2) سباق حقيقي (طلبان شبه-متزامنين على نفس الاتصال بقاعدة واحدة) → واحد
     ينجح، الآخر يعالج IntegrityError داخلياً ويُعيد نفس هذا id — لا استثناء
     يصل للمستدعي في أي من الحالتين.
  3) شركتان مختلفتان → كل واحدة تحصل على walk-in معزول تماماً (تُغطّى أيضاً
     في اختبار PKG-B1 على مستوى DB مباشرة؛ هنا على مستوى use case).
"""
import os
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from modules.partners.application.use_cases.partner_use_cases import (
    GetOrCreateWalkInPartnerUseCase,
)
from modules.partners.domain.rules import WALK_IN_PARTNER_NAME
from modules.partners.infrastructure.models.partner_models import Partner
from platform_core.auth_middleware import TenantContext

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not TEST_DATABASE_URL,
        reason=(
            "PKG-B2 walk-in recovery depends on the PKG-B1 partial unique index, "
            "which requires a real Postgres instance. Set TEST_DATABASE_URL to run "
            "this test (see module docstring)."
        ),
    ),
]

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


def _async_url(url: str) -> str:
    """يحوّل رابط sync (المستخدَم من alembic) لرابط async (المستخدَم من التطبيق)."""
    if url.startswith("postgresql+psycopg://") or url.startswith("postgresql://"):
        return url.replace("postgresql+psycopg://", "postgresql+asyncpg://").replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )
    return url


@pytest.fixture()
def async_engine():
    """`scope=\"module\"` (النسخة الأصلية من الحزمة المعزولة) يخلق محرك asyncpg
    واحداً يُعاد استخدامه عبر عدة اختبارات — لكن `pytest-asyncio` (وضع auto،
    نطاق الحلقة الافتراضي = function) يخلق حلقة أحداث event loop جديدة لكل
    دالة اختبار. محرك asyncpg مرتبط بحلقة الإنشاء الأولى فقط؛ استخدامه من
    حلقة اختبار لاحقة يفشل فعلياً بـ`InterfaceError: another operation is
    in progress` — تأكَّد هذا بالتشغيل الفعلي هنا عند الدمج (لم يُكتشَف في
    الحزمة المعزولة لأن اختباراتها لم تُشغَّل فعلياً هناك، Postgres غير متاح).
    الإصلاح: نطاق function بدل module — يعيد إنشاء المحرك (وتشغيل alembic
    upgrade السريع والآمن idempotent) لكل اختبار، فيبقى المحرك دائماً على
    نفس حلقة الاختبار الحالية."""
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(alembic_cfg, "head")

    eng = create_async_engine(_async_url(TEST_DATABASE_URL), future=True)
    yield eng


@pytest_asyncio.fixture
async def company_id(async_engine):
    new_id = uuid.uuid4()
    async with async_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "CREATE TABLE IF NOT EXISTS companies "
                "(id UUID PRIMARY KEY DEFAULT gen_random_uuid())"
            )
        )
        await conn.execute(sa.text("INSERT INTO companies (id, name, created_at, updated_at) VALUES (:id, :name, now(), now())"), {"id": new_id, "name": f"walkin-test-{new_id}"})
    return new_id


class TestGetOrCreateWalkInPartnerUseCase:
    async def test_repeated_calls_return_same_id_no_duplicate_row(self, async_engine, company_id):
        ctx = TenantContext(company_id=str(company_id), user_id="cashier-1")

        async with AsyncSession(async_engine) as session:
            first = await GetOrCreateWalkInPartnerUseCase(session).execute(ctx)
        async with AsyncSession(async_engine) as session:
            second = await GetOrCreateWalkInPartnerUseCase(session).execute(ctx)

        assert first.id == second.id
        assert first.name == WALK_IN_PARTNER_NAME
        assert first.is_system_managed is True

        async with AsyncSession(async_engine) as session:
            count = (
                await session.execute(
                    sa.select(sa.func.count())
                    .select_from(Partner)
                    .where(
                        Partner.company_id == company_id,
                        Partner.is_system_managed.is_(True),
                    )
                )
            ).scalar_one()
        assert count == 1, "لا يجب أن يوجد أكثر من صف walk-in واحد لنفس الشركة"

    async def test_concurrent_requests_one_wins_other_recovers_same_id(
        self, async_engine, company_id
    ):
        """سباق حقيقي: طلبان شبه-متزامنان، كلاهما لا يرى صفاً موجوداً وقت
        الفحص، ثم كلاهما يحاول الإدخال. أحدهما يفوز، والآخر يجب أن يتعافى
        عبر معالجة IntegrityError (الفهرس الجزئي من PKG-B1) بدل رفع خطأ
        للمستدعي."""
        ctx = TenantContext(company_id=str(company_id), user_id="cashier-race")

        session_a = AsyncSession(async_engine)
        session_b = AsyncSession(async_engine)
        try:
            uc_a = GetOrCreateWalkInPartnerUseCase(session_a)
            uc_b = GetOrCreateWalkInPartnerUseCase(session_b)

            # كلاهما يفحص قبل أن يُنشئ أي منهما شيئاً — يضمن سباقاً حقيقياً
            # لا مجرد تسلسل عرضي.
            assert await uc_a._find(ctx) is None
            assert await uc_b._find(ctx) is None

            result_a = await uc_a.execute(ctx)
            result_b = await uc_b.execute(ctx)

            assert result_a.id == result_b.id, (
                "لا فشل ظاهر للمستخدم في أي من الحالتين، وكلاهما يجب أن "
                "يشير لنفس صف walk-in النهائي"
            )
        finally:
            await session_a.close()
            await session_b.close()

    async def test_isolated_per_company(self, async_engine, company_id):
        other_company_id = uuid.uuid4()
        async with async_engine.begin() as conn:
            await conn.execute(
                sa.text("INSERT INTO companies (id, name, created_at, updated_at) VALUES (:id, :name, now(), now())"), {"id": other_company_id, "name": f"walkin-test-other-{other_company_id}"}
            )

        ctx_1 = TenantContext(company_id=str(company_id), user_id="u1")
        ctx_2 = TenantContext(company_id=str(other_company_id), user_id="u2")

        async with AsyncSession(async_engine) as session:
            p1 = await GetOrCreateWalkInPartnerUseCase(session).execute(ctx_1)
        async with AsyncSession(async_engine) as session:
            p2 = await GetOrCreateWalkInPartnerUseCase(session).execute(ctx_2)

        assert p1.id != p2.id
        assert p1.company_id == company_id
        assert p2.company_id == other_company_id
