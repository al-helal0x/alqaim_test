from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.inventory.application.dto.inventory_dto import (
    RecordMovementRequest,
    StockAdjustmentCreateRequest,
    StockTransferCreateRequest,
)
from modules.inventory.application.ports.inventory_port import InsufficientStockError
from modules.inventory.domain.rules import MovementType, validate_quantity_positive
from modules.inventory.infrastructure.models.inventory_models import (
    StockAdjustment,
    StockBalance,
    StockMovement,
    StockTransfer,
)
from modules.inventory.infrastructure.repositories.inventory_repository import apply_movement
from platform_core.auth_middleware import TenantContext
from shared_kernel.pagination import PageParams, paginate


class RecordMovementUseCase:
    """إدخال حركة يدوية مباشرة (in/out) — يسدّ فجوة عدم وجود purchasing بعد
    لإدخال رصيد ابتدائي أو استلام بضاعة بدون فاتورة شراء رسمية."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: RecordMovementRequest) -> StockMovement:
        if request.movement_type not in (MovementType.IN, MovementType.OUT):
            raise ValueError("الإدخال اليدوي يقبل فقط الأنواع in/out — استخدم /transfers أو /adjustments لغيرها")

        validate_quantity_positive(request.quantity)
        signed_quantity = request.quantity if request.movement_type == MovementType.IN else -request.quantity

        try:
            movement = await apply_movement(
                self._session,
                company_id=ctx.company_id,
                warehouse_id=request.warehouse_id,
                product_id=request.product_id,
                movement_type=request.movement_type.value,
                signed_quantity=signed_quantity,
                unit_cost=request.unit_cost,
                source_type="manual_entry",
                source_id=str(ctx.user_id),
            )
        except InsufficientStockError:
            await self._session.rollback()
            raise
        await self._session.commit()
        await self._session.refresh(movement)
        return movement


class CreateStockTransferUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: StockTransferCreateRequest) -> StockTransfer:
        validate_quantity_positive(request.quantity)
        if request.from_warehouse_id == request.to_warehouse_id:
            raise ValueError("لا يمكن تحويل بضاعة من مستودع لنفسه")

        transfer_date = datetime.now(UTC)
        transfer = StockTransfer(
            company_id=ctx.company_id,
            from_warehouse_id=request.from_warehouse_id,
            to_warehouse_id=request.to_warehouse_id,
            product_id=request.product_id,
            quantity=request.quantity,
            transfer_date=transfer_date,
            notes=request.notes,
        )
        self._session.add(transfer)
        await self._session.flush()  # نحتاج transfer.id كـ source_id للحركتين

        try:
            # الخصم أولاً — إن فشل بسبب رصيد غير كافٍ، لا يوجد أثر جزئي لأن الحركتين
            # ضمن نفس معاملة الـ session (commit واحد أدناه، لا commit وسيط هنا).
            await apply_movement(
                self._session,
                company_id=ctx.company_id,
                warehouse_id=request.from_warehouse_id,
                product_id=request.product_id,
                movement_type="transfer",
                signed_quantity=-request.quantity,
                unit_cost=None,
                source_type="stock_transfer",
                source_id=str(transfer.id),
                movement_date=transfer_date,
            )
            await apply_movement(
                self._session,
                company_id=ctx.company_id,
                warehouse_id=request.to_warehouse_id,
                product_id=request.product_id,
                movement_type="transfer",
                signed_quantity=request.quantity,
                unit_cost=None,
                source_type="stock_transfer",
                source_id=str(transfer.id),
                movement_date=transfer_date,
            )
        except InsufficientStockError:
            await self._session.rollback()
            raise

        await self._session.commit()
        await self._session.refresh(transfer)
        return transfer


class CreateStockAdjustmentUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, request: StockAdjustmentCreateRequest
    ) -> StockAdjustment:
        if request.quantity_delta == 0:
            raise ValueError("قيمة التسوية لا يمكن أن تساوي صفر")

        adjustment_date = datetime.now(UTC)
        adjustment = StockAdjustment(
            company_id=ctx.company_id,
            warehouse_id=request.warehouse_id,
            product_id=request.product_id,
            quantity_delta=request.quantity_delta,
            reason=request.reason,
            adjustment_date=adjustment_date,
        )
        self._session.add(adjustment)
        await self._session.flush()

        try:
            await apply_movement(
                self._session,
                company_id=ctx.company_id,
                warehouse_id=request.warehouse_id,
                product_id=request.product_id,
                movement_type="adjustment",
                signed_quantity=request.quantity_delta,
                unit_cost=None,
                source_type="stock_adjustment",
                source_id=str(adjustment.id),
                movement_date=adjustment_date,
            )
        except InsufficientStockError:
            await self._session.rollback()
            raise

        await self._session.commit()
        await self._session.refresh(adjustment)
        return adjustment


class ListBalancesUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, params: PageParams, *, warehouse_id: str | None = None
    ) -> tuple[list[StockBalance], int]:
        stmt = select(StockBalance).where(StockBalance.company_id == ctx.company_id)
        if warehouse_id:
            stmt = stmt.where(StockBalance.warehouse_id == warehouse_id)
        return await paginate(self._session, stmt, StockBalance, params)


class GetProductBalanceUseCase:
    """رصيد منتج واحد — بالمجموع عبر كل المستودعات، أو بمستودع محدَّد إن مُرِّر."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, product_id: str, *, warehouse_id: str | None = None
    ) -> list[StockBalance]:
        stmt = select(StockBalance).where(
            StockBalance.company_id == ctx.company_id, StockBalance.product_id == product_id
        )
        if warehouse_id:
            stmt = stmt.where(StockBalance.warehouse_id == warehouse_id)
        return list((await self._session.execute(stmt)).scalars().all())


class ListMovementsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        ctx: TenantContext,
        params: PageParams,
        *,
        product_id: str | None = None,
        warehouse_id: str | None = None,
    ) -> tuple[list[StockMovement], int]:
        stmt = select(StockMovement).where(StockMovement.company_id == ctx.company_id)
        if product_id:
            stmt = stmt.where(StockMovement.product_id == product_id)
        if warehouse_id:
            stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
        return await paginate(self._session, stmt, StockMovement, params)


# يُعاد تصدير هنا كي لا تحتاج الوحدات المستهلكة (sales/pos) استيراد ports مباشرة
# في السياقات التي تتعامل مع الأخطاء فقط.
__all__ = [
    "CreateStockAdjustmentUseCase",
    "CreateStockTransferUseCase",
    "GetProductBalanceUseCase",
    "InsufficientStockError",
    "ListBalancesUseCase",
    "ListMovementsUseCase",
    "RecordMovementUseCase",
]
