"""Middleware المصادقة وعزل الشركات (Multi-Tenancy) — القسم 6.10.

ترتيب التحقق الإلزامي لكل طلب API محمي:
1. Authentication  (JWT صالح — عبر get_current_context)
2. Tenant Isolation (company_id يُستخرج من التوكن فقط — لا يُقبل أبداً من الـ Body/Query)
3. Authorization    (RBAC عبر IPermissionChecker — يُستدعى صراحةً داخل كل Use Case)
4. Schema Validation (Pydantic — تلقائي عبر FastAPI)

مبدأ Zero Trust (القسم 6.10): TenantContext يُمرَّر بشكل صريح كوسيط لكل
استدعاء بين الطبقات، ولا يُقرأ company_id من أي مصدر غير التوكن الموقَّع.
"""
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from platform_core.config import get_settings
from platform_core.security import TokenPayloadError, decode_token

_bearer_scheme = HTTPBearer(auto_error=True)


@dataclass(frozen=True)
class TenantContext:
    """يُمرَّر بشكل صريح لكل استدعاء بين الوحدات — لا Global/Thread-local state."""

    company_id: str
    user_id: str
    branch_id: str | None = None


async def get_current_context(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> TenantContext:
    """FastAPI Dependency: يُحقَن في كل Endpoint محمي.

    مثال:
        @router.get("/partners")
        async def list_partners(ctx: TenantContext = Depends(get_current_context)):
            ...
    """
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except TokenPayloadError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    company_id = payload.get("company_id")
    user_id = payload.get("sub")
    if not company_id or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="توكن ناقص: company_id/sub مفقودان",
        )

    return TenantContext(
        company_id=company_id, user_id=user_id, branch_id=payload.get("branch_id")
    )


async def get_service_context(
    x_service_token: str | None = Header(default=None, alias="X-Service-Token"),
) -> None:
    """Dependency مصادقة خدمة-لخدمة (self-hosted) — **منفصل تماماً** عن
    ``get_current_context``. لا يُنتج ``TenantContext`` (لا يوجد مستخدم ولا
    توكن JWT هنا) — فقط يتحقّق من ترويسة ``X-Service-Token`` مقابل
    ``Settings.ai_platform_service_token``، ثم يسمح للـ Endpoint بمتابعة
    تنفيذه. أي ``company_id`` مطلوب على مسار محمي بهذا الـ Dependency
    يجب أن يأتي صراحةً كمعامل Query من المتصل — قرار موثَّق في
    README_عضو-1.md §3.2؛ مقبول فقط لأن المتصل موثوق عبر هذا المفتاح.

    يُستخدم حصرياً على مسارات القراءة الداخلية الجديدة (``/internal/...``)
    ولا يُطبَّق أبداً على ``get_current_context`` أو مسارات POST/PATCH
    الحالية الموجَّهة للمستخدمين.
    """
    settings = get_settings()
    expected = settings.ai_platform_service_token

    # القيمة الافتراضية في config.py تُستخدَم كعلامة "غير مُهيَّأ" عمداً —
    # نرفض صراحةً حتى لا يُفتَح المسار الداخلي بالكامل بمجرد نسيان تعيين
    # القيمة في .env (فشل آمن Fail-closed).
    if not expected or expected == "CHANGE_ME_IN_ENV" or not x_service_token or x_service_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Service-Token غير صحيح أو مفقود",
        )


class IPermissionChecker:
    """واجهة تحقق الصلاحيات (RBAC) — تُستهلك من كل الوحدات دون معرفة تفاصيل التنفيذ.
    التنفيذ الفعلي: modules/identity/infrastructure/repositories/permission_repository.py
    """

    async def has_permission(self, ctx: TenantContext, permission_code: str) -> bool:
        raise NotImplementedError


def require_permission(permission_code: str):
    """مصنع Dependency جاهز للاستخدام المباشر في أي Router:

        @router.post("/companies", dependencies=[Depends(require_permission("tenancy.company.create"))])
    """

    async def _checker(
        ctx: TenantContext = Depends(get_current_context),
    ) -> TenantContext:
        from modules.identity.infrastructure.repositories.permission_repository import (
            SqlPermissionChecker,
        )
        from platform_core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            checker = SqlPermissionChecker(session)
            allowed = await checker.has_permission(ctx, permission_code)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"صلاحية مفقودة: {permission_code}",
            )
        return ctx

    return _checker
