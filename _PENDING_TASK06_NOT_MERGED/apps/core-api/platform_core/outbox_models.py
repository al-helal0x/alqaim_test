"""جدول outbox_events — مهمة 6 (Outbox Pattern لـ event_bus، القسم 6.6).

الفكرة: أي حدث يُراد نشره يُكتَب أولاً كسطر هنا **ضمن نفس معاملة قاعدة
البيانات** التي أنتجت الحدث (نفس commit — راجع platform_core/event_bus.py:
EventBus.publish لا يعمل commit بنفسه، بل session.add + flush فقط، ليبقى
جزءاً من معاملة المستدعي). هذا يضمن عدم فقدان الحدث أبداً حتى لو تعطّل
التطبيق بين حفظ التغيير التجاري ونشر الحدث فعلياً للمشتركين.

التسليم الفعلي للمشتركين المحليين يتم لاحقاً (محاولة فورية بعد الـ commit،
ثم Worker دوري كشبكة أمان — انظر platform_core/outbox_worker.py) وليس هنا؛
هذا الملف نموذج بيانات فقط.
"""
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db_base import BaseModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class OutboxEventStatus(str, Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    FAILED = "failed"  # تجاوز الحد الأقصى لعدد المحاولات — يحتاج تدخلاً يدوياً


class OutboxEvent(BaseModel):
    """سطر واحد لكل حدث يُراد نشره عبر event_bus. لا علاقة مباشرة بأي جدول
    عمل آخر عمداً (عزل تام — القسم 11.2)، لذا لا company_id هنا: من يحتاجه
    يقرأه من payload نفسه (كل الأحداث المُعلَنة في contracts.md §2 تتضمنه
    صراحة في حمولتها)."""

    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_events_status_next_attempt", "status", "next_attempt_at"),
    )

    event_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=OutboxEventStatus.PENDING.value
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # متى تُحاوَل التسليم مجدداً — تُساوي created_at افتراضياً (محاولة فورية)،
    # وتُدفَع للأمام عند فشل محاولة (Exponential Backoff) — انظر outbox_worker.py
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
