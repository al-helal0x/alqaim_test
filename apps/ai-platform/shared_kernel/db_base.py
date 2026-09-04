"""نفس مبادئ shared_kernel/db_base.py في core-api (UUID PK + Audit Fields —
القسم 8.2)، لكن معرَّفة هنا بشكل مستقل لأن ai-platform قاعدة بيانات منفصلة
فعلياً (القسم 8.5) ولا يجوز أن تستورد من core-api مباشرة (لا اعتماد كود بين
الخدمتين — التواصل فقط عبر Job Queue + Events، القسم 7.10)."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class AuditFieldsMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BaseModel(Base, AuditFieldsMixin):
    __abstract__ = True
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
