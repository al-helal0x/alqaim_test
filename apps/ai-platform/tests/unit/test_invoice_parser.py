"""اختبارات محلّل الفواتير على نص عربي/إنجليزي مختلط (شائع في السوق العربي — 7.2)."""
from services.invoice_parser.invoice_parser import HeuristicInvoiceParser

parser = HeuristicInvoiceParser()

SAMPLE_TEXT = """
شركة القائم للتجارة العامة
فاتورة رقم: INV-2026-0042
التاريخ: 05/08/2026
المورد: شركة بغداد للمواد الغذائية
سكر أبيض 5 3.500
زيت طبخ 2 7.000
المجموع الفرعي: 31.500
الضريبة: 3.150
الخصم: 0
الإجمالي: 34.650
"""


def test_extracts_invoice_number():
    draft = parser.parse(SAMPLE_TEXT)
    assert draft.invoice_number_guess == "INV-2026-0042"


def test_extracts_total_and_tax():
    draft = parser.parse(SAMPLE_TEXT)
    assert draft.total_guess == 34.65
    assert draft.tax_guess == 3.15


def test_extracts_line_items():
    draft = parser.parse(SAMPLE_TEXT)
    descriptions = [line.description for line in draft.lines]
    assert any("سكر" in d for d in descriptions)
    assert any("زيت" in d for d in descriptions)
