"""مهمة 7 — يتحقق أن ProcessInvoiceDocumentUseCase تنشر فعلياً حدث
InvoiceDraftReady (عبر event_publisher المحقون) بالحقول المتفَق عليها في
docs/architecture/contracts.md §4 (يجب أن تتضمن company_id صراحة)، وأنها
لا تنشر شيئاً إن فشلت المعالجة.

هذا يغطي الفجوة الفعلية التي كانت موجودة: workers/tasks.py كان يمرّر
event_publisher لمُنشئ الصف لكن __init__/execute لم يكونا يقبلانه أو
يستدعيانه إطلاقاً (كان سيفشل بـ TypeError في الإنتاج قبل هذا الإصلاح)."""
import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from application.use_cases.process_document_pipeline import ProcessInvoiceDocumentUseCase
from services.entity_matching.entity_matcher import FuzzyEntityMatcher
from services.invoice_parser.invoice_parser import HeuristicInvoiceParser
from services.ocr.ocr_engine import TesseractOCREngine
from services.preprocessing.preprocessor import OpenCvPreprocessor
from services.validation.validator import InvoiceValidator

pytestmark = pytest.mark.asyncio
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _render_invoice_image() -> bytes:
    img = Image.new("RGB", (900, 400), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 28)
    lines = [
        "Invoice No: INV-2026-0099",
        "Supplier: AlQaim Trading Co",
        "Cable 3 5.000",
        "Subtotal: 15.000",
        "Tax: 1.500",
        "Total: 16.500",
    ]
    y = 20
    for line in lines:
        draw.text((30, y), line, fill="black", font=font)
        y += 45
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def _build_pipeline(db_session, event_publisher=None):
    return ProcessInvoiceDocumentUseCase(
        session=db_session,
        preprocessor=OpenCvPreprocessor(),
        ocr_engine=TesseractOCREngine(),
        invoice_parser=HeuristicInvoiceParser(),
        product_matcher=FuzzyEntityMatcher(),
        supplier_matcher=FuzzyEntityMatcher(),
        validator=InvoiceValidator(),
        event_publisher=event_publisher,
    )


async def test_publishes_invoice_draft_ready_with_contracted_fields_on_success(db_session):
    published = []

    async def _fake_publisher(event_name: str, payload: dict) -> None:
        published.append((event_name, payload))

    company_id = "33333333-3333-3333-3333-333333333333"
    pipeline = _build_pipeline(db_session, event_publisher=_fake_publisher)

    draft = await pipeline.execute(
        company_id=company_id,
        attachment_id="44444444-4444-4444-4444-444444444444",
        image_bytes=_render_invoice_image(),
        company_currency="IQD",
    )

    assert len(published) == 1
    event_name, payload = published[0]
    assert event_name == "InvoiceDraftReady"

    # كل الحقول المثبَّتة في contracts.md §4 (company_id إلزامي صراحة)
    for field in (
        "draft_id", "company_id", "ocr_job_id", "confidence",
        "supplier_name_guess", "matched_supplier_id", "total_guess",
        "has_validation_errors",
    ):
        assert field in payload

    assert payload["draft_id"] == str(draft.id)
    assert payload["company_id"] == company_id
    assert isinstance(payload["has_validation_errors"], bool)


async def test_does_not_publish_when_no_publisher_injected(db_session):
    """المسارات التي لا تحقن event_publisher (مثال: اختبارات أخرى لا تهتم
    بالنشر) تستمر بالعمل دون أي محاولة نشر — سلوك اختياري صريح."""
    pipeline = _build_pipeline(db_session, event_publisher=None)

    draft = await pipeline.execute(
        company_id="55555555-5555-5555-5555-555555555555",
        attachment_id="66666666-6666-6666-6666-666666666666",
        image_bytes=_render_invoice_image(),
        company_currency="IQD",
    )

    assert draft.status == "pending_review"


async def test_does_not_publish_when_processing_fails(db_session):
    published = []

    async def _fake_publisher(event_name: str, payload: dict) -> None:
        published.append((event_name, payload))

    class _BrokenPreprocessor:
        def preprocess(self, image_bytes: bytes) -> bytes:
            raise RuntimeError("فشل معالجة مقصود للاختبار")

    pipeline = ProcessInvoiceDocumentUseCase(
        session=db_session,
        preprocessor=_BrokenPreprocessor(),
        ocr_engine=TesseractOCREngine(),
        invoice_parser=HeuristicInvoiceParser(),
        product_matcher=FuzzyEntityMatcher(),
        supplier_matcher=FuzzyEntityMatcher(),
        validator=InvoiceValidator(),
        event_publisher=_fake_publisher,
    )

    with pytest.raises(RuntimeError):
        await pipeline.execute(
            company_id="77777777-7777-7777-7777-777777777777",
            attachment_id="88888888-8888-8888-8888-888888888888",
            image_bytes=b"not-really-an-image",
            company_currency="IQD",
        )

    assert published == []
