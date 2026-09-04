"""application/use_cases/process_qr_document_use_case.py — `ProcessQrDocumentUseCase`
(TASK-AI-05b).

مسار دخول ثانٍ **بديل كامل**، لا يعتمد على `process_document_pipeline.py`
ولا يعدّله بأي شكل (Files الممنوع لمسها في 00_TASK_PACKAGE.md § TASK-AI-05b).
يبني `Draft` مباشرة من `QrInvoicePayload` بثقة كاملة — لا OCR، لا تخمين
Fuzzy Matching، فقط تحقق `checksum` + مطابقة `company_id` + بحث اختياري عن
المورد. من هذه النقطة فصاعداً: **نفس** `InvoiceExtractionDraft` ونفس مسار
`Human Review → Approve → core-api` الموجود فعلياً — صفر تعديل هناك.
"""
from __future__ import annotations

import logging

import httpx
from qr_invoice_codec import QrInvoicePayload
from qr_invoice_codec import decode as qr_decode
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.core_api_client import CoreApiClient
from infrastructure.qr_reader import IQrCodeReader
from models.ai_models import InvoiceExtractionDraft, OcrJob

logger = logging.getLogger(__name__)

# عتبة تطابق اسم المورد لاعتماد matched_supplier_id تلقائياً. نستخدم مطابقة
# نصية دقيقة (بعد تطبيع بسيط: strip + casefold) لا Fuzzy Matching — بيانات
# QR بثقة كاملة أصلاً، فمطابقة اسم تقريبية هنا قد "تخمّن" مورداً خاطئاً رغم
# أن البيانات نفسها مؤكدة 100%؛ الأصح تركه لمراجعة بشرية عند أي شك (نفس
# سلوك عدم المطابقة في مسار OCR الحالي — راجع Tests Required في
# 00_TASK_PACKAGE.md § TASK-AI-05b).
#
# ⚠️ قرار مفتوح يحتاج تنسيقاً مع مالك core-api (نفس روح تحذير العقد في
# core_api_client.py): العقد الحالي المتفق عليه لـ`/internal/partners/
# known-suppliers` يعيد فقط `{id, name}` — **لا يعيد الرقم الضريبي**. بطاقة
# المهمة الأصلية افترضت مطابقة عبر `sup.tax` "بحث مباشر"، لكن هذا يتطلب
# endpoint جديد أو حقلاً إضافياً في العقد القائم لم يُتفَق عليه بعد. التنفيذ
# هنا يستخدم مطابقة بالاسم (`sup.n`) كحل مؤقت آمن (فشل المطابقة = مراجعة
# بشرية، لا اعتماد خاطئ) — يحتاج قراراً صريحاً لاحقاً: هل يُضاف حقل `tax`
# لعقد `known-suppliers`، أم endpoint منفصل `lookup-by-tax`؟


class QrNotFoundError(Exception):
    """لا يوجد أي رمز QR قابل للقراءة في الصورة المرسَلة إطلاقاً.

    **مختلف تماماً** عن وجود رمز QR تالف (`qr_invoice_codec.ChecksumMismatchError`)
    — رسالتا 422 مختلفتان تماماً للمستخدم النهائي؛ لا يجوز دمجهما في نفس
    الاستثناء أو نفس الرسالة (راجع Tests Required في § TASK-AI-05b).
    """


class CompanyMismatchError(Exception):
    """حقل `co` في حمولة QR لا يطابق `company_id` الفعلي لجلسة/طلب المستخدم.

    **دفاع أمني إلزامي** — `co` من داخل QR نفسه لا يُعتمَد كمصدر ثقة وحيد
    (Security/Tenancy Considerations في § TASK-AI-05b): أي مستخدم يقدر يصوّر
    QR لفاتورة مورّد تخص شركة أخرى وتمريره هنا؛ رفض هذا الاستثناء صراحةً هو
    ما يمنع تسريب/حقن بيانات عابر للشركات (cross-tenant).
    """

    def __init__(self, *, qr_company_id: str, request_company_id: str) -> None:
        self.qr_company_id = qr_company_id
        self.request_company_id = request_company_id
        super().__init__(
            "company_id في رمز QR لا يطابق company_id الفعلي للطلب — رفض صريح"
        )


