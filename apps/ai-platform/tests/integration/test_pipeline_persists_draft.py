"""يتحقق أن ProcessInvoiceDocumentUseCase يُنشئ OcrJob + InvoiceExtractionDraft
فعلياً في قاعدة البيانات بحالة 'pending_review' دائماً — لا اعتماد تلقائي
(القسم 7.5/17)، بدءاً من صورة فعلية وليس نص جاهز."""
import io

import pytest
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select

from application.use_cases.process_document_pipeline import ProcessInvoiceDocumentUseCase
from models.ai_models import OcrJob
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
        "Invoice No: INV-2026-0055",
        "Supplier: Basra Electronics LLC",
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


async def test_pipeline_creates_pending_review_draft(db_session):
    pipeline = ProcessInvoiceDocumentUseCase(
        session=db_session,
        preprocessor=OpenCvPreprocessor(),
        ocr_engine=TesseractOCREngine(),
        invoice_parser=HeuristicInvoiceParser(),
        product_matcher=FuzzyEntityMatcher(),
        supplier_matcher=FuzzyEntityMatcher(),
        validator=InvoiceValidator(),
    )

    company_id = "11111111-1111-1111-1111-111111111111"
    draft = await pipeline.execute(
        company_id=company_id,
        attachment_id="22222222-2222-2222-2222-222222222222",
        image_bytes=_render_invoice_image(),
        company_currency="IQD",
    )

    assert draft.status == "pending_review"
    assert draft.extracted_payload["invoice_number_guess"] == "INV-2026-0055"

    job = (await db_session.execute(select(OcrJob).where(OcrJob.id == draft.ocr_job_id))).scalar_one()
    assert job.status == "done"
    assert job.engine_used == "tesseract"
