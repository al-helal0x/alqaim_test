"""اختبار مستوى HTTP فعلي (وليس use cases مباشرة) لتغطية: الترقيم الموحّد
(page/page_size/sort) وendpoints الاستيراد/التصدير (blueprint القسم 9.3/9.4)
عبر app الحقيقي مع override لجلسة قاعدة البيانات على SQLite في الذاكرة.
"""
import uuid

import httpx
import pytest

from modules.catalog.application.dto.catalog_dto import (
    ProductCreateRequest,
    UomCreateRequest,
)
from modules.catalog.application.use_cases.catalog_use_cases import (
    CreateProductUseCase,
    CreateUomUseCase,
)
from modules.identity.infrastructure.models.identity_models import (
    Permission,
    Role,
    RolePermission,
    UserCompanyRole,
)
from modules.partners.application.dto.partner_dto import PartnerCreateRequest
from modules.partners.application.use_cases.partner_use_cases import CreatePartnerUseCase
from modules.tenancy.infrastructure.models.tenancy_models import Company
from platform_core.auth_middleware import TenantContext, get_current_context
from platform_core.database import get_db_session

pytestmark = pytest.mark.asyncio


async def _make_company_ctx(db_session) -> TenantContext:
    company = Company(name=f"شركة {uuid.uuid4().hex[:8]}")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return TenantContext(company_id=str(company.id), user_id=str(uuid.uuid4()))


class _SameSessionContextManager:
    """يحاكي async_sessionmaker() لكن يعيد نفس جلسة الاختبار المشتركة (db_session)
    بدل فتح اتصال Postgres حقيقي جديد — مطلوب لأن require_permission()
    (platform_core.auth_middleware) يفتح جلسته الخاصة عبر AsyncSessionLocal
    مباشرة، متجاوزاً get_db_session تماماً، فلا يكفي تجاوز الـ DI العادي هنا.
    """

    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


async def _grant_permission(db_session, ctx: TenantContext, permission_code: str) -> None:
    """يمنح ctx.user_id صلاحية محددة داخل شركته — لتفعيل require_permission()
    على endpoint محمي أثناء الاختبار (نفس آلية RBAC الحقيقية عبر role_permissions)."""
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


async def _client(db_session, ctx: TenantContext) -> httpx.AsyncClient:
    """يبني عميل HTTP حقيقي فوق main.app، مع استبدال جلسة الـ DB بجلسة الاختبار
    (SQLite في الذاكرة) وتجاوز التوثيق لتفادي إعداد JWT فعلي هنا."""
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


async def test_products_list_is_paginated(db_session):
    ctx = await _make_company_ctx(db_session)
    uom = await CreateUomUseCase(db_session).execute(ctx, UomCreateRequest(code="PCS", name="قطعة"))
    for i in range(5):
        await CreateProductUseCase(db_session).execute(
            ctx, ProductCreateRequest(sku=f"SKU-{i}", name=f"منتج {i}", base_uom_id=str(uom.id))
        )

    async with await _client(db_session, ctx) as client:
        resp = await client.get("/products", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["page"] == 1
        assert body["page_size"] == 2


async def test_products_export_csv(db_session):
    ctx = await _make_company_ctx(db_session)
    uom = await CreateUomUseCase(db_session).execute(ctx, UomCreateRequest(code="PCS", name="قطعة"))
    await CreateProductUseCase(db_session).execute(
        ctx, ProductCreateRequest(sku="EXP-1", name="منتج للتصدير", base_uom_id=str(uom.id))
    )

    async with await _client(db_session, ctx) as client:
        resp = await client.get("/products/export")
        assert resp.status_code == 200
        assert "EXP-1" in resp.text
        assert resp.headers["content-type"].startswith("text/csv")


async def test_products_import_csv_reports_per_row_result(db_session):
    ctx = await _make_company_ctx(db_session)
    uom = await CreateUomUseCase(db_session).execute(ctx, UomCreateRequest(code="PCS", name="قطعة"))
    await _grant_permission(db_session, ctx, "catalog.product.create")

    csv_content = (
        "sku,name,base_uom_id,sale_price,purchase_price\n"
        f"IMP-1,منتج مستورد 1,{uom.id},1000,800\n"
        "IMP-2,منتج بمرجع خاطئ,not-a-real-uuid,500,400\n"
    )

    async with await _client(db_session, ctx) as client:
        files = {"file": ("products.csv", csv_content.encode("utf-8"), "text/csv")}
        resp = await client.post("/products/import", files=files)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_rows"] == 2
        assert body["succeeded"] == 1
        assert body["failed"] == 1
        assert body["rows"][0]["success"] is True
        assert body["rows"][1]["success"] is False


async def test_partners_list_is_paginated(db_session):
    ctx = await _make_company_ctx(db_session)
    for i in range(3):
        await CreatePartnerUseCase(db_session).execute(
            ctx, PartnerCreateRequest(name=f"عميل {i}")
        )

    async with await _client(db_session, ctx) as client:
        resp = await client.get("/partners", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 2
