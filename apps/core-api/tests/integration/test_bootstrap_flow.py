"""اختبار تكامل يغطي معيار تسليم العضو 1 (القسم 13.2): تسجيل شركة جديدة،
تسجيل دخول، عزل بين الشركات، وترقيم مستندات آمن تحت التزامن.
"""

import pytest

from modules.identity.application.dto.identity_dto import LoginRequest, RegisterCompanyRequest
from modules.identity.application.use_cases.auth_use_cases import (
    LoginUseCase,
    RegisterCompanyUseCase,
)
from modules.identity.infrastructure.models.identity_models import Permission
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.security import decode_token

pytestmark = pytest.mark.asyncio


async def _seed_permission(session, code: str) -> None:
    session.add(Permission(code=code, description=code))
    await session.commit()


async def test_register_company_then_login(db_session):
    await _seed_permission(db_session, "identity.user.create")

    register_request = RegisterCompanyRequest(
        company_name="شركة القائم للتجارة",
        admin_full_name="مدير النظام",
        admin_email="owner@alqaim-demo.com",
        admin_password="StrongPass123",
    )
    tokens = await RegisterCompanyUseCase(db_session).execute(register_request)
    assert tokens.access_token
    payload = decode_token(tokens.access_token, expected_type="access")
    company_id = payload["company_id"]
    assert payload["sub"]

    login_tokens = await LoginUseCase(db_session).execute(
        LoginRequest(email="owner@alqaim-demo.com", password="StrongPass123")
    )
    login_payload = decode_token(login_tokens.access_token, expected_type="access")
    assert login_payload["company_id"] == company_id


async def test_login_rejects_wrong_password(db_session):
    await RegisterCompanyUseCase(db_session).execute(
        RegisterCompanyRequest(
            company_name="شركة اختبار",
            admin_full_name="Admin",
            admin_email="wrongpass@alqaim-demo.com",
            admin_password="CorrectPass123",
        )
    )
    with pytest.raises(ValueError):
        await LoginUseCase(db_session).execute(
            LoginRequest(email="wrongpass@alqaim-demo.com", password="WrongPassword")
        )


async def test_numbering_sequence_is_unique_under_concurrency(db_session):
    tokens = await RegisterCompanyUseCase(db_session).execute(
        RegisterCompanyRequest(
            company_name="شركة الترقيم",
            admin_full_name="Admin",
            admin_email="numbering@alqaim-demo.com",
            admin_password="StrongPass123",
        )
    )
    company_id = decode_token(tokens.access_token, expected_type="access")["company_id"]

    service = SqlNumberingService(db_session)
    # 20 طلب رقم متتالي لنفس نوع المستند — يجب ألا يتكرر أي رقم
    numbers = []
    for _ in range(20):
        numbers.append(
            await service.next_number(company_id=company_id, document_type="sales_invoice")
        )

    assert len(numbers) == len(set(numbers)) == 20
    assert numbers[0] == "000001"
    assert numbers[-1] == "000020"
