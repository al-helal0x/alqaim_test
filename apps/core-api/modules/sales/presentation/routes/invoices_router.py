from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.infrastructure.adapters.accounting_port_adapter import SqlAccountingPort
from modules.catalog.infrastructure.repositories.product_lookup_repository import SqlProductLookup
from modules.inventory.application.ports.inventory_port import InsufficientStockError
from modules.inventory.infrastructure.repositories.inventory_repository import SqlInventoryPort
from modules.partners.infrastructure.repositories.partner_lookup_repository import SqlPartnerLookup
from modules.sales.application.dto.sales_dto import (
    SalesInvoiceCreateRequest,
    SalesInvoiceResponse,
)
from modules.sales.application.use_cases.sales_use_cases import (
    CancelDraftSalesInvoiceUseCase,
    CreateSalesInvoiceUseCase,
    InvoiceApprovalPendingError,
    InvoiceApprovalRejectedError,
    InvoiceNotDraftError,
    ListSalesInvoicesUseCase,
    OrderNotConfirmedError,
    PartnerNotFoundError,
    PostSalesInvoiceUseCase,
    ProductNotFoundError,
)
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from modules.workflow.infrastructure.adapters.workflow_port_adapter import WorkflowPortAdapter
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session
from shared_kernel.pagination import Page, PageParams, page_params

router = APIRouter()

_VALIDATION_ERRORS = (PartnerNotFoundError, ProductNotFoundError, OrderNotConfirmedError, ValueError)

# ملاحظة (تعارض #6×#11×#12 محسوم): بوابة موافقة المدير على فواتير > 10,000
# (مهمة #12) مُفعَّلة الآن — يُحقَن WorkflowPortAdapter حقيقي فقط في مسار
# الترحيل عبر API أدناه؛ أي مسار آخر لا يمرّر workflow_port صراحة (مثال:
# modules/pos) يستخدم _NullWorkflowPort ضمنياً داخل PostSalesInvoiceUseCase
# — بلا أي تغيير سلوك هناك.


@router.post(
    "",
    response_model=SalesInvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("sales.invoice.create"))],
)
async def create_sales_invoice(
    request: SalesInvoiceCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> SalesInvoiceResponse:
    # الترويسة `Idempotency-Key` (إن وُجدت) لها الأولوية على حقل الـ body بنفس
    # الاسم — نمط شائع (Stripe-style) يسمح لطبقات وسيطة (proxy/gateway) بضبط
    # إعادة المحاولة دون تعديل جسم الطلب.
    if idempotency_key:
        request = request.model_copy(update={"idempotency_key": idempotency_key})

    use_case = CreateSalesInvoiceUseCase(
        session, SqlPartnerLookup(session), SqlProductLookup(session), SqlNumberingService(session)
    )
    try:
        invoice = await use_case.execute(ctx, request)
    except _VALIDATION_ERRORS as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SalesInvoiceResponse.model_validate(invoice)


@router.get("", response_model=Page[SalesInvoiceResponse])
async def list_sales_invoices(
    params: PageParams = Depends(page_params),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> Page[SalesInvoiceResponse]:
    invoices, total = await ListSalesInvoicesUseCase(session).execute(ctx, params)
    return Page(
        items=[SalesInvoiceResponse.model_validate(i) for i in invoices],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post(
    "/{invoice_id}/post",
    response_model=SalesInvoiceResponse,
    dependencies=[Depends(require_permission("sales.invoice.post"))],
)
async def post_sales_invoice(
    invoice_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> SalesInvoiceResponse:
    numbering_service = SqlNumberingService(session)
    use_case = PostSalesInvoiceUseCase(
        session,
        SqlInventoryPort(session),
        SqlAccountingPort(session, numbering_service),
        # مهمة #12: يُحقَن Adapter حقيقي هنا صراحة — فقط هذا المسار (الترحيل
        # عبر API) يخضع لفحص موافقة المدير. أي مسار آخر لا يمرّر workflow_port
        # (مثال: modules/pos) يستخدم _NullWorkflowPort ضمنياً (لا تغيير سلوك).
        WorkflowPortAdapter(session),
    )
    try:
        invoice = await use_case.execute(ctx, invoice_id)
    except (InvoiceApprovalPendingError, InvoiceApprovalRejectedError) as exc:
        # 409 وليس 422: الفاتورة نفسها صحيحة تماماً (لا خطأ في البيانات) —
        # المشكلة أنها بحالة عمل (Workflow state) لا تسمح بالترحيل الآن.
        # ⚠️ يجب أن يسبق هذا الشرط except (...ValueError) أدناه — كلا
        # الصنفين يرث من ValueError، فلو جاء الشرط العام أولاً سيلتقطهما
        # بصمت كـ 422 ولن يُنفَّذ هذا الشرط إطلاقاً.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (InvoiceNotDraftError, InsufficientStockError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return SalesInvoiceResponse.model_validate(invoice)


@router.post(
    "/{invoice_id}/cancel",
    response_model=SalesInvoiceResponse,
    dependencies=[Depends(require_permission("sales.invoice.update"))],
)
async def cancel_sales_invoice(
    invoice_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> SalesInvoiceResponse:
    try:
        invoice = await CancelDraftSalesInvoiceUseCase(session).execute(ctx, invoice_id)
    except InvoiceNotDraftError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        # ⚠️ إصلاح حقيقي: قبل هذا التعديل، الحالة "غير موجودة أو لا تعود
        # لشركتك" (من _reload_invoice — وهي بالضبط حالة عزل مستأجِر عابر
        # tenant، أي فحص company_id يعمل بشكل صحيح ولا يوجد تسريب بيانات)
        # لم تكن مُلتَقَطة هنا إطلاقاً وكانت تتسرّب كاستثناء غير معالَج
        # (HTTP 500) بدل استجابة نظيفة. اكتُشِف هذا فقط بتشغيل اختبار IDOR
        # حقيقي هنا لأول مرة (test_idor_sales_invoices.py::test_invoice_cancel_is_isolated).
        # ملاحظة اتساق: مسار /post المجاور يُعيد 422 لنفس نوع الخطأ (لا
        # 403/404) — هنا اخترنا 404 لأن رسالة الخطأ الفعلية صريحة بأنها
        # "غير موجودة أو لا تعود لشركتك"، وهذا أقرب لدلالة 404 القياسية.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SalesInvoiceResponse.model_validate(invoice)
