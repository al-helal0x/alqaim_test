"""مسارات /ai/documents/* و /ai/drafts/* — القسم 9.7. تُعرَض فعلياً خلف
بوابة core-api في الإنتاج (نفس Auth/RBAC الموحّد)، ومباشرة هنا للتطوير/الاختبار
المحلي لخدمة ai-platform بمعزل عن core-api (استقلالية النشر — القسم 7.10).
"""
import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from qr_invoice_codec import (
    ChecksumMismatchError,
    MalformedPayloadError,
    UnsupportedVersionError,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.dto.ai_dto import (
    AnalyzeDocumentResponse,
    CorrectionRequest,
    DraftResponse,
    JobStatusResponse,
)
from application.use_cases.process_document_pipeline import (
    ProcessInvoiceDocumentUseCase,
    ProductCandidate,
    SupplierCandidate,
)
from application.use_cases.process_qr_document_use_case import (
    CompanyMismatchError,
    ProcessQrDocumentUseCase,
    QrNotFoundError,
)
from infrastructure.core_api_client import CoreApiClient
from infrastructure.qr_reader import PyzbarQrCodeReader
from models.ai_models import InvoiceExtractionDraft, OcrJob
from platform_core.database import get_db_session
from services.entity_matching.entity_matcher import FuzzyEntityMatcher
from services.invoice_parser.invoice_parser import HeuristicInvoiceParser
from services.learning.learning_store import SqlLearningStore
from services.ocr.ocr_engine import TesseractOCREngine
from services.preprocessing.preprocessor import OpenCvPreprocessor
from services.validation.validator import InvoiceValidator

logger = logging.getLogger(__name__)

router = APIRouter()

# ⚠️ ملاحظة (خطوة 1 في القسم 3.3 وREADME_عضو-2.md): حزمة هذا العضو معزولة
# ولا تتضمن apps/web أو أي عميل آخر لهذه الحزمة، لذا تعذَّر التحقق فعلياً من
# هوية المستدعي الحالي لـ /ai/documents/analyze من داخل هذا النطاق. يجب على
# من يملك رؤية كاملة للمستودع (أو العضو المسؤول عن الدمج النهائي) تأكيد ذلك
# قبل إغلاق TASK-AI-04 نهائياً — إن ظهر مستدعٍّ يمرّر بيانات مطابقة يدوياً
# اليوم (نمط الخيار ب)، يحتاج القرار هنا مراجعة.


def _build_pipeline(session: AsyncSession) -> ProcessInvoiceDocumentUseCase:
    from platform_core.redis_events import publish_event

    return ProcessInvoiceDocumentUseCase(
        session=session,
        preprocessor=OpenCvPreprocessor(),
        ocr_engine=TesseractOCREngine(),
        invoice_parser=HeuristicInvoiceParser(),
        product_matcher=FuzzyEntityMatcher(),
        supplier_matcher=FuzzyEntityMatcher(),
        validator=InvoiceValidator(),
        event_publisher=publish_event,
    )


async def _fetch_known_entities(
    company_id: str, client: CoreApiClient | None = None
) -> tuple[list[SupplierCandidate] | None, list[ProductCandidate] | None]:
    """يجلب الموردين/المنتجات المعروفين من core-api قبل تشغيل pipeline
    (النصف الثاني من TASK-AI-04، القسم 3.3 خطوة 4). عند تعذّر الاتصال
    (Timeout/خطأ اتصال/401 توكن خاطئ) **لا يُسقِط الطلب** — يُرجع
    (None, None) ويسجّل تحذيراً فقط، فيكمل pipeline.execute() بلا مطابقة
    (خطوة 5، بنفس روح ADR-001 — استقلالية نشر ai-platform عن core-api)."""
    client = client or CoreApiClient()
    try:
        known_suppliers = await client.fetch_known_suppliers(company_id)
        known_products = await client.fetch_known_products(company_id)
        return known_suppliers, known_products
    except httpx.HTTPError as exc:
        logger.warning(
            "تعذَّر الاتصال بـ core-api لجلب known_suppliers/known_products "
            "(company_id=%s) — المتابعة بلا مطابقة: %s",
            company_id,
            exc,
        )
        return None, None


@router.post(
    "/documents/analyze", response_model=AnalyzeDocumentResponse, status_code=status.HTTP_202_ACCEPTED
)
async def analyze_document(
    company_id: str,
    company_currency: str = "IQD",
    file: UploadFile | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> AnalyzeDocumentResponse:
    """في الإنتاج: ينشر مهمة على Redis/Celery ويرجع job_id فوراً (معالجة غير
    متزامنة — القسم 7.10). هنا: تنفيذ متزامن مباشر للتبسيط أثناء التطوير
    المحلي؛ workers/tasks.py يحتوي نسخة Celery الحقيقية لنفس المنطق تماماً.
    """
    if file is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ملف مطلوب")

    image_bytes = await file.read()
    known_suppliers, known_products = await _fetch_known_entities(company_id)
    pipeline = _build_pipeline(session)
    draft = await pipeline.execute(
        company_id=company_id,
        attachment_id=str(uuid.uuid4()),
        image_bytes=image_bytes,
        company_currency=company_currency,
        known_suppliers=known_suppliers,
        known_products=known_products,
    )
    return AnalyzeDocumentResponse(job_id=str(draft.ocr_job_id), status="done")


def _build_qr_use_case(session: AsyncSession) -> ProcessQrDocumentUseCase:
    """يعيد استخدام `CoreApiClient` الجاهز من `TASK-AI-04` اختيارياً فقط
    (Dependencies § TASK-AI-05: "لا اعتماد إلزامي") — إن تعذّر بناؤه لأي
    سبب بيئي، `ProcessQrDocumentUseCase` يعمل بلا مطابقة مورد تلقائية
    (`matched_supplier_id=None` دائماً، يُترك للمراجعة البشرية بالكامل)."""
    return ProcessQrDocumentUseCase(
        session=session,
        qr_reader=PyzbarQrCodeReader(),
        core_api_client=CoreApiClient(),
    )


@router.post(
    "/documents/analyze-qr",
    response_model=DraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def analyze_qr_document(
    company_id: str,
    file: UploadFile | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> DraftResponse:
    """مسار دخول ثانٍ يوازي `/documents/analyze` (TASK-AI-05b) — يتخطى
    OCR/Matching بالكامل حين تكون الصورة رمز QR بمخطط `qr_invoice_codec`.
    `Draft` يُبنى فوراً وبثقة كاملة، بلا حاجة لـpolling عبر job_id/status
    كما في المسار الأخرى — الاستجابة هنا متزامنة ومباشرة (`Draft` جاهز
    فور نجاح الاستدعاء)، لذا 201 لا 202.

    **إضافة صرفة — endpoint `/documents/analyze` القائم أعلاه لم يُعدَّل
    بأي حرف.**
    """
    if file is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ملف مطلوب")

    image_bytes = await file.read()
    use_case = _build_qr_use_case(session)

    try:
        draft = await use_case.execute(
            company_id=company_id,
            attachment_id=str(uuid.uuid4()),
            image_bytes=image_bytes,
        )
    except QrNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except ChecksumMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except UnsupportedVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except MalformedPayloadError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except CompanyMismatchError as exc:
        # عمداً 403 لا 422: هذه ليست بيانات غير صالحة، هي رفض تفويض/تسريب
        # عابر للشركات (Security/Tenancy Considerations § TASK-AI-05b) —
        # نفس منطق التمييز بين 409/422 المتبع في core-api § invoices_router.py
        # (فصل خطأ الحالة/التفويض عن خطأ بنية البيانات).
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc

    return DraftResponse(
        id=str(draft.id),
        status=draft.status,
        extracted_payload=draft.extracted_payload,
        matched_supplier_id=(
            str(draft.matched_supplier_id) if draft.matched_supplier_id else None
        ),
    )


@router.get("/documents/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str, session: AsyncSession = Depends(get_db_session)
) -> JobStatusResponse:
    """يتضمّن `draft_id` صراحة (عند وجوده) حتى يقدر المستهلك (عميل يعمل
    Polling على هذا المسار فقط، مثل PKG-A3 E2E) الانتقال مباشرة لـ
    `GET /ai/drafts/{draft_id}` دون أي مسار إضافي — قبل هذا الإصلاح لم يكن
    هناك أي طريق فعلي للوصول من job_id إلى draft_id عبر الـ API رغم أن
    العلاقة (`InvoiceExtractionDraft.ocr_job_id`) موجودة أصلاً في الموديل."""
    job = (await session.execute(select(OcrJob).where(OcrJob.id == job_id))).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مهمة غير موجودة")

    draft = (
        await session.execute(
            select(InvoiceExtractionDraft).where(InvoiceExtractionDraft.ocr_job_id == job.id)
        )
    ).scalar_one_or_none()

    return JobStatusResponse(
        job_id=str(job.id), status=job.status, engine_used=job.engine_used,
        confidence_score=job.confidence_score, error_message=job.error_message,
        draft_id=str(draft.id) if draft is not None else None,
    )


@router.get("/drafts/{draft_id}", response_model=DraftResponse)
async def get_draft(draft_id: str, session: AsyncSession = Depends(get_db_session)) -> DraftResponse:
    draft = (
        await session.execute(
            select(InvoiceExtractionDraft).where(InvoiceExtractionDraft.id == draft_id)
        )
    ).scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مسودة غير موجودة")
    return DraftResponse(
        id=str(draft.id), status=draft.status, extracted_payload=draft.extracted_payload,
        matched_supplier_id=str(draft.matched_supplier_id) if draft.matched_supplier_id else None,
    )


@router.post("/drafts/{draft_id}/confirm", response_model=DraftResponse)
async def confirm_draft(
    draft_id: str, reviewer_user_id: str, session: AsyncSession = Depends(get_db_session)
) -> DraftResponse:
    """اعتماد بشري إلزامي (القسم 7.6/17) — بعد هذه النقطة فقط يتحول لفاتورة
    فعلية في وحدة purchasing عبر حدث InvoiceDraftReady (يُترك للعضو المسؤول
    عن الاستهلاك — راجع docs/architecture/contracts.md)."""
    draft = (
        await session.execute(
            select(InvoiceExtractionDraft).where(InvoiceExtractionDraft.id == draft_id)
        )
    ).scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مسودة غير موجودة")

    draft.status = "approved"
    draft.reviewed_by = reviewer_user_id
    await session.commit()
    await session.refresh(draft)
    return DraftResponse(
        id=str(draft.id), status=draft.status, extracted_payload=draft.extracted_payload,
        matched_supplier_id=str(draft.matched_supplier_id) if draft.matched_supplier_id else None,
    )


@router.post("/drafts/{draft_id}/reject", response_model=DraftResponse)
async def reject_draft(
    draft_id: str, reviewer_user_id: str, session: AsyncSession = Depends(get_db_session)
) -> DraftResponse:
    draft = (
        await session.execute(
            select(InvoiceExtractionDraft).where(InvoiceExtractionDraft.id == draft_id)
        )
    ).scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مسودة غير موجودة")

    draft.status = "rejected"
    draft.reviewed_by = reviewer_user_id
    await session.commit()
    await session.refresh(draft)
    return DraftResponse(
        id=str(draft.id), status=draft.status, extracted_payload=draft.extracted_payload,
        matched_supplier_id=None,
    )


@router.post("/drafts/{draft_id}/corrections", status_code=status.HTTP_201_CREATED)
async def record_correction(
    draft_id: str,
    request: CorrectionRequest,
    company_id: str,
    corrected_by: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    store = SqlLearningStore(session)
    await store.record_correction(
        company_id=company_id, draft_id=draft_id, field_name=request.field_name,
        ai_predicted_value=request.ai_predicted_value,
        user_corrected_value=request.user_corrected_value, corrected_by=corrected_by,
    )
    return {"recorded": True}