class ProcessQrDocumentUseCase:
    """يبني `InvoiceExtractionDraft` مباشرة من صورة QR — بلا preprocessing،
    بلا OCR، بلا parsing احتمالي. كل تبعية مُحقَنة (نفس مبدأ Dependency
    Inversion المتبع في `ProcessInvoiceDocumentUseCase`، القسم 7.9)."""

    def __init__(
        self,
        session: AsyncSession,
        qr_reader: IQrCodeReader,
        core_api_client: CoreApiClient | None = None,
    ) -> None:
        self._session = session
        self._qr_reader = qr_reader
        # اختياري عمداً: لو TASK-AI-04 لم تكتمل بعد في بيئة معينة، يمكن تشغيل
        # هذا المسار بدون مطابقة مورد إطلاقاً (matched_supplier_id=None دائماً،
        # يُترك بالكامل للمراجعة البشرية) — "لا اعتماد إلزامي" per Dependencies.
        self._core_api_client = core_api_client

    async def execute(
        self,
        *,
        company_id: str,
        attachment_id: str,
        image_bytes: bytes,
    ) -> InvoiceExtractionDraft:
        raw_text = self._qr_reader.read(image_bytes)
        if raw_text is None:
            raise QrNotFoundError("لم يُعثَر على رمز QR في الصورة")

        # QrCodecError (وفروعها: ChecksumMismatchError / UnsupportedVersionError
        # / MalformedPayloadError) تُعاد رفعها كما هي بلا التقاط هنا — طبقة
        # الراوتر هي من تميّز النوع الدقيق لاختيار رسالة 422 المناسبة.
        payload: QrInvoicePayload = qr_decode(raw_text)

        if payload.co != company_id:
            raise CompanyMismatchError(
                qr_company_id=payload.co, request_company_id=company_id
            )

        matched_supplier_id = await self._match_supplier(company_id, payload)

        job = OcrJob(
            company_id=company_id,
            attachment_id=attachment_id,
            status="done",
            engine_used="qr",
            confidence_score=1.0,
        )
        self._session.add(job)
        await self._session.flush()

        extracted_payload = self._build_extracted_payload(payload)

        extraction_draft = InvoiceExtractionDraft(
            company_id=company_id,
            ocr_job_id=job.id,
            extracted_payload=extracted_payload,
            matched_supplier_id=matched_supplier_id,
            status="pending_review",  # إلزامي دائماً — نفس القاعدة العامة
            # (القسم 7.5/17): حتى مع ثقة 100% في القراءة، لا اعتماد تلقائي
            # لفاتورة فعلية بلا مراجعة بشرية — هذا خارج نطاق ما تحله هذه
            # المهمة (دقة الاستخراج)، وضمن نطاق التحكم التشغيلي المتعمَّد
            # في مسار الفواتير ككل.
        )
        self._session.add(extraction_draft)
        await self._session.commit()
        await self._session.refresh(extraction_draft)
        return extraction_draft

    async def _match_supplier(
        self, company_id: str, payload: QrInvoicePayload
    ) -> str | None:
        if self._core_api_client is None:
            return None
        try:
            known_suppliers = await self._core_api_client.fetch_known_suppliers(
                company_id
            )
        except httpx.HTTPError as exc:
            # نفس روح ADR-001 المتبعة في documents_router._fetch_known_entities:
            # تعذّر الاتصال بـcore-api لا يُسقِط الطلب، يكمل بلا مطابقة.
            logger.warning(
                "تعذَّر الاتصال بـ core-api لمطابقة المورد عبر QR "
                "(company_id=%s): %s",
                company_id,
                exc,
            )
            return None

        target = payload.sup.n.strip().casefold()
        for supplier in known_suppliers:
            if supplier.name.strip().casefold() == target:
                return supplier.id
        return None

    @staticmethod
    def _build_extracted_payload(payload: QrInvoicePayload) -> dict:
        """نفس شكل `extracted_payload` الذي يبنيه `process_document_pipeline.py`
        (نفس المفاتيح تقريباً) حتى تبقى واجهة `/ai/drafts/{id}` الموجودة
        فعلياً (`DraftResponse.extracted_payload: dict`) موحَّدة بصرف النظر
        عن مصدر المسودة — لا تعديل مطلوب على طبقة العرض/المراجعة البشرية.
        حقول إضافية خاصة بمصدر QR (`source`, `qr_schema_version`,
        `supplier_tax_number`) تُضاف بدون كسر أي مستهلك حالي يقرأ فقط
        المفاتيح المشتركة مع مسار OCR.
        """
        lines = [
            {
                "description": line.p,
                "quantity": line.q,
                "unit_price": line.u,
                "line_total": round(line.q * line.u * (1 + line.tax / 100), 2),
                "confidence": 1.0,
            }
            for line in payload.ln
        ]
        field_confidence = {
            "supplier_name_guess": 1.0,
            "invoice_number_guess": 1.0,
            "invoice_date_guess": 1.0,
            "currency_guess": 1.0,
            "total_guess": 1.0,
        }
        return {
            "supplier_name_guess": payload.sup.n,
            "supplier_tax_number": payload.sup.tax,
            "invoice_number_guess": payload.no,
            "invoice_date_guess": payload.dt,
            "currency_guess": payload.cur,
            "subtotal_guess": None,
            "tax_guess": None,
            "discount_guess": None,
            "total_guess": payload.tot,
            "lines": lines,
            "field_confidence": field_confidence,
            "validation_warnings": [],
            "supplier_matches": [],
            "line_matches": [],
            "source": "qr",
            "qr_schema_version": payload.v,
        }
