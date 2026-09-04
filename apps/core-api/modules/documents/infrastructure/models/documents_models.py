"""جدول documents — مرفقات عامة قابلة للربط بأي كيان في أي Module آخر عبر
(entity_type, entity_id) بدل مفتاح خارجي صريح لكل نوع مستند — هذا عمداً،
لأن Module واحداً (documents) لا يجوز أن يستورد جداول كل الوحدات الأخرى
(القسم 11.2: ممنوع استيراد infrastructure الخاص بموديول آخر مباشرة).
"""
import uuid

from sqlalchemy import BigInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db_base import BaseModel


class Document(BaseModel):
    __tablename__ = "documents"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
