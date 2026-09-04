"""اختبار تكامل يغطي معيار تسليم العضو 4 (Sales & POS): عرض سعر → أمر بيع →
فاتورة → مرحّلة، بتكامل حقيقي (وليس Mock) مع inventory/accounting/partners/
catalog — كل هذه الوحدات منفَّذة فعلياً في هذه الحزمة. كذلك يغطي POS: فتح
جلسة، مزامنة بيع (Idempotent)، وتأثيره الفعلي على المخزون والمحاسبة.
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
from modules.catalog.application.dto.catalog_dto import ProductCreateRequest, UomCreateRequest
from modules.catalog.application.use_cases.catalog_use_cases import (
    CreateProductUseCase,
    CreateUomUseCase,
)
from modules.catalog.infrastructure.repositories.product_lookup_repository import SqlProductLookup
from modules.inventory.application.dto.inventory_dto import RecordMovementRequest
from modules.inventory.application.use_cases.inventory_use_cases import RecordMovementUseCase
from modules.inventory.domain.rules import MovementType
from modules.inventory.infrastructure.repositories.inventory_repository import (
    SqlInventoryPort,
    get_balance_row,
)
from modules.partners.application.dto.partner_dto import PartnerCreateRequest
from modules.partners.application.use_cases.partner_use_cases import CreatePartnerUseCase
from modules.partners.infrastructure.repositories.partner_lookup_repository import SqlPartnerLookup
from modules.pos.application.dto.pos_dto import (
    CloseSessionRequest,
    OpenSessionRequest,
    PosSaleRequest,
    PosSyncRequest,
)
from modules.pos.application.use_cases.pos_use_cases import (
    ClosePosSessionUseCase,
    OpenPosSessionUseCase,
    SyncPosSalesUseCase,
)
from modules.pos.domain.rules import PosSyncItemStatus
from modules.sales.application.dto.sales_dto import (
    CreditNoteCreateRequest,
    LineItemRequest,
    QuotationCreateRequest,
    SalesInvoiceCreateRequest,
    SalesOrderCreateRequest,
)
from modules.sales.application.use_cases.sales_use_cases import (
    CreateAndPostCreditNoteUseCase,
    CreateQuotationUseCase,
    CreateSalesInvoiceUseCase,
    CreateSalesOrderUseCase,
    PostSalesInvoiceUseCase,
    UpdateQuotationStatusUseCase,
    UpdateSalesOrderStatusUseCase,
)
from modules.sales.domain.rules import QuotationStatus, SalesInvoiceStatus, SalesOrderStatus
from modules.tenancy.infrastructure.models.tenancy_models import Branch, Company, Warehouse
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext

pytestmark = pytest.mark.asyncio


async def _seed_full_company(session):
    """شركة كاملة الإعداد: فترة مالية مفتوحة + شجرة حسابات + مستودع + شريك + منتج."""
    company = Company(name=f"شركة {uuid.uuid4().hex[:8]}", default_currency="IQD")
    session.add(company)
    await session.flush()

    branch = Branch(company_id=company.id, name="الفرع الرئيسي")
    session.add(branch)
    await session.flush()

    warehouse = Warehouse(company_id=company.id, branch_id=branch.id, name="المستودع الرئيسي")
    session.add(warehouse)

    fiscal_year = FiscalYear(company_id=company.id, code="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
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

    ctx = TenantContext(company_id=str(company.id), user_id=str(uuid.uuid4()), branch_id=str(branch.id))

    await SeedDefaultChartOfAccountsUseCase(session).execute(str(company.id))

    partner = await CreatePartnerUseCase(session).execute(
        ctx, PartnerCreateRequest(name="عميل تجريبي")
    )
    uom = await CreateUomUseCase(session).execute(ctx, UomCreateRequest(code="PCS", name="قطعة"))
    product = await CreateProductUseCase(session).execute(
        ctx, ProductCreateRequest(sku="ITEM-1", name="منتج تجريبي", base_uom_id=str(uom.id), sale_price="1000")
    )

    await RecordMovementUseCase(session).execute(
        ctx,
        RecordMovementRequest(
            warehouse_id=str(warehouse.id), product_id=str(product.id), movement_type=MovementType.IN,
            quantity=Decimal(100),
        ),
    )

    return ctx, warehouse, partner, product


def _lookups(session):
    return SqlPartnerLookup(session), SqlProductLookup(session)


async def test_full_lifecycle_quotation_to_posted_invoice(db_session):
    ctx, warehouse, partner, product = await _seed_full_company(db_session)
    partner_lookup, product_lookup = _lookups(db_session)
    numbering_service = SqlNumberingService(db_session)

    quotation = await CreateQuotationUseCase(
        db_session, partner_lookup, product_lookup, numbering_service
    ).execute(
        ctx,
        QuotationCreateRequest(
            partner_id=str(partner.id),
            lines=[LineItemRequest(product_id=str(product.id), quantity=Decimal(5), unit_price=Decimal(1000))],
        ),
    )
    assert quotation.status == QuotationStatus.DRAFT.value
    assert quotation.total_amount == Decimal(5000)

    quotation = await UpdateQuotationStatusUseCase(db_session).execute(ctx, str(quotation.id), QuotationStatus.SENT)
    quotation = await UpdateQuotationStatusUseCase(db_session).execute(ctx, str(quotation.id), QuotationStatus.ACCEPTED)

    order = await CreateSalesOrderUseCase(
        db_session, partner_lookup, product_lookup, numbering_service
    ).execute(
        ctx,
        SalesOrderCreateRequest(
            partner_id=str(partner.id), quotation_id=str(quotation.id),
            lines=[LineItemRequest(product_id=str(product.id), quantity=Decimal(5), unit_price=Decimal(1000))],
        ),
    )
    order = await UpdateSalesOrderStatusUseCase(db_session).execute(ctx, str(order.id), SalesOrderStatus.CONFIRMED)

    invoice = await CreateSalesInvoiceUseCase(
        db_session, partner_lookup, product_lookup, numbering_service
    ).execute(
        ctx,
        SalesInvoiceCreateRequest(
            partner_id=str(partner.id), warehouse_id=str(warehouse.id), sales_order_id=str(order.id),
            lines=[LineItemRequest(product_id=str(product.id), quantity=Decimal(5), unit_price=Decimal(1000))],
        ),
    )
    assert invoice.status == "draft"

    posted = await PostSalesInvoiceUseCase(
        db_session, SqlInventoryPort(db_session), SqlAccountingPort(db_session, numbering_service)
    ).execute(ctx, str(invoice.id))

    assert posted.status == "posted"
    assert posted.journal_entry_id is not None

    balance = await get_balance_row(
        db_session, company_id=ctx.company_id, warehouse_id=str(warehouse.id), product_id=str(product.id)
    )
    assert balance.quantity == Decimal(95)  # 100 - 5 المباعة


async def test_reposting_already_posted_invoice_is_idempotent_noop(db_session):
    """مهمة #11 غيّرت هذا السلوك عمداً: إعادة إرسال /post لفاتورة مُرحَّلة
    فعلاً لم تعد تُطلِق `InvoiceNotDraftError` — تُعيد نفس الفاتورة (نفس
    invoice_id/status) بلا أي أثر جانبي إضافي (idempotency على مستوى طلب
    الترحيل، معيار القبول #3 في README مهمة #11 — راجع أيضاً
    `test_post_already_posted_invoice_is_a_pure_noop` في
    `test_sales_invoice_idempotent_posting.py` لنفس العقد على مستوى sales
    وحدها بمعزل عن باقي الوحدات).
    """
    ctx, warehouse, partner, product = await _seed_full_company(db_session)
    partner_lookup, product_lookup = _lookups(db_session)
    numbering_service = SqlNumberingService(db_session)

    invoice = await CreateSalesInvoiceUseCase(
        db_session, partner_lookup, product_lookup, numbering_service
    ).execute(
        ctx,
        SalesInvoiceCreateRequest(
            partner_id=str(partner.id), warehouse_id=str(warehouse.id),
            lines=[LineItemRequest(product_id=str(product.id), quantity=Decimal(2), unit_price=Decimal(1000))],
        ),
    )
    post_use_case = PostSalesInvoiceUseCase(
        db_session, SqlInventoryPort(db_session), SqlAccountingPort(db_session, numbering_service)
    )
    posted_once = await post_use_case.execute(ctx, str(invoice.id))
    assert posted_once.status == SalesInvoiceStatus.POSTED.value

    # إعادة إرسال /post مرتين إضافيتين: نفس النتيجة، بلا استثناء، وبلا خصم
    # مخزون إضافي (لو كرّرت الحجز/الخصم، رصيد المخزون كان سيصبح سالباً هنا
    # لأن الكمية الأصلية 2 فقط ولا يوجد رصيد كافٍ لخصمها ثلاث مرات).
    for _ in range(2):
        posted_again = await post_use_case.execute(ctx, str(invoice.id))
        assert posted_again.id == posted_once.id
        assert posted_again.status == SalesInvoiceStatus.POSTED.value


async def test_posting_fails_gracefully_when_stock_insufficient_and_releases_reservation(db_session):
    ctx, warehouse, partner, product = await _seed_full_company(db_session)
    partner_lookup, product_lookup = _lookups(db_session)
    numbering_service = SqlNumberingService(db_session)

    invoice = await CreateSalesInvoiceUseCase(
        db_session, partner_lookup, product_lookup, numbering_service
    ).execute(
        ctx,
        SalesInvoiceCreateRequest(
            partner_id=str(partner.id), warehouse_id=str(warehouse.id),
            lines=[LineItemRequest(product_id=str(product.id), quantity=Decimal(500), unit_price=Decimal(1000))],
        ),
    )
    invoice_id = str(invoice.id)
    warehouse_id = str(warehouse.id)
    product_id = str(product.id)

    from modules.inventory.application.ports.inventory_port import InsufficientStockError

    post_use_case = PostSalesInvoiceUseCase(
        db_session, SqlInventoryPort(db_session), SqlAccountingPort(db_session, numbering_service)
    )
    with pytest.raises(InsufficientStockError):
        await post_use_case.execute(ctx, invoice_id)

    # الرصيد الفعلي لم يتأثر إطلاقاً (الحجز أُلغي تلقائياً عند الفشل)
    balance = await get_balance_row(
        db_session, company_id=ctx.company_id, warehouse_id=warehouse_id, product_id=product_id
    )
    assert balance.quantity == Decimal(100)


async def test_credit_note_reduces_receivable_and_revenue(db_session):
    ctx, warehouse, partner, product = await _seed_full_company(db_session)
    partner_lookup, product_lookup = _lookups(db_session)
    numbering_service = SqlNumberingService(db_session)

    invoice = await CreateSalesInvoiceUseCase(
        db_session, partner_lookup, product_lookup, numbering_service
    ).execute(
        ctx,
        SalesInvoiceCreateRequest(
            partner_id=str(partner.id), warehouse_id=str(warehouse.id),
            lines=[LineItemRequest(product_id=str(product.id), quantity=Decimal(4), unit_price=Decimal(1000))],
        ),
    )
    invoice = await PostSalesInvoiceUseCase(
        db_session, SqlInventoryPort(db_session), SqlAccountingPort(db_session, numbering_service)
    ).execute(ctx, str(invoice.id))

    credit_note = await CreateAndPostCreditNoteUseCase(
        db_session, SqlAccountingPort(db_session, numbering_service), numbering_service
    ).execute(
        ctx,
        CreditNoteCreateRequest(
            invoice_id=str(invoice.id),
            lines=[LineItemRequest(product_id=str(product.id), quantity=Decimal(1), unit_price=Decimal(1000))],
        ),
    )
    assert credit_note.status == "posted"
    assert credit_note.total_amount == Decimal(1000)


# ── POS ──────────────────────────────────────────────────────────────────


async def test_pos_open_session_sell_and_close(db_session):
    ctx, warehouse, partner, product = await _seed_full_company(db_session)
    partner_lookup, product_lookup = _lookups(db_session)
    numbering_service = SqlNumberingService(db_session)

    pos_session = await OpenPosSessionUseCase(db_session).execute(
        ctx, OpenSessionRequest(warehouse_id=str(warehouse.id), opening_cash=Decimal(50000))
    )
    assert pos_session.status == "open"

    sync_use_case = SyncPosSalesUseCase(
        db_session, partner_lookup, product_lookup, numbering_service,
        SqlInventoryPort(db_session), SqlAccountingPort(db_session, numbering_service),
    )
    results = await sync_use_case.execute(
        ctx,
        PosSyncRequest(
            session_id=str(pos_session.id),
            sales=[
                PosSaleRequest(
                    client_reference="device-A-txn-1",
                    partner_id=str(partner.id),
                    lines=[LineItemRequest(product_id=str(product.id), quantity=Decimal(3), unit_price=Decimal(1000))],
                )
            ],
        ),
    )
    assert len(results) == 1
    item, invoice_number = results[0]
    assert item.status == PosSyncItemStatus.PROCESSED.value
    assert invoice_number is not None

    balance = await get_balance_row(
        db_session, company_id=ctx.company_id, warehouse_id=str(warehouse.id), product_id=str(product.id)
    )
    assert balance.quantity == Decimal(97)

    closed = await ClosePosSessionUseCase(db_session).execute(
        ctx, str(pos_session.id), CloseSessionRequest(closing_cash=Decimal(53000))
    )
    assert closed.status == "closed"


async def test_pos_sync_is_idempotent_on_retry(db_session):
    """محاكاة انقطاع اتصال: نفس client_reference يُرسَل مرتين — يجب ألا تُنشأ
    فاتورتان ولا يُخصَم المخزون مرتين."""
    ctx, warehouse, partner, product = await _seed_full_company(db_session)
    partner_lookup, product_lookup = _lookups(db_session)
    numbering_service = SqlNumberingService(db_session)

    pos_session = await OpenPosSessionUseCase(db_session).execute(
        ctx, OpenSessionRequest(warehouse_id=str(warehouse.id))
    )

    sale = PosSaleRequest(
        client_reference="device-B-txn-1",
        partner_id=str(partner.id),
        lines=[LineItemRequest(product_id=str(product.id), quantity=Decimal(2), unit_price=Decimal(1000))],
    )

    def make_use_case():
        return SyncPosSalesUseCase(
            db_session, partner_lookup, product_lookup, numbering_service,
            SqlInventoryPort(db_session), SqlAccountingPort(db_session, numbering_service),
        )

    results_1 = await make_use_case().execute(ctx, PosSyncRequest(session_id=str(pos_session.id), sales=[sale]))
    results_2 = await make_use_case().execute(ctx, PosSyncRequest(session_id=str(pos_session.id), sales=[sale]))

    assert results_1[0][0].sales_invoice_id == results_2[0][0].sales_invoice_id

    balance = await get_balance_row(
        db_session, company_id=ctx.company_id, warehouse_id=str(warehouse.id), product_id=str(product.id)
    )
    assert balance.quantity == Decimal(98)  # خُصمت مرة واحدة فقط رغم إرسالها مرتين


async def test_pos_sync_reports_failure_without_blocking_batch(db_session):
    ctx, warehouse, partner, product = await _seed_full_company(db_session)
    partner_lookup, product_lookup = _lookups(db_session)
    numbering_service = SqlNumberingService(db_session)

    pos_session = await OpenPosSessionUseCase(db_session).execute(
        ctx, OpenSessionRequest(warehouse_id=str(warehouse.id))
    )

    sync_use_case = SyncPosSalesUseCase(
        db_session, partner_lookup, product_lookup, numbering_service,
        SqlInventoryPort(db_session), SqlAccountingPort(db_session, numbering_service),
    )
    results = await sync_use_case.execute(
        ctx,
        PosSyncRequest(
            session_id=str(pos_session.id),
            sales=[
                PosSaleRequest(  # هذه ستفشل: كمية أكبر من المتاح
                    client_reference="device-C-txn-1", partner_id=str(partner.id),
                    lines=[LineItemRequest(product_id=str(product.id), quantity=Decimal(999), unit_price=Decimal(1000))],
                ),
                PosSaleRequest(  # هذه يجب أن تنجح رغم فشل سابقتها
                    client_reference="device-C-txn-2", partner_id=str(partner.id),
                    lines=[LineItemRequest(product_id=str(product.id), quantity=Decimal(1), unit_price=Decimal(1000))],
                ),
            ],
        ),
    )

    assert results[0][0].status == PosSyncItemStatus.FAILED.value
    assert results[0][0].error_message is not None
    assert results[1][0].status == PosSyncItemStatus.PROCESSED.value
