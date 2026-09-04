"""يثبت أن `GET /ai/documents/jobs/{job_id}` يُرجع `draft_id` فعلياً بعد
اكتمال المعالجة — الثغرة التي كانت موجودة سابقاً: لم يكن هناك أي طريق عبر
الـ API للانتقال من job_id (الوحيد المتاح من استجابة /documents/analyze أو من
نتيجة Celery غير المتاحة مباشرة للعميل) إلى draft_id اللازم لـ
`GET /ai/drafts/{draft_id}` — رغم أن العلاقة موجودة أصلاً في الموديل
(`InvoiceExtractionDraft.ocr_job_id`)."""
import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from application.use_cases.process_document_pipeline import ProcessInvoiceDocumentUseCase
from presentation.routes.documents_router import get_job_status
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
    for i, line in enumerate([
        "Invoice No: INV-2026-0077",
        "Supplier: Najaf Supplies Co",
        "Cable 3 5.000",
        "Subtotal: 15.000",
        "Tax: 1.500",
        "Total: 16.500",
    ]):
        draw.text((30, 20 + i * 45), line, fill="black", font=font)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


async def test_job_status_includes_draft_id_once_processing_completes(db_session):
    pipeline = ProcessInvoiceDocumentUseCase(
        session=db_session,
        preprocessor=OpenCvPreprocessor(),
        ocr_engine=TesseractOCREngine(),
        invoice_parser=HeuristicInvoiceParser(),
        product_matcher=FuzzyEntityMatcher(),
        supplier_matcher=FuzzyEntityMatcher(),
        validator=InvoiceValidator(),
    )
    draft = await pipeline.execute(
        company_id="11111111-1111-1111-1111-111111111111",
        attachment_id="22222222-2222-2222-2222-222222222222",
        image_bytes=_render_invoice_image(),
        company_currency="IQD",
    )

    response = await get_job_status(job_id=str(draft.ocr_job_id), session=db_session)

    assert response.status == "done"
    assert response.draft_id == str(draft.id)


async def test_job_status_draft_id_is_none_when_job_has_no_draft_yet(db_session):
    from models.ai_models import OcrJob

    job = OcrJob(
        company_id="33333333-3333-3333-3333-333333333333",
        attachment_id="44444444-4444-4444-4444-444444444444",
        status="processing",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    response = await get_job_status(job_id=str(job.id), session=db_session)

    assert response.status == "processing"
    assert response.draft_id is None
