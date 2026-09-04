from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.inventory.infrastructure.repositories.inventory_repository import SqlInventoryPort
from modules.purchasing.application.dto.purchasing_dto import (
    PurchaseOrderCreateRequest,
    PurchaseOrderResponse,
)
from modules.purchasing.application.use_cases.purchase_order_use_cases import (
    CancelPurchaseOrderUseCase,
    ConfirmPurchaseOrderUseCase,
    CreatePurchaseOrderUseCase,
    ReceivePurchaseOrderUseCase,
)
from modules.purchasing.infrastructure.repositories.purchasing_repository import (
    PurchaseOrderRepository,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("purchasing.order.create"))],
)
async def create_purchase_order(
    request: PurchaseOrderCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PurchaseOrderResponse:
    order = await CreatePurchaseOrderUseCase(session).execute(ctx, request)
    return PurchaseOrderResponse.model_validate(order)


@router.get("", response_model=list[PurchaseOrderResponse])
async def list_purchase_orders(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[PurchaseOrderResponse]:
    orders = await PurchaseOrderRepository(session).list_for_company(company_id=ctx.company_id)
    return [PurchaseOrderResponse.model_validate(o) for o in orders]


@router.get("/{order_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order(
    order_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PurchaseOrderResponse:
    order = await PurchaseOrderRepository(session).get_by_id(order_id, company_id=ctx.company_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="أمر الشراء غير موجود")
    return PurchaseOrderResponse.model_validate(order)


@router.post(
    "/{order_id}/confirm", response_model=PurchaseOrderResponse,
    dependencies=[Depends(require_permission("purchasing.order.confirm"))],
)
async def confirm_purchase_order(
    order_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PurchaseOrderResponse:
    try:
        order = await ConfirmPurchaseOrderUseCase(session).execute(ctx, order_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PurchaseOrderResponse.model_validate(order)


@router.post(
    "/{order_id}/cancel", response_model=PurchaseOrderResponse,
    dependencies=[Depends(require_permission("purchasing.order.confirm"))],
)
async def cancel_purchase_order(
    order_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PurchaseOrderResponse:
    try:
        order = await CancelPurchaseOrderUseCase(session).execute(ctx, order_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PurchaseOrderResponse.model_validate(order)


@router.post(
    "/{order_id}/receive", response_model=PurchaseOrderResponse,
    dependencies=[Depends(require_permission("purchasing.order.receive"))],
)
async def receive_purchase_order(
    order_id: str,
    warehouse_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PurchaseOrderResponse:
    use_case = ReceivePurchaseOrderUseCase(session, SqlInventoryPort(session))
    try:
        order = await use_case.execute(ctx, order_id, warehouse_id=warehouse_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PurchaseOrderResponse.model_validate(order)
