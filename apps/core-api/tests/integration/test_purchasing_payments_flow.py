"""يغطي معيار تسليم العضو 5: أمر شراء → تأكيد → استلام → فاتورة شراء →
ترحيل محاسبي حقيقي (وليس Fake — انظر تعليق `_register_company` أدناه) →
سند صرف يُحدِّث رصيد الفاتورة عبر Event Bus (وليس استيراداً مباشراً بين
purchasing وpayments — القسم 11.2)."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from modules.accounting.application.use_cases.chart_of_accounts_seed_use_case import (
    SeedDefaultChartOfAccountsUseCase,
)
from modules.accounting.infrastructure.adapters.accounting_port_adapter import SqlAccountingPort
from modules.accounting.infrastructure.models.accounting_models import FiscalPeriod, FiscalYear
from modules.identity.application.dto.identity_dto import RegisterCompanyRequest
from modules.identity.application.use_cases.auth_use_cases import RegisterCompanyUseCase
from modules.identity.infrastructure.models.identity_models import Permission
from modules.inventory.infrastructure.repositories.inventory_repository import (
    SqlInventoryPort,
    get_balance_row,
)
from modules.payments.application.dto.payments_dto import PaymentCreateRequest
from modules.payments.application.use_cases.payments_use_cases import CreatePaymentUseCase
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
from modules.purchasing.infrastructure.event_handlers import make_handler
from modules.purchasing.infrastructure.repositories.purchasing_repository import (
    PurchaseInvoiceRepository,
    PurchaseOrderRepository,
)
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext
from platform_core.event_bus import EventBus
from platform_core.security import decode_token

pytestmark = pytest.mark.asyncio

ALL_PERMISSIONS = [
    "purchasing.order.create", "purchasing.order.confirm", "purchasing.order.receive",
    "purchasing.invoice.create", "purchasing.invoice.post",
    "payments.bank_account.create", "payments.payment.create", "payments.receipt.create",
]


async def _ensure_permissions_seeded(db_session) -> None:
    from sqlalchemy import select

    existing = (
        (await db_session.execute(select(Permission.code))).scalars().all()
    )
    missing = [code for code in ALL_PERMISSIONS if code not in existing]
    for code in missing:
        db_session.add(Permission(code=code, description=code))
    if missing:
        await db_session.commit()


async def _register_company(db_session, email: str) -> TenantContext:
    """يُسجِّل شركة جديدة عبر Bootstrap الحقيقي للعضو 1 (`RegisterCompanyUseCase`)،
    ثم يزرع فوقه ما يحتاجه الترحيل المحاسبي **الحقيقي** الآن (بعد إغلاق فجوة
    FakeAccountingPort): شجرة حسابات افتراضية + سنة/فترة مالية مفتوحة تغطي
    تاريخ اليوم — بدون هذا، `PostPurchaseInvoiceUseCase` سيفشل بـ
    `NoOpenFiscalPeriodError` لأن Bootstrap (ملك العضو 1) لا يزرع فترات مالية
    (ليست من مسؤوليته — القسم 15.2)، تماماً كما يفعل test_sales_and_pos.py
    لنفس السبب بالضبط."""
    await _ensure_permissions_seeded(db_session)

    tokens = await RegisterCompanyUseCase(db_session).execute(
        RegisterCompanyRequest(
            company_name=f"Company {email}", admin_full_name="Admin",
            admin_email=email, admin_password="StrongPass123",
        )
    )
    payload = decode_token(tokens.access_token, expected_type="access")
    company_id = payload["company_id"]

    await SeedDefaultChartOfAccountsUseCase(db_session).execute(company_id)

    today = datetime.now(UTC).date()
    fiscal_year = FiscalYear(
        company_id=company_id, code=str(today.year),
        start_date=today.replace(month=1, day=1), end_date=today.replace(month=12, day=31),
    )
    db_session.add(fiscal_year)
    await db_session.flush()
    period_end = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    db_session.add(
        FiscalPeriod(
            company_id=company_id, fiscal_year_id=fiscal_year.id, period_number=today.month,
            start_date=today.replace(day=1), end_date=period_end,
        )
    )
    await db_session.commit()

    return TenantContext(company_id=company_id, user_id=payload["sub"])


def _order_request(**overrides) -> PurchaseOrderCreateRequest:
    defaults = {
        "branch_id": "11111111-1111-1111-1111-111111111111",
        "supplier_id": "22222222-2222-2222-2222-222222222222",
        "currency_code": "IQD",
        "tax_amount": Decimal(10),
        "discount_amount": Decimal(0),
        "lines": [
            PurchaseOrderLineRequest(
                product_id="33333333-3333-3333-3333-333333333333",
                description="سكر أبيض 5 كغم", quantity=Decimal(10), unit_price=Decimal("3.5"),
            ),
            PurchaseOrderLineRequest(
                product_id="44444444-4444-4444-4444-444444444444",
                description="زيت طبخ", quantity=Decimal(5), unit_price=Decimal(7),
            ),
        ],
    }
    defaults.update(overrides)
    return PurchaseOrderCreateRequest(**defaults)


async def test_purchase_order_totals_calculated_correctly(db_session):
    ctx = await _register_company(db_session, "buyer-a@alqaim-demo.com")
    order = await CreatePurchaseOrderUseCase(db_session).execute(ctx, _order_request())

    # (10*3.5) + (5*7) = 35 + 35 = 70 ، + ضريبة 10 = 80
    assert order.subtotal == Decimal("70.0000")
    assert order.total_amount == Decimal("80.0000")
    assert order.status == "draft"
    assert order.order_number == "000001"


async def test_full_purchase_to_payment_flow_updates_invoice_paid_amount(db_session):
    ctx = await _register_company(db_session, "buyer-b@alqaim-demo.com")

    order = await CreatePurchaseOrderUseCase(db_session).execute(ctx, _order_request())
    order = await ConfirmPurchaseOrderUseCase(db_session).execute(ctx, str(order.id))
    assert order.status == "confirmed"

    warehouse_id = "55555555-5555-5555-5555-555555555555"
    order = await ReceivePurchaseOrderUseCase(db_session, SqlInventoryPort(db_session)).execute(
        ctx, str(order.id), warehouse_id=warehouse_id
    )
    assert order.status == "received"

    # يتحقق من الفجوة التي رصدها المشرف: الاستلام ضد SqlInventoryPort الحقيقي
    # (لا Fake) يجب أن يرفع رصيد كل بند فعلياً في stock_balances، لا أن يمر
    # بصمت فقط.
    for line in order.lines:
        balance = await get_balance_row(
            db_session,
            company_id=ctx.company_id,
            warehouse_id=warehouse_id,
            product_id=str(line.product_id),
        )
        assert balance is not None
        assert balance.quantity == line.quantity

    invoice = await CreatePurchaseInvoiceFromOrderUseCase(db_session).execute(ctx, str(order.id))
    assert invoice.total_amount == order.total_amount
    assert invoice.status == "draft"

    numbering_service = SqlNumberingService(db_session)
    invoice = await PostPurchaseInvoiceUseCase(
        db_session, SqlAccountingPort(db_session, numbering_service)
    ).execute(ctx, str(invoice.id))
    assert invoice.status == "posted"
    assert invoice.journal_entry_ref is not None
    # يتحقق من الفجوة الثانية التي رصدها المشرف: الترحيل ضد SqlAccountingPort
    # الحقيقي (لا Fake) — رقم القيد يجب أن يأتي من INumberingService الحقيقي
    # (تسلسل نظيف، ليس النمط الوهمي "FAKE/PURCHASE_INVOICE/xxxxxxxx" السابق)
    # ويجب أن يتوازن القيد فعلياً في قاعدة البيانات (مدين = دائن).
    assert not invoice.journal_entry_ref.startswith("FAKE")

    from sqlalchemy import select

    from modules.accounting.infrastructure.models.accounting_models import (
        JournalEntry,
        JournalEntryLine,
    )

    journal_entry = (
        await db_session.execute(
            select(JournalEntry).where(
                JournalEntry.source_document_type == "purchase_invoice",
                JournalEntry.source_document_id == str(invoice.id),
            )
        )
    ).scalar_one()
    lines = (
        (
            await db_session.execute(
                select(JournalEntryLine).where(
                    JournalEntryLine.journal_entry_id == journal_entry.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert sum(line.debit for line in lines) == sum(line.credit for line in lines)
    assert sum(line.debit for line in lines) == invoice.total_amount

    # سند صرف جزئي يُحدِّث paid_amount عبر Event Bus (بلا استيراد مباشر لجدول purchasing)
    test_event_bus = EventBus()
    test_event_bus.subscribe("PaymentRecorded", make_handler(db_session))

    payment = await CreatePaymentUseCase(db_session, test_event_bus).execute(
        ctx,
        PaymentCreateRequest(
            supplier_id=str(order.supplier_id), amount=Decimal(30),
            reference_invoice_id=str(invoice.id),
        ),
    )
    assert payment.payment_number == "000001"

    refreshed_invoice = await PurchaseInvoiceRepository(db_session).get_by_id(
        str(invoice.id), company_id=ctx.company_id
    )
    assert refreshed_invoice.paid_amount == Decimal("30.0000")


async def test_cannot_receive_unconfirmed_order(db_session):
    ctx = await _register_company(db_session, "buyer-c@alqaim-demo.com")
    order = await CreatePurchaseOrderUseCase(db_session).execute(ctx, _order_request())

    with pytest.raises(ValueError, match="يجب تأكيده أولاً"):
        # (إصلاح إضافي: كان هذا الاستدعاء يمرّر FakeInventoryPort() بلا استيراده
        # إطلاقاً — NameError كامن لم يظهر إلا لو مرّ هذا الفرع فعلياً. نستخدم
        # SqlInventoryPort الحقيقي هنا بدل ذلك، اتساقاً مع بقية الملف.)
        await ReceivePurchaseOrderUseCase(db_session, SqlInventoryPort(db_session)).execute(
            ctx, str(order.id), warehouse_id="55555555-5555-5555-5555-555555555555"
        )


async def test_cannot_invoice_order_not_yet_received(db_session):
    ctx = await _register_company(db_session, "buyer-d@alqaim-demo.com")
    order = await CreatePurchaseOrderUseCase(db_session).execute(ctx, _order_request())
    order = await ConfirmPurchaseOrderUseCase(db_session).execute(ctx, str(order.id))

    with pytest.raises(ValueError, match="received"):
        await CreatePurchaseInvoiceFromOrderUseCase(db_session).execute(ctx, str(order.id))


async def test_purchase_order_isolated_between_companies(db_session):
    ctx_a = await _register_company(db_session, "buyer-e@alqaim-demo.com")
    ctx_b = await _register_company(db_session, "buyer-f@alqaim-demo.com")

    order = await CreatePurchaseOrderUseCase(db_session).execute(ctx_a, _order_request())

    leaked = await PurchaseOrderRepository(db_session).get_by_id(
        str(order.id), company_id=ctx_b.company_id
    )
    assert leaked is None

    visible = await PurchaseOrderRepository(db_session).get_by_id(
        str(order.id), company_id=ctx_a.company_id
    )
    assert visible is not None
