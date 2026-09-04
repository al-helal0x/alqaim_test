"""اختبار تكامل حقيقي: يولّد صورة فاتورة فعلية عبر PIL، ثم يمرّرها كاملة عبر
Preprocessing (OpenCV) → OCR (Tesseract حقيقي) → Invoice Parsing → Validation
→ Product Matching، ويتحقق أن القيم المستخرجة من البكسلات الفعلية صحيحة.

هذا يثبت أن الأنبوب يعمل فعلياً على صورة، وليس فقط على نص جاهز (كما في
tests/unit/test_invoice_parser.py الذي يختبر منطق التحليل بمعزل عن OCR).
"""
import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from services.entity_matching.entity_matcher import FuzzyEntityMatcher
from services.invoice_parser.invoice_parser import HeuristicInvoiceParser
from services.ocr.ocr_engine import TesseractOCREngine
from services.preprocessing.preprocessor import OpenCvPreprocessor
from services.validation.validator import InvoiceValidator

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _render_invoice_image() -> bytes:
    img = Image.new("RGB", (900, 500), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 28)

    lines = [
        "Baghdad Foodstuff Trading Co",
        "Invoice No: INV-2026-0099",
        "Date: 05/08/2026",
        "Supplier: Baghdad Foodstuff Trading Co",
        "Sugar 5kg 10 3.000",
        "Cooking Oil 2 7.000",
        "Subtotal: 44.000",
        "Tax: 4.400",
        "Discount: 0",
        "Total: 48.400",
    ]
    y = 20
    for line in lines:
        draw.text((30, y), line, fill="black", font=font)
        y += 45

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(scope="module")
def pipeline_components():
    return {
        "preprocessor": OpenCvPreprocessor(),
        "ocr": TesseractOCREngine(),
        "parser": HeuristicInvoiceParser(),
        "validator": InvoiceValidator(),
        "matcher": FuzzyEntityMatcher(),
    }


def test_real_image_ocr_extracts_correct_invoice_number(pipeline_components):
    image_bytes = _render_invoice_image()
    cleaned = pipeline_components["preprocessor"].preprocess(image_bytes)
    ocr_result = pipeline_components["ocr"].extract(cleaned, languages="eng")

    assert "INV-2026-0099" in ocr_result.text
    assert ocr_result.confidence > 0.3  # نص واضح مطبوع رقمياً — ثقة يجب أن تكون معقولة


def test_real_image_pipeline_extracts_structured_fields(pipeline_components):
    image_bytes = _render_invoice_image()
    cleaned = pipeline_components["preprocessor"].preprocess(image_bytes)
    ocr_result = pipeline_components["ocr"].extract(cleaned, languages="eng")
    draft = pipeline_components["parser"].parse(ocr_result.text)

    assert draft.invoice_number_guess == "INV-2026-0099"
    assert draft.total_guess == pytest.approx(48.4, abs=0.5)
    assert draft.tax_guess == pytest.approx(4.4, abs=0.5)


def test_real_image_pipeline_validates_and_matches_supplier(pipeline_components):
    image_bytes = _render_invoice_image()
    cleaned = pipeline_components["preprocessor"].preprocess(image_bytes)
    ocr_result = pipeline_components["ocr"].extract(cleaned, languages="eng")
    draft = pipeline_components["parser"].parse(ocr_result.text)

    warnings = pipeline_components["validator"].validate(draft, company_currency="IQD")
    # لا خطأ في تطابق الإجمالي (البيانات المُولَّدة متسقة رياضياً)
    assert not any(w.severity == "error" and w.code == "TOTAL_MISMATCH" for w in warnings)

    known_suppliers = [
        ("s1", "Baghdad Foodstuff Trading Co"),
        ("s2", "Basra Electronics LLC"),
    ]
    matches = pipeline_components["matcher"].match(draft.supplier_name_guess or "", known_suppliers)
    assert matches[0].entity_id == "s1"
    assert matches[0].confidence > 0.6
