"""جداول ai-platform — القسم 8.5. company_id هنا مرجع منطقي فقط (لا FK فعلي
لأنه في قاعدة بيانات core-api المختلفة فيزيائياً — عزل الخدمتين مقصود).
"""
import uuid

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db_base import BaseModel


class OcrJob(BaseModel):
    __tablename__ = "ocr_jobs"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    attachment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    # queued | processing | done | failed
    engine_used: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String, nullable=True)


class InvoiceExtractionDraft(BaseModel):
    __tablename__ = "invoice_extraction_drafts"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    ocr_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ocr_jobs.id"), nullable=False
    )
    extracted_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    matched_supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending_review", nullable=False)
    # pending_review | approved | rejected
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[str | None] = mapped_column(String, nullable=True)


class EntityMatchSuggestion(BaseModel):
    __tablename__ = "entity_match_suggestions"

    extraction_draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoice_extraction_drafts.id"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)  # product | supplier
    extracted_text: Mapped[str] = mapped_column(String, nullable=False)
    matched_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_confirmed: Mapped[bool] = mapped_column(default=False, nullable=False)
    user_selected_alternative_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )


class AiLearningFeedback(BaseModel):
    """جوهر حلقة التعلّم — القسم 7.6."""

    __tablename__ = "ai_learning_feedback"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    extraction_draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoice_extraction_drafts.id"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    ai_predicted_value: Mapped[str | None] = mapped_column(String, nullable=True)
    user_corrected_value: Mapped[str] = mapped_column(String, nullable=False)
    corrected_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class EntityEmbedding(BaseModel):
    """يستخدم pgvector في الإنتاج (`VECTOR(768)` — القسم 8.5/7.12). هنا نستخدم
    `ARRAY(Float)` كبديل متوافق مع أي محرك PostgreSQL قياسي أثناء التطوير
    المحلي دون امتداد pgvector مُفعَّل؛ الترحيل للإنتاج يستبدل النوع فقط دون
    تغيير أي كود مستهلك (Repository يخفي هذا التفصيل تماماً)."""

    __tablename__ = "entity_embeddings"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_text: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)
