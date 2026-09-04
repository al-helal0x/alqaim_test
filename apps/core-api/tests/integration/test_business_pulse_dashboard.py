"""TASK-BI-01 — لوحة "نبض الشركة اليومي": اختبار المؤشرات الخمسة على
بيانات حقيقية (لا Mock)، + اختبار عزل tenant الإلزامي المطلوب صراحة في
بطاقة المهمة (قسم Tests Required).

نمط الاختبار مطابق لـ `test_chart_of_accounts_and_statements.py`: بناء
مباشر عبر db_session + models، بلا حاجة لعبور طبقة HTTP الكاملة، لأن
الهدف هنا اختبار منطق `BusinessPulseUseCase` نفسه (تجميع بيانات صحيح +
عزل tenant)، لا مسار المصادقة (ذاك مغطى فعلاً في tests/integration/idor/).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from modules.inventory.infrastructure.models.inventory_models import StockBalance
from modules.payments.infrastructure.models.payments_models import BankAccount, Payment, Receipt
from modules.reporting.application.use_cases.business_pulse_use_case import BusinessPulseUseCase
from modules.sales.infrastructure.models.sales_models import SalesInvoice, SalesInvoiceLine
from modules.tenancy.infrastructure.models.tenancy_models import Branch, Company, Warehouse
from platform_core.auth_middleware import TenantContext

pytestmark = pytest.mark.asyncio


async def _seed_company(session, *, name: str = "شركة اختبار نبض الشركة"):
    company = Company(name=name, default_currency="IQD")
    session.add(company)
    await session.flush()

    branch = Branch(company_id=company.id, name="الفرع الرئيسي")
    session.add(branch)
    await session.flush()

    warehouse = Warehouse(company_id=company.id, branch_id=branch.id, name="المستودع الرئيسي")
    session.add(warehouse)
    await session.commit()
    await session.refresh(warehouse)

    ctx = TenantContext(company_id=str(company.id), user_id=str(uuid.uuid4()), branch_id=str(branch.id))
    return company, warehouse, ctx


def _make_posted_invoice(*, company_id, warehouse_id, days_ago: int, total: Decimal, product_id=None):
    product_id = product_id or uuid.uuid4()
    invoice = SalesInvoice(
        company_id=company_id,
        warehouse_id=warehouse_id,
        partner_id=uuid.uuid4(),
        invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
        status="posted",
        currency="IQD",
        subtotal=total,
        total_amount=total,
        created_at=datetime.now(UTC) - timedelta(days=days_ago),
    )
    invoice.lines = [
        SalesInvoiceLine(
            product_id=product_id, quantity=Decimal(2), unit_price=total / 2, line_total=total
        )
    ]
    return invoice


async def test_business_pulse_aggregates_sales_trend_and_top_products(db_session):
    _company, warehouse, ctx = await _seed_company(db_session)
    shared_product = uuid.uuid4()

    # فاتورتان اليوم لنفس المنتج (400 + 100 = 500)، وفاتورة قبل 10 أيام
    # (خارج نافذة 7 أيام الافتراضية) لا يجب أن تدخل في مجموع الفترة الحالية
    db_session.add_all(
        [
            _make_posted_invoice(
                company_id=ctx.company_id, warehouse_id=warehouse.id, days_ago=0,
                total=Decimal(400), product_id=shared_product,
            ),
            _make_posted_invoice(
                company_id=ctx.company_id, warehouse_id=warehouse.id, days_ago=0,
                total=Decimal(100), product_id=shared_product,
            ),
            _make_posted_invoice(
                company_id=ctx.company_id, warehouse_id=warehouse.id, days_ago=10,
                total=Decimal(9999),
            ),
        ]
    )
    # فاتورة مسودة (غير مرحَّلة) — يجب ألا تُحتسَب إطلاقاً
    draft = _make_posted_invoice(
        company_id=ctx.company_id, warehouse_id=warehouse.id, days_ago=0, total=Decimal(5000)
    )
    draft.status = "draft"
    db_session.add(draft)
    await db_session.commit()

    result = await BusinessPulseUseCase(db_session).execute(ctx, period_days=7)

    assert result.sales_total_current_period == Decimal(500)
    assert len(result.sales_trend) == 7  # كل أيام الفترة تظهر، بلا فجوات
    assert result.sales_trend[-1].total_amount == Decimal(500)  # اليوم الحالي = آخر نقطة

    assert len(result.top_products) == 1
    assert result.top_products[0].product_id == str(shared_product)
    assert result.top_products[0].total_amount == Decimal(500)
    assert result.top_products[0].total_quantity == Decimal(4)  # 2 + 2


async def test_business_pulse_cash_position_from_opening_balance_and_confirmed_transactions(db_session):
    _company, _warehouse, ctx = await _seed_company(db_session)

    account = BankAccount(
        company_id=ctx.company_id, name="الصندوق الرئيسي", currency_code="IQD",
        opening_balance=Decimal(1000),
    )
    db_session.add(account)
    await db_session.flush()

    db_session.add_all(
        [
            Receipt(
                company_id=ctx.company_id, bank_account_id=account.id, customer_id=uuid.uuid4(),
                receipt_number="RC-1", amount=Decimal(500), status="confirmed",
            ),
            # مقبوض غير مؤكَّد (مسودة) — يجب ألا يُحتسَب
            Receipt(
                company_id=ctx.company_id, bank_account_id=account.id, customer_id=uuid.uuid4(),
                receipt_number="RC-2", amount=Decimal(300), status="draft",
            ),
            Payment(
                company_id=ctx.company_id, bank_account_id=account.id, supplier_id=uuid.uuid4(),
                payment_number="PM-1", amount=Decimal(200), status="confirmed",
            ),
        ]
    )
    await db_session.commit()

    result = await BusinessPulseUseCase(db_session).execute(ctx, period_days=7)

    # 1000 (افتتاحي) + 500 (مقبوض مؤكَّد) - 200 (مدفوع مؤكَّد) = 1300
    # الـ 300 غير المؤكَّد لا يظهر في الحساب إطلاقاً
    assert result.cash_total == Decimal(1300)
    assert len(result.cash_accounts) == 1
    assert result.cash_accounts[0].balance == Decimal(1300)


async def test_business_pulse_low_stock_returns_lowest_five(db_session):
    _company, warehouse, ctx = await _seed_company(db_session)

    for i in range(7):
        db_session.add(
            StockBalance(
                company_id=ctx.company_id, warehouse_id=warehouse.id, product_id=uuid.uuid4(),
                quantity=Decimal(i * 10),  # 0, 10, 20, ..., 60
            )
        )
    await db_session.commit()

    result = await BusinessPulseUseCase(db_session).execute(ctx, period_days=7)

    assert len(result.low_stock_items) == 5
    quantities = [item.quantity for item in result.low_stock_items]
    assert quantities == sorted(quantities)  # مرتَّبة تصاعدياً
    assert quantities[0] == Decimal(0)


async def test_business_pulse_receivables_aging_buckets_by_invoice_age(db_session):
    _company, warehouse, ctx = await _seed_company(db_session)

    invoice_recent = _make_posted_invoice(
        company_id=ctx.company_id, warehouse_id=warehouse.id, days_ago=5, total=Decimal(1000)
    )
    invoice_mid = _make_posted_invoice(
        company_id=ctx.company_id, warehouse_id=warehouse.id, days_ago=45, total=Decimal(2000)
    )
    invoice_old = _make_posted_invoice(
        company_id=ctx.company_id, warehouse_id=warehouse.id, days_ago=90, total=Decimal(3000)
    )
    invoice_fully_paid = _make_posted_invoice(
        company_id=ctx.company_id, warehouse_id=warehouse.id, days_ago=90, total=Decimal(500)
    )
    db_session.add_all([invoice_recent, invoice_mid, invoice_old, invoice_fully_paid])
    await db_session.flush()

    # invoice_recent مدفوعة جزئياً (400 من 1000 → متبقٍ 600)
    db_session.add(
        Receipt(
            company_id=ctx.company_id, customer_id=uuid.uuid4(), receipt_number="RC-A",
            amount=Decimal(400), status="confirmed", reference_invoice_id=invoice_recent.id,
        )
    )
    # invoice_fully_paid مدفوعة بالكامل → يجب ألا تظهر في أي bucket
    db_session.add(
        Receipt(
            company_id=ctx.company_id, customer_id=uuid.uuid4(), receipt_number="RC-B",
            amount=Decimal(500), status="confirmed", reference_invoice_id=invoice_fully_paid.id,
        )
    )
    await db_session.commit()

    result = await BusinessPulseUseCase(db_session).execute(ctx, period_days=7)

    assert result.receivables_aging.bucket_0_30 == Decimal(600)
    assert result.receivables_aging.bucket_31_60 == Decimal(2000)
    assert result.receivables_aging.bucket_61_plus == Decimal(3000)


async def test_business_pulse_is_isolated_between_tenants(db_session):
    """اختبار عزل tenant الإلزامي (بطاقة المهمة، قسم Tests Required):
    شركة أخرى بنفس بيئة الاختبار يجب ألا تظهر بياناتها إطلاقاً."""
    _company_a, _warehouse_a, ctx_a = await _seed_company(db_session, name="الشركة أ")
    _company_b, warehouse_b, ctx_b = await _seed_company(db_session, name="الشركة ب")

    db_session.add(
        _make_posted_invoice(
            company_id=ctx_b.company_id, warehouse_id=warehouse_b.id, days_ago=0, total=Decimal(99999)
        )
    )
    db_session.add(
        StockBalance(
            company_id=ctx_b.company_id, warehouse_id=warehouse_b.id, product_id=uuid.uuid4(),
            quantity=Decimal(1),
        )
    )
    bank_b = BankAccount(
        company_id=ctx_b.company_id, name="حساب الشركة ب", currency_code="IQD",
        opening_balance=Decimal(50000),
    )
    db_session.add(bank_b)
    await db_session.commit()

    result_a = await BusinessPulseUseCase(db_session).execute(ctx_a, period_days=7)

    assert result_a.sales_total_current_period == Decimal(0)
    assert result_a.top_products == []
    assert result_a.low_stock_items == []
    assert result_a.cash_accounts == []
    assert result_a.cash_total == Decimal(0)
    assert result_a.receivables_aging.bucket_0_30 == Decimal(0)

    # تأكيد إيجابي أن بيانات الشركة ب فعلاً موجودة (لا أن الإعداد نفسه فارغ خطأً)
    result_b = await BusinessPulseUseCase(db_session).execute(ctx_b, period_days=7)
    assert result_b.sales_total_current_period == Decimal(99999)
    assert result_b.cash_total == Decimal(50000)
    assert len(result_b.low_stock_items) == 1


async def test_business_pulse_rejects_invalid_period_days(db_session):
    _company, _warehouse, ctx = await _seed_company(db_session)
    with pytest.raises(ValueError):
        await BusinessPulseUseCase(db_session).execute(ctx, period_days=0)
