from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.identity.application.dto.identity_dto import CreateUserRequest
from modules.identity.infrastructure.models.identity_models import Role, User, UserCompanyRole
from modules.identity.infrastructure.repositories.user_repository import UserRepository
from platform_core.auth_middleware import TenantContext
from platform_core.security import hash_password


class CreateUserUseCase:
    """يدعو مستخدماً جديداً (أو موجوداً مسبقاً في شركة أخرى) للشركة الحالية بدور محدد.
    يتطلب صلاحية `identity.user.create` (تُفرَض عبر require_permission في الـ Router).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: CreateUserRequest) -> User:
        # الدور المطلوب يجب أن يعود لنفس الشركة الحالية (عزل صارم)
        role_stmt = select(Role).where(
            Role.id == request.role_id, Role.company_id == ctx.company_id
        )
        role = (await self._session.execute(role_stmt)).scalar_one_or_none()
        if role is None:
            raise ValueError("الدور غير موجود أو لا يعود لشركتك")

        user = await UserRepository(self._session).get_by_email(request.email)
        if user is None:
            user = User(
                email=request.email.lower(),
                password_hash=hash_password(request.password),
                full_name=request.full_name,
            )
            self._session.add(user)
            await self._session.flush()

        existing_membership = await self._session.execute(
            select(UserCompanyRole).where(
                UserCompanyRole.user_id == user.id,
                UserCompanyRole.company_id == ctx.company_id,
            )
        )
        if existing_membership.scalar_one_or_none() is not None:
            raise ValueError("المستخدم عضو بالفعل في هذه الشركة")

        self._session.add(
            UserCompanyRole(user_id=user.id, company_id=ctx.company_id, role_id=role.id)
        )
        await self._session.commit()
        await self._session.refresh(user)
        return user
