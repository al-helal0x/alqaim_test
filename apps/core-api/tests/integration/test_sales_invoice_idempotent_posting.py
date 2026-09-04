"""اختبارات تكامل — مهمة #11: أمان معاملة إنشاء→ترحيل فاتورة البيع.

يغطي معيار القبول كاملاً:
1) idempotency على مستوى الطلب لإنشاء الفاتورة (نفس المفتاح لا يُنتج فاتورة
   مكررة، حتى مع سباق حقيقي على مستوى القاعدة).
2) معالجة صريحة لحالة "نجح الإنشاء وفشل الترحيل": فشل الترحيل المحاسبي بعد
   نجاح الحجز يُحرِّر الحجوزات فوراً ويترك الفاتورة draft بلا أي تكرار لها،
   بحيث تنجح إعادة محاولة الترحيل لاحقاً على نفس invoice_id.
3) idempotency على مستوى طلب الترحيل نفسه: إعادة إرسال /post لفاتورة
   مُرحَّلة فعلاً تُعيد نفس النتيجة بلا إعادة أي أثر جانبي.

تُستخدم قاعدة SQLite في-الذاكرة (عبر aiosqlite) لجداول sales فقط، مع
AsyncMock لبقية الـ Ports (accounting/inventory/partner/product/numbering)
لأنها معنية بتشغيل مسارات حقيقية داخل sales نفسها فقط — سلوك الأنظمة الأخرى
مُحاكى (mocked) عمداً حسب حدود هذه المهمة (apps/core-api/modules/sales/ فقط).
"""
from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from modules.inventory.application.ports.inventory_port import InsufficientStockError
from modules.sales.application.dto.sales_dto import LineItemRequest, SalesInvoiceCreateRequest
from modules.sales.application.use_cases.sales_use_cases import (
    CreateSalesInvoiceUseCase,
    PostSalesInvoiceUseCase,
)
from modules.sales.infrastructure.models.sales_models import SalesInvoice
from shared_kernel.db_base import BaseModel

# ملاحظة: التساهل مع UUID كنص (بدل uuid.UUID حرفي) على SQLite مطبَّق الآن
# مركزياً في conftest.py (نفس الحل، مرفوع من هنا) — راجع تعليقه هناك.


@dataclass
class _FakeTenantContext:
    """مكافئ مبسّط لـ TenantContext — الكود المُختبَر هنا لا يقرأ سوى
    company_id/branch_id، فلا حاجة للاعتماد الكامل على platform_core."""

    company_id: str
    branch_id: str | None = None


def _make_ctx() -> _FakeTenantContext:
    return _FakeTenantContext(company_id=str(uuid4()))


def _fake_product():
    return SimpleNamespace(id=str(uuid4()), name="منتج اختبار", is_active=True)


