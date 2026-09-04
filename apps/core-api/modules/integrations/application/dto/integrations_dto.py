from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from shared_kernel.pydantic_types import UUIDStr

# الأحداث الفعلية المنشورة حالياً عبر event_bus (راجع docs/architecture/contracts.md §2
# و platform_core/event_bus.py) — القائمة تُبقي المستخدم من تسجيل اسم حدث غير موجود
# فعلياً بالخطأ.
KNOWN_EVENT_NAMES = {"InvoicePosted", "PaymentRecorded", "InvoiceDraftReady"}


class WebhookSubscriptionCreateRequest(BaseModel):
    target_url: str = Field(min_length=8, max_length=2048)
    event_types: list[str] = Field(min_length=1)

    @field_validator("event_types")
    @classmethod
    def _validate_event_types(cls, value: list[str]) -> list[str]:
        unknown = set(value) - KNOWN_EVENT_NAMES
        if unknown:
            raise ValueError(f"أحداث غير معروفة: {', '.join(sorted(unknown))}")
        return value

    @field_validator("target_url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValueError("target_url يجب أن يبدأ بـ http:// أو https://")
        return value


class WebhookSubscriptionResponse(BaseModel):
    id: UUIDStr
    target_url: str
    event_types: list[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookSubscriptionCreatedResponse(WebhookSubscriptionResponse):
    """يُعاد فقط من POST — المرة الوحيدة التي يظهر فيها السر كاملاً، حتى
    يستطيع العميل حفظه للتحقق من توقيع HMAC لاحقاً. `GET` العادي لا يكشف
    السر أبداً (لا في القائمة ولا بمعرِّف واحد)."""

    secret: str


class WebhookDeliveryResponse(BaseModel):
    id: UUIDStr
    event_name: str
    success: bool
    status_code: int | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
