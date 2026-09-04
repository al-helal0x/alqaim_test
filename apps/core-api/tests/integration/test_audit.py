"""اختبارات تكامل لموديول audit — نشر حدث وهمي عبر event_bus.publish(...)
مباشرة (بدون HTTP)، تماماً كما تفعل test_integrations_webhooks.py."""
import uuid

import pytest
from sqlalchemy import select

from modules.audit.application.use_cases.audit_use_cases import (
    ListAuditLogsUseCase,
    RecordAuditLogUseCase,
)
from modules.audit.infrastructure.models.audit_models import AuditLogEntry
from platform_core.auth_middleware import TenantContext
from shared_kernel.pagination import PageParams


@pytest.mark.asyncio
async def test_record_audit_log_creates_entry(db_session):
    company_id = str(uuid.uuid4())
    payload = {"invoice_id": str(uuid.uuid4()), "total": 100, "currency": "IQD", "company_id": company_id}

    await RecordAuditLogUseCase(db_session).execute("InvoicePosted", payload)

    rows = (await db_session.execute(select(AuditLogEntry))).scalars().all()
    assert len(rows) == 1
    assert rows[0].event_name == "InvoicePosted"
    assert str(rows[0].company_id) == company_id
    assert rows[0].payload["total"] == 100


@pytest.mark.asyncio
async def test_record_audit_log_ignores_payload_without_company_id(db_session):
    await RecordAuditLogUseCase(db_session).execute("FiscalPeriodClosed", {"period_id": "p1"})

    rows = (await db_session.execute(select(AuditLogEntry))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_list_audit_logs_filters_by_company_and_event_name(db_session):
    company_id = str(uuid.uuid4())
    other_company_id = str(uuid.uuid4())

    await RecordAuditLogUseCase(db_session).execute(
        "InvoicePosted", {"company_id": company_id, "invoice_id": "i1"}
    )
    await RecordAuditLogUseCase(db_session).execute(
        "PaymentRecorded", {"company_id": company_id, "payment_id": "p1"}
    )
    await RecordAuditLogUseCase(db_session).execute(
        "InvoicePosted", {"company_id": other_company_id, "invoice_id": "i2"}
    )

    ctx = TenantContext(company_id=company_id, user_id=str(uuid.uuid4()))
    rows, total = await ListAuditLogsUseCase(db_session).execute(
        ctx, "InvoicePosted", PageParams(page=1, page_size=20)
    )

    assert total == 1
    assert len(rows) == 1
    assert rows[0].event_name == "InvoicePosted"
    assert str(rows[0].company_id) == company_id
