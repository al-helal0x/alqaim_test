"""حقول تدقيق موحّدة تُضاف لكل SQLAlchemy Model يحتاج تتبعاً (القسم 1.3 — معالجة
غياب Audit Trail في V1).

- soft delete عبر deleted_at (لا حذف فعلي أبداً من الجداول المالية/التشغيلية).
- created_by/updated_by يخزّنان user_id كنص (UUID) وليس علاقة صارمة، لتفادي
  اعتماديات دائرية بين shared_kernel و identity.
"""
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuditFieldsMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
