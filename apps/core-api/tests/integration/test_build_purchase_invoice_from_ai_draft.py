"""اختبارات لجزء صغير من `TASK-AI-01` — دالة تحويل صرفة فقط (لا endpoint، لا
شبكة، لا قاعدة بيانات). راجع تحذير النطاق أعلى
`build_purchase_invoice_from_ai_draft.py`.
"""
from decimal import Decimal

import pytest

from modules.purchasing.application.use_cases.build_purchase_invoice_from_ai_draft import (
    DraftMappingError,
    build_purchase_invoice_request_from_ai_draft,
)


def _valid_payload() -> dict:
    return {
        "currency_guess": "iqd",
        "tax_guess": 500.0,
        "discount_guess": None,
        "lines": [
            {"description": "قلم أزرق", "quantity": 10.0, "unit_price": 250.0, "line_total": 2500.0},
            {"description": "دفتر A4", "quantity": 3.0, "unit_price": 1000.0, "line_total": 3000.0},
        ],
    }


def test_valid_draft_maps_to_purchase_invoice_request():
    request = build_purchase_invoice_request_from_ai_draft(
        extracted_payload=_valid_payload(),
        branch_id="branch-1",
        supplier_id="supplier-1",
        product_id_by_line_index={0: "product-pen", 1: "product-notebook"},
    )

    assert request.branch_id == "branch-1"
    assert request.supplier_id == "supplier-1"
    assert request.currency_code == "IQD"  # طُبِّع لحروف كبيرة
    assert request.tax_amount == Decimal("500.0")
    assert request.discount_amount == Decimal(0)  # None → صفر، لا كسر
    assert len(request.lines) == 2
    assert request.lines[0].product_id == "product-pen"
    assert request.lines[0].quantity == Decimal("10.0")
    assert request.lines[1].product_id == "product-notebook"


def test_missing_supplier_raises_no_partial_invoice():
    with pytest.raises(DraftMappingError):
        build_purchase_invoice_request_from_ai_draft(
            extracted_payload=_valid_payload(),
            branch_id="branch-1",
            supplier_id=None,
            product_id_by_line_index={0: "p1", 1: "p2"},
        )


def test_missing_branch_id_raises():
    with pytest.raises(DraftMappingError):
        build_purchase_invoice_request_from_ai_draft(
            extracted_payload=_valid_payload(),
            branch_id="",
            supplier_id="supplier-1",
            product_id_by_line_index={0: "p1", 1: "p2"},
        )


def test_empty_lines_raises():
    with pytest.raises(DraftMappingError):
        build_purchase_invoice_request_from_ai_draft(
            extracted_payload={"lines": []},
            branch_id="branch-1",
            supplier_id="supplier-1",
            product_id_by_line_index={},
        )


def test_unmatched_product_line_raises_no_partial_invoice():
    """لا فاتورة جزئية — بند واحد بلا منتج مطابَق يفشّل التحويل كاملاً."""
    with pytest.raises(DraftMappingError, match="بند رقم 2"):
        build_purchase_invoice_request_from_ai_draft(
            extracted_payload=_valid_payload(),
            branch_id="branch-1",
            supplier_id="supplier-1",
            product_id_by_line_index={0: "product-pen"},  # البند الثاني بلا مطابقة
        )


def test_line_missing_quantity_or_price_raises():
    payload = {
        "currency_guess": "IQD",
        "lines": [{"description": "بند ناقص", "quantity": None, "unit_price": 100.0}],
    }
    with pytest.raises(DraftMappingError):
        build_purchase_invoice_request_from_ai_draft(
            extracted_payload=payload,
            branch_id="branch-1",
            supplier_id="supplier-1",
            product_id_by_line_index={0: "p1"},
        )


def test_zero_or_negative_quantity_rejected():
    payload = {
        "lines": [{"description": "بند غير صالح", "quantity": 0, "unit_price": 100.0}],
    }
    with pytest.raises(DraftMappingError):
        build_purchase_invoice_request_from_ai_draft(
            extracted_payload=payload,
            branch_id="branch-1",
            supplier_id="supplier-1",
            product_id_by_line_index={0: "p1"},
        )


def test_missing_currency_defaults_to_iqd():
    payload = {
        "lines": [{"description": "بند", "quantity": 1.0, "unit_price": 50.0}],
    }
    request = build_purchase_invoice_request_from_ai_draft(
        extracted_payload=payload,
        branch_id="branch-1",
        supplier_id="supplier-1",
        product_id_by_line_index={0: "p1"},
    )
    assert request.currency_code == "IQD"
