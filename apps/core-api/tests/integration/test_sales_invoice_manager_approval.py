"""اختبار تكامل مهمة #12 (sales↔workflow): فاتورة بيع > 10,000 تحتاج موافقة
مدير قبل الترحيل. يغطي: بدء نسخة الموافقة تلقائياً عبر IWorkflowPort عند
تجاوز الحد، منع الترحيل وهي pending_approval، السماح بالترحيل بعد approve،
منعه نهائياً بعد reject، وعدم أي تأثير على فاتورة ≤10,000 أو على أي مسار لا
يُمرِّر workflow_port صراحة (سلوك ما قبل هذه المهمة يبقى كما هو).
"""
from decimal import Decimal

import pytest

from modules.accounting.infrastructure.adapters.accounting_port_adapter import SqlAccountingPort
from modules.inventory.infrastructure.repositories.inventory_repository import SqlInventoryPort
from modules.sales.application.dto.sales_dto import LineItemRequest, SalesInvoiceCreateRequest
from modules.sales.application.use_cases.sales_use_cases import (
    CreateSalesInvoiceUseCase,
    InvoiceApprovalPendingError,
    InvoiceApprovalRejectedError,
    PostSalesInvoiceUseCase,
    StartManagerApprovalForSalesInvoiceUseCase,
)
from modules.sales.domain.rules import (
    SALES_INVOICE_APPROVAL_ENTITY_TYPE,
    requires_manager_approval,
)
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from modules.workflow.application.use_cases.workflow_use_cases import (
    TransitionWorkflowInstanceUseCase,
)
from modules.workflow.infrastructure.adapters.workflow_port_adapter import WorkflowPortAdapter
from modules.workflow.infrastructure.repositories.workflow_repository import (
    WorkflowInstanceRepository,
)
from tests.integration.test_sales_and_pos import _lookups, _seed_full_company


async def _create_invoice(db_session, ctx, warehouse, partner, product, *, quantity: Decimal):
    partner_lookup, product_lookup = _lookups(db_session)
    numbering_service = SqlNumberingService(db_session)
    return await CreateSalesInvoiceUseCase(
        db_session, partner_lookup, product_lookup, numbering_service
    ).execute(
        ctx,
        SalesInvoiceCreateRequest(
            partner_id=str(partner.id),
            warehouse_id=str(warehouse.id),
            lines=[LineItemRequest(product_id=str(product.id), quantity=quantity, unit_price=Decimal(1000))],
        ),
    )


async def _latest_instance(db_session, ctx, invoice_id):
    instances = await WorkflowInstanceRepository(db_session).list_for_company(
        company_id=ctx.company_id,
        entity_type=SALES_INVOICE_APPROVAL_ENTITY_TYPE,
        entity_id=str(invoice_id),
    )
    return instances[-1] if instances else None


def test_requires_manager_approval_boundary_is_strictly_greater_than():
    assert requires_manager_approval(Decimal(10000)) is False  # الحد نفسه لا يحتاج موافقة
    assert requires_manager_approval(Decimal("10000.01")) is True
    assert requires_manager_approval(Decimal(9999)) is False


@pytest.mark.asyncio
async def test_invoice_over_threshold_starts_pending_approval_instance_on_create(db_session):
    ctx, warehouse, partner, product = await _seed_full_company(db_session)
    invoice = await _create_invoice(db_session, ctx, warehouse, partner, product, quantity=Decimal(11))
    assert invoice.total_amount == Decimal(11000)

    # CreateSalesInvoiceUseCase تنشر SalesInvoiceCreated فعلياً — نستدعي
    # المعالِج هنا يدوياً (بدل الاعتماد على تسجيل main.py) لعزل الاختبار عن
    # تفاصيل تسجيل Event Bus في نقطة التوصيل.
    await StartManagerApprovalForSalesInvoiceUseCase(WorkflowPortAdapter(db_session)).execute(
        {
            "invoice_id": str(invoice.id),
            "company_id": ctx.company_id,
            "total_amount": str(invoice.total_amount),
        }
    )

    instance = await _latest_instance(db_session, ctx, invoice.id)
    assert instance is not None
    assert instance.current_state == "pending_approval"


