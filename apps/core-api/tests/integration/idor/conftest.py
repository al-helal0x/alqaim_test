"""PKG-C1 — تفعيل فعلي (لا Stub) لتوصيلات `client`/`company_a_headers`/
`company_b_headers` المطلوبة من كل ملف `test_idor_*.py` في هذا المجلد.

الحزمة الأصلية (PKG-C) سلَّمت هذه الملفات كقوالب `NotImplementedError` عمداً
— بصراحة موثَّقة: لم يكن لديها رؤية لـ`platform_core/` الحقيقي وقت بنائها.
هنا، بامتلاك الشجرة الكاملة، الشيء الصحيح فعلياً هو التوصيل عبر **تسجيل
حقيقي كامل** عبر `POST /auth/register-company` (لا تجاوز لطبقة المصادقة،
لا `dependency_overrides` على `get_current_context`) — هذا يعني أن كل
اختبار IDOR هنا يفحص العزل الحقيقي على طول السلسلة كاملة: JWT حقيقي موقَّع
→ `get_current_context` الحقيقي → `require_permission` الحقيقي (يتحقق من
DB فعلياً) → فلترة `ctx.company_id` الحقيقية في كل Use Case/Repository.

`RegisterCompanyUseCase` يمنح دور Owner **كل** الصلاحيات الموجودة في جدول
`permissions` وقت التسجيل (نفس نمط `scripts/seed_demo_company.py`) — هذا
يعني كل مستخدمي هذا الملف عندهم كل الصلاحيات اللازمة لأي endpoint، فلا
حاجة لضبط صلاحيات يدوياً لكل وحدة من 11 وحدة المُغطاة هنا.
"""
from __future__ import annotations

import uuid

import httpx
import pytest

pytestmark = pytest.mark.asyncio


# كل رموز الصلاحيات المُستخدَمة فعلياً عبر `require_permission("...")` في
# كامل الشجرة (استُخرجت بـ grep، لا افتراضاً) — راجع اكتشافاً حقيقياً هنا:
# `RegisterCompanyUseCase` يمنح دور Owner كل صف *موجود فعلياً* في جدول
# `permissions` وقت التسجيل (لا wildcard حقيقي كما توحي التعليقات في
# `auth_use_cases.py` — التعليق يشير لخيارين، والمُطبَّق فعلياً هو "زرع كل
# الصلاحيات لدور owner عبر Migration"). في الإنتاج تُزرع هذه الصفوف عبر
# migrations الحقيقية (`*_seed_permissions.py`)؛ اختبارات SQLite في الذاكرة
# هنا تبني الجدول من `Base.metadata.create_all` مباشرة — **بلا أي بيانات
# seed** — فيبقى جدول `permissions` فارغاً تماماً ما لم يُزرَع صراحة، وإلا
# فكل تسجيل شركة عبر `/auth/register-company` يمنح Owner صفر صلاحيات
# فعلياً (اكتُشف هذا بتشغيل هذه الاختبارات فعلياً، لا بالقراءة).
ALL_PERMISSION_CODES = [
    "accounting.account.create", "accounting.fiscal_period.close",
    "accounting.fiscal_year.create", "accounting.journal_entry.post",
    "audit.log.view", "catalog.category.create", "catalog.price_list.create",
    "catalog.price_list.update", "catalog.product.create", "catalog.product.update",
    "catalog.uom.create", "documents.delete", "documents.upload",
    "identity.user.create", "integrations.webhook.manage",
    "inventory.adjustment.create", "inventory.movement.create",
    "inventory.transfer.create", "inventory.warehouse.create",
    "partners.partner.create", "partners.partner.update",
    "payments.bank_account.create", "payments.payment.create",
    "payments.receipt.create", "platform_admin.company.manage",
    "pos.sale.create", "pos.sale.sync", "pos.session.close", "pos.session.open",
    "purchasing.invoice.create", "purchasing.invoice.post",
    "purchasing.invoice.receive_inventory", "purchasing.order.confirm",
    "purchasing.order.create", "purchasing.order.receive",
    "sales.credit_note.create", "sales.invoice.create", "sales.invoice.post",
    "sales.invoice.update", "sales.order.create", "sales.order.update",
    "sales.quotation.create", "sales.quotation.update",
    "taxation.tax_rate.create", "tenancy.branch.create",
    "workflow.definition.manage", "workflow.instance.transition",
]


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


