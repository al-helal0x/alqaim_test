"""PKG-B2 — اختبارات على مستوى هذا router لِـ`POST /partners/walk-in`.

هدف هذا الملف مختلف عن `test_walkin_use_case.py`: التحقق من *سلك التوصيل*
(wiring) نفسه — الصلاحية الصحيحة (`pos.sale.create` لا `partners.partner.create`)
والاستجابة الصحيحة — دون الحاجة لبيئة Postgres حقيقية أو لبنية هذا identity/auth
الكاملة (`SqlPermissionChecker` وإصدار JWT فعلي غير متوفرين في نطاق هذه
الحزمة المعزولة). لذلك تُستبدَل طبقة الصلاحيات وهذه DB بـ dependency overrides
قياسية في FastAPI — نمط اختبار شائع ولا يغيّر منطق endpoint الفعلي المُختبَر.

اختبار السباق الحقيقي (DB-level IntegrityError) والتكرار الفعلي للـid عبر DB
حقيقية مغطّى في `test_walkin_use_case.py` — لا يُكرَّر هنا.
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from platform_core.auth_middleware import TenantContext, get_current_context
from platform_core.database import get_db_session

FAKE_CTX = TenantContext(
    company_id="11111111-1111-1111-1111-111111111111", user_id="cashier-1"
)


@pytest.fixture
def captured_permission_codes():
    """يسجّل كل permission_code مُمرَّر لـ require_permission وقت استيراد
    هذا router — يُستخدَم للتأكد أن هذا endpoint محمي بـpos.sale.create فعلاً،
    وليس partners.partner.create (صلب المطلوب في PKG-B2)."""
    codes: list[str] = []

    from platform_core import auth_middleware

    def spy(permission_code: str):
        codes.append(permission_code)

        # يسمح بالمرور دائماً — الصلاحية نفسها تُختبَر عبر captured_permission_codes
        # (الاسم المُمرَّر لـrequire_permission)، لا عبر رفض/قبول الطلب فعلياً هنا
        # (ذلك يتطلب SqlPermissionChecker حقيقي غير متوفر في نطاق هذه الحزمة).
        # بلا معاملات عمداً: أي معامل بلا Depends() صريح يُفسَّر كـquery/body
        # param من FastAPI ويكسر هذا routing.
        async def _always_allow() -> TenantContext:
            return FAKE_CTX

        return _always_allow

    with patch.object(auth_middleware, "require_permission", side_effect=spy):
        yield codes


@pytest.fixture
def client(captured_permission_codes):
    import importlib

    # إعادة استيراد هذا router بعد تفعيل هذا patch أعلاه حتى تُلتقَط قيمة
    # permission_code الممرَّرة فعلياً لـrequire_permission("...") عند تعريف
    # هذا router (تُقيَّم مرة واحدة فقط، وقت الاستيراد).
    module = importlib.import_module(
        "modules.partners.presentation.routes.partners_walkin_router"
    )
    module = importlib.reload(module)

    app = FastAPI()
    app.include_router(module.router, prefix="/partners")
    app.dependency_overrides[get_current_context] = lambda: FAKE_CTX
    app.dependency_overrides[get_db_session] = lambda: None

    return TestClient(app), module


class TestWalkInRouter:
    def test_protected_by_pos_sale_create_not_partners_create(
        self, client, captured_permission_codes
    ):
        assert "pos.sale.create" in captured_permission_codes
        assert "partners.partner.create" not in captured_permission_codes

    def test_endpoint_returns_id_and_name(self, client):
        test_client, module = client
        fake_partner = type(
            "FakePartner", (), {"id": "abc-123", "name": "عميل نقدي"}
        )()

        with patch.object(
            module.GetOrCreateWalkInPartnerUseCase,
            "execute",
            new=AsyncMock(return_value=fake_partner),
        ):
            response = test_client.post("/partners/walk-in")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "abc-123"
        assert body["name"] == "عميل نقدي"

    def test_repeated_calls_are_idempotent_at_router_level(self, client):
        """يتأكد أن هذا router لا يفرض أي حالة (state) تمنع نداءً متكرراً —
        السلوك idempotent فعلياً يُختبَر على مستوى use case/DB في
        test_walkin_use_case.py؛ هنا فقط نتأكد أن استدعاءين متتاليين لا
        يفشلان على مستوى HTTP."""
        test_client, module = client
        fake_partner = type(
            "FakePartner", (), {"id": "same-id", "name": "عميل نقدي"}
        )()

        with patch.object(
            module.GetOrCreateWalkInPartnerUseCase,
            "execute",
            new=AsyncMock(return_value=fake_partner),
        ):
            first = test_client.post("/partners/walk-in")
            second = test_client.post("/partners/walk-in")

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["id"] == second.json()["id"] == "same-id"
