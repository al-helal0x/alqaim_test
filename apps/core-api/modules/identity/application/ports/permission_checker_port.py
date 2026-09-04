"""IPermissionChecker — Port مُعلَن (contracts.md). التنفيذ الفعلي في
infrastructure/repositories/permission_repository.py."""
from typing import Protocol

from platform_core.auth_middleware import TenantContext


class IPermissionChecker(Protocol):
    async def has_permission(self, ctx: TenantContext, permission_code: str) -> bool: ...
