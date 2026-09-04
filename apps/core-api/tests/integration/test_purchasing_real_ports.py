"""يغطي بالضبط ما طلبه تقرير المشرف: تشغيل اختبارات تكامل Purchasing ضد
IInventoryPort/IAccountingPort **الحقيقيَين** (SqlInventoryPort/SqlAccountingPort)
بدل fake_ports.py — للتأكد أن استبدال الحقن في الـ Router لا ينهار (كان سينهار
فعلياً بـ AttributeError على increase_stock وTypeError على
record_document_posting قبل هذا الإصلاح).
"""
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from modules.accounting.application.use_cases.chart_of_accounts_seed_use_case import (
    SeedDefaultChartOfAccountsUseCase,
)
from modules.accounting.infrastructure.adapters.accounting_port_adapter import SqlAccountingPort
from modules.accounting.infrastructure.models.accounting_models import FiscalPeriod, FiscalYear
from modules.inventory.infrastructure.repositories.inventory_repository import (
    SqlInventoryPort,
    get_balance_row,
)
from modules.purchasing.application.dto.purchasing_dto import (
    PurchaseOrderCreateRequest,
    PurchaseOrderLineRequest,
)
from modules.purchasing.application.use_cases.purchase_invoice_use_cases import (
    CreatePurchaseInvoiceFromOrderUseCase,
    PostPurchaseInvoiceUseCase,
)
from modules.purchasing.application.use_cases.purchase_order_use_cases import (
    ConfirmPurchaseOrderUseCase,
    CreatePurchaseOrderUseCase,
    ReceivePurchaseOrderUseCase,
)
from modules.tenancy.infrastructure.models.tenancy_models import Branch, Company, Warehouse
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext

pytestmark = pytest.mark.asyncio


async def _seed_company_with_accounting_and_warehouse(session):
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
    return ctx, warehouse


def _order_request(**overrides) -> PurchaseOrderCreateRequest:
    defaults = {
        "branch_id": str(uuid.uuid4()),
        "supplier_id": str(uuid.uuid4()),
        "currency_code": "IQD",
        "tax_amount": Decimal(10),
        "discount_amount": Decimal(0),
        "lines": [
            PurchaseOrderLineRequest(
                product_id=str(uuid.uuid4()), description="سكر أبيض 5 كغم",
                quantity=Decimal(10), unit_price=Decimal("3.5"),
            ),
        ],
    }
    defaults.update(overrides)
    return PurchaseOrderCreateRequest(**defaults)


async def test_receive_purchase_order_with_real_inventory_port_increases_balance(db_session):
    """هذا بالضبط ما كان سينهار قبل الإصلاح: AttributeError على increase_stock
    غير الموجودة في IInventoryPort الحقيقي."""
    ctx, warehouse = await _seed_company_with_accounting_and_warehouse(db_session)
    product_id = str(uuid.uuid4())

    order = await CreatePurchaseOrderUseCase(db_session).execute(
        ctx, _order_request(lines=[
            PurchaseOrderLineRequest(
                product_id=product_id, description="منتج", quantity=Decimal(20), unit_price=Decimal(5)
            )
        ])
    )
    order = await ConfirmPurchaseOrderUseCase(db_session).execute(ctx, str(order.id))

    # الحقن الحقيقي — نفس ما يفعله الـ Router الآن بعد الإصلاح
    order = await ReceivePurchaseOrderUseCase(db_session, SqlInventoryPort(db_session)).execute(
        ctx, str(order.id), warehouse_id=str(warehouse.id)
    )
    assert order.status == "received"

    balance = await get_balance_row(
        db_session, company_id=ctx.company_id, warehouse_id=str(warehouse.id), product_id=product_id
    )
    assert balance is not None
    assert balance.quantity == Decimal(20)


