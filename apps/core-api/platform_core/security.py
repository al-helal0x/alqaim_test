"""تجزئة كلمات المرور وتوليد/فك تشفير JWT — القسم 6.10.

Access Token قصير العمر (15 دقيقة افتراضياً) + Refresh Token طويل العمر
(30 يوم) مخزَّن كـ Hash فقط في جدول refresh_tokens (لا يُخزَّن نص صريح
حتى في قاعدة البيانات — يسمح بإبطال جلسة واحدة دون بقية الجلسات).
"""
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from platform_core.config import get_settings

settings = get_settings()
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _pwd_context.verify(plain_password, password_hash)


def create_access_token(*, user_id: str, company_id: str, branch_id: str | None = None) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "company_id": company_id,
        "branch_id": branch_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def create_refresh_token(*, user_id: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_token_expire_days),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


class TokenPayloadError(Exception):
    pass


def decode_token(token: str, *, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except JWTError as exc:
        raise TokenPayloadError("توكن غير صالح أو منتهي الصلاحية") from exc

    if payload.get("type") != expected_type:
        raise TokenPayloadError(f"نوع التوكن غير متوقَّع: يُطلب {expected_type}")
    return payload


def hash_refresh_token(token: str) -> str:
    """Hash لتخزين refresh token في جدول `refresh_tokens` بدل النص الصريح.

    عمداً SHA-256 وليس bcrypt: الـ refresh token نفسه عالي الإنتروبيا (JWT
    موقَّع بمفتاح سري 256+ بت) وليس كلمة مرور بشرية قصيرة تحتاج مقاومة قوة
    غاشمة بطيئة عمداً؛ الحاجة الفعلية هنا هي بحث مساواة سريع في الجدول عبر
    index عادي (`WHERE token_hash = ?`) عند كل `/auth/refresh` و`/auth/logout`
    — وهو ما لا يوفّره bcrypt أصلاً لأنه غير حتمي (salt عشوائي لكل استدعاء).
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
