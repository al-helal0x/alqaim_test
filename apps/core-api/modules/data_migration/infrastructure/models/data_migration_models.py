"""جداول data_migration. راجع TASK-MIG-02 في خطة البناء قبل توليد أول Migration
فعلي (`alembic revision --autogenerate`) — تأكد من import هذا الملف في
migrations/env.py مثل بقية الموديولات أولاً وإلا لن يكتشفه autogenerate."""
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db_base import BaseModel


class ImportJob(BaseModel):
    __tablename__ = "data_migration_import_jobs"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="connected")
    # مرجع اتصال المصدر — ليس كلمة مرور صريحة، بل معرّف سرّ مُدار (راجع
    # TASK-MIG-02 لآلية التخزين الآمن، منسجمة مع secrets.token_hex المستخدَم
    # فعلياً في modules/integrations لأسرار الـ Webhooks)
    connection_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    mappings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ImportBatch(BaseModel):
    """سجل تنفيذ كل دفعة — للتتبّع وإعادة المحاولة عند فشل جزئي، بدل إعادة
    الاستيراد كاملاً من الصفر (يماثل مبدأ Outbox المطبَّق فعلياً في المشروع:
    كل خطوة قابلة للتتبع وإعادة المحاولة، لا عملية "كل شيء أو لا شيء" ضخمة)."""

    __tablename__ = "data_migration_import_batches"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_migration_import_jobs.id"), nullable=False, index=True
    )
    target_entity: Mapped[str] = mapped_column(String(64), nullable=False)
    offset: Mapped[int] = mapped_column(Integer, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    success: Mapped[bool] = mapped_column(nullable=False, default=False)


class ImportRowError(BaseModel):
    __tablename__ = "data_migration_import_row_errors"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_migration_import_jobs.id"), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    table_name: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_row: Mapped[dict] = mapped_column(JSONB, nullable=False)
