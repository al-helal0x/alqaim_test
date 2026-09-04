"""جداول integrations — Webhooks الصادرة فقط في هذه المرحلة (النطاق الكامل
المذكور في README — Import/Export — مؤجَّل عمداً؛ خارج نطاق هذا التسليم)."""
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db_base import BaseModel


class WebhookSubscription(BaseModel):
    __tablename__ = "webhook_subscriptions"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    secret: Mapped[str] = mapped_column(String(128), nullable=False)
    # قائمة أسماء أحداث (مثل ["InvoicePosted", "PaymentRecorded"]) — JSONB
    # بدل جدول علاقة منفصل لأن عدد الأحداث لكل اشتراك صغير جداً عادة (§ بساطة أولاً)
    event_types: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class WebhookDelivery(BaseModel):
    """سجل كل محاولة إرسال — للمراقبة والتشخيص عند فشل تسليم عميل خارجي."""

    __tablename__ = "webhook_deliveries"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("webhook_subscriptions.id"), nullable=False, index=True
    )
    event_name: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
