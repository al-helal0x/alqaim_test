"""Celery worker — يلتقط مهمة ProcessInvoiceDocument من Redis التي ينشرها
core-api (القسم 7.10)، وينشر حدث InvoiceDraftReady عائداً عبر Redis Pub/Sub
عند الاكتمال (`platform_core/redis_events.publish_event` — القسم 6.6،
يُستهلَك عبر core-api/platform_core/redis_bridge.py ثم event_bus المحلي).

Skeleton أولي: منطق المعالجة الفعلي في application/use_cases — هذا الملف
غلاف Celery رقيق فقط (Thin Adapter)، ليسهل اختبار المنطق دون Celery/Redis.
"""
import asyncio

from celery import Celery

from platform_core.config import get_settings

settings = get_settings()
celery_app = Celery("ai_platform", broker=settings.redis_url, backend=settings.redis_url)


@celery_app.task(name="process_invoice_document")
def process_invoice_document(
    *, company_id: str, attachment_id: str, image_bytes_hex: str, company_currency: str
) -> str:
    """image_bytes يُمرَّر كـ hex عبر Celery (JSON-serializable) بدل bytes خام."""
    from application.use_cases.process_document_pipeline import ProcessInvoiceDocumentUseCase
    from platform_core.database import AsyncSessionLocal
    from services.entity_matching.entity_matcher import FuzzyEntityMatcher
    from services.invoice_parser.invoice_parser import HeuristicInvoiceParser
    from services.ocr.ocr_engine import TesseractOCREngine
    from services.preprocessing.preprocessor import OpenCvPreprocessor
    from services.validation.validator import InvoiceValidator

    async def _run() -> str:
        from platform_core.redis_events import publish_event

        async with AsyncSessionLocal() as session:
            pipeline = ProcessInvoiceDocumentUseCase(
                session=session,
                preprocessor=OpenCvPreprocessor(),
                ocr_engine=TesseractOCREngine(),
                invoice_parser=HeuristicInvoiceParser(),
                product_matcher=FuzzyEntityMatcher(),
                supplier_matcher=FuzzyEntityMatcher(),
                validator=InvoiceValidator(),
                event_publisher=publish_event,
            )
            draft = await pipeline.execute(
                company_id=company_id,
                attachment_id=attachment_id,
                image_bytes=bytes.fromhex(image_bytes_hex),
                company_currency=company_currency,
            )
            return str(draft.id)

    return asyncio.run(_run())