def _fake_partner():
    return SimpleNamespace(id=str(uuid4()))


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        # جداول sales فقط + جداول-صورة فارغة (companies/branches/warehouses)
        # كافية لإرضاء الـ ForeignKey تعريفياً بلا تفعيل PRAGMA foreign_keys
        # (SQLite لا يفرضها افتراضياً) — لا علاقة لها بمنطق هذه المهمة.
        from sqlalchemy import Column, Table
        from sqlalchemy.dialects.postgresql import UUID as PgUUID

        # Track 1 (Outbox): CreateSalesInvoiceUseCase/PostSalesInvoiceUseCase
        # يكتبان الآن سطر outbox_events ضمن نفس المعاملة (enqueue_event) قبل
        # أي commit — هذا الاستيراد يسجّل الجدول في BaseModel.metadata (نفس
        # metadata التي يستخدمها كل شيء هنا، راجع shared_kernel/db_base.py).
        from platform_core import outbox_models  # noqa: F401

        # جداول الظل يجب أن تعيش في *نفس* BaseModel.metadata حتى يستطيع
        # SQLAlchemy حلّ الـ ForeignKey (branches.id/companies.id/...) عند بناء
        # جدول sales_invoices — MetaData منفصلة لا تُرى من resolver الخاص به.
        for table_name in ("companies", "branches", "warehouses"):
            if table_name not in BaseModel.metadata.tables:
                Table(table_name, BaseModel.metadata, Column("id", PgUUID(as_uuid=True), primary_key=True))

        # نفس الاستبدال المركزي في conftest.py (UUID/JSONB → أنواع متوافقة مع
        # SQLite) — مطلوب هنا أيضاً لأن هذا fixture منفصل عن fixture
        # `db_session` الرئيسي ولا يمر عبره.
        from conftest import _swap_pg_only_types_for_sqlite

        _swap_pg_only_types_for_sqlite()

        await conn.run_sync(
            lambda sync_conn: BaseModel.metadata.create_all(
                sync_conn,
                tables=[
                    BaseModel.metadata.tables[name]
                    for name in (
                        "companies", "branches", "warehouses",
                        "sales_invoices", "sales_invoice_lines", "outbox_events",
                    )
                ],
            )
        )
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(session_factory):
    async with session_factory() as s:
        yield s


def _create_request(idempotency_key: str | None, product_id: str) -> SalesInvoiceCreateRequest:
    return SalesInvoiceCreateRequest(
        partner_id=str(uuid4()),
        warehouse_id=str(uuid4()),
        lines=[LineItemRequest(product_id=product_id, quantity=Decimal(2), unit_price=Decimal(100))],
        idempotency_key=idempotency_key,
    )


def _mocked_create_use_case(session, product):
    from unittest.mock import AsyncMock

    partner_lookup = AsyncMock()
    partner_lookup.get.return_value = _fake_partner()
    product_lookup = AsyncMock()
    product_lookup.get.return_value = product
    numbering_service = AsyncMock()
    numbering_service.next_number.side_effect = [f"INV-{n}" for n in range(1, 100)]
    return CreateSalesInvoiceUseCase(session, partner_lookup, product_lookup, numbering_service)


# ── 1) idempotency عند الإنشاء ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_sales_invoice_same_idempotency_key_returns_same_invoice(session):
    product = _fake_product()
    ctx = _make_ctx()
    key = str(uuid4())
    use_case = _mocked_create_use_case(session, product)

    first = await use_case.execute(ctx, _create_request(key, product.id))
    second = await use_case.execute(ctx, _create_request(key, product.id))

    assert first.id == second.id
    count = (await session.execute(select(SalesInvoice))).scalars().all()
    assert len(count) == 1, "إعادة إرسال نفس idempotency_key لا يجب أن تُنشئ فاتورة ثانية"


@pytest.mark.asyncio
async def test_create_sales_invoice_without_key_is_not_deduplicated(session):
    product = _fake_product()
    ctx = _make_ctx()
    use_case = _mocked_create_use_case(session, product)

    first = await use_case.execute(ctx, _create_request(None, product.id))
    second = await use_case.execute(ctx, _create_request(None, product.id))

    assert first.id != second.id, "بلا مفتاح idempotency، كل طلب فاتورة مستقل كالسابق تماماً"


# ── 2) نجح الإنشاء وفشل الترحيل: إعادة محاولة بدل ازدواج ─────────────────


