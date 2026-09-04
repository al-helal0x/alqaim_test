"""الواجهات المجرّدة لخدمات الذكاء الاصطناعي (القسم 7.9) — كل خدمة تعيش خلف
واجهتها فقط، بحيث يمكن استبدال أي تنفيذ (مثال: Tesseract → PaddleOCR → محرك
سحابي) دون لمس بقية الأنابيب (Pipeline) أو أي Module في core-api (القسم 7.10).
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class RawOcrResult:
    text: str
    confidence: float
    engine: str


@dataclass
class InvoiceLineDraft:
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    line_total: float | None = None
    confidence: float = 0.0


@dataclass
class InvoiceDraft:
    supplier_name_guess: str | None = None
    invoice_number_guess: str | None = None
    invoice_date_guess: str | None = None
    currency_guess: str | None = None
    subtotal_guess: float | None = None
    tax_guess: float | None = None
    discount_guess: float | None = None
    total_guess: float | None = None
    lines: list[InvoiceLineDraft] = field(default_factory=list)
    field_confidence: dict[str, float] = field(default_factory=dict)


@dataclass
class ValidationWarning:
    code: str
    message: str
    field: str | None = None
    severity: str = "warning"  # warning | error


@dataclass
class MatchCandidate:
    entity_id: str
    entity_text: str
    confidence: float


class IDocumentPreprocessor(Protocol):
    def preprocess(self, image_bytes: bytes) -> bytes: ...


class IOCREngine(Protocol):
    def extract(self, image_bytes: bytes, *, languages: str = "ara+eng") -> RawOcrResult: ...


class IInvoiceParser(Protocol):
    def parse(self, raw_text: str) -> InvoiceDraft: ...


class IEntityMatcher(Protocol):
    def match(
        self, query_text: str, candidates: list[tuple[str, str]]
    ) -> list[MatchCandidate]:
        """candidates: [(entity_id, entity_text), ...] → أفضل المرشحين مرتَّبين تنازلياً."""
        ...


class IValidator(Protocol):
    def validate(self, draft: InvoiceDraft, *, company_currency: str) -> list[ValidationWarning]: ...


class ILearningStore(Protocol):
    async def record_correction(
        self, *, company_id: str, draft_id: str, field_name: str,
        ai_predicted_value: str | None, user_corrected_value: str, corrected_by: str,
    ) -> None: ...


class ILLMProvider(Protocol):
    async def complete(self, prompt: str, *, context: dict | None = None) -> str: ...


class IRecommendationService(Protocol):
    def suggest_reorder(self, *, current_qty: float, avg_daily_usage: float, lead_time_days: int) -> dict: ...
