"""جداول workflow — محرك حالات عام (State Machine) قابل للربط بأي كيان
(entity_type/entity_id، نفس نمط `documents`). بلا أي تكامل تلقائي مع أحداث
الوحدات الأخرى في هذه الجولة — راجع README لتوثيق هذا كـ TODO صريح."""
import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db_base import BaseModel


class WorkflowDefinition(BaseModel):
    __tablename__ = "workflow_definitions"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # ["draft", "pending", "approved", "rejected"]
    states: Mapped[list] = mapped_column(JSONB, nullable=False)
    # [{"name": "submit", "from": "draft", "to": "pending"}, ...]
    transitions: Mapped[list] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class WorkflowInstance(BaseModel):
    __tablename__ = "workflow_instances"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_definitions.id"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    current_state: Mapped[str] = mapped_column(String(64), nullable=False)
    # [{"from": ..., "to": ..., "at": ...}]
    history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
