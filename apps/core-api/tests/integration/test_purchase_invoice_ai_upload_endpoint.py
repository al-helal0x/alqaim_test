"""اختبار مستوى HTTP فعلي لـ `POST /purchase-invoices/ai-upload`
(`TASK-AI-01`) عبر `main.app` الحقيقي — بنفس نمط
`test_pagination_and_import_export.py::_client` تماماً (ASGITransport +
override لجلسة الـDB).

**الحد الوحيد المُحاكى (mock) هنا هو حدود الشبكة الخارجية لـ`ai-platform`**
(`get_ai_platform_client`) — عبر `httpx.MockTransport`، وليس أي جزء من
منطق core-api نفسه. هذا استثناء متعمَّد ومحدود: اختبار حقيقي بخادم
`ai-platform` فعلي يتطلب بنية تحتية غير متاحة محلياً (تماماً كما توثّق
`test_ai_gateway_proxy.py` الموجودة أصلاً وتُخطَّى تلقائياً بلا خادم حقيقي
— راجع `TEST_BASELINE.md`)؛ محاكاة الحد الخارجي فقط هنا تتيح تغطية سلوك
الـ endpoint نفسه (routing، معالجة الأخطاء، الصلاحيات) دون الحاجة لتلك
البنية التحتية.
"""
import uuid

import httpx
import pytest

from modules.identity.infrastructure.models.identity_models import (
    Permission,
    Role,
    RolePermission,
    UserCompanyRole,
)
from modules.tenancy.infrastructure.models.tenancy_models import Company
from platform_core.auth_middleware import TenantContext, get_current_context
from platform_core.database import get_db_session

pytestmark = pytest.mark.asyncio


class _SameSessionContextManager:
    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


async def _make_company_ctx(db_session) -> TenantContext:
    company = Company(name=f"شركة {uuid.uuid4().hex[:8]}")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return TenantContext(company_id=str(company.id), user_id=str(uuid.uuid4()))


async def _grant_permission(db_session, ctx: TenantContext, permission_code: str) -> None:
    permission = Permission(code=permission_code, description=permission_code)
    db_session.add(permission)
    await db_session.flush()

    role = Role(company_id=ctx.company_id, code="tester", name="Tester")
    db_session.add(role)
    await db_session.flush()

    db_session.add(RolePermission(role_id=role.id, permission_id=permission.id))
    db_session.add(
        UserCompanyRole(user_id=ctx.user_id, company_id=ctx.company_id, role_id=role.id)
    )
    await db_session.commit()


def _mock_ai_platform_client_factory(draft_response_json: dict, status_code: int = 200):
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=draft_response_json)

    def _factory() -> httpx.AsyncClient:
        transport = httpx.MockTransport(_handler)
        return httpx.AsyncClient(transport=transport, base_url="http://mock-ai-platform")

    return _factory


async def _client(db_session, ctx: TenantContext) -> httpx.AsyncClient:
    import main
    import platform_core.database as database_module

    async def _override_db():
        yield db_session

    async def _override_ctx():
        return ctx

    main.app.dependency_overrides[get_db_session] = _override_db
    main.app.dependency_overrides[get_current_context] = _override_ctx
    database_module.AsyncSessionLocal = _SameSessionContextManager(db_session)

    transport = httpx.ASGITransport(app=main.app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    import main

    main.app.dependency_overrides.clear()


async def test_ai_upload_endpoint_creates_invoice_from_approved_draft(db_session, monkeypatch):
    ctx = await _make_company_ctx(db_session)
    await _grant_permission(db_session, ctx, "purchasing.invoice.create")

    draft_id = str(uuid.uuid4())
    supplier_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    draft_json = {
        "id": draft_id,
        "status": "approved",
        "matched_supplier_id": supplier_id,
        "extracted_payload": {
            "currency_guess": "IQD",
            "tax_guess": 0,
            "discount_guess": 0,
            "lines": [{"description": "بند", "quantity": 2.0, "unit_price": 50.0}],
            "line_matches": [
                {"matches": [{"entity_id": product_id, "text": "منتج", "confidence": 0.95}]}
            ],
        },
    }

    import modules.purchasing.presentation.routes.purchase_invoices_router as router_module

    monkeypatch.setattr(
        router_module, "get_ai_platform_client", _mock_ai_platform_client_factory(draft_json)
    )

    async with await _client(db_session, ctx) as client:
        response = await client.post(
            "/purchase-invoices/ai-upload",
            json={"draft_id": draft_id, "branch_id": str(uuid.uuid4())},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["total_amount"] == "100.0000"


async def test_ai_upload_endpoint_rejects_draft_without_matched_supplier(db_session, monkeypatch):
    ctx = await _make_company_ctx(db_session)
    await _grant_permission(db_session, ctx, "purchasing.invoice.create")

    draft_id = str(uuid.uuid4())
    draft_json = {
        "id": draft_id,
        "status": "approved",
        "matched_supplier_id": None,
        "extracted_payload": {"lines": [{"description": "بند", "quantity": 1.0, "unit_price": 10.0}]},
    }

    import modules.purchasing.presentation.routes.purchase_invoices_router as router_module

    monkeypatch.setattr(
        router_module, "get_ai_platform_client", _mock_ai_platform_client_factory(draft_json)
    )

    async with await _client(db_session, ctx) as client:
        response = await client.post(
            "/purchase-invoices/ai-upload",
            json={"draft_id": draft_id, "branch_id": str(uuid.uuid4())},
        )

    assert response.status_code == 422


async def test_ai_upload_endpoint_forwards_ai_platform_404(db_session, monkeypatch):
    """المسودة غير موجودة في ai-platform → 404 يُمرَّر كما هو، لا 500."""
    ctx = await _make_company_ctx(db_session)
    await _grant_permission(db_session, ctx, "purchasing.invoice.create")

    import modules.purchasing.presentation.routes.purchase_invoices_router as router_module

    monkeypatch.setattr(
        router_module,
        "get_ai_platform_client",
        _mock_ai_platform_client_factory({"detail": "غير موجودة"}, status_code=404),
    )

    async with await _client(db_session, ctx) as client:
        response = await client.post(
            "/purchase-invoices/ai-upload",
            json={"draft_id": str(uuid.uuid4()), "branch_id": str(uuid.uuid4())},
        )

    assert response.status_code == 404


async def test_ai_upload_endpoint_same_draft_id_twice_no_duplicate(db_session, monkeypatch):
    ctx = await _make_company_ctx(db_session)
    await _grant_permission(db_session, ctx, "purchasing.invoice.create")

    draft_id = str(uuid.uuid4())
    supplier_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    draft_json = {
        "id": draft_id,
        "status": "approved",
        "matched_supplier_id": supplier_id,
        "extracted_payload": {
            "currency_guess": "IQD",
            "lines": [{"description": "بند", "quantity": 1.0, "unit_price": 10.0}],
            "line_matches": [
                {"matches": [{"entity_id": product_id, "text": "منتج", "confidence": 0.99}]}
            ],
        },
    }

    import modules.purchasing.presentation.routes.purchase_invoices_router as router_module

    monkeypatch.setattr(
        router_module, "get_ai_platform_client", _mock_ai_platform_client_factory(draft_json)
    )

    branch_id = str(uuid.uuid4())
    async with await _client(db_session, ctx) as client:
        first = await client.post(
            "/purchase-invoices/ai-upload", json={"draft_id": draft_id, "branch_id": branch_id}
        )
        second = await client.post(
            "/purchase-invoices/ai-upload", json={"draft_id": draft_id, "branch_id": branch_id}
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
