"""Use Cases مصادقة — تُغطّي "مسار الاستخدام الأساسي الكامل" (تسجيل شركة
جديدة + دخول + تجديد توكن + خروج)، مع تصليب Auth (مهمة #5 — خطة الإغلاق):

1. `refresh_tokens` تُخزَّن كـ hash فقط (لا نص صريح) وتُبطَل صراحة عند
   `/auth/logout`، وتُدار عبر Rotation (إبطال القديم + إصدار جديد) عند كل
   `/auth/refresh` لتقليل نافذة إعادة استخدام توكن مسروق.
2. Rate Limiting وقفل حساب مؤقت على `/auth/login`: 5 محاولات فاشلة خلال
   15 دقيقة (بمعيارين مستقلّين: البريد الإلكتروني وعنوان IP).
"""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.identity.application.dto.identity_dto import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterCompanyRequest,
    TokenResponse,
)
from modules.identity.infrastructure.models.identity_models import (
    Permission,
    Role,
    RolePermission,
    User,
    UserCompanyRole,
)
from modules.identity.infrastructure.repositories.login_attempt_repository import (
    LoginAttemptRepository,
)
from modules.identity.infrastructure.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from modules.identity.infrastructure.repositories.user_repository import UserRepository
from modules.tenancy.infrastructure.models.tenancy_models import Company
from platform_core.config import get_settings
from platform_core.security import (
    TokenPayloadError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from shared_kernel.db_base import utcnow

# صلاحية الملّاك: wildcard مطابقة لكل شيء (المطابقة تحدث في IPermissionChecker
# بالإضافة لهذه الحالة الخاصة، أو عبر زرع كل الصلاحيات لدور owner في Migration).
OWNER_ROLE_CODE = "owner"

# حدود Rate Limiting / قفل الحساب على /auth/login (القسم 17 — منع Brute Force).
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 5
LOGIN_RATE_LIMIT_WINDOW_MINUTES = 15


class AccountLockedError(Exception):
    """يُرفع عند تجاوز حد محاولات الدخول الفاشلة المسموح بها خلال النافذة
    الزمنية (سواء لحساب معيّن أو لعنوان IP) — يُترجَم في الراوتر إلى
    429 Too Many Requests، بدل 401 المستخدَمة لبيانات الدخول الخاطئة.
    """


def _refresh_token_expiry() -> datetime:
    settings = get_settings()
    return utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)


