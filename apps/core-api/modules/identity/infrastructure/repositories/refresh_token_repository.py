from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.identity.infrastructure.models.identity_models import RefreshToken
from platform_core.security import hash_refresh_token
from shared_kernel.db_base import utcnow


def _as_aware_utc(value: datetime) -> datetime:
    """SQLite (مستخدَمة فقط في اختبارات integration، راجع tests/README.md)
    لا تحفظ معلومة المنطقة الزمنية وتُعيد datetime "ساذج" (naive) رغم أن
    العمود مُعرَّف كـ `DateTime(timezone=True)`؛ Postgres في الإنتاج تُعيده
    aware دائماً. هذه الدالة تطبّع القيمة قبل أي مقارنة لتفادي كسر السلوك
    في بيئة الاختبار دون التأثير على السلوك الفعلي في Postgres.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class RefreshTokenRepository:
    """طبقة وصول بيانات لجدول `refresh_tokens` — لا يتعامل أي مستدعٍ خارج هذا
    الملف مع `token_hash` أو النص الصريح للتوكن مباشرة؛ كل عملية بحث/تخزين
    تمر عبر `hash_refresh_token` هنا فقط.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def store(self, *, user_id: str, token: str, expires_at: datetime) -> RefreshToken:
        row = RefreshToken(
            user_id=user_id, token_hash=hash_refresh_token(token), expires_at=expires_at
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_active_by_token(self, token: str) -> RefreshToken | None:
        """يُعيد السجل فقط إن كان غير مُبطَل وغير منتهي الصلاحية بعد."""
        token_hash = hash_refresh_token(token)
        stmt = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is not None and _as_aware_utc(row.expires_at) < utcnow():
            return None
        return row

    async def revoke(self, row: RefreshToken) -> None:
        row.revoked_at = utcnow()
        await self._session.flush()

    async def revoke_by_token(self, token: str) -> None:
        """إبطال idempotent: لا يرفع خطأً إن كان التوكن غير موجود/مُبطَلاً
        مسبقاً — Logout يجب أن ينجح دائماً من منظور العميل، ولا يُسرّب ما إذا
        كان التوكن صالحاً أصلاً (تفادي كشف معلومات عبر رسالة الخطأ).
        """
        row = await self.get_active_by_token(token)
        if row is not None:
            row.revoked_at = utcnow()
            await self._session.flush()
