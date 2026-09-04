"""اختبارات ProcessQrDocumentUseCase (TASK-AI-05b) — تغطي الخمسة سيناريوهات
المطلوبة صراحة في 00_TASK_PACKAGE.md § TASK-AI-05b → "Tests Required":

1. QR صالح لمورد معروف → matched_supplier_id غير None.
2. QR صالح لمورد غير معروف → matched_supplier_id=None، يُترك للمراجعة البشرية.
3. QR تالف (checksum فاشل) → استثناء نوعي من عائلة qr_invoice_codec.QrCodecError
   (يترجمها الراوتر لـ422 — راجع presentation/routes/documents_router.py).
4. صورة بلا أي QR فيها إطلاقاً → QrNotFoundError (يترجمها الراوتر لـ422 مختلف).
5. company_id في QR لا يطابق الطلب → CompanyMismatchError (اختبار أمني مباشر).

نفس نمط test_pipeline_persists_draft.py/test_job_status_draft_lookup.py: تختبر
`ProcessQrDocumentUseCase` مباشرة (لا عبر HTTP/TestClient — لا سابقة لذلك في
هذه الحزمة، endpoint نفسه طبقة رقيقة جداً لتحويل استثناء→HTTPException فقط)،
باستخدام `db_session` الحقيقية (fixture من conftest.py — SQLite في الذاكرة عبر
aiosqlite، بنفس مخطط `models.ai_models` الفعلي) و`CoreApiClient` الحقيقي
(مموَّه عبر respx، بنفس نمط test_core_api_client.py — لا mock/stub وهمي).
"""
from __future__ import annotations

import io

import httpx
import pytest
import qrcode
import respx
from qr_invoice_codec import (
    QrCodecError,
    QrInvoiceLine,
    QrInvoicePayload,
    QrInvoiceSupplier,
    encode,
)
from qrcode.constants import ERROR_CORRECT_M
from sqlalchemy import select

from application.use_cases.process_qr_document_use_case import (
    CompanyMismatchError,
    ProcessQrDocumentUseCase,
    QrNotFoundError,
)
from infrastructure.core_api_client import CoreApiClient
from infrastructure.qr_reader import PyzbarQrCodeReader
from models.ai_models import InvoiceExtractionDraft, OcrJob
from platform_core.config import Settings

# لا حاجة لـ"pytestmark = pytest.mark.asyncio" هنا — asyncio_mode="auto" مضبوط
# فعلياً في pyproject.toml (يُعلِّم كل async def تلقائياً)، وهذا الملف يحتوي
# أيضاً اختبارات متزامنة صرفة (TestPyzbarQrCodeReader) كانت ستُعلَّم خطأً
# بـ@pytest.mark.asyncio لو استُخدم pytestmark على مستوى الملف.

_SETTINGS = Settings(
    core_api_base_url="http://core-api.internal:8000",
    ai_platform_service_token="test-service-token",
)
_COMPANY_ID = "11111111-1111-1111-1111-111111111111"


def _make_payload(supplier_name: str = "Furat General Trading Co") -> QrInvoicePayload:
    lines = [QrInvoiceLine(p="Cable 3x5mm", q=10, u=25.5, tax=15)]
    total = round(sum(line.q * line.u * (1 + line.tax / 100) for line in lines), 2)
    return QrInvoicePayload(
        co=_COMPANY_ID,
        sup=QrInvoiceSupplier(n=supplier_name, tax="3101234567"),
        cur="SAR",
        dt="2026-08-16",
        no="INV-2026-00042",
        ln=lines,
        tot=total,
    )


def _make_qr_text(payload: QrInvoicePayload | None = None) -> str:
    return encode(payload or _make_payload()).decode("ascii")


class _FakeQrReader:
    """قارئ QR وهمي — يعيد نصاً ثابتاً بدل قراءة صورة فعلية، لعزل اختبارات
    الحالة الأمنية/المنطقية عن مكتبة pyzbar (تلك تُختبَر بمعزل بالكامل في
    `TestPyzbarQrCodeReader` أدناه، مع صورة QR فعلية حقيقية)."""

    def __init__(self, text: str | None) -> None:
        self._text = text

    def read(self, _image_bytes: bytes) -> str | None:
        return self._text


