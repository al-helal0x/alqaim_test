from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.infrastructure.adapters.accounting_port_adapter import SqlAccountingPort
from modules.catalog.infrastructure.repositories.product_lookup_repository import SqlProductLookup
from modules.inventory.infrastructure.repositories.inventory_repository import SqlInventoryPort
from modules.partners.infrastructure.repositories.partner_lookup_repository import SqlPartnerLookup
from modules.pos.application.dto.pos_dto import (
    CloseSessionRequest,
    OpenSessionRequest,
    PosSyncRequest,
    PosSyncResponse,
    PosSyncResultItem,
    SessionResponse,
)
from modules.pos.application.use_cases.pos_use_cases import (
    ClosePosSessionUseCase,
    OpenPosSessionUseCase,
    SessionNotOpenError,
    SyncPosSalesUseCase,
)
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("pos.session.open"))],
)
async def open_session(
    request: OpenSessionRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    pos_session = await OpenPosSessionUseCase(session).execute(ctx, request)
    return SessionResponse.model_validate(pos_session)


@router.post(
    "/sessions/{session_id}/close",
    response_model=SessionResponse,
    dependencies=[Depends(require_permission("pos.session.close"))],
)
async def close_session(
    session_id: str,
    request: CloseSessionRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    try:
        pos_session = await ClosePosSessionUseCase(session).execute(ctx, session_id, request)
    except (SessionNotOpenError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SessionResponse.model_validate(pos_session)


@router.post(
    "/sync",
    response_model=PosSyncResponse,
    dependencies=[Depends(require_permission("pos.sale.sync"))],
)
async def sync_sales(
    request: PosSyncRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PosSyncResponse:
    """نقطة الدخول الوحيدة لمزامنة مبيعات POS — Idempotent عبر client_reference.
    لا تفشل الطلب كله إن فشلت عملية بيع واحدة ضمن الدفعة؛ كل عملية لها نتيجتها
    الخاصة في الاستجابة (القسم 41: Simulated Offline resilience)."""
    numbering_service = SqlNumberingService(session)
    use_case = SyncPosSalesUseCase(
        session,
        SqlPartnerLookup(session),
        SqlProductLookup(session),
        numbering_service,
        SqlInventoryPort(session),
        SqlAccountingPort(session, numbering_service),
    )
    try:
        results = await use_case.execute(ctx, request)
    except (SessionNotOpenError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return PosSyncResponse(
        results=[
            PosSyncResultItem(
                client_reference=item.client_reference,
                status=item.status,
                sales_invoice_id=str(item.sales_invoice_id) if item.sales_invoice_id else None,
                invoice_number=invoice_number,
                error=item.error_message,
            )
            for item, invoice_number in results
        ]
    )