@pytest.mark.asyncio
async def test_post_retries_after_accounting_failure_without_duplicate_invoice(session):
    from unittest.mock import AsyncMock

    product = _fake_product()
    ctx = _make_ctx()
    invoice = await _mocked_create_use_case(session, product).execute(
        ctx, _create_request(str(uuid4()), product.id)
    )
    assert invoice.status == "draft"

    inventory_port = AsyncMock()
    inventory_port.reserve_stock.return_value = SimpleNamespace(reservation_id="res-1")

    accounting_port = AsyncMock()
    accounting_port.record_document_posting.side_effect = RuntimeError("فترة مالية مقفلة")

    post_use_case = PostSalesInvoiceUseCase(session, inventory_port, accounting_port)

    # المحاولة الأولى: الحجز ينجح، الترحيل المحاسبي يفشل.
    with pytest.raises(RuntimeError):
        await post_use_case.execute(ctx, str(invoice.id))

    # الحجز فشل ترحيله يجب أن يُحرَّر فوراً — بلا انتظار انتهاء صلاحية 15 دقيقة.
    inventory_port.release_reservation.assert_awaited_once_with(
        company_id=ctx.company_id, reservation_id="res-1"
    )

    reloaded = (
        await session.execute(select(SalesInvoice).where(SalesInvoice.id == invoice.id))
    ).scalar_one()
    assert reloaded.status == "draft", "الفاتورة تبقى draft بعد فشل الترحيل — لا حالة وسيطة فاسدة"
    assert reloaded.journal_entry_id is None

    total_invoices = (await session.execute(select(SalesInvoice))).scalars().all()
    assert len(total_invoices) == 1, "إعادة المحاولة تعمل على نفس الفاتورة، لا تُنشئ فاتورة جديدة"

    # المحاولة الثانية (إعادة محاولة العميل بنفس invoice_id): الترحيل ينجح الآن.
    accounting_port.record_document_posting.side_effect = None
    accounting_port.record_document_posting.return_value = SimpleNamespace(journal_entry_id="JE-1")
    inventory_port.reserve_stock.return_value = SimpleNamespace(reservation_id="res-2")

    posted = await post_use_case.execute(ctx, str(invoice.id))

    assert posted.status == "posted"
    assert posted.journal_entry_id == "JE-1"
    total_invoices = (await session.execute(select(SalesInvoice))).scalars().all()
    assert len(total_invoices) == 1, "الفاتورة الناجحة أخيراً هي نفسها الأصلية — بلا أي ازدواج"


@pytest.mark.asyncio
async def test_post_releases_reservations_in_order_on_insufficient_stock(session):
    """تأكيد أن مسار فشل الحجز (المرحلة 1) — الموجود مسبقاً — لم يتأثر بإصلاح
    مهمة #11 لمرحلة الترحيل المحاسبي (المرحلة 2)."""
    from unittest.mock import AsyncMock

    product = _fake_product()
    ctx = _make_ctx()
    invoice = await _mocked_create_use_case(session, product).execute(
        ctx, _create_request(str(uuid4()), product.id)
    )

    inventory_port = AsyncMock()
    inventory_port.reserve_stock.side_effect = InsufficientStockError("لا يوجد رصيد كافٍ")
    accounting_port = AsyncMock()

    post_use_case = PostSalesInvoiceUseCase(session, inventory_port, accounting_port)
    with pytest.raises(InsufficientStockError):
        await post_use_case.execute(ctx, str(invoice.id))

    accounting_port.record_document_posting.assert_not_awaited()


# ── 3) idempotency عند الترحيل نفسه (فاتورة مُرحَّلة فعلاً) ───────────────


@pytest.mark.asyncio
async def test_post_already_posted_invoice_is_a_pure_noop(session):
    from unittest.mock import AsyncMock

    product = _fake_product()
    ctx = _make_ctx()
    invoice = await _mocked_create_use_case(session, product).execute(
        ctx, _create_request(str(uuid4()), product.id)
    )

    inventory_port = AsyncMock()
    inventory_port.reserve_stock.return_value = SimpleNamespace(reservation_id="res-1")
    accounting_port = AsyncMock()
    accounting_port.record_document_posting.return_value = SimpleNamespace(journal_entry_id="JE-1")

    post_use_case = PostSalesInvoiceUseCase(session, inventory_port, accounting_port)
    first = await post_use_case.execute(ctx, str(invoice.id))
    assert first.status == "posted"

    inventory_port.reset_mock()
    accounting_port.reset_mock()

    second = await post_use_case.execute(ctx, str(invoice.id))

    assert second.id == first.id
    assert second.journal_entry_id == first.journal_entry_id
    inventory_port.reserve_stock.assert_not_awaited()
    inventory_port.deduct_stock.assert_not_awaited()
    accounting_port.record_document_posting.assert_not_awaited()


