"""جداول pos (blueprint القسم 13 العضو 4): `pos_sessions, pos_sync_queue`.

pos_sync_queue هو آلية "Offline-first Simulated" (القسم 8/41 في Blueprint):
كل عملية بيع من جهاز POS تحمل `client_reference` (معرّف يولّده الجهاز نفسه،
مثال UUID محلي) — يضمن ذلك أن إعادة إرسال نفس العملية بعد انقطاع اتصال لا
تُنشئ فاتورتين (Idempotency)، تماماً كما لو كان الجهاز يعمل Offline ثم يُزامن.
"""
import uuid
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db_base import BaseModel


class PosSession(BaseModel):
    __tablename__ = "pos_sessions"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False
    )
    opened_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    closing_cash: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    opened_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)


class PosSyncQueueItem(BaseModel):
    __tablename__ = "pos_sync_queue"
    __table_args__ = (
        UniqueConstraint("company_id", "client_reference", name="uq_pos_sync_client_reference"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_sessions.id"), nullable=False, index=True
    )
    client_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    sales_invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)
