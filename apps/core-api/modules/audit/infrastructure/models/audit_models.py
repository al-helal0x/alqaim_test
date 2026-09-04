"""جداول audit — تسجيل تدقيق شامل لكل الأحداث الستة المُعلَنة في
docs/architecture/contracts.md §2 (بلا انتقائية، عكس notifications)."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db_base import BaseModel


class AuditLogEntry(BaseModel):
    __tablename__ = "audit_log_entries"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    event_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
