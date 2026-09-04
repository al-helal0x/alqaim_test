"""اختبارات لجزء آمن ثالث من `TASK-AI-01` — `create_purchase_invoice_from_approved_draft`
(تجميع الجزأين السابقين فوق مسودة جاهزة). لا شبكة هنا — `draft` يُمرَّر كـdict
جاهز مباشرة، تماماً كما لو كان قادماً من `DraftResponse.model_dump()`.
"""
import uuid
from decimal import Decimal

import pytest

from modules.purchasing.application.use_cases.build_purchase_invoice_from_ai_draft import (
    DraftMappingError,
)
from modules.purchasing.application.use_cases.resolve_purchase_invoice_from_ai_draft import (
    create_purchase_invoice_from_approved_draft,
)
from platform_core.auth_middleware import TenantContext

pytestmark = pytest.mark.asyncio


def _ctx() -> TenantContext:
    return TenantContext(
        company_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()), branch_id=str(uuid.uuid4())
    )


def _approved_draft(**overrides) -> dict:
    supplier_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    draft = {
        "id": str(uuid.uuid4()),
        "status": "approved",
        "matched_supplier_id": supplier_id,
        "extracted_payload": {
            "currency_guess": "IQD",
            "tax_guess": 0,
            "discount_guess": 0,
            "lines": [
                {"description": "بند AI", "quantity": 2.0, "unit_price": 50.0, "line_total": 100.0},
            ],
            "line_matches": [
                {"line": "بند AI", "matches": [{"entity_id": product_id, "text": "منتج", "confidence": 0.97}]},
            ],
        },
    }
    draft.update(overrides)
    return draft


async def test_approved_draft_with_high_confidence_match_creates_invoice(db_session):
    ctx = _ctx()
    draft = _approved_draft()

    invoice = await create_purchase_invoice_from_approved_draft(
        db_session, ctx, draft=draft, branch_id=str(uuid.uuid4())
    )

    assert invoice.source_ai_draft_id == draft["id"]
    assert str(invoice.supplier_id) == draft["matched_supplier_id"]
    assert invoice.total_amount == Decimal("100.0000")


async def test_non_approved_draft_rejected(db_session):
    ctx = _ctx()
    draft = _approved_draft(status="pending_review")

    with pytest.raises(DraftMappingError):
        await create_purchase_invoice_from_approved_draft(
            db_session, ctx, draft=draft, branch_id=str(uuid.uuid4())
        )


async def test_no_matched_supplier_rejected(db_session):
    ctx = _ctx()
    draft = _approved_draft(matched_supplier_id=None)

    with pytest.raises(DraftMappingError):
        await create_purchase_invoice_from_approved_draft(
            db_session, ctx, draft=draft, branch_id=str(uuid.uuid4())
        )


async def test_low_confidence_product_match_rejected_no_partial_invoice():
    """ثقة أقل من 0.92 (نفس عتبة المورد المُعاد استخدامها) → لا مطابقة تلقائية."""
    from modules.purchasing.application.use_cases.resolve_purchase_invoice_from_ai_draft import (
        _resolve_product_id_by_line_index,
    )

    payload = {
        "lines": [{"description": "بند", "quantity": 1.0, "unit_price": 10.0}],
        "line_matches": [
            {"line": "بند", "matches": [{"entity_id": "p1", "text": "شبه تطابق", "confidence": 0.5}]}
        ],
    }
    resolved = _resolve_product_id_by_line_index(payload)
    assert resolved == {}


async def test_misaligned_line_matches_length_treated_as_no_matches():
    """فجوة مكتشَفة: len(line_matches) != len(lines) → لا تخمين، لا مطابقات
    (راجع توثيق الملف)."""
    from modules.purchasing.application.use_cases.resolve_purchase_invoice_from_ai_draft import (
        _resolve_product_id_by_line_index,
    )

    payload = {
        "lines": [
            {"description": "بند 1", "quantity": 1.0, "unit_price": 10.0},
            {"description": "بند 2", "quantity": 1.0, "unit_price": 20.0},
        ],
        "line_matches": [
            {"line": "بند 1", "matches": [{"entity_id": "p1", "text": "x", "confidence": 0.99}]},
        ],  # طول 1 بدل 2 — محاذاة غير موثوقة
    }
    resolved = _resolve_product_id_by_line_index(payload)
    assert resolved == {}


async def test_same_draft_id_twice_via_orchestration_is_idempotent(db_session):
    ctx = _ctx()
    branch_id = str(uuid.uuid4())
    draft = _approved_draft()

    first = await create_purchase_invoice_from_approved_draft(
        db_session, ctx, draft=draft, branch_id=branch_id
    )
    second = await create_purchase_invoice_from_approved_draft(
        db_session, ctx, draft=draft, branch_id=branch_id
    )

    assert first.id == second.id
