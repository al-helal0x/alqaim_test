"""جداول identity — users/roles/permissions/role_permissions/user_company_roles
(القسم 8). Role/Permission معرَّفة على مستوى الشركة (كل شركة تدير أدوارها
الخاصة) لتفادي تسريب صلاحيات بين المستأجرين (Tenants).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared_kernel.db_base import BaseModel


class User(BaseModel):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Role(BaseModel):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_roles_company_code"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "owner", "accountant"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_system_role: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    permissions: Mapped[list["RolePermission"]] = relationship(back_populates="role")


class Permission(BaseModel):
    """كتالوج صلاحيات عام على مستوى النظام (ليس لكل شركة) — تُزرَع عبر Migration/Seed.
    الشكل: `{module}.{resource}.{action}` مثل `accounting.journal_entry.post`.
    """

    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("code", name="uq_permissions_code"),)

    code: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class RolePermission(BaseModel):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False, index=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("permissions.id"), nullable=False, index=True
    )

    role: Mapped["Role"] = relationship(back_populates="permissions")
    permission: Mapped["Permission"] = relationship()


class UserCompanyRole(BaseModel):
    """ربط مستخدم بشركة بدور معيّن — يسمح لنفس المستخدم بالعمل في أكثر من شركة
    (مكتب محاسبة يخدم عدة عملاء مثلاً) بأدوار مختلفة في كل شركة.
    """

    __tablename__ = "user_company_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_user_company"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False, index=True
    )


class RefreshToken(BaseModel):
    """تخزين Hash فقط (SHA-256) لكل Refresh Token صادر — لا نص صريح إطلاقاً في
    قاعدة البيانات (راجع `platform_core/security.py::hash_refresh_token`).

    يسمح بإبطال جلسة واحدة تحديداً عند `/auth/logout` دون التأثير على بقية
    جلسات نفس المستخدم على أجهزة أخرى، وبإبطال+إصدار جديد (Rotation) عند كل
    `/auth/refresh` لتقليل نافذة إعادة استخدام توكن مسروق لطلب واحد فقط.

    `revoked_at` منفصل عمداً عن `deleted_at` (Soft Delete القياسي في
    AuditFieldsMixin): إبطال توكن حدث عمل صريح (Logout/Rotation) وليس حذفاً
    منطقياً للسجل — نحتفظ بالسجل نفسه للتدقيق.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LoginAttempt(BaseModel):
    """سجل كل محاولة دخول (ناجحة أو فاشلة) على `/auth/login` — يُستخدم حصراً
    لحساب Rate Limiting وقفل الحساب المؤقت (5 محاولات فاشلة/15 دقيقة)، بمعيارين
    مستقلّين: البريد الإلكتروني (قفل حساب) وعنوان IP (Rate Limiting عام).

    معياران منفصلان عمداً: معيار IP فقط كان سيسمح لمهاجم يبدّل عنوانه بتجاوز
    القفل على حساب معيّن؛ معيار البريد فقط كان سيسمح لمهاجم خلف IP واحد
    باستهلاك محاولات آلاف الحسابات دفعة واحدة دون أن يُوقَف.
    """

    __tablename__ = "login_attempts"

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
