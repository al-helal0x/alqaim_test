"""اختبار تكامل يغطي إصلاحاً حقيقياً وُجد أثناء دمج حزمة data_migration:
RunImportBatchUseCase الأصلية كانت تعمل `session.add(ImportRowError(...))`
ثم `await session.rollback()` فوراً — وrollback يُلغي أي كائن مُضاف لم
يُلتزَم بعد، فسجل الخطأ يضيع بصمت رغم نجاح استيراد بقية الدفعة. الإصلاح:
rollback أولاً (لتنظيف أي حالة معاملة فاشلة تركها use_case.execute())، ثم
إضافة ImportRowError بعد ذلك — مع التقاط job.id في متغيّر محلي قبل أي
rollback محتمل، لأن rollback() يُفرِغ (expire) كل خصائص الكائنات في الجلسة
بصرف النظر عن `expire_on_commit=False`، وقراءة خاصية مُفرَغة على
AsyncSession متزامناً ترمي MissingGreenlet.
"""
import uuid

import pytest
from sqlalchemy import select

from modules.data_migration.application.use_cases.run_import_batch import (
    RunImportBatchUseCase,
)
from modules.data_migration.domain.value_objects.enums import ImportStatus, TargetEntity
from modules.data_migration.infrastructure.models.data_migration_models import (
    ImportJob,
)
from modules.data_migration.infrastructure.repositories.data_migration_repository import (
    ImportRowErrorRepository,
)
from modules.tenancy.infrastructure.models.tenancy_models import Company
from platform_core.auth_middleware import TenantContext

pytestmark = pytest.mark.asyncio


class _FakeConnector:
    """SourceConnector وهمي بأدنى ما تحتاجه RunImportBatchUseCase: صفّان
    فقط — واحد صالح (يُنشئ شريكاً بنجاح) وواحد يفشل تحقُّق Pydantic عمداً
    (اسم أقصر من الحد الأدنى المطلوب name: min_length=2)."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.closed = False

    async def discover_schema(self):
        return []

    async def row_count(self, table_name: str) -> int:
        return len(self._rows)

    async def read_batch(self, table_name: str, *, offset: int, limit: int) -> list[dict]:
        return self._rows[offset : offset + limit]

    async def close(self) -> None:
        self.closed = True


async def _make_company_ctx(db_session) -> TenantContext:
    company = Company(name=f"شركة {uuid.uuid4().hex[:8]}")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return TenantContext(company_id=str(company.id), user_id=str(uuid.uuid4()))


async def test_failed_row_error_is_actually_persisted_not_lost_by_rollback(db_session):
    ctx = await _make_company_ctx(db_session)

    job = ImportJob(
        company_id=ctx.company_id,
        source_type="csv",
        status=ImportStatus.PREVIEWED.value,
        connection_ref="test-ref",
        mappings=[
            {"target_entity": "partners", "source_column": "name", "target_field": "name"},
            {
                "target_entity": "partners",
                "source_column": "tax_no",
                "target_field": "tax_number",
            },
        ],
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    job_id = str(job.id)

    rows = [
        {"name": "مورد صالح للاستيراد", "tax_no": "TX-OK-1"},
        {"name": "س", "tax_no": "TX-BAD"},  # أقصر من min_length=2 → ValidationError
        {"name": "مورد صالح آخر", "tax_no": "TX-OK-2"},
    ]
    connector = _FakeConnector(rows)

    result = await RunImportBatchUseCase(db_session, connector).execute(
        ctx, job_id, TargetEntity.PARTNERS, source_table="ignored"
    )

    assert result.processed_rows == 2
    assert result.error_count == 1
    assert connector.closed is True

    # الاختبار الحاسم: هل سجل ImportRowError نفسه وصل فعلاً لقاعدة البيانات،
    # أم ضاع بفعل rollback كما كان يحدث قبل الإصلاح؟
    persisted_errors = await ImportRowErrorRepository(db_session).list_for_job(job_id=job_id)
    assert len(persisted_errors) == 1
    assert persisted_errors[0].row_number == 2
    assert persisted_errors[0].table_name == TargetEntity.PARTNERS.value
    assert "string_too_short" in persisted_errors[0].message  # رسالة Pydantic فعلية، ليست نصاً وهمياً
    assert persisted_errors[0].raw_row == {"name": "س", "tax_no": "TX-BAD"}

    # وأن الجلسة نفسها بقيت صالحة تماماً للاستخدام بعد كل ذلك (job.id لم
    # يُقرَأ من كائن مُفرَغ في أي مكان).
    stmt = select(ImportJob).where(ImportJob.id == job_id)
    refreshed = (await db_session.execute(stmt)).scalar_one()
    assert refreshed.status == ImportStatus.COMPLETED.value
    assert refreshed.processed_rows == 2

    # وأن الصفَّين الصالحَين فعلاً أُنشئا (ليسا فقط معدودَين) — تأكيد إضافي
    # أن نجاح processed_rows=2 ليس عدّاً وهمياً.
    from modules.partners.application.use_cases.partner_use_cases import ListPartnersUseCase

    partners = await ListPartnersUseCase(db_session).execute(ctx)
    assert {p.tax_number for p in partners} == {"TX-OK-1", "TX-OK-2"}
