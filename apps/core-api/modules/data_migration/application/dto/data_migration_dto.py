from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from modules.data_migration.domain.value_objects.enums import (
    ImportStatus,
    SourceType,
    TargetEntity,
)


class CreateImportJobRequest(BaseModel):
    source_type: SourceType
    # بيانات اتصال المصدر (مثال: connection string لـ SQL Server مؤقت بعد
    # استعادة .bak، أو معرّف ملف مرفوع مسبقاً عبر /documents). لا كلمات مرور
    # تُخزَّن كنص صريح — راجع TASK-MIG-02 في خطة البناء لآلية إدارة الأسرار.
    connection_ref: str


class ImportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_type: SourceType
    status: ImportStatus
    total_rows: int
    processed_rows: int
    created_at: datetime


class TableDescriptorResponse(BaseModel):
    table_name: str
    columns: list[str]
    estimated_row_count: int
    sample_rows: list[dict]


class FieldMappingRequest(BaseModel):
    target_entity: TargetEntity
    source_column: str
    target_field: str
    transform: str | None = None


class SetMappingRequest(BaseModel):
    mappings: list[FieldMappingRequest]


class PreviewResultResponse(BaseModel):
    """نتيجة مرحلة المعاينة — بدون أي كتابة فعلية (القسم §4.3، المرحلة 4)."""

    target_entity: TargetEntity
    total_rows: int
    valid_rows: int
    error_count: int
    sample_errors: list[str]


class CommitResultResponse(BaseModel):
    job_id: UUID
    status: ImportStatus
    processed_rows: int
    error_count: int