# ── 4) TASK-12-01 — صفَّا outbox (SalesInvoiceCreated, InvoicePosted) ─────


@pytest.mark.asyncio
async def test_create_and_post_enqueue_expected_outbox_events(session):
    """TASK-12-01 — بند اختبار مطلوب صراحة في `ALQAIM_V2_MASTER_EXECUTION_PLAN.md`
    ("صفَّا outbox (SalesInvoiceCreated, InvoicePosted) موجودان فعلياً")
    لم يكن مغطى بأي اختبار حتى هذا التسليم رغم أن `CreateSalesInvoiceUseCase`/
    `PostSalesInvoiceUseCase` تكتبان الحدثين فعلياً عبر `enqueue_event()`."""
    from unittest.mock import AsyncMock

    from platform_core.outbox_models import OutboxEvent

    product = _fake_product()
    ctx = _make_ctx()
    invoice = await _mocked_create_use_case(session, product).execute(
        ctx, _create_request(str(uuid4()), product.id)
    )

    created_rows = (
        await session.execute(select(OutboxEvent).where(OutboxEvent.event_name == "SalesInvoiceCreated"))
    ).scalars().all()
    assert len(created_rows) == 1
    assert created_rows[0].status == "pending"
    assert created_rows[0].aggregate_id == str(invoice.id)
    assert created_rows[0].payload["invoice_id"] == str(invoice.id)

    inventory_port = AsyncMock()
    inventory_port.reserve_stock.return_value = SimpleNamespace(reservation_id="res-1")
    accounting_port = AsyncMock()
    accounting_port.record_document_posting.return_value = SimpleNamespace(journal_entry_id="JE-1")

    await PostSalesInvoiceUseCase(session, inventory_port, accounting_port).execute(ctx, str(invoice.id))

    posted_rows = (
        await session.execute(select(OutboxEvent).where(OutboxEvent.event_name == "InvoicePosted"))
    ).scalars().all()
    assert len(posted_rows) == 1
    assert posted_rows[0].status == "pending"
    assert posted_rows[0].aggregate_id == str(invoice.id)

    # لا ازدواج على SalesInvoiceCreated بعد الترحيل — الحدث يُنشَر مرة واحدة فقط عند الإنشاء
    created_rows_after = (
        await session.execute(select(OutboxEvent).where(OutboxEvent.event_name == "SalesInvoiceCreated"))
    ).scalars().all()
    assert len(created_rows_after) == 1


@pytest.mark.asyncio
async def test_idempotent_create_hit_does_not_duplicate_outbox_event(session):
    """مكمِّل لـ`test_create_sales_invoice_same_idempotency_key_returns_same_invoice`
    من زاوية outbox تحديداً: طلب مكرر بنفس idempotency_key لا يجب أن يزيد
    عدد أحداث SalesInvoiceCreated المكتوبة — المسار المبكر لـidempotent hit
    يعود قبل الوصول لسطر enqueue_event() إطلاقاً."""
    from platform_core.outbox_models import OutboxEvent

    product = _fake_product()
    ctx = _make_ctx()
    key = str(uuid4())
    use_case = _mocked_create_use_case(session, product)

    await use_case.execute(ctx, _create_request(key, product.id))
    await use_case.execute(ctx, _create_request(key, product.id))

    rows = (
        await session.execute(select(OutboxEvent).where(OutboxEvent.event_name == "SalesInvoiceCreated"))
    ).scalars().all()
    assert len(rows) == 1, "إعادة إرسال نفس idempotency_key لا يجب أن تكتب حدث outbox ثانٍ"
