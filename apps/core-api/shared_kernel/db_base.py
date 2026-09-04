"""القاعدة المشتركة لكل SQLAlchemy Model في المشروع.

- UUID كمفتاح أساسي (وليس Integer تسلسلي) — يعالج ضعف V1 (القسم 1.3):
  يسهّل المزامنة Offline/Cloud مستقبلاً ولا يكشف حجم البيانات (IDOR).
- AuditFieldsMixin على كل جدول يحتاج تتبعاً.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from shared_kernel.audit_fields import AuditFieldsMixin


class Base(DeclarativeBase):
    pass


class BaseModel(Base, AuditFieldsMixin):
    """كل Model في المشروع يرث من هذا الصف. لا Integer IDs إطلاقاً."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)


def utcnow() -> datetime:
    return datetime.now(UTC)
