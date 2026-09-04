import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.infrastructure.adapters.accounting_port_adapter import SqlAccountingPort
from modules.inventory.infrastructure.repositories.inventory_repository import SqlInventoryPort
from modules.purchasing.application.dto.purchasing_dto import (
    PurchaseInvoiceCreateRequest,
    PurchaseInvoiceFromAiDraftRequest,
    PurchaseInvoiceFromOrderRequest,
    PurchaseInvoiceResponse,
)
from modules.purchasing.application.use_cases.build_purchase_invoice_from_ai_draft import (
    DraftMappingError,
)
from modules.purchasing.application.use_cases.purchase_invoice_use_cases import (
    CreatePurchaseInvoiceFromOrderUseCase,
    CreatePurchaseInvoiceUseCase,
    PostPurchaseInvoiceUseCase,
    ReceivePurchaseInvoiceInventoryUseCase,
)
from modules.purchasing.application.use_cases.resolve_purchase_invoice_from_ai_draft import (
    create_purchase_invoice_from_approved_draft,
)
from modules.purchasing.infrastructure.repositories.purchasing_repository import (
    PurchaseInvoiceRepository,
)
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.ai_gateway_client import get_ai_platform_client
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "", response_model=PurchaseInvoiceResponse, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("purchasing.invoice.create"))],
)
async def create_purchase_invoice(
    request: PurchaseInvoiceCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PurchaseInvoiceResponse:
    invoice = await CreatePurchaseInvoiceUseCase(session).execute(ctx, request)
    return PurchaseInvoiceResponse.model_validate(invoice)


@router.get("", response_model=list[PurchaseInvoiceResponse])
async def list_purchase_invoices(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[PurchaseInvoiceResponse]:
    invoices = await PurchaseInvoiceRepository(session).list_for_company(company_id=ctx.company_id)
    return [PurchaseInvoiceResponse.model_validate(i) for i in invoices]


@router.post(
    "/from-order", response_model=PurchaseInvoiceResponse, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("purchasing.invoice.create"))],
)
async def create_purchase_invoice_from_order(
    request: PurchaseInvoiceFromOrderRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PurchaseInvoiceResponse:
    try:
        invoice = await CreatePurchaseInvoiceFromOrderUseCase(session).execute(
            ctx, request.purchase_order_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PurchaseInvoiceResponse.model_validate(invoice)


@router.post(
    "/ai-upload", response_model=PurchaseInvoiceResponse, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("purchasing.invoice.create"))],
)
async def create_purchase_invoice_from_ai_draft(
    request: PurchaseInvoiceFromAiDraftRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PurchaseInvoiceResponse:
    """`TASK-AI-01` — يجلب مسودة معتمَدة من `ai-platform` عبر نفس البوابة
    الموجودة فعلاً (`platform_core.ai_gateway_client`، نمط مطابق تماماً
    لـ`presentation/routes/ai_proxy_router.py::get_draft`)، ثم يحوّلها
    لفاتورة شراء عبر الجزأين المُسلَّمين سابقاً — بلا إنشاء فاتورة جزئية
    (`DraftMappingError` → 422 صريح)."""
    async with get_ai_platform_client() as client:
        try:
            response = await client.get(f"/ai/drafts/{request.draft_id}")
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"تعذّر الوصول لخدمة ai-platform: {exc}",
            ) from exc
    draft = response.json()

    try:
        invoice = await create_purchase_invoice_from_approved_draft(
            session, ctx, draft=draft, branch_id=request.branch_id
        )
    except DraftMappingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return PurchaseInvoiceResponse.model_validate(invoice)


@router.post(
    "/{invoice_id}/receive-inventory", response_model=PurchaseInvoiceResponse,
    dependencies=[Depends(require_permission("purchasing.invoice.receive_inventory"))],
)
async def receive_purchase_invoice_inventory(
    invoice_id: str,
    warehouse_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PurchaseInvoiceResponse:
    """`TASK-AI-02b` — خطوة استلام صريحة لفواتير الشراء بلا أمر شراء مرتبط
    (فواتير AI أساساً، وأي فاتورة شراء مباشرة يدوية مستقبلاً). نفس نمط
    `receive_purchase_order` تماماً (`warehouse_id` صريح من المُستدعي،
    `SqlInventoryPort` الحقيقي)."""
    use_case = ReceivePurchaseInvoiceInventoryUseCase(session, SqlInventoryPort(session))
    try:
        invoice = await use_case.execute(ctx, invoice_id, warehouse_id=warehouse_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PurchaseInvoiceResponse.model_validate(invoice)


@router.get("/{invoice_id}", response_model=PurchaseInvoiceResponse)
async def get_purchase_invoice(
    invoice_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PurchaseInvoiceResponse:
    invoice = await PurchaseInvoiceRepository(session).get_by_id(
        invoice_id, company_id=ctx.company_id
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="فاتورة الشراء غير موجودة")
    return PurchaseInvoiceResponse.model_validate(invoice)


@router.post(
    "/{invoice_id}/post", response_model=PurchaseInvoiceResponse,
    dependencies=[Depends(require_permission("purchasing.invoice.post"))],
)
async def post_purchase_invoice(
    invoice_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PurchaseInvoiceResponse:
    numbering_service = SqlNumberingService(session)
    use_case = PostPurchaseInvoiceUseCase(session, SqlAccountingPort(session, numbering_service))
    try:
        invoice = await use_case.execute(ctx, invoice_id)
    except ValueError as exc:
        # يغطي: فاتورة غير موجودة/ليست draft (Purchasing) وكذلك
        # AccountNotFoundError/NoOpenFiscalPeriodError/FiscalPeriodClosedError
        # (Accounting الحقيقي — كلها ValueError، القسم 11.2: لا استيراد مباشر
        # لاستثناءات accounting هنا، فحص نوع الأب كافٍ ومقصود).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return PurchaseInvoiceResponse.model_validate(invoice)