# ---------------------------------------------------------------------------
# 1. مورد معروف
# ---------------------------------------------------------------------------


@respx.mock
async def test_valid_qr_known_supplier_sets_matched_supplier_id(db_session):
    payload = _make_payload(supplier_name="Furat General Trading Co")
    qr_text = _make_qr_text(payload)

    respx.get(
        "http://core-api.internal:8000/internal/partners/known-suppliers",
        params={"company_id": _COMPANY_ID},
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": "22222222-2222-2222-2222-222222222222", "name": "Furat General Trading Co"},
                {"id": "33333333-3333-3333-3333-333333333333", "name": "Najaf Trading Co"},
            ],
        )
    )

    use_case = ProcessQrDocumentUseCase(
        session=db_session,
        qr_reader=_FakeQrReader(qr_text),
        core_api_client=CoreApiClient(settings=_SETTINGS),
    )

    draft = await use_case.execute(
        company_id=_COMPANY_ID, attachment_id="44444444-4444-4444-4444-444444444444",
        image_bytes=b"irrelevant",
    )

    assert draft.status == "pending_review"
    assert str(draft.matched_supplier_id) == "22222222-2222-2222-2222-222222222222"
    assert draft.extracted_payload["source"] == "qr"
    assert draft.extracted_payload["total_guess"] == payload.tot
    assert len(draft.extracted_payload["lines"]) == 1

    # يتحقق فعلياً من الصف في قاعدة البيانات (لا فقط الكائن المُعاد) — نفس
    # منهج test_pipeline_persists_draft.py.
    job = (await db_session.execute(select(OcrJob).where(OcrJob.id == draft.ocr_job_id))).scalar_one()
    assert job.status == "done"
    assert job.engine_used == "qr"
    assert job.confidence_score == 1.0


# ---------------------------------------------------------------------------
# 2. مورد غير معروف
# ---------------------------------------------------------------------------


@respx.mock
async def test_valid_qr_unknown_supplier_leaves_unmatched(db_session):
    qr_text = _make_qr_text(_make_payload(supplier_name="Totally Unknown Supplier LLC"))

    respx.get(
        "http://core-api.internal:8000/internal/partners/known-suppliers",
        params={"company_id": _COMPANY_ID},
    ).mock(
        return_value=httpx.Response(
            200, json=[{"id": "22222222-2222-2222-2222-222222222222", "name": "Furat General Trading Co"}]
        )
    )

    use_case = ProcessQrDocumentUseCase(
        session=db_session,
        qr_reader=_FakeQrReader(qr_text),
        core_api_client=CoreApiClient(settings=_SETTINGS),
    )

    draft = await use_case.execute(
        company_id=_COMPANY_ID, attachment_id="55555555-5555-5555-5555-555555555555",
        image_bytes=b"irrelevant",
    )

    assert draft.status == "pending_review"
    assert draft.matched_supplier_id is None


async def test_no_core_api_client_leaves_unmatched_without_failing(db_session):
    """Dependencies § TASK-AI-05: "لا اعتماد إلزامي" — بلا core_api_client
    إطلاقاً، المسار يجب أن يعمل وينتج Draft صالحاً بلا مطابقة."""
    qr_text = _make_qr_text()

    use_case = ProcessQrDocumentUseCase(
        session=db_session, qr_reader=_FakeQrReader(qr_text), core_api_client=None
    )

    draft = await use_case.execute(
        company_id=_COMPANY_ID, attachment_id="66666666-6666-6666-6666-666666666666",
        image_bytes=b"irrelevant",
    )

    assert draft.status == "pending_review"
    assert draft.matched_supplier_id is None


