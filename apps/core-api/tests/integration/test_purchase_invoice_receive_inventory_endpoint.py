"""اختبار مستوى HTTP فعلي لـ `POST /purchase-invoices/{id}/receive-inventory`
(`TASK-AI-02b`) عبر `main.app` الحقيقي — نفس نمط
`test_purchase_invoice_ai_upload_endpoint.py` تماماً (ASGITransport + override
لجلسة DB)، بلا أي محاكاة (mock) هنا إطلاقاً — لا حدود خارجية يستدعيها
هذا Endpoint (بخلاف `/ai-upload` الذي يستدعي `ai-platform`).

الغرض: تغطية سلوك Endpoint نفسه (routing، الصلاحيات، رموز الحالة HTTP)
فوق ما تغطيه اختبارات مستوى Use Case في
`test_ai_invoice_posting_and_inventory_gap.py` — التي تبقى مصدر التحقق من
منطق الحراسات الثلاث نفسه.
"""
import uuid
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from modules.accounting.application.use_cases.chart_of_accounts_seed_use_case import (
    SeedDefaultChartOfAccountsUseCase,
)
from modules.accounting.infrastructure.adapters.accounting_port_adapter import SqlAccountingPort
from modules.accounting.infrastructure.models.accounting_models import FiscalPeriod, FiscalYear
from modules.identity.infrastructure.models.identity_models import (
    Permission,
    Role,
    RolePermission,
    UserCompanyRole,
)
from modules.purchasing.application.dto.purchasing_dto import (
    PurchaseInvoiceCreateRequest,
    PurchaseOrderLineRequest,
)
from modules.purchasing.application.use_cases.purchase_invoice_use_cases import (
    CreatePurchaseInvoiceUseCase,
    PostPurchaseInvoiceUseCase,
)
from modules.tenancy.infrastructure.models.tenancy_models import Branch, Company, Warehouse
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
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


async def _seed_company_with_accounting_and_warehouse(session):
    """نفس دالة الإعداد حرفياً من `test_ai_invoice_posting_and_inventory_gap.py`."""
    company = Company(name=f"شركة {uuid.uuid4().hex[:8]}", default_currency="IQD")
    session.add(company)
    await session.flush()

    branch = Branch(company_id=company.id, name="الفرع الرئيسي")
    session.add(branch)
    await session.flush()

    warehouse = Warehouse(company_id=company.id, branch_id=branch.id, name="المستودع الرئيسي")
    session.add(warehouse)

    fiscal_year = FiscalYear(
        company_id=company.id, code="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)
    )
    session.add(fiscal_year)
    await session.flush()

    today = datetime.now(UTC).date()
    period = FiscalPeriod(
        company_id=company.id, fiscal_year_id=fiscal_year.id, period_number=today.month,
        start_date=today.replace(day=1),
        end_date=(today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1),
    )
    session.add(period)
    await session.commit()
    await session.refresh(warehouse)

    await SeedDefaultChartOfAccountsUseCase(session).execute(str(company.id))

    ctx = TenantContext(company_id=str(company.id), user_id=str(uuid.uuid4()), branch_id=str(branch.id))
    return ctx, branch, warehouse


async def _grant_permission(db_session, ctx: TenantContext, permission_code: str) -> None:
    """يمنح صلاحية للسياق عبر دور مشترك واحد باسم `tester` لكل شركة —
    يدعم استدعاءات متعددة لنفس `ctx` (عدة صلاحيات) بلا انتهاك القيد
    الفريد `(company_id, code)` على `roles` (خلافاً لنسخة
    `test_purchase_invoice_ai_upload_endpoint.py` التي تستدعيه مرة واحدة
    فقط لكل اختبار، فلا تحتاج إعادة استخدام الدور)."""
    from sqlalchemy import select

    permission = Permission(code=permission_code, description=permission_code)
    db_session.add(permission)
    await db_session.flush()

    role_stmt = select(Role).where(Role.company_id == ctx.company_id, Role.code == "tester")
    role = (await db_session.execute(role_stmt)).scalar_one_or_none()
    if role is None:
        role = Role(company_id=ctx.company_id, code="tester", name="Tester")
        db_session.add(role)
        await db_session.flush()
        db_session.add(
            UserCompanyRole(user_id=ctx.user_id, company_id=ctx.company_id, role_id=role.id)
        )

    db_session.add(RolePermission(role_id=role.id, permission_id=permission.id))
    await db_session.commit()


