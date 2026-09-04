"""جدول notifications — إشعارات على مستوى الشركة كاملة (لا توجيه لمستخدم
بعينه في هذه الجولة، راجع README لتوثيق هذا القيد)."""
import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db_base import BaseModel


class Notification(BaseModel):
    __tablename__ = "notifications"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    event_name: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
