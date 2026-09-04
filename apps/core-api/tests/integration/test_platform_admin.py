"""يغطي معيار تسليم العضو 13 (platform_admin): سرد كل الشركات عبر المنصة
(الاستثناء المتعمَّد الوحيد لعزل company_id — موثَّق في platform_admin_use_cases.py)،
وتعليق/تفعيل شركة."""
import pytest

from modules.identity.application.dto.identity_dto import RegisterCompanyRequest
from modules.identity.application.use_cases.auth_use_cases import RegisterCompanyUseCase
from modules.platform_admin.application.use_cases.platform_admin_use_cases import (
    ListAllCompaniesUseCase,
    SetCompanyActiveStatusUseCase,
)
from platform_core.security import decode_token

pytestmark = pytest.mark.asyncio


async def _register(db_session, email: str) -> str:
    tokens = await RegisterCompanyUseCase(db_session).execute(
        RegisterCompanyRequest(
            company_name=f"Company for {email}", admin_full_name="Admin",
            admin_email=email, admin_password="StrongPass123",
        )
    )
    payload = decode_token(tokens.access_token, expected_type="access")
    return payload["company_id"]


async def test_list_all_companies_spans_every_tenant(db_session):
    company_a = await _register(db_session, "platform-a@alqaim-demo.com")
    company_b = await _register(db_session, "platform-b@alqaim-demo.com")

    rows = await ListAllCompaniesUseCase().execute(db_session)
    seen_ids = {str(company.id) for company, _branch_count in rows}

    # على عكس كل استعلام آخر في النظام، هذا يرى شركتين مختلفتين تماماً بلا
    # أي ctx.company_id — هذا هو جوهر ما تختبره هذه الحالة
    assert company_a in seen_ids
    assert company_b in seen_ids


async def test_suspend_then_activate_company(db_session):
    company_id = await _register(db_session, "platform-c@alqaim-demo.com")

    suspended, _ = await SetCompanyActiveStatusUseCase().execute(
        db_session, company_id, is_active=False
    )
    assert suspended.is_active is False

    activated, _ = await SetCompanyActiveStatusUseCase().execute(
        db_session, company_id, is_active=True
    )
    assert activated.is_active is True


async def test_suspend_unknown_company_raises(db_session):
    with pytest.raises(ValueError):
        await SetCompanyActiveStatusUseCase().execute(
            db_session, "00000000-0000-0000-0000-000000000000", is_active=False
        )
