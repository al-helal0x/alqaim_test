"""اختبارات وحدة سريعة (بدون DB) لقواعد المنطق المالي — القسم 7.5."""
from application.ports.ai_ports import InvoiceDraft, InvoiceLineDraft
from services.validation.validator import InvoiceValidator

validator = InvoiceValidator()


def test_matching_total_produces_no_error():
    draft = InvoiceDraft(
        total_guess=115.0, tax_guess=15.0, discount_guess=0.0,
        lines=[InvoiceLineDraft(description="منتج", quantity=1, unit_price=100.0, line_total=100.0)],
    )
    warnings = validator.validate(draft, company_currency="IQD")
    codes = [w.code for w in warnings]
    assert "TOTAL_MISMATCH" not in codes


def test_mismatched_total_flags_error():
    draft = InvoiceDraft(
        total_guess=999.0, tax_guess=15.0, discount_guess=0.0,
        lines=[InvoiceLineDraft(description="منتج", quantity=1, unit_price=100.0, line_total=100.0)],
    )
    warnings = validator.validate(draft, company_currency="IQD")
    codes = [w.code for w in warnings]
    assert "TOTAL_MISMATCH" in codes


def test_negative_price_flagged():
    draft = InvoiceDraft(
        total_guess=100.0,
        lines=[InvoiceLineDraft(description="منتج", quantity=1, unit_price=-5.0, line_total=-5.0)],
    )
    warnings = validator.validate(draft, company_currency="IQD")
    codes = [w.code for w in warnings]
    assert "NEGATIVE_PRICE" in codes


def test_currency_mismatch_is_warning_not_error():
    draft = InvoiceDraft(total_guess=100.0, currency_guess="USD")
    warnings = validator.validate(draft, company_currency="IQD")
    mismatch = next(w for w in warnings if w.code == "CURRENCY_MISMATCH")
    assert mismatch.severity == "warning"


def test_missing_total_is_error():
    draft = InvoiceDraft(total_guess=None)
    warnings = validator.validate(draft, company_currency="IQD")
    assert any(w.code == "MISSING_TOTAL" and w.severity == "error" for w in warnings)
