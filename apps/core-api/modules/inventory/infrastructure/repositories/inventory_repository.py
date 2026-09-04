"""طبقة infrastructure المشتركة لوحدة inventory.

قرار تصميم مهم (يوثَّق هنا صراحة لأنه يخالف قراءة حرفية سطحية لسطر واحد في
Blueprint القسم 8): عمود `stock_movements.quantity` هنا **موجَّه إشارياً**
(موجب = زيادة رصيد، سالب = نقص) وليس مقداراً مطلقاً دائماً. هذا يجعل معيار
تسليم العضو 3 ("رصيد كل منتج بكل مستودع = مجموع حركاته دائماً") قابلاً
للتحقق مباشرة بـ `SUM(quantity)` بدل الحاجة لجدول تفاصيل إضافي لمعرفة الاتجاه.
المدخلات من المستخدم (API) تبقى دائماً كميات موجبة (`quantity: Decimal = Field(gt=0)`)
والتحويل للإشارة الصحيحة يحدث هنا فقط، في نقطة واحدة.
"""
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.inventory.application.ports.inventory_port import (
    InsufficientStockError,
    ReservationNotFoundError,
    ReservationRef,
)
from modules.inventory.infrastructure.models.inventory_models import (
    StockBalance,
    StockMovement,
    StockReservation,
)

DEFAULT_RESERVATION_TTL_SECONDS = 15 * 60  # 15 دقيقة — مدة معقولة لعربة بيع/عرض سعر قيد الإنشاء