@pytest.mark.asyncio
async def test_posting_blocked_while_pending_then_succeeds_after_manager_approval(db_session):
    ctx, warehouse, partner, product = await _seed_full_company(db_session)
    invoice = await _create_invoice(db_session, ctx, warehouse, partner, product, quantity=Decimal(11))

    await StartManagerApprovalForSalesInvoiceUseCase(WorkflowPortAdapter(db_session)).execute(
        {"invoice_id": str(invoice.id), "company_id": ctx.company_id, "total_amount": str(invoice.total_amount)}
    )

    numbering_service = SqlNumberingService(db_session)
    post_use_case = PostSalesInvoiceUseCase(
        db_session,
        SqlInventoryPort(db_session),
        SqlAccountingPort(db_session, numbering_service),
        WorkflowPortAdapter(db_session),
    )

    with pytest.raises(InvoiceApprovalPendingError):
        await post_use_case.execute(ctx, str(invoice.id))

    instance = await _latest_instance(db_session, ctx, invoice.id)
    await TransitionWorkflowInstanceUseCase(db_session).execute(ctx, str(instance.id), "approve")

    posted = await post_use_case.execute(ctx, str(invoice.id))
    assert posted.status == "posted"
    assert posted.journal_entry_id is not None


@pytest.mark.asyncio
async def test_posting_blocked_permanently_after_manager_rejection(db_session):
    ctx, warehouse, partner, product = await _seed_full_company(db_session)
    invoice = await _create_invoice(db_session, ctx, warehouse, partner, product, quantity=Decimal(11))

    await StartManagerApprovalForSalesInvoiceUseCase(WorkflowPortAdapter(db_session)).execute(
        {"invoice_id": str(invoice.id), "company_id": ctx.company_id, "total_amount": str(invoice.total_amount)}
    )
    instance = await _latest_instance(db_session, ctx, invoice.id)
    await TransitionWorkflowInstanceUseCase(db_session).execute(ctx, str(instance.id), "reject")

    numbering_service = SqlNumberingService(db_session)
    post_use_case = PostSalesInvoiceUseCase(
        db_session,
        SqlInventoryPort(db_session),
        SqlAccountingPort(db_session, numbering_service),
        WorkflowPortAdapter(db_session),
    )
    with pytest.raises(InvoiceApprovalRejectedError):
        await post_use_case.execute(ctx, str(invoice.id))


@pytest.mark.asyncio
async def test_invoice_at_or_under_threshold_posts_directly_no_workflow_instance(db_session):
    ctx, warehouse, partner, product = await _seed_full_company(db_session)
    invoice = await _create_invoice(db_session, ctx, warehouse, partner, product, quantity=Decimal(10))
    assert invoice.total_amount == Decimal(10000)  # الحد نفسه — لا يحتاج موافقة

    await StartManagerApprovalForSalesInvoiceUseCase(WorkflowPortAdapter(db_session)).execute(
        {"invoice_id": str(invoice.id), "company_id": ctx.company_id, "total_amount": str(invoice.total_amount)}
    )
    assert await _latest_instance(db_session, ctx, invoice.id) is None  # لم تُنشأ أي نسخة

    numbering_service = SqlNumberingService(db_session)
    posted = await PostSalesInvoiceUseCase(
        db_session,
        SqlInventoryPort(db_session),
        SqlAccountingPort(db_session, numbering_service),
        WorkflowPortAdapter(db_session),
    ).execute(ctx, str(invoice.id))
    assert posted.status == "posted"


@pytest.mark.asyncio
async def test_posting_without_workflow_port_keeps_pre_task12_behavior(db_session):
    """مسار لا يُمرِّر workflow_port صراحة (مثال حقيقي: modules/pos عند البيع
    المباشر) — يجب أن يترحّل حتى لو تجاوزت الفاتورة 10,000، إذ لا Adapter
    حقيقي مُحقَناً (_NullWorkflowPort الافتراضي). هذا يثبت عدم كسر أي مسار
    قائم لم يُعدَّل ضمن نطاق ملفات هذه المهمة."""
    ctx, warehouse, partner, product = await _seed_full_company(db_session)
    invoice = await _create_invoice(db_session, ctx, warehouse, partner, product, quantity=Decimal(11))

    numbering_service = SqlNumberingService(db_session)
    posted = await PostSalesInvoiceUseCase(
        db_session, SqlInventoryPort(db_session), SqlAccountingPort(db_session, numbering_service)
    ).execute(ctx, str(invoice.id))
    assert posted.status == "posted"
