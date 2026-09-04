"""تنفيذ IPermissionChecker — يتحقق أن دور المستخدم داخل الشركة الحالية
(من TenantContext) يملك الصلاحية المطلوبة، عبر role_permissions.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.identity.infrastructure.models.identity_models import (
    Permission,
    RolePermission,
    UserCompanyRole,
)
from platform_core.auth_middleware import TenantContext


class SqlPermissionChecker:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_permission(self, ctx: TenantContext, permission_code: str) -> bool:
        stmt = (
            select(Permission.id)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserCompanyRole, UserCompanyRole.role_id == RolePermission.role_id)
            .where(
                UserCompanyRole.user_id == ctx.user_id,
                UserCompanyRole.company_id == ctx.company_id,
                Permission.code == permission_code,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
