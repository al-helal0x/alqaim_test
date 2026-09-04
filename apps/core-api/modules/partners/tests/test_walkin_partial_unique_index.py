"""PKG-B1 — Tests Required (00_TASK_PACKAGE.md § PKG-B1).

⚠️ يتطلب Postgres حقيقياً وليس SQLite في الذاكرة: Partial Unique Index
(`CREATE UNIQUE INDEX ... WHERE is_system_managed = true`) غير مدعوم على
SQLite بنفس الدلالة. يقرأ الاختبار رابط الاتصال من متغير البيئة
`TEST_DATABASE_URL` ويُتخطّى (skip) تلقائياً إن لم يكن معرَّفاً، بدل أن
يفشل بصمت على SQLite.

طريقة التشغيل المتوقعة:
    TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost/alqaim_test \
        pytest apps/core-api/modules/partners/tests/test_walkin_partial_unique_index.py -v

الاختبار يشغّل `alembic upgrade` الفعلي لـ migration هذه PKG-B1
(b1_partners_walkin_system_managed) قبل التحقق، تماشياً مع اشتراط
GATE-WI: "alembic upgrade فعلي ... يُختبَر بمحاولة إدخال صفَّي walk-in
متزامنَين لنفس الشركة".
"""
import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason=(
        "PKG-B1 partial unique index requires a real Postgres instance. "
        "Set TEST_DATABASE_URL to run this test (see module docstring)."
    ),
)

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


@pytest.fixture(scope="module")
def engine():
    eng = sa.create_engine(TEST_DATABASE_URL, future=True)

    # يشغّل alembic upgrade الفعلي حتى head — بما فيه migration PKG-B1 —
    # على نفس قاعدة الاختبار، تماشياً مع اشتراط GATE-WI.
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(alembic_cfg, "head")

    # يضمن وجود جدول companies بأقل شكل ممكن (id فقط) لإشباع هذا FK من
    # partners.company_id — لا يُنشئ الجدول من جديد إن كان موجوداً فعلاً
    # بمخططه الكامل في قاعدة الاختبار.
    with eng.begin() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE IF NOT EXISTS companies "
                "(id UUID PRIMARY KEY DEFAULT gen_random_uuid())"
            )
        )

    yield eng
    eng.dispose()


@pytest.fixture
def company_id(engine):
    """Company معزولة لكل اختبار — تفادياً لتداخل بيانات بين الاختبارات."""
    new_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO companies (id, name, created_at, updated_at) VALUES (:id, :name, now(), now())"), {"id": new_id, "name": f"walkin-test-{new_id}"})
    return new_id


def _insert_partner(engine, company_id, *, is_system_managed: bool, name: str = "عميل نقدي"):
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO partners "
                "(id, company_id, name, partner_type, is_system_managed, "
                " payment_terms_days, is_active, created_at, updated_at) "
                "VALUES (:id, :company_id, :name, 'customer', :is_system_managed, "
                " 0, true, now(), now())"
            ),
            {
                "id": uuid.uuid4(),
                "company_id": company_id,
                "name": name,
                "is_system_managed": is_system_managed,
            },
        )


class TestWalkInPartialUniqueIndex:
    def test_second_walkin_same_company_rejected_by_db(self, engine, company_id):
        """صفَّان بـ is_system_managed=true لنفس company_id → الثاني يُرفَض بـIntegrityError فعلي."""
        _insert_partner(engine, company_id, is_system_managed=True)

        with pytest.raises(IntegrityError):
            _insert_partner(engine, company_id, is_system_managed=True)

    def test_two_companies_each_allowed_own_walkin(self, engine, company_id):
        """صفّان لشركتين مختلفتين، كلاهما is_system_managed=true → كلاهما يُقبَل."""
        other_company_id = uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                sa.text("INSERT INTO companies (id, name, created_at, updated_at) VALUES (:id, :name, now(), now())"), {"id": other_company_id, "name": f"walkin-test-other-{other_company_id}"}
            )

        _insert_partner(engine, company_id, is_system_managed=True)
        # لا يجب أن يرفع أي استثناء — شركة مختلفة، صف walk-in منفصل.
        _insert_partner(engine, other_company_id, is_system_managed=True)

    def test_non_system_managed_partners_not_restricted(self, engine, company_id):
        """عملاء عاديون (is_system_managed=false) غير مقيَّدين بالفهرس الجزئي — يمكن تكرارهم."""
        _insert_partner(engine, company_id, is_system_managed=False, name="عميل 1")
        # لا يجب أن يرفع أي استثناء — الفهرس ينطبق فقط على is_system_managed=true.
        _insert_partner(engine, company_id, is_system_managed=False, name="عميل 2")
