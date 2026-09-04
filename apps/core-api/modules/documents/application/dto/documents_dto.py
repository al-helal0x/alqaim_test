"""DTOs لموديول documents (Attachment Manager عام — العضو 13)."""
from datetime import datetime

from pydantic import BaseModel, Field

from shared_kernel.pydantic_types import UUIDStr


class DocumentResponse(BaseModel):
    id: UUIDStr
    entity_type: str
    entity_id: str
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_by: UUIDStr
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadMeta(BaseModel):
    """حقول Form (وليست JSON body) — الملف نفسه يصل عبر UploadFile في الـ
    router مباشرة، لذا هذا الـ DTO يغطي الحقول الوصفية المرافقة فقط."""

    entity_type: str = Field(min_length=2, max_length=64)
    entity_id: str = Field(min_length=1, max_length=128)
