"""ProcessInvoiceDocumentUseCase — تنفيذ خط الأنابيب الكامل من القسم 7.11:

Image/PDF → Preprocessing → OCR → Invoice Understanding → Entity Recognition
→ Validation → Product Matching → Supplier Matching → (تخزين كمسودة تنتظر
مراجعة بشرية إلزامية — لا اعتماد تلقائي إطلاقاً، القسم 7.5/17).

يُستدعى من Celery worker (workers/tasks.py) بعد التقاط مهمة
`ProcessInvoiceDocument` من طابور Redis التي ينشرها core-api (القسم 7.10).
"""
from dataclasses import dataclass
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from application.ports.ai_ports import (
    IDocumentPreprocessor,
    IEntityMatcher,
    IInvoiceParser,
    IOCREngine,
    IValidator,
)
from models.ai_models import InvoiceExtractionDraft, OcrJob

# اتفاق سطرين (مهمة 7، منسّق مع مالك core-api) — توقيع الناشر الذي تحقنه
# طبقات الاستدعاء (workers/tasks.py و documents_router.py). أي دالة نشر
# متوافقة مع platform_core.redis_events.publish_event تُقبَل هنا مباشرة.
EventPublisher = Callable[[str, dict], Awaitable[None]]


@dataclass
class ProductCandidate:
    id: str
    name: str


@dataclass
class SupplierCandidate:
    id: str
    name: str


class ProcessInvoiceDocumentUseCase:
    """كل تبعية تُحقَن كواجهة مجرّدة (Port) — يمكن استبدال أي محرك دون تعديل
    هذا الملف إطلاقاً (مبدأ Dependency Inversion المطلوب صراحة في القسم 7.9).
    """

    def __init__(
        self,
        session: AsyncSession,
        preprocessor: IDocumentPreprocessor,
        ocr_engine: IOCREngine,
        invoice_parser: IInvoiceParser,
        product_matcher: IEntityMatcher,
        supplier_matcher: IEntityMatcher,
        validator: IValidator,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self._session = session
        self._preprocessor = preprocessor
        self._ocr_engine = ocr_engine
        self._invoice_parser = invoice_parser
        self._product_matcher = product_matcher
        self._supplier_matcher = supplier_matcher
        self._validator = validator
        # اختياري عمداً: المسارات التي لا تحتاج نشر أحداث (اختبارات، تحليل
        # تجريبي محلي) تبقى تعمل دون Redis. القرار التجاري بشأن *متى* يُنشر
        # الحدث محسوم أدناه في execute() فقط عند نجاح المعالجة كاملة.
        self._event_publisher = event_publisher

    async def execute(
        self,
        *,
        company_id: str,
        attachment_id: str,
        image_bytes: bytes,
        company_currency: str,
        known_products: list[ProductCandidate] | None = None,
        known_suppliers: list[SupplierCandidate] | None = None,
    ) -> InvoiceExtractionDraft:
        job = OcrJob(company_id=company_id, attachment_id=attachment_id, status="processing")
        self._session.add(job)
        await self._session.flush()

        try:
            cleaned_image = self._preprocessor.preprocess(image_bytes)
            ocr_result = self._ocr_engine.extract(cleaned_image)
            draft = self._invoice_parser.parse(ocr_result.text)
            warnings = self._validator.validate(draft, company_currency=company_currency)

            supplier_matches = []
            if draft.supplier_name_guess and known_suppliers:
                supplier_matches = self._supplier_matcher.match(
                    draft.supplier_name_guess,
                    [(s.id, s.name) for s in known_suppliers],
                )

            line_matches = []
            if known_products:
                for line in draft.lines:
                    matches = self._product_matcher.match(
                        line.description, [(p.id, p.name) for p in known_products]
                    )
                    line_matches.append({"line": line.description, "matches": [
                        {"entity_id": m.entity_id, "text": m.entity_text, "confidence": m.confidence}
                        for m in matches
                    ]})

            job.status = "done"
            job.engine_used = ocr_result.engine
            job.confidence_score = ocr_result.confidence

            payload = {
                "supplier_name_guess": draft.supplier_name_guess,
                "invoice_number_guess": draft.invoice_number_guess,
                "invoice_date_guess": draft.invoice_date_guess,
                "currency_guess": draft.currency_guess,
                "subtotal_guess": draft.subtotal_guess,
                "tax_guess": draft.tax_guess,
                "discount_guess": draft.discount_guess,
                "total_guess": draft.total_guess,
                "lines": [
                    {
                        "description": l.description, "quantity": l.quantity,
                        "unit_price": l.unit_price, "line_total": l.line_total,
                        "confidence": l.confidence,
                    }
                    for l in draft.lines
                ],
                "field_confidence": draft.field_confidence,
                "validation_warnings": [
                    {"code": w.code, "message": w.message, "field": w.field, "severity": w.severity}
                    for w in warnings
                ],
                "supplier_matches": [
                    {"entity_id": m.entity_id, "text": m.entity_text, "confidence": m.confidence}
                    for m in supplier_matches
                ],
                "line_matches": line_matches,
            }

            extraction_draft = InvoiceExtractionDraft(
                company_id=company_id,
                ocr_job_id=job.id,
                extracted_payload=payload,
                matched_supplier_id=(
                    supplier_matches[0].entity_id
                    if supplier_matches and supplier_matches[0].confidence >= 0.92
                    else None
                ),
                status="pending_review",  # إلزامي دائماً — لا اعتماد تلقائي (القسم 7.5/17)
            )
            self._session.add(extraction_draft)
            await self._session.commit()
            await self._session.refresh(extraction_draft)

            if self._event_publisher is not None:
                has_validation_errors = any(w.severity == "error" for w in warnings)
                await self._event_publisher(
                    "InvoiceDraftReady",
                    {
                        "draft_id": str(extraction_draft.id),
                        "company_id": company_id,
                        "ocr_job_id": str(job.id),
                        "confidence": ocr_result.confidence,
                        "supplier_name_guess": draft.supplier_name_guess,
                        "matched_supplier_id": (
                            str(extraction_draft.matched_supplier_id)
                            if extraction_draft.matched_supplier_id
                            else None
                        ),
                        "total_guess": draft.total_guess,
                        "has_validation_errors": has_validation_errors,
                    },
                )

            return extraction_draft

        except Exception as exc:  # noqa: BLE001 — نسجّل الفشل في job بدل كسر الـ worker
            job.status = "failed"
            job.error_message = str(exc)
            await self._session.commit()
            raise
