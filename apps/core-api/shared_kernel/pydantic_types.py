"""إصلاح حرج عابر للوحدات: SQLAlchemy مع UUID(as_uuid=True) يعيد كائنات
`uuid.UUID` فعلية، لكن Pydantic v2 (مع `from_attributes=True`) لا يحوّلها
تلقائياً لحقل `str` — يفشل بخطأ `string_type` عند أي استدعاء حقيقي عبر
HTTP/response_model (لم يظهر سابقاً لأن لا اختبار كان يمر فعلياً عبر Router
حقيقي — كل الاختبارات كانت تستدعي Use Cases مباشرة).

الحل: `UUIDStr` بديل لـ `str` في أي DTO حقل id/company_id/...، يقبل UUID أو
str أو None ويحوّله دائماً لـ str قبل التحقق.

الاستخدام: `id: UUIDStr` بدلاً من `id: str` في أي Response DTO يُبنى من
`model_validate(sqlalchemy_row)`.
"""
from typing import Annotated

from pydantic import BeforeValidator


def _to_str(value: object) -> object:
    if value is None:
        return value
    return str(value)


UUIDStr = Annotated[str, BeforeValidator(_to_str)]