@respx.mock
async def test_core_api_unreachable_leaves_unmatched_without_failing(db_session):
    """نفس روح ADR-001 المتبعة في documents_router._fetch_known_entities —
    تعذّر الاتصال بـcore-api لا يُسقِط الطلب."""
    qr_text = _make_qr_text()

    respx.get(
        "http://core-api.internal:8000/internal/partners/known-suppliers",
        params={"company_id": _COMPANY_ID},
    ).mock(side_effect=httpx.ConnectError("connection refused"))

    use_case = ProcessQrDocumentUseCase(
        session=db_session,
        qr_reader=_FakeQrReader(qr_text),
        core_api_client=CoreApiClient(settings=_SETTINGS),
    )

    draft = await use_case.execute(
        company_id=_COMPANY_ID, attachment_id="77777777-7777-7777-7777-777777777777",
        image_bytes=b"irrelevant",
    )

    assert draft.status == "pending_review"
    assert draft.matched_supplier_id is None


# ---------------------------------------------------------------------------
# 3. QR تالف
# ---------------------------------------------------------------------------


async def test_corrupted_checksum_raises_qr_codec_error(db_session):
    qr_text = _make_qr_text()
    mid = len(qr_text) // 2
    tampered = qr_text[:mid] + ("A" if qr_text[mid] != "A" else "B") + qr_text[mid + 1 :]

    use_case = ProcessQrDocumentUseCase(
        session=db_session, qr_reader=_FakeQrReader(tampered), core_api_client=None
    )

    # تغيير حرف واحد قد يكسر تدفق zlib نفسه قبل الوصول لمقارنة chk (فيظهر
    # كـMalformedPayloadError) أو يمر عبره لكن يفشل عند مقارنة chk
    # (ChecksumMismatchError) — كلاهما فرع من QrCodecError، استثناء نوعي
    # واضح لا استثناء عام غامض؛ الراوتر يترجم كليهما لـ422 (راجع
    # documents_router.analyze_qr_document).
    with pytest.raises(QrCodecError):
        await use_case.execute(
            company_id=_COMPANY_ID, attachment_id="88888888-8888-8888-8888-888888888888",
            image_bytes=b"irrelevant",
        )


# ---------------------------------------------------------------------------
# 4. لا يوجد QR في الصورة إطلاقاً
# ---------------------------------------------------------------------------


async def test_no_qr_in_image_raises_qr_not_found_error(db_session):
    use_case = ProcessQrDocumentUseCase(
        session=db_session, qr_reader=_FakeQrReader(None), core_api_client=None
    )

    with pytest.raises(QrNotFoundError):
        await use_case.execute(
            company_id=_COMPANY_ID, attachment_id="99999999-9999-9999-9999-999999999999",
            image_bytes=b"irrelevant",
        )


# ---------------------------------------------------------------------------
# 5. company_id مزوَّر (اختبار أمني)
# ---------------------------------------------------------------------------


async def test_forged_company_id_is_rejected(db_session):
    qr_text = _make_qr_text(_make_payload())  # co=_COMPANY_ID

    use_case = ProcessQrDocumentUseCase(
        session=db_session, qr_reader=_FakeQrReader(qr_text), core_api_client=None
    )

    with pytest.raises(CompanyMismatchError):
        await use_case.execute(
            company_id="00000000-0000-0000-0000-000000000000",  # شركة مختلفة عن co
            attachment_id="10101010-1010-1010-1010-101010101010",
            image_bytes=b"irrelevant",
        )

    # لا شيء يُكتب لقاعدة البيانات عند الرفض — تحقق فعلي لا افتراضي.
    count = len((await db_session.execute(select(InvoiceExtractionDraft))).all())
    assert count == 0


# ---------------------------------------------------------------------------
# infrastructure/qr_reader.py — تقريب آلي لبند GATE-QR اليدوي
# ---------------------------------------------------------------------------


class TestPyzbarQrCodeReader:
    def test_reads_real_qr_image_end_to_end(self):
        qr_text = _make_qr_text()

        qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M)
        qr.add_data(qr_text, optimize=0)
        qr.make(fit=True)
        image = qr.make_image()

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        reader = PyzbarQrCodeReader()
        assert reader.read(buffer.getvalue()) == qr_text

    def test_returns_none_for_image_without_qr(self):
        from PIL import Image

        plain_image = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        plain_image.save(buffer, format="PNG")

        reader = PyzbarQrCodeReader()
        assert reader.read(buffer.getvalue()) is None

    def test_returns_none_for_unopenable_bytes(self):
        reader = PyzbarQrCodeReader()
        assert reader.read(b"not an image at all") is None
