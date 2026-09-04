"""أول اختبار تكامل حقيقي (يحتاج db_session fixture) لهذا الموديول — يثبت أن
الجداول الثلاثة تُنشَأ فعلياً عبر Base.metadata.create_all وأن Repository
يعمل ضد قاعدة بيانات حقيقية (SQLite في الذاكرة)، لا Mock."""
import uuid

import pytest

from modules.data_migration.infrastructure.models.data_migration_models import (
    ImportBatch,
    ImportJob,
    ImportRowError,
)
from modules.data_migration.infrastructure.repositories.data_migration_repository import (
    ImportBatchRepository,
    ImportJobRepository,
    ImportRowErrorRepository,
)

pytestmark = pytest.mark.asyncio


async def test_create_and_fetch_import_job(db_session):
    company_id = uuid.uuid4()
    job = ImportJob(
        company_id=company_id,
        source_type="alameen_mssql",
        status="connected",
        connection_ref="mssql://staging-only-placeholder",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    fetched = await ImportJobRepository(db_session).get_by_id(str(job.id), company_id=str(company_id))
    assert fetched is not None
    assert fetched.source_type == "alameen_mssql"
    assert fetched.status == "connected"


async def test_import_job_isolated_by_company(db_session):
    """يثبت أن get_by_id يفلتر حسب company_id — نفس معيار عزل IDOR المطبَّق
    على كل موديول آخر في المشروع (راجع test_idor_*.py)."""
    company_a, company_b = uuid.uuid4(), uuid.uuid4()
    job = ImportJob(
        company_id=company_a,
        source_type="csv",
        status="connected",
        connection_ref="local-file-placeholder",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    leaked = await ImportJobRepository(db_session).get_by_id(str(job.id), company_id=str(company_b))
    assert leaked is None


async def test_batch_and_row_error_repositories(db_session):
    job = ImportJob(
        company_id=uuid.uuid4(),
        source_type="xlsx",
        status="committing",
        connection_ref="local-file-placeholder",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    db_session.add(
        ImportBatch(job_id=job.id, target_entity="partners", offset=0, row_count=500, success=True)
    )
    db_session.add(
        ImportRowError(
            job_id=job.id,
            row_number=17,
            table_name="partners",
            message="رقم هاتف غير صالح",
            raw_row={"phone": "abc"},
        )
    )
    await db_session.commit()

    batches = await ImportBatchRepository(db_session).list_for_job(job_id=str(job.id))
    errors = await ImportRowErrorRepository(db_session).list_for_job(job_id=str(job.id))

    assert len(batches) == 1
    assert batches[0].row_count == 500
    assert len(errors) == 1
    assert errors[0].row_number == 17