async def get_balance_row(
    session: AsyncSession, *, company_id: str, warehouse_id: str, product_id: str
) -> StockBalance | None:
    stmt = select(StockBalance).where(
        StockBalance.company_id == company_id,
        StockBalance.warehouse_id == warehouse_id,
        StockBalance.product_id == product_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_available_quantity(
    session: AsyncSession, *, company_id: str, warehouse_id: str, product_id: str
) -> Decimal:
    """المتاح = الرصيد الفعلي - مجموع الحجوزات النشطة غير المنتهية."""
    balance = await get_balance_row(
        session, company_id=company_id, warehouse_id=warehouse_id, product_id=product_id
    )
    on_hand = balance.quantity if balance else Decimal(0)

    stmt = select(StockReservation).where(
        StockReservation.company_id == company_id,
        StockReservation.warehouse_id == warehouse_id,
        StockReservation.product_id == product_id,
        StockReservation.status == "active",
        StockReservation.expires_at > datetime.now(UTC),
    )
    reservations = (await session.execute(stmt)).scalars().all()
    reserved = sum((r.quantity for r in reservations), Decimal(0))
    return on_hand - reserved


async def apply_movement(
    session: AsyncSession,
    *,
    company_id: str,
    warehouse_id: str,
    product_id: str,
    movement_type: str,
    signed_quantity: Decimal,
    unit_cost: Decimal | None,
    source_type: str,
    source_id: str,
    movement_date: datetime | None = None,
    allow_negative_balance: bool = False,
) -> StockMovement:
    """يسجّل حركة ويحدّث stock_balances ضمن نفس الجلسة/المعاملة — نقطة الكتابة
    الوحيدة المسموحة لهذين الجدولين معاً (كل الـ Use Cases في هذه الوحدة تمر
    من هنا، فلا يوجد مسار يكتب حركة بدون تحديث الرصيد المقابل أو العكس)."""
    balance = await get_balance_row(
        session, company_id=company_id, warehouse_id=warehouse_id, product_id=product_id
    )
    if balance is None:
        balance = StockBalance(
            company_id=company_id, warehouse_id=warehouse_id, product_id=product_id, quantity=Decimal(0)
        )
        session.add(balance)

    new_quantity = balance.quantity + signed_quantity
    if new_quantity < 0 and not allow_negative_balance:
        raise InsufficientStockError(
            f"رصيد غير كافٍ: المتوفر {balance.quantity} والمطلوب خصمه {-signed_quantity}"
        )
    balance.quantity = new_quantity

    movement = StockMovement(
        company_id=company_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        movement_type=movement_type,
        quantity=signed_quantity,
        unit_cost=unit_cost,
        source_type=source_type,
        source_id=source_id,
        movement_date=movement_date or datetime.now(UTC),
    )
    session.add(movement)
    return movement


class SqlInventoryPort:
    """تنفيذ IInventoryPort — نقطة الدخول الوحيدة المسموحة للوحدات الأخرى
    (sales/pos/purchasing) للتأثير على المخزون. لا reserve بلا expiry، ولا
    deduct بلا تحديث فوري للرصيد ضمن نفس المعاملة."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def reserve_stock(
        self, *, company_id: str, product_id: str, warehouse_id: str, quantity: Decimal
    ) -> ReservationRef:
        if quantity <= 0:
            raise ValueError("كمية الحجز يجب أن تكون أكبر من صفر")

        available = await get_available_quantity(
            self._session, company_id=company_id, warehouse_id=warehouse_id, product_id=product_id
        )
        if available < quantity:
            raise InsufficientStockError(
                f"لا كمية كافية متاحة للحجز: المتاح {available} والمطلوب {quantity}"
            )

        expires_at = datetime.now(UTC).timestamp() + DEFAULT_RESERVATION_TTL_SECONDS
        expires_dt = datetime.fromtimestamp(expires_at, tz=UTC)

        reservation = StockReservation(
            company_id=company_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=quantity,
            status="active",
            expires_at=expires_dt,
        )
        self._session.add(reservation)
        await self._session.commit()
        await self._session.refresh(reservation)

        return ReservationRef(
            reservation_id=str(reservation.id), expires_at=expires_dt.isoformat()
        )

    async def deduct_stock(
        self,
        *,
        company_id: str,
        product_id: str,
        warehouse_id: str,
        quantity: Decimal,
        reservation_id: str | None = None,
    ) -> None:
        if quantity <= 0:
            raise ValueError("كمية الخصم يجب أن تكون أكبر من صفر")

        if reservation_id is not None:
            stmt = select(StockReservation).where(
                StockReservation.id == reservation_id,
                StockReservation.company_id == company_id,
                StockReservation.status == "active",
            )
            reservation = (await self._session.execute(stmt)).scalar_one_or_none()
            if reservation is None:
                raise ReservationNotFoundError(f"لا يوجد حجز نشط بالمعرّف {reservation_id}")
            reservation.status = "consumed"

        try:
            await apply_movement(
                self._session,
                company_id=company_id,
                warehouse_id=warehouse_id,
                product_id=product_id,
                movement_type="out",
                signed_quantity=-quantity,
                unit_cost=None,
                source_type="reservation" if reservation_id else "direct_deduction",
                source_id=reservation_id or "manual",
            )
        except InsufficientStockError:
            await self._session.rollback()
            raise
        await self._session.commit()

    async def release_reservation(self, *, company_id: str, reservation_id: str) -> None:
        stmt = select(StockReservation).where(
            StockReservation.id == reservation_id,
            StockReservation.company_id == company_id,
            StockReservation.status == "active",
        )
        reservation = (await self._session.execute(stmt)).scalar_one_or_none()
        if reservation is None:
            raise ReservationNotFoundError(f"لا يوجد حجز نشط بالمعرّف {reservation_id}")
        reservation.status = "cancelled"
        await self._session.commit()

    async def increase_stock(
        self,
        *,
        company_id: str,
        product_id: str,
        warehouse_id: str,
        quantity: Decimal,
        reference: str,
    ) -> None:
        """يُطابق `FakeInventoryPort.increase_stock` المُستهلَكة فعلياً من
        Purchasing (`ReceivePurchaseOrderUseCase`). لا Reservation هنا —
        زيادة مباشرة في `stock_balances` عبر حركة `in` حقيقية مسجَّلة في
        `stock_movements`، بنفس مسار الكتابة الوحيد (`apply_movement`) المستخدَم
        في بقية طرق هذا الـ Port لضمان اتساق الرصيد مع مجموع الحركات دائماً."""
        if quantity <= 0:
            raise ValueError("كمية الزيادة يجب أن تكون أكبر من صفر")

        await apply_movement(
            self._session,
            company_id=company_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            movement_type="in",
            signed_quantity=quantity,
            unit_cost=None,
            source_type="purchase_order",
            source_id=reference,
        )
        await self._session.commit()
