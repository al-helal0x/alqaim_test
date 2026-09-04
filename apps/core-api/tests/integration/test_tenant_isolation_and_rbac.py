"""يغطي أهم قاعدتين معماريتين إلزاميتين (القسم 6.10 / 17): لا مستخدم يستطيع
لمس بيانات شركة أخرى، ولا صلاحية تُمنح بدون تفويض صريح عبر role_permissions.
"""
import pytest

from modules.identity.application.dto.identity_dto import RegisterCompanyRequest
from modules.identity.application.use_cases.auth_use_cases import RegisterCompanyUseCase
from modules.identity.infrastructure.models.identity_models import Permission
from modules.identity.infrastructure.repositories.permission_repository import (
    SqlPermissionChecker,
)
from modules.tenancy.application.dto.tenancy_dto import WarehouseCreateRequest
from modules.tenancy.application.use_cases.company_use_cases import CreateWarehouseUseCase
from platform_core.auth_middleware import TenantContext
from platform_core.security import decode_token

pytestmark = pytest.mark.asyncio


async def _ensure_permission_seeded(db_session) -> None:
    existing = await db_session.execute(
        Permission.__table__.select().where(Permission.code == "tenancy.branch.create")
    )
    if existing.first() is None:
        db_session.add(Permission(code="tenancy.branch.create", description="x"))
        await db_session.commit()


async def _register(db_session, email: str):
    await _ensure_permission_seeded(db_session)
    tokens = await RegisterCompanyUseCase(db_session).execute(
        RegisterCompanyRequest(
            company_name=f"Company for {email}",
            admin_full_name="Admin",
            admin_email=email,
            admin_password="StrongPass123",
        )
    )
    payload = decode_token(tokens.access_token, expected_type="access")
    return TenantContext(company_id=payload["company_id"], user_id=payload["sub"])


async def test_owner_gets_permission_granted_at_registration(db_session):
    ctx = await _register(db_session, "owner-a@alqaim-demo.com")
    checker = SqlPermissionChecker(db_session)
    assert await checker.has_permission(ctx, "tenancy.branch.create") is True


async def test_user_has_no_permission_in_unrelated_company(db_session):
    ctx_a = await _register(db_session, "owner-b@alqaim-demo.com")
    ctx_b = await _register(db_session, "owner-c@alqaim-demo.com")

    checker = SqlPermissionChecker(db_session)
    # صلاحيات owner-b صحيحة داخل شركته فقط
    assert await checker.has_permission(ctx_a, "tenancy.branch.create") is True
    # لكن لا يملك أي صلاحية إذا انتحلنا company_id الخاص بشركة أخرى
    forged_ctx = TenantContext(company_id=ctx_b.company_id, user_id=ctx_a.user_id)
    assert await checker.has_permission(forged_ctx, "tenancy.branch.create") is False


async def test_cannot_create_warehouse_in_another_companys_branch(db_session):
    from modules.tenancy.infrastructure.models.tenancy_models import Branch

    ctx_a = await _register(db_session, "owner-d@alqaim-demo.com")
    ctx_b = await _register(db_session, "owner-e@alqaim-demo.com")

    # فرع تابع لشركة B فعلياً
    branch_b = Branch(company_id=ctx_b.company_id, name="فرع B")
    db_session.add(branch_b)
    await db_session.commit()
    await db_session.refresh(branch_b)

    # مستخدم من شركة A يحاول إنشاء مستودع داخل فرع يعود لشركة B
    with pytest.raises(ValueError, match="لا يعود لشركتك"):
        await CreateWarehouseUseCase(db_session).execute(
            ctx_a, WarehouseCreateRequest(branch_id=str(branch_b.id), name="مستودع مخترق")
        )
