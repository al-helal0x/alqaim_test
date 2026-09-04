"""`TASK-AI-02` — "التأكد أن فاتورة الشراء من TASK-AI-01 تمر بنفس مسار
الترحيل العادي — لا بناء جديد، فقط تكامل واختبار." كما تنص الخطة حرفياً:
*"Definition of Done: VERIFIED فقط (فجوة مكتشَفة هنا تُفتَح كـTask منفصلة،
لا تُحَل ضمنياً)."* هذا الملف يتحقق مما يعمل فعلاً (الترحيل المحاسبي).

**`TASK-AI-02b` (بعد القرار المعتمَد من صاحب القرار — راجع
`قرار_مطلوب_TASK-AI-02b.md`):** الفجوة المذكورة أعلاه (لا حركة مخزون
لفواتير AI) أُغلقت عبر `ReceivePurchaseInvoiceInventoryUseCase` — خطوة
استلام صريحة منفصلة (القرار الأول → ج) بمعامل `warehouse_id` صريح من
المُستدعي (القرار الثاني → أ). اختبار "يثبت الفجوة" السابق حُدِّث الآن
لإثبات أن الفجوة **مغلقة** بعد استدعاء خطوة الاستلام، بالإضافة لاختبارات
جديدة تُثبِت الحراسات الثلاث (idempotency، منع الاستلام قبل الترحيل، منع
الاستلام لفاتورة مرتبطة بأمر شراء) المذكورة صراحة في تصميم Use Case الاستلام.
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
    PostPurchaseInvoiceUseCase,
    ReceivePurchaseInvoiceInventoryUseCase,
)
from modules.purchasing.application.use_cases.purchase_order_use_cases import (
    ConfirmPurchaseOrderUseCase,
    CreatePurchaseOrderUseCase,
)
from modules.purchasing.application.use_cases.resolve_purchase_invoice_from_ai_draft import (
    create_purchase_invoice_from_approved_draft,
)
from modules.tenancy.infrastructure.models.tenancy_models import Branch, Company, Warehouse
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext

pytestmark = pytest.mark.asyncio


async def _seed_company_with_accounting_and_warehouse(session):
    """نفس دالة الإعداد حرفياً من `test_purchasing_real_ports.py` — إعادة
    استخدام، لا تكرار منطق."""
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


def _approved_draft(**overrides) -> dict:
    supplier_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    draft = {
        "id": str(uuid.uuid4()),
        "status": "approved",
        "matched_supplier_id": supplier_id,
        "extracted_payload": {
            "currency_guess": "IQD",
            "tax_guess": 0,
            "discount_guess": 0,
            "lines": [
                {"description": "بند AI", "quantity": 10.0, "unit_price": 5.0, "line_total": 50.0},
            ],
            "line_matches": [
                {"matches": [{"entity_id": product_id, "text": "منتج", "confidence": 0.97}]},
            ],
        },
    }
    draft.update(overrides)
    return draft, product_id


async def test_ai_invoice_posts_with_real_accounting_port_creates_balanced_entry(db_session):
    """الشطر الأول من TASK-AI-02 — يعمل فعلاً بلا أي تعديل: PostPurchaseInvoiceUseCase
    لا يفرّق بين فاتورة AI وفاتورة عادية (لا يفحص purchase_order_id إطلاقاً)."""
    ctx, _warehouse = await _seed_company_with_accounting_and_warehouse(db_session)
    draft, _product_id = _approved_draft()

    invoice = await create_purchase_invoice_from_approved_draft(
        db_session, ctx, draft=draft, branch_id=ctx.branch_id
    )
    assert invoice.status == "draft"
    assert invoice.purchase_order_id is None  # مسار AI بلا أمر شراء إطلاقاً

    numbering_service = SqlNumberingService(db_session)
    posted = await PostPurchaseInvoiceUseCase(
        db_session, SqlAccountingPort(db_session, numbering_service)
    ).execute(ctx, str(invoice.id))

    assert posted.status == "posted"
    assert posted.journal_entry_ref is not None
    assert not posted.journal_entry_ref.startswith("FAKE")  # قيد حقيقي وليس وهمياً


async def test_ai_invoice_receive_inventory_closes_the_gap(db_session):
    """✅ `TASK-AI-02b` — الفجوة الموثَّقة سابقاً (`STATUS_20_TASKS.md §19.2`:
    فاتورة AI تُرحَّل محاسبياً بنجاح لكن لا حركة مخزون تحدث إطلاقاً) مغلقة
    الآن عبر خطوة استلام صريحة. بعد الترحيل، استدعاء
    `ReceivePurchaseInvoiceInventoryUseCase` بـ`warehouse_id` صريح يزيد
    الرصيد فعلياً بنفس الكمية المفوترة — كان هذا الاختبار سابقاً يُثبِت
    غياب الرصيد (`balance is None`)؛ الآن يُثبِت وجوده بالكمية الصحيحة."""
    ctx, warehouse = await _seed_company_with_accounting_and_warehouse(db_session)
    draft, product_id = _approved_draft()

    invoice = await create_purchase_invoice_from_approved_draft(
        db_session, ctx, draft=draft, branch_id=ctx.branch_id
    )
    numbering_service = SqlNumberingService(db_session)
    posted = await PostPurchaseInvoiceUseCase(
        db_session, SqlAccountingPort(db_session, numbering_service)
    ).execute(ctx, str(invoice.id))

    received = await ReceivePurchaseInvoiceInventoryUseCase(
        db_session, SqlInventoryPort(db_session)
    ).execute(ctx, str(posted.id), warehouse_id=str(warehouse.id))

    assert received.inventory_received_at is not None

    balance = await get_balance_row(
        db_session, company_id=ctx.company_id, warehouse_id=str(warehouse.id), product_id=product_id
    )
    assert balance is not None
    assert balance.quantity == Decimal("10.0000")  # نفس الكمية الواردة في المسودة (§_approved_draft)


async def test_ai_invoice_receive_inventory_is_idempotent_guarded(db_session):
    """حارس Idempotency: استدعاء ثانٍ على نفس الفاتورة يُرفَض صراحة (لا
    زيادة مخزون مزدوجة صامتة) — بنفس نمط `ReceivePurchaseOrderUseCase`."""
    ctx, warehouse = await _seed_company_with_accounting_and_warehouse(db_session)
    draft, _product_id = _approved_draft()

    invoice = await create_purchase_invoice_from_approved_draft(
        db_session, ctx, draft=draft, branch_id=ctx.branch_id
    )
    numbering_service = SqlNumberingService(db_session)
    posted = await PostPurchaseInvoiceUseCase(
        db_session, SqlAccountingPort(db_session, numbering_service)
    ).execute(ctx, str(invoice.id))

    use_case = ReceivePurchaseInvoiceInventoryUseCase(db_session, SqlInventoryPort(db_session))
    await use_case.execute(ctx, str(posted.id), warehouse_id=str(warehouse.id))

    with pytest.raises(ValueError, match="مسبقاً"):
        await use_case.execute(ctx, str(posted.id), warehouse_id=str(warehouse.id))


async def test_ai_invoice_receive_inventory_rejects_before_posting(db_session):
    """حارس ترتيب: لا يمكن استلام بضاعة فاتورة لا تزال `draft` — يمنع مخزوناً
    "موجوداً" لفاتورة غير مُلزِمة محاسبياً بعد (نفس منطق رفض الخيار (ب) في
    وثيقة القرار)."""
    ctx, warehouse = await _seed_company_with_accounting_and_warehouse(db_session)
    draft, _product_id = _approved_draft()

    invoice = await create_purchase_invoice_from_approved_draft(
        db_session, ctx, draft=draft, branch_id=ctx.branch_id
    )
    assert invoice.status == "draft"

    use_case = ReceivePurchaseInvoiceInventoryUseCase(db_session, SqlInventoryPort(db_session))
    with pytest.raises(ValueError, match="ترحيلها محاسبياً"):
        await use_case.execute(ctx, str(invoice.id), warehouse_id=str(warehouse.id))


async def test_ai_invoice_receive_inventory_rejects_invoice_linked_to_purchase_order(db_session):
    """حارس ازدواج: فاتورة مرتبطة بأمر شراء تُستلَم عبر
    `ReceivePurchaseOrderUseCase` (عند استلام الأمر نفسه) — استدعاء هذا
    هذا Use Case عليها يعني مضاعفة نفس الكمية في المخزون، فيُرفَض صراحة."""
    from modules.purchasing.application.use_cases.purchase_invoice_use_cases import (
        CreatePurchaseInvoiceFromOrderUseCase,
    )
    from modules.purchasing.application.use_cases.purchase_order_use_cases import (
        ReceivePurchaseOrderUseCase,
    )

    ctx, warehouse = await _seed_company_with_accounting_and_warehouse(db_session)
    supplier_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())

    order = await CreatePurchaseOrderUseCase(db_session).execute(
        ctx,
        PurchaseOrderCreateRequest(
            branch_id=ctx.branch_id,
            supplier_id=supplier_id,
            lines=[
                PurchaseOrderLineRequest(
                    product_id=product_id, description="بند", quantity=Decimal(5),
                    unit_price=Decimal(10),
                )
            ],
        ),
    )
    confirmed = await ConfirmPurchaseOrderUseCase(db_session).execute(ctx, str(order.id))
    await ReceivePurchaseOrderUseCase(db_session, SqlInventoryPort(db_session)).execute(
        ctx, str(confirmed.id), warehouse_id=str(warehouse.id)
    )
    invoice = await CreatePurchaseInvoiceFromOrderUseCase(db_session).execute(ctx, str(order.id))
    numbering_service = SqlNumberingService(db_session)
    posted = await PostPurchaseInvoiceUseCase(
        db_session, SqlAccountingPort(db_session, numbering_service)
    ).execute(ctx, str(invoice.id))

    use_case = ReceivePurchaseInvoiceInventoryUseCase(db_session, SqlInventoryPort(db_session))
    with pytest.raises(ValueError, match="أمر شراء"):
        await use_case.execute(ctx, str(posted.id), warehouse_id=str(warehouse.id))


async def test_ai_invoice_idempotent_creation_survives_across_posting(db_session):
    """تأكيد إضافي: idempotency (الجزء الثاني المُسلَّم سابقاً) لا يتأثر
    بمرحلة الترحيل — استدعاء ثانٍ لنفس draft_id بعد الترحيل يُعيد نفس
    الفاتورة المُرحَّلة، لا فاتورة جديدة بحالة draft."""
    ctx, _warehouse = await _seed_company_with_accounting_and_warehouse(db_session)
    draft, _product_id = _approved_draft()

    invoice = await create_purchase_invoice_from_approved_draft(
        db_session, ctx, draft=draft, branch_id=ctx.branch_id
    )
    numbering_service = SqlNumberingService(db_session)
    posted = await PostPurchaseInvoiceUseCase(
        db_session, SqlAccountingPort(db_session, numbering_service)
    ).execute(ctx, str(invoice.id))
    assert posted.status == "posted"

    again = await create_purchase_invoice_from_approved_draft(
        db_session, ctx, draft=draft, branch_id=ctx.branch_id
    )
    assert again.id == posted.id
    assert again.status == "posted"  # لم تُعَد الفاتورة لحالة draft
