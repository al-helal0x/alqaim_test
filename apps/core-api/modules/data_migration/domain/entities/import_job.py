"""كيانات domain صرفة — تمثيل منطقي فقط، بدون SQLAlchemy وبدون أي I/O.
الـ Models الفعلية (SQLAlchemy) في infrastructure/models/data_migration_models.py
تُطابق هذه الحقول لكنها طبقة منفصلة تماماً (القسم 6.4 — Domain لا يعرف DB)."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal  # تذكير: أي مبلغ يُستورَد لاحقاً Decimal فقط، أبداً float
from uuid import UUID

from modules.data_migration.domain.value_objects.enums import (
    ImportStatus,
    SourceType,
    TargetEntity,
)


@dataclass
class TableDescriptor:
    """نتيجة اكتشاف جدول واحد في المصدر — تُبنى من discover_source_schema."""

    table_name: str
    columns: list[str]
    estimated_row_count: int
    sample_rows: list[dict] = field(default_factory=list)  # أول عينة صغيرة فقط، ليس الجدول كاملاً


@dataclass
class FieldMapping:
    """تعيين حقل واحد من عمود مصدر إلى حقل هدف في AlQaim V2."""

    target_entity: TargetEntity
    source_column: str
    target_field: str
    transform: str | None = None  # اسم دالة تحويل اختيارية (مثال: "parse_arabic_date")


@dataclass
class ImportError:
    """خطأ سطر واحد أثناء الترحيل — لا يوقف بقية الدفعة (القسم §4.3 من الخطة)."""

    row_number: int
    table_name: str
    message: str
    raw_row: dict


def apply_field_mappings(row: dict, mappings: list[FieldMapping], *, target_entity: TargetEntity) -> dict:
    """دالة صرفة (بلا I/O): تحوّل سطراً خاماً من المصدر إلى dict بمفاتيح
    الحقول الهدف، حسب قائمة mappings الخاصة بـ target_entity فقط. مُصمَّمة
    لتُستدعى من use case المعاينة (بدون كتابة) واستخدام case الترحيل
    (بكتابة فعلية) على حد سواء — منطق تحويل واحد لا نسختان قد تنحرفان."""
    result: dict = {}
    for m in mappings:
        if m.target_entity is not target_entity:
            continue
        value = row.get(m.source_column)
        if m.transform:
            transform_fn = TRANSFORMS.get(m.transform)
            if transform_fn is None:
                raise ValueError(f"دالة تحويل غير معروفة: {m.transform}")
            value = transform_fn(value)
        result[m.target_field] = value
    return result


def _identity(value):
    return value


def _strip_or_none(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal_or_zero(value):
    from decimal import InvalidOperation

    if value is None or value == "":
        return Decimal(0)
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"قيمة غير صالحة كرقم عشري: {value!r}") from exc


# سجل دوال التحويل المسمّاة — يُشار إليها بالاسم من FieldMapping.transform
# بدل كود Python حر داخل ملف mapping profile (JSON)، لأسباب أمنية (لا eval).
TRANSFORMS = {
    "strip_or_none": _strip_or_none,
    "decimal_or_zero": _decimal_or_zero,
    "identity": _identity,
}


@dataclass
class ImportJob:
    id: UUID
    company_id: UUID
    source_type: SourceType
    status: ImportStatus
    created_at: datetime
    mappings: list[FieldMapping] = field(default_factory=list)
    total_rows: int = 0
    processed_rows: int = 0
    errors: list[ImportError] = field(default_factory=list)