async def _client(db_session, ctx: TenantContext) -> httpx.AsyncClient:
    import main
    import platform_core.database as database_module

    async def _override_db():
        yield db_session

    async def _override_ctx():
        return ctx

    main.app.dependency_overrides[get_db_session] = _override_db
    main.app.dependency_overrides[get_current_context] = _override_ctx
    _ORIGINAL_ASYNC_SESSION_LOCAL_HOLDER.append(database_module.AsyncSessionLocal)
    database_module.AsyncSessionLocal = _SameSessionContextManager(db_session)

    transport = httpx.ASGITransport(app=main.app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# محجوز قبل أول استبدال فقط (queue بسيط بدل global متغيّر واحد، لتفادي
# تضارب لو استُدعيت _client أكثر من مرة قبل استعادة _clear_overrides —
# لا يحدث فعلياً هنا لكن أأمن من الاعتماد على متغيّر واحد قابل للكتابة).
_ORIGINAL_ASYNC_SESSION_LOCAL_HOLDER: list = []


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    import main
    import platform_core.database as database_module

    # ⚠️ إصلاح فعلي حرج: بلا استعادة AsyncSessionLocal الحقيقي هنا، يبقى
    # مُستبدَلاً على مستوى الوحدة لكل اختبار لاحق في نفس عملية pytest —
    # اكتُشِف هذا لاحقاً بتشغيل السويت الكاملة (كسر اختبارات لا علاقة لها
    # بهذا الملف إطلاقاً، مثل test_sales_invoice_idempotent_posting.py).
    if _ORIGINAL_ASYNC_SESSION_LOCAL_HOLDER:
        database_module.AsyncSessionLocal = _ORIGINAL_ASYNC_SESSION_LOCAL_HOLDER.pop()
    main.app.dependency_overrides.clear()


async def _create_and_post_direct_invoice(db_session, ctx: TenantContext):
    """فاتورة شراء مباشرة (بلا أمر شراء، بلا AI) — نفس مسار الحارس الأول
    (`purchase_order_id is None`) الذي تختبره فواتير AI أيضاً، بلا حاجة
    لمحاكاة بوابة ai-platform هنا."""
    invoice = await CreatePurchaseInvoiceUseCase(db_session).execute(
        ctx,
        PurchaseInvoiceCreateRequest(
            branch_id=ctx.branch_id,
            supplier_id=str(uuid.uuid4()),
            lines=[
                PurchaseOrderLineRequest(
                    product_id=str(uuid.uuid4()), description="بند", quantity=3,
                    unit_price=20,
                )
            ],
        ),
    )
    numbering_service = SqlNumberingService(db_session)
    posted = await PostPurchaseInvoiceUseCase(
        db_session, SqlAccountingPort(db_session, numbering_service)
    ).execute(ctx, str(invoice.id))
    return posted


async def test_receive_inventory_endpoint_marks_invoice_received(db_session):
    ctx, _branch, warehouse = await _seed_company_with_accounting_and_warehouse(db_session)
    await _grant_permission(db_session, ctx, "purchasing.invoice.create")
    await _grant_permission(db_session, ctx, "purchasing.invoice.post")
    await _grant_permission(db_session, ctx, "purchasing.invoice.receive_inventory")

    posted = await _create_and_post_direct_invoice(db_session, ctx)

    async with await _client(db_session, ctx) as client:
        response = await client.post(
            f"/purchase-invoices/{posted.id}/receive-inventory",
            params={"warehouse_id": str(warehouse.id)},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["inventory_received_at"] is not None


async def test_receive_inventory_endpoint_rejects_second_call(db_session):
    ctx, _branch, warehouse = await _seed_company_with_accounting_and_warehouse(db_session)
    await _grant_permission(db_session, ctx, "purchasing.invoice.create")
    await _grant_permission(db_session, ctx, "purchasing.invoice.post")
    await _grant_permission(db_session, ctx, "purchasing.invoice.receive_inventory")

    posted = await _create_and_post_direct_invoice(db_session, ctx)

    async with await _client(db_session, ctx) as client:
        first = await client.post(
            f"/purchase-invoices/{posted.id}/receive-inventory",
            params={"warehouse_id": str(warehouse.id)},
        )
        second = await client.post(
            f"/purchase-invoices/{posted.id}/receive-inventory",
            params={"warehouse_id": str(warehouse.id)},
        )

    assert first.status_code == 200
    assert second.status_code == 400


async def test_receive_inventory_endpoint_rejects_unposted_invoice(db_session):
    ctx, _branch, warehouse = await _seed_company_with_accounting_and_warehouse(db_session)
    await _grant_permission(db_session, ctx, "purchasing.invoice.create")
    await _grant_permission(db_session, ctx, "purchasing.invoice.receive_inventory")

    draft_invoice = await CreatePurchaseInvoiceUseCase(db_session).execute(
        ctx,
        PurchaseInvoiceCreateRequest(
            branch_id=ctx.branch_id,
            supplier_id=str(uuid.uuid4()),
            lines=[
                PurchaseOrderLineRequest(
                    product_id=str(uuid.uuid4()), description="بند", quantity=1,
                    unit_price=10,
                )
            ],
        ),
    )

    async with await _client(db_session, ctx) as client:
        response = await client.post(
            f"/purchase-invoices/{draft_invoice.id}/receive-inventory",
            params={"warehouse_id": str(warehouse.id)},
        )

    assert response.status_code == 400


async def test_receive_inventory_endpoint_requires_permission(db_session):
    """بلا `purchasing.invoice.receive_inventory` مُمنوحة → 403 (نفس نمط
    `require_permission` القياسي في كل مسار آخر بالمشروع)."""
    ctx, _branch, warehouse = await _seed_company_with_accounting_and_warehouse(db_session)
    await _grant_permission(db_session, ctx, "purchasing.invoice.create")
    await _grant_permission(db_session, ctx, "purchasing.invoice.post")
    # عمداً: لا نمنح purchasing.invoice.receive_inventory هنا

    posted = await _create_and_post_direct_invoice(db_session, ctx)

    async with await _client(db_session, ctx) as client:
        response = await client.post(
            f"/purchase-invoices/{posted.id}/receive-inventory",
            params={"warehouse_id": str(warehouse.id)},
        )

    assert response.status_code == 403
