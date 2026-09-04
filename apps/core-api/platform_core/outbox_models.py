"""OutboxEvent — نموذج ORM فقط (بلا أي منطق نشر/تسليم، لا Worker، لا
Exponential Backoff — ذلك من اختصاص تنفيذ #6 الفعلي لاحقًا).

**محدَّث ضمن Task #6-S2 (Migration Chain Fix):** جدول `outbox_events` صار
له الآن migration فعلية (`migrations/versions/platform_20260809_0002_outbox_events.py`،
مبنية فوق الرأس الفعلي المتحقَّق منه `sales_20260809_0001` — راجع
تعليق تلك الـ migration لتفصيل لماذا ليس `identity_20260808_0003` كما
ورد في بطاقة تسليم #6 الأصلية). شكل الحقول هنا مطابق تمامًا لما زُرع في
تلك الـ migration وما ورد في DELIVERY_CARD_TASK_06.md — لم يتغيّر شيء في
تعريف الحقول نفسها عن النسخة المؤقتة السابقة، فقط تأكيد أنها الآن مدعومة
بجدول حقيقي بدل كونها تعريفًا معلَّقًا.
"""
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db_base import Base


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # مضافة ضمن Track 1 (تنفيذ #6×#11×#12×#10) — عقد enqueue_event() المجمَّد
    # في INTERFACE_CONTRACT_OUTBOX.md يتطلب aggregate_id إلزامياً، لكن الجدول
    # كما ورد في migration platform_20260809_0002 لم يتضمّنه. أُضيف هنا +
    # migration تابعة (platform_20260812_0003) بدل تعديل تلك الـ migration
    # القائمة أصلاً (Postgres حقيقي قد يكون طبّقها فعلاً — تعديل migration
    # مطبَّقة يكسر alembic، إضافة migration تالية لا). Nullable لأنه معلومة
    # مفيدة للاستعلام (كل أحداث Aggregate معيّن) لا قيد عمل.
    aggregate_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