async def _register_company(client: httpx.AsyncClient) -> dict[str, str]:
    suffix = uuid.uuid4().hex[:10]
    resp = await client.post(
        "/auth/register-company",
        json={
            "company_name": f"IDOR Test Co {suffix}",
            "default_currency": "IQD",
            "admin_full_name": "IDOR Tester",
            "admin_email": f"idor-{suffix}@example.com",
            "admin_password": "P@ssw0rd12345",
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class _SameSessionContextManager:
    """`require_permission`'s `_checker` (platform_core/auth_middleware.py)
    يستورد `AsyncSessionLocal` مباشرة (لا عبر `Depends(get_db_session)`) —
    اكتشاف حقيقي عند تشغيل هذه الاختبارات فعلياً لأول مرة: `dependency_overrides`
    وحدها لا تكفي لتوجيه فحص الصلاحيات لنفس جلسة SQLite في الذاكرة. نفس
    الحل المُستخدَم فعلاً في `test_purchase_invoice_receive_inventory_endpoint.py`
    — استبدال `AsyncSessionLocal` نفسه بمدير سياق يُعيد نفس `db_session`
    الوحيدة، بدل محرك Postgres الحقيقي."""

    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


@pytest.fixture
async def client(db_session):
    """يعيد استخدام `db_session` (fixture مشترك من `tests/integration/conftest.py`
    — SQLite في الذاكرة، بعد نقل هذا المجلد تحت `tests/integration/idor/`
    عند الدمج ليرثه) عبر override مزدوج: `get_db_session` (لمعظم المسارات
    عبر FastAPI DI العادي) و`AsyncSessionLocal` (لأن `require_permission`
    يتجاوز DI ويستورده مباشرة — انظر التوثيق أعلاه). طبقة المصادقة/الصلاحيات
    نفسها تبقى حقيقية بالكامل، بلا أي تجاوز على `get_current_context`."""
    import main
    import platform_core.database as database_module
    from platform_core.database import get_db_session

    async def _override_db():
        yield db_session

    main.app.dependency_overrides[get_db_session] = _override_db
    _original_async_session_local = database_module.AsyncSessionLocal
    database_module.AsyncSessionLocal = _SameSessionContextManager(db_session)

    from modules.identity.infrastructure.models.identity_models import Permission

    for code in ALL_PERMISSION_CODES:
        db_session.add(Permission(code=code, description=code))
    await db_session.commit()

    transport = httpx.ASGITransport(app=main.app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        # ⚠️ إصلاح فعلي حرج اكتُشِف عند تشغيل السويت الكاملة: بلا هذا الاستعادة،
        # `AsyncSessionLocal` المُستبدَل يبقى مُسرَّباً على مستوى الوحدة (module-level
        # global) لكل الاختبارات اللاحقة في نفس عملية pytest — بما فيها ملفات لا
        # علاقة لها بـIDOR إطلاقاً (كسر 11 اختباراً في
        # `test_sales_invoice_idempotent_posting.py` فعلياً عند أول تشغيل كامل
        # للسويت، لأن `db_session` هذا الاختبار مُغلَقة أصلاً `await engine.dispose()`
        # بحلول وقت تشغيلها). كل اختبار IDOR يجب أن يستعيد القيمة الأصلية دائماً.
        database_module.AsyncSessionLocal = _original_async_session_local
        main.app.dependency_overrides.clear()


@pytest.fixture
async def company_a_headers(client: httpx.AsyncClient) -> dict[str, str]:
    return await _register_company(client)


@pytest.fixture
async def company_b_headers(client: httpx.AsyncClient) -> dict[str, str]:
    return await _register_company(client)


async def create_product(
    client: httpx.AsyncClient, headers: dict[str, str], *, name: str, sku: str
) -> str:
    """مساعد مشترك (اكتُشِف عند تشغيل الاختبارات فعلياً هنا لأول مرة —
    ProductCreateRequest.base_uom_id إلزامي، لم يكن هذا ظاهراً لصاحب حزمة
    IDOR الأصلية لأن catalog_dto.py لم يكن ضمن حزمتها المعزولة). ينشئ وحدة
    قياس جديدة ثم منتجاً يستخدمها، ويعيد id المنتج فقط — هذا كل ما تحتاجه
    اختبارات IDOR هنا."""
    uom_resp = await client.post(
        "/units-of-measure", json={"code": f"U{uuid.uuid4().hex[:6]}", "name": "Unit"}, headers=headers
    )
    assert uom_resp.status_code == 201, uom_resp.text
    uom_id = uom_resp.json()["id"]

    product_resp = await client.post(
        "/products",
        json={"name": name, "sku": sku, "base_uom_id": uom_id},
        headers=headers,
    )
    assert product_resp.status_code == 201, product_resp.text
    return product_resp.json()["id"]


async def create_warehouse(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    """مساعد مشترك آخر اكتُشِفت الحاجة إليه فعلياً هنا: `POST /sales-invoices`
    و`POST /pos/sessions` يتطلبان `warehouse_id`، وهذا بدوره يتطلب `branch_id`
    (سلسلة company → branch → warehouse لا وجود لها تلقائياً بعد التسجيل).
    لم يكن `tenancy_dto.py` ظاهراً لأي من حزم عضو 3 أو عضو 4 المعزولتين."""
    branch_resp = await client.post(
        "/branches", json={"name": f"Branch-{uuid.uuid4().hex[:6]}"}, headers=headers
    )
    assert branch_resp.status_code == 201, branch_resp.text
    branch_id = branch_resp.json()["id"]

    warehouse_resp = await client.post(
        "/warehouses",
        json={"branch_id": branch_id, "name": f"Warehouse-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    assert warehouse_resp.status_code == 201, warehouse_resp.text
    return warehouse_resp.json()["id"]


async def stock_in(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    warehouse_id: str,
    product_id: str,
    quantity: float = 100,
) -> None:
    """يزوّد مخزوناً كافياً في مستودع قبل بيع/ترحيل — بدون هذا يفشل ترحيل
    فاتورة المبيعات بـ422 (\"لا كمية كافية متاحة للحجز\")، وهو ما اكتُشِف فقط
    عند تشغيل مسار POST /sales-invoices/{id}/post فعلياً هنا لأول مرة."""
    resp = await client.post(
        "/inventory/adjustments",
        json={
            "warehouse_id": warehouse_id,
            "product_id": product_id,
            "quantity_delta": quantity,
            "reason": "IDOR test setup — initial stock",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text


async def seed_chart_of_accounts(client: httpx.AsyncClient, headers: dict[str, str]) -> None:
    """ترحيل أي فاتورة مبيعات فعلي يتطلب شجرة حسابات موجودة مسبقاً (بحث عن
    كود حساب ثابت مثل 1110). لا تفشل إن كانت مزروعة مسبقاً (409) — هذا
    متوقَّع ومقبول إذا استُدعيت أكثر من مرة لنفس الشركة."""
    resp = await client.post("/accounts/seed-defaults", headers=headers)
    assert resp.status_code in (200, 409), resp.text