class RegisterCompanyUseCase:
    """ينشئ شركة جديدة + مستخدم Owner + دور Owner بكل الصلاحيات، بمعاملة واحدة.
    هذا هو مسار onboarding الوحيد المفتوح بدون مصادقة مسبقة.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, request: RegisterCompanyRequest) -> TokenResponse:
        existing = await UserRepository(self._session).get_by_email(request.admin_email)
        if existing is not None:
            raise ValueError("البريد الإلكتروني مستخدَم مسبقاً")

        company = Company(
            name=request.company_name, default_currency=request.default_currency
        )
        self._session.add(company)
        await self._session.flush()

        owner_role = Role(
            company_id=company.id, code=OWNER_ROLE_CODE, name="Owner", is_system_role=True
        )
        self._session.add(owner_role)
        await self._session.flush()

        # منح كل الصلاحيات الموجودة حالياً في الكتالوج لدور Owner
        all_permissions = (await self._session.execute(select(Permission))).scalars().all()
        for perm in all_permissions:
            self._session.add(RolePermission(role_id=owner_role.id, permission_id=perm.id))

        user = User(
            email=request.admin_email.lower(),
            password_hash=hash_password(request.admin_password),
            full_name=request.admin_full_name,
        )
        self._session.add(user)
        await self._session.flush()

        self._session.add(
            UserCompanyRole(user_id=user.id, company_id=company.id, role_id=owner_role.id)
        )
        await self._session.commit()

        access = create_access_token(user_id=str(user.id), company_id=str(company.id))
        refresh = create_refresh_token(user_id=str(user.id))
        await RefreshTokenRepository(self._session).store(
            user_id=str(user.id), token=refresh, expires_at=_refresh_token_expiry()
        )
        await self._session.commit()
        return TokenResponse(access_token=access, refresh_token=refresh)


class LoginUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, request: LoginRequest, *, ip_address: str | None = None
    ) -> TokenResponse:
        attempts = LoginAttemptRepository(self._session)
        window_start = utcnow() - timedelta(minutes=LOGIN_RATE_LIMIT_WINDOW_MINUTES)

        email_failures = await attempts.count_recent_failures_by_email(
            request.email, since=window_start
        )
        if email_failures >= LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
            raise AccountLockedError(
                "الحساب مُقفَل مؤقتاً بسبب محاولات دخول فاشلة متكررة — حاول مجدداً بعد دقائق"
            )
        if ip_address is not None:
            ip_failures = await attempts.count_recent_failures_by_ip(
                ip_address, since=window_start
            )
            if ip_failures >= LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
                raise AccountLockedError(
                    "تم تجاوز الحد المسموح من محاولات الدخول من هذا العنوان — حاول لاحقاً"
                )

        async def _fail(message: str) -> None:
            await attempts.record(email=request.email, ip_address=ip_address, success=False)
            await self._session.commit()
            raise ValueError(message)

        user = await UserRepository(self._session).get_by_email(request.email)
        if user is None or not user.is_active:
            await _fail("بيانات الدخول غير صحيحة")
        if not verify_password(request.password, user.password_hash):
            await _fail("بيانات الدخول غير صحيحة")

        stmt = select(UserCompanyRole).where(UserCompanyRole.user_id == user.id)
        memberships = (await self._session.execute(stmt)).scalars().all()
        if not memberships:
            await _fail("المستخدم غير مرتبط بأي شركة")

        if request.company_id:
            membership = next(
                (m for m in memberships if str(m.company_id) == request.company_id), None
            )
            if membership is None:
                await _fail("المستخدم لا ينتمي لهذه الشركة")
        elif len(memberships) == 1:
            membership = memberships[0]
        else:
            await _fail(
                "المستخدم عضو في أكثر من شركة — يجب تمرير company_id عند الدخول"
            )

        access = create_access_token(user_id=str(user.id), company_id=str(membership.company_id))
        refresh = create_refresh_token(user_id=str(user.id))
        await RefreshTokenRepository(self._session).store(
            user_id=str(user.id), token=refresh, expires_at=_refresh_token_expiry()
        )
        await attempts.record(email=request.email, ip_address=ip_address, success=True)
        await self._session.commit()
        return TokenResponse(access_token=access, refresh_token=refresh)


class RefreshTokenUseCase:
    """يُصدر Access Token جديد من Refresh Token صالح، ويُدوِّر (Rotate) الـ
    Refresh Token نفسه: يُبطِل القديم فوراً ويُصدر واحداً جديداً، بدل إعادة
    استخدام نفس التوكن — يحدّ من نافذة إعادة استخدام توكن مسروق لطلب واحد.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, request: RefreshRequest) -> TokenResponse:
        try:
            payload = decode_token(request.refresh_token, expected_type="refresh")
        except TokenPayloadError as exc:
            raise ValueError(str(exc)) from exc

        token_repo = RefreshTokenRepository(self._session)
        stored = await token_repo.get_active_by_token(request.refresh_token)
        if stored is None:
            raise ValueError("refresh token غير صالح أو تم إبطاله مسبقاً")

        user = await UserRepository(self._session).get_by_id(payload["sub"])
        if user is None or not user.is_active:
            raise ValueError("مستخدم غير صالح")

        stmt = select(UserCompanyRole).where(UserCompanyRole.user_id == user.id)
        memberships = (await self._session.execute(stmt)).scalars().all()
        if not memberships:
            raise ValueError("المستخدم غير مرتبط بأي شركة")

        # في غياب company_id داخل refresh token: نفترض أول عضوية (يكفي للـ MVP
        # بحكم أن أغلب المستخدمين ينتمون لشركة واحدة فقط — التحسين لاحقاً).
        company_id = str(memberships[0].company_id)
        access = create_access_token(user_id=str(user.id), company_id=company_id)
        new_refresh = create_refresh_token(user_id=str(user.id))

        await token_repo.revoke(stored)
        await token_repo.store(
            user_id=str(user.id), token=new_refresh, expires_at=_refresh_token_expiry()
        )
        await self._session.commit()
        return TokenResponse(access_token=access, refresh_token=new_refresh)


class LogoutUseCase:
    """يُبطل refresh token محدد فقط (الجلسة الحالية) — بقية جلسات نفس المستخدم
    على أجهزة أخرى تبقى سارية. لا يشترط Access Token صالحاً عمداً: Logout قد
    يُستدعى بعد انتهاء صلاحية access token (15 دقيقة) بينما refresh token لا
    يزال سارياً؛ الأمان يعتمد على معرفة قيمة refresh token نفسها (سر عالي
    الإنتروبيا)، والعملية idempotent (راجع `revoke_by_token`).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, request: LogoutRequest) -> None:
        await RefreshTokenRepository(self._session).revoke_by_token(request.refresh_token)
        await self._session.commit()