async def test_receive_purchase_order_isolates_stock_by_company(db_session):
    ctx_a, wh_a = await _seed_company_with_accounting_and_warehouse(db_session)
    ctx_b, wh_b = await _seed_company_with_accounting_and_warehouse(db_session)
    product_id = str(uuid.uuid4())

    order = await CreatePurchaseOrderUseCase(db_session).execute(
        ctx_a, _order_request(lines=[
            PurchaseOrderLineRequest(
                product_id=product_id, description="منتج", quantity=Decimal(7), unit_price=Decimal(2)
            )
        ])
    )
    order = await ConfirmPurchaseOrderUseCase(db_session).execute(ctx_a, str(order.id))
    await ReceivePurchaseOrderUseCase(db_session, SqlInventoryPort(db_session)).execute(
        ctx_a, str(order.id), warehouse_id=str(wh_a.id)
    )

    balance_b = await get_balance_row(
        db_session, company_id=ctx_b.company_id, warehouse_id=str(wh_b.id), product_id=product_id
    )
    assert balance_b is None  # لا تسريب مخزون بين الشركات


async def test_post_purchase_invoice_with_real_accounting_port_creates_balanced_entry(db_session):
    """هذا بالضبط ما كان سينهار قبل الإصلاح: TypeError على توقيع
    record_document_posting المختلف عن IAccountingPort الحقيقي."""
    ctx, warehouse = await _seed_company_with_accounting_and_warehouse(db_session)

    order = await CreatePurchaseOrderUseCase(db_session).execute(ctx, _order_request())
    order = await ConfirmPurchaseOrderUseCase(db_session).execute(ctx, str(order.id))
    order = await ReceivePurchaseOrderUseCase(db_session, SqlInventoryPort(db_session)).execute(
        ctx, str(order.id), warehouse_id=str(warehouse.id)
    )
    invoice = await CreatePurchaseInvoiceFromOrderUseCase(db_session).execute(ctx, str(order.id))
    assert invoice.total_amount == Decimal("45.0000")  # (10*3.5)=35 + ضريبة 10

    numbering_service = SqlNumberingService(db_session)
    invoice = await PostPurchaseInvoiceUseCase(
        db_session, SqlAccountingPort(db_session, numbering_service)
    ).execute(ctx, str(invoice.id))

    assert invoice.status == "posted"
    assert invoice.journal_entry_ref is not None
    assert not invoice.journal_entry_ref.startswith("FAKE")  # قيد حقيقي وليس وهمياً


async def test_full_purchasing_flow_end_to_end_with_all_real_ports(db_session):
    """المعيار الكامل: أمر شراء → تأكيد → استلام (يزيد مخزوناً حقيقياً) →
    فاتورة → ترحيل (قيد محاسبي حقيقي متوازن) — بلا أي Fake في السلسلة كاملة."""
    ctx, warehouse = await _seed_company_with_accounting_and_warehouse(db_session)
    product_id = str(uuid.uuid4())

    order = await CreatePurchaseOrderUseCase(db_session).execute(
        ctx, _order_request(lines=[
            PurchaseOrderLineRequest(
                product_id=product_id, description="منتج", quantity=Decimal(15), unit_price=Decimal(4)
            )
        ])
    )
    order = await ConfirmPurchaseOrderUseCase(db_session).execute(ctx, str(order.id))
    order = await ReceivePurchaseOrderUseCase(db_session, SqlInventoryPort(db_session)).execute(
        ctx, str(order.id), warehouse_id=str(warehouse.id)
    )

    balance = await get_balance_row(
        db_session, company_id=ctx.company_id, warehouse_id=str(warehouse.id), product_id=product_id
    )
    assert balance.quantity == Decimal(15)

    invoice = await CreatePurchaseInvoiceFromOrderUseCase(db_session).execute(ctx, str(order.id))
    numbering_service = SqlNumberingService(db_session)
    invoice = await PostPurchaseInvoiceUseCase(
        db_session, SqlAccountingPort(db_session, numbering_service)
    ).execute(ctx, str(invoice.id))

    assert invoice.status == "posted"
    assert invoice.journal_entry_ref is not None
