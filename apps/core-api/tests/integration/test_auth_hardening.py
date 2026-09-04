"""اختبار تكامل يغطي معيار تسليم مهمة #5 (تصليب Auth — خطة الإغلاق):

- جدول `refresh_tokens` يخزّن hash فقط (لا نص صريح).
- `/auth/logout` يُبطل refresh token المحدد فقط (idempotent).
- `/auth/refresh` يُدوِّر (Rotate) refresh token: القديم يُبطَل، الجديد صالح.
- Rate Limiting + قفل حساب مؤقت على `/auth/login`: 5 محاولات فاشلة/15 دقيقة.
"""
from datetime import timedelta

import pytest
from sqlalchemy import select

from modules.identity.application.dto.identity_dto import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterCompanyRequest,
)
from modules.identity.application.use_cases.auth_use_cases import (
    AccountLockedError,
    LoginUseCase,
    LogoutUseCase,
    RefreshTokenUseCase,
    RegisterCompanyUseCase,
)
from modules.identity.infrastructure.models.identity_models import LoginAttempt, RefreshToken
from platform_core.security import decode_token, hash_refresh_token
from shared_kernel.db_base import utcnow

pytestmark = pytest.mark.asyncio


async def _register(db_session, email: str, password: str = "StrongPass123"):
    return await RegisterCompanyUseCase(db_session).execute(
        RegisterCompanyRequest(
            company_name="شركة اختبار Auth",
            admin_full_name="Admin",
            admin_email=email,
            admin_password=password,
        )
    )


async def test_refresh_token_is_stored_as_hash_only(db_session):
    tokens = await _register(db_session, "hash-only@alqaim-demo.com")

    rows = (await db_session.execute(select(RefreshToken))).scalars().all()
    assert len(rows) == 1
    stored = rows[0]

    # النص الصريح لا يُخزَّن إطلاقاً — القيمة المخزّنة هي hash فقط ومطابقة
    # لدالة hash_refresh_token المعتمدة.
    assert stored.token_hash != tokens.refresh_token
    assert stored.token_hash == hash_refresh_token(tokens.refresh_token)
    assert stored.revoked_at is None


async def test_logout_revokes_refresh_token_and_refresh_then_fails(db_session):
    tokens = await _register(db_session, "logout@alqaim-demo.com")

    await LogoutUseCase(db_session).execute(LogoutRequest(refresh_token=tokens.refresh_token))

    with pytest.raises(ValueError):
        await RefreshTokenUseCase(db_session).execute(
            RefreshRequest(refresh_token=tokens.refresh_token)
        )


async def test_logout_is_idempotent_for_unknown_token(db_session):
    # لا يجب أن يرفع أي استثناء حتى لو كان التوكن غير موجود أصلاً.
    await LogoutUseCase(db_session).execute(LogoutRequest(refresh_token="not-a-real-token"))


async def test_refresh_rotates_token_and_old_one_becomes_unusable(db_session):
    tokens = await _register(db_session, "rotate@alqaim-demo.com")
    old_refresh = tokens.refresh_token

    new_tokens = await RefreshTokenUseCase(db_session).execute(
        RefreshRequest(refresh_token=old_refresh)
    )

    assert new_tokens.refresh_token != old_refresh
    decode_token(new_tokens.access_token, expected_type="access")

    # التوكن القديم أصبح مُبطَلاً (Rotation) — لا يمكن استخدامه مرة أخرى.
    with pytest.raises(ValueError):
        await RefreshTokenUseCase(db_session).execute(RefreshRequest(refresh_token=old_refresh))

    # لكن التوكن الجديد لا يزال صالحاً.
    again = await RefreshTokenUseCase(db_session).execute(
        RefreshRequest(refresh_token=new_tokens.refresh_token)
    )
    assert again.access_token


async def test_login_locks_account_after_five_failed_attempts(db_session):
    await _register(db_session, "lockout@alqaim-demo.com", password="CorrectPass123")

    for _ in range(5):
        with pytest.raises(ValueError):
            await LoginUseCase(db_session).execute(
                LoginRequest(email="lockout@alqaim-demo.com", password="WrongPassword"),
                ip_address="10.0.0.1",
            )

    # المحاولة السادسة تُقفَل حتى لو كانت كلمة المرور صحيحة هذه المرة.
    with pytest.raises(AccountLockedError):
        await LoginUseCase(db_session).execute(
            LoginRequest(email="lockout@alqaim-demo.com", password="CorrectPass123"),
            ip_address="10.0.0.1",
        )


async def test_login_rate_limits_by_ip_across_different_emails(db_session):
    await _register(db_session, "victim1@alqaim-demo.com", password="CorrectPass123")
    await _register(db_session, "victim2@alqaim-demo.com", password="CorrectPass123")

    # 5 محاولات فاشلة من نفس الـ IP لكن على بريد مختلف كل مرة يجب ألا تُفلت
    # من القفل عبر معيار البريد وحده.
    for i in range(5):
        with pytest.raises(ValueError):
            await LoginUseCase(db_session).execute(
                LoginRequest(email=f"attacker{i}@nowhere.com", password="whatever"),
                ip_address="203.0.113.9",
            )

    with pytest.raises(AccountLockedError):
        await LoginUseCase(db_session).execute(
            LoginRequest(email="victim1@alqaim-demo.com", password="CorrectPass123"),
            ip_address="203.0.113.9",
        )

    # نفس الحساب من IP مختلف غير محظور يبقى قادراً على الدخول بنجاح.
    ok = await LoginUseCase(db_session).execute(
        LoginRequest(email="victim2@alqaim-demo.com", password="CorrectPass123"),
        ip_address="198.51.100.7",
    )
    assert ok.access_token


async def test_failed_attempts_outside_window_do_not_count(db_session):
    await _register(db_session, "window@alqaim-demo.com", password="CorrectPass123")

    for _ in range(5):
        with pytest.raises(ValueError):
            await LoginUseCase(db_session).execute(
                LoginRequest(email="window@alqaim-demo.com", password="WrongPassword"),
                ip_address="10.0.0.2",
            )

    # نُزيح كل المحاولات المسجَّلة إلى خارج نافذة الـ 15 دقيقة يدوياً لمحاكاة
    # مرور الوقت دون الحاجة لانتظار فعلي في الاختبار.
    rows = (await db_session.execute(select(LoginAttempt))).scalars().all()
    for row in rows:
        row.created_at = utcnow() - timedelta(minutes=16)
    await db_session.commit()

    ok = await LoginUseCase(db_session).execute(
        LoginRequest(email="window@alqaim-demo.com", password="CorrectPass123"),
        ip_address="10.0.0.2",
    )
    assert ok.access_token
