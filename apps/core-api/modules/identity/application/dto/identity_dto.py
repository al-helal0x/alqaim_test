from pydantic import BaseModel, EmailStr, Field

from shared_kernel.pydantic_types import UUIDStr


class RegisterCompanyRequest(BaseModel):
    """تسجيل أولي: ينشئ الشركة + أول مستخدم (Owner) دفعة واحدة (Bootstrap)."""

    company_name: str = Field(min_length=2, max_length=255)
    default_currency: str = Field(default="IQD", min_length=3, max_length=3)
    admin_full_name: str = Field(min_length=2, max_length=255)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    company_id: str | None = Field(
        default=None, description="مطلوب فقط إذا كان المستخدم عضواً في أكثر من شركة"
    )


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUIDStr
    email: str
    full_name: str
    is_active: bool

    model_config = {"from_attributes": True}


class CreateUserRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role_id: str
