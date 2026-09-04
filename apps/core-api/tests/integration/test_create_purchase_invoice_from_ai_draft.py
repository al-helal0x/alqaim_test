"""اختبارات لجزء آمن ثانٍ من `TASK-AI-01` — Idempotency بـ`ai_draft_id`.
تستخدم `db_session` (SQLite في الذاكرة) — نفس نمط باقي اختبارات purchasing.
"""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from modules.purchasing.application.dto.purchasing_dto import (
    PurchaseInvoiceCreateRequest,
    PurchaseOrderLineRequest,
)
from modules.purchasing.application.use_cases.create_purchase_invoice_from_ai_draft_use_case import (
    CreatePurchaseInvoiceFromAiDraftUseCase,
)
from modules.purchasing.infrastructure.models.purchasing_models import PurchaseInvoice
from platform_core.auth_middleware import TenantContext

pytestmark = pytest.mark.asyncio


def _ctx() -> TenantContext:
    return TenantContext(
        company_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()), branch_id=str(uuid.uuid4())
    )


def _request(**overrides) -> PurchaseInvoiceCreateRequest:
    defaults = {
        "branch_id": str(uuid.uuid4()),
        "supplier_id": str(uuid.uuid4()),
        "currency_code": "IQD",
        "tax_amount": Decimal(0),
        "discount_amount": Decimal(0),
        "lines": [
            PurchaseOrderLineRequest(
                product_id=str(uuid.uuid4()), description="بند AI",
                quantity=Decimal(5), unit_price=Decimal(100),
            ),
        ],
    }
    defaults.update(overrides)
    return PurchaseInvoiceCreateRequest(**defaults)


async def test_creates_invoice_with_source_ai_draft_id_set(db_session):
    ctx = _ctx()
    draft_id = str(uuid.uuid4())

    invoice = await CreatePurchaseInvoiceFromAiDraftUseCase(db_session).execute(
        ctx, _request(), ai_draft_id=draft_id
    )

    assert invoice.source_ai_draft_id == draft_id
    assert invoice.status == "draft"
    assert invoice.total_amount == Decimal("500.0000")


async def test_same_draft_id_twice_returns_same_invoice_no_duplicate(db_session):
    """جوهر Idempotency — نفس المسودة مرتين لا تُنشئ فاتورتين."""
    ctx = _ctx()
    draft_id = str(uuid.uuid4())

    first = await CreatePurchaseInvoiceFromAiDraftUseCase(db_session).execute(
        ctx, _request(), ai_draft_id=draft_id
    )
    second = await CreatePurchaseInvoiceFromAiDraftUseCase(db_session).execute(
        ctx, _request(), ai_draft_id=draft_id
    )

    assert first.id == second.id

    count = (
        await db_session.execute(
            select(PurchaseInvoice).where(PurchaseInvoice.source_ai_draft_id == draft_id)
        )
    ).scalars().all()
    assert len(count) == 1


async def test_different_draft_ids_create_separate_invoices(db_session):
    ctx = _ctx()

    first = await CreatePurchaseInvoiceFromAiDraftUseCase(db_session).execute(
        ctx, _request(), ai_draft_id=str(uuid.uuid4())
    )
    second = await CreatePurchaseInvoiceFromAiDraftUseCase(db_session).execute(
        ctx, _request(), ai_draft_id=str(uuid.uuid4())
    )

    assert first.id != second.id


async def test_same_draft_id_different_companies_both_succeed(db_session):
    """القيد UNIQUE مركّب مع company_id — نفس draft_id (نظرياً غير متوقَّع لكن
    غير محظور تقنياً) بين شركتين مختلفتين لا يتعارض."""
    draft_id = str(uuid.uuid4())

    invoice_a = await CreatePurchaseInvoiceFromAiDraftUseCase(db_session).execute(
        _ctx(), _request(), ai_draft_id=draft_id
    )
    invoice_b = await CreatePurchaseInvoiceFromAiDraftUseCase(db_session).execute(
        _ctx(), _request(), ai_draft_id=draft_id
    )

    assert invoice_a.id != invoice_b.id


async def test_missing_ai_draft_id_raises():
    ctx = _ctx()
    with pytest.raises(ValueError):
        await CreatePurchaseInvoiceFromAiDraftUseCase(None).execute(  # type: ignore[arg-type]
            ctx, _request(), ai_draft_id=""
        )


async def test_regular_purchase_invoices_unaffected(db_session):
    """فواتير الشراء العادية (بلا AI) تبقى بلا `source_ai_draft_id` — لا كسر
    لمسار `CreatePurchaseInvoiceUseCase` الموجود أصلاً."""
    from modules.purchasing.application.use_cases.purchase_invoice_use_cases import (
        CreatePurchaseInvoiceUseCase,
    )

    ctx = _ctx()
    invoice = await CreatePurchaseInvoiceUseCase(db_session).execute(ctx, _request())
    assert invoice.source_ai_draft_id is None
