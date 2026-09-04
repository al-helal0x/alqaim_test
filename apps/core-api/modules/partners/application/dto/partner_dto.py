from decimal import Decimal

from pydantic import BaseModel, Field

from modules.partners.domain.rules import PartnerType
from shared_kernel.pydantic_types import UUIDStr


class PartnerCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    partner_type: PartnerType = PartnerType.CUSTOMER
    tax_number: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = None
    credit_limit: Decimal | None = None
    payment_terms_days: int = Field(default=0, ge=0)


class PartnerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    partner_type: PartnerType | None = None
    tax_number: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = None
    credit_limit: Decimal | None = None
    payment_terms_days: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class PartnerResponse(BaseModel):
    id: UUIDStr
    company_id: UUIDStr
    name: str
    partner_type: PartnerType
    tax_number: str | None
    phone: str | None
    email: str | None
    address: str | None
    credit_limit: Decimal | None
    payment_terms_days: int
    is_active: bool

    model_config = {"from_attributes": True}


class WalkInPartnerResponse(BaseModel):
    """PKG-B2 — استجابة endpoint walk-in. مُتعمَّد إبقاؤها صغيرة (id + name
    فقط) بدل إعادة استخدام PartnerResponse كاملة: المستهلك (Flutter POS) لا
    يحتاج فعلياً غير هذا id ليحفظه محلياً (cache) ويستخدمه كـpartner_id للبيع."""

    id: UUIDStr
    name: str

    model_config = {"from_attributes": True}


class PartnerDTO(BaseModel):
    """DTO المعلَن في docs/architecture/contracts.md §3 — يُستهلك من sales/purchasing/payments
    عبر IPartnerLookup. لا يتغيّر إلا بموافقة الفريق (يوم العقود)."""

    id: str
    name: str
    type: PartnerType
    tax_number: str | None
    company_id: str

    model_config = {"from_attributes": True}
