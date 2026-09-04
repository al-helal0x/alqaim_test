from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.identity.infrastructure.models.identity_models import LoginAttempt


class LoginAttemptRepository:
    """طبقة وصول بيانات لجدول `login_attempts`، تُستهلك من `LoginUseCase`
    لتطبيق Rate Limiting وقفل الحساب المؤقت على `/auth/login`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, *, email: str, ip_address: str | None, success: bool) -> None:
        self._session.add(
            LoginAttempt(email=email.lower(), ip_address=ip_address, success=success)
        )
        await self._session.flush()

    async def count_recent_failures_by_email(self, email: str, *, since: datetime) -> int:
        stmt = select(func.count()).select_from(LoginAttempt).where(
            LoginAttempt.email == email.lower(),
            LoginAttempt.success.is_(False),
            LoginAttempt.created_at >= since,
        )
        return (await self._session.execute(stmt)).scalar_one()

    async def count_recent_failures_by_ip(self, ip_address: str, *, since: datetime) -> int:
        stmt = select(func.count()).select_from(LoginAttempt).where(
            LoginAttempt.ip_address == ip_address,
            LoginAttempt.success.is_(False),
            LoginAttempt.created_at >= since,
        )
        return (await self._session.execute(stmt)).scalar_one()
