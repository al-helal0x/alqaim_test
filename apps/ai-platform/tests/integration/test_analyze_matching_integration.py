"""يغطي البندين الأول والثاني من "الاختبارات المطلوبة" في README_عضو-2.md:

1) core-api حي (mock ناجح) + مورّد معروف → matched_supplier_id غير None في
   المسودة المخزَّنة فعلياً.
2) core-api معطَّل (محاكاة انقطاع اتصال) → pipeline.execute() يكمل بنجاح
   بلا مطابقة (known_suppliers=None) — لا استثناء غير مُتحكَّم به (أي ما
   يوازي عدم رجوع 500 من /analyze لو حدث هذا في الراوتر الحقيقي).

يستخدم test doubles بسيطة لـ preprocessor/OCR/parser/validator (بدل
tesseract/opencv الحقيقيين، غير المضمَّنين في حزمة هذا العضو المعزولة)
حتى نختبر فعلياً نقطة التكامل الحقيقية بيننا: _fetch_known_entities +
CoreApiClient + pipeline.execute() + FuzzyEntityMatcher الحقيقي + قاعدة
بيانات حقيقية (SQLite في الذاكرة عبر db_session من conftest)."""
import httpx
import pytest
import respx

from application.ports.ai_ports import InvoiceDraft, RawOcrResult, ValidationWarning
from application.use_cases.process_document_pipeline import ProcessInvoiceDocumentUseCase
from infrastructure.core_api_client import CoreApiClient
from platform_core.config import Settings
from presentation.routes.documents_router import _fetch_known_entities
from services.entity_matching.entity_matcher import FuzzyEntityMatcher

pytestmark = pytest.mark.asyncio

_SETTINGS = Settings(
    core_api_base_url="http://core-api.internal:8000",
    ai_platform_service_token="test-service-token",
)
_COMPANY_ID = "11111111-1111-1111-1111-111111111111"


class _FakePreprocessor:
    def preprocess(self, image_bytes: bytes) -> bytes:
        return image_bytes


class _FakeOCREngine:
    def extract(self, image_bytes: bytes, *, languages: str = "ara+eng") -> RawOcrResult:
        return RawOcrResult(text="fake-ocr-text", confidence=0.95, engine="fake")


class _FakeInvoiceParser:
    """يرجع اسم مورّد قريب جداً (بفرق إملائي بسيط) من known_suppliers، تماماً
    كما يحدث واقعياً مع OCR — هذا ما يفعّل FuzzyEntityMatcher الحقيقي."""

    def parse(self, raw_text: str) -> InvoiceDraft:
        return InvoiceDraft(supplier_name_guess="Basra Electronics LLC", total_guess=16500.0)


class _FakeValidator:
    def validate(self, draft: InvoiceDraft, *, company_currency: str) -> list[ValidationWarning]:
        return []


def _build_pipeline_with_fakes(session):
    return ProcessInvoiceDocumentUseCase(
        session=session,
        preprocessor=_FakePreprocessor(),
        ocr_engine=_FakeOCREngine(),
        invoice_parser=_FakeInvoiceParser(),
        product_matcher=FuzzyEntityMatcher(),
        supplier_matcher=FuzzyEntityMatcher(),
        validator=_FakeValidator(),
    )


@respx.mock
async def test_analyze_flow_sets_matched_supplier_id_when_core_api_live(db_session):
    # ⚠️ إصلاح حقيقي: كان المعرِّف الوهمي هنا "s-1" (غير صالح كـUUID) — يمر
    # بصمت عبر respx/matching، لكن session.refresh(extraction_draft) بعدها
    # يفشل فعلياً لأن عمود matched_supplier_id مُعرَّف UUID (نوع SQLite
    # مخصَّص في conftest.py يحاول uuid.UUID(value)). اكتُشِف فقط بتشغيل هذا
    # الاختبار حقيقياً هنا لأول مرة؛ في الواقع الفعلي معرِّفات
    # /internal/partners/known-suppliers دائماً UUID حقيقي (Partner.id في
    # core-api) — استُبدِل بمعرِّف UUID شكلاً ليطابق الواقع، وليس لتفادي
    # الاختبار.
    respx.get(
        "http://core-api.internal:8000/internal/partners/known-suppliers",
        params={"company_id": _COMPANY_ID},
    ).mock(
        return_value=httpx.Response(
            200, json=[{"id": "33333333-3333-3333-3333-333333333333", "name": "Basra Electronics LLC"}]
        )
    )
    respx.get(
        "http://core-api.internal:8000/internal/catalog/known-products",
        params={"company_id": _COMPANY_ID},
    ).mock(return_value=httpx.Response(200, json=[]))

    known_suppliers, known_products = await _fetch_known_entities(
        _COMPANY_ID, client=CoreApiClient(settings=_SETTINGS)
    )
    assert known_suppliers is not None and known_products is not None

    pipeline = _build_pipeline_with_fakes(db_session)
    draft = await pipeline.execute(
        company_id=_COMPANY_ID,
        attachment_id="22222222-2222-2222-2222-222222222222",
        image_bytes=b"fake-bytes",
        company_currency="IQD",
        known_suppliers=known_suppliers,
        known_products=known_products,
    )

    assert draft.status == "pending_review"
    assert draft.matched_supplier_id is not None
    assert str(draft.matched_supplier_id) == "33333333-3333-3333-3333-333333333333"


@respx.mock
async def test_analyze_flow_completes_without_match_when_core_api_down(db_session):
    respx.get("http://core-api.internal:8000/internal/partners/known-suppliers").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    respx.get("http://core-api.internal:8000/internal/catalog/known-products").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    # لا يجب أن يرفع استثناءً — هذا هو جوهر معالجة الفشل الإلزامية (خطوة 5)
    known_suppliers, known_products = await _fetch_known_entities(
        _COMPANY_ID, client=CoreApiClient(settings=_SETTINGS)
    )
    assert known_suppliers is None
    assert known_products is None

    pipeline = _build_pipeline_with_fakes(db_session)
    draft = await pipeline.execute(
        company_id=_COMPANY_ID,
        attachment_id="33333333-3333-3333-3333-333333333333",
        image_bytes=b"fake-bytes",
        company_currency="IQD",
        known_suppliers=known_suppliers,
        known_products=known_products,
    )

    # يكمل بنجاح ويُخزَّن بحالة pending_review كالمعتاد — بلا مطابقة، بلا انهيار
    assert draft.status == "pending_review"
    assert draft.matched_supplier_id is None
