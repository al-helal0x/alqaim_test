"""اختبار تكامل يغطي معيار تسليم العضو 3 (Inventory): رصيد كل منتج بكل
مستودع صحيح ومطابق لمجموع حركاته دائماً، خصم/حجز يمنعان الرصيد السالب،
والتحويل بين مستودعين متّسق (ما يُخصم من الأول يظهر بالضبط في الثاني).
"""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from modules.inventory.application.dto.inventory_dto import (
    RecordMovementRequest,
    StockAdjustmentCreateRequest,
    StockTransferCreateRequest,
)
from modules.inventory.application.ports.inventory_port import InsufficientStockError
from modules.inventory.application.use_cases.inventory_use_cases import (
    CreateStockAdjustmentUseCase,
    CreateStockTransferUseCase,
    RecordMovementUseCase,
)
from modules.inventory.domain.rules import MovementType
from modules.inventory.infrastructure.models.inventory_models import StockMovement
from modules.inventory.infrastructure.repositories.inventory_repository import (
    SqlInventoryPort,
    get_balance_row,
)
from modules.tenancy.infrastructure.models.tenancy_models import Branch, Company, Warehouse
from platform_core.auth_middleware import TenantContext

pytestmark = pytest.mark.asyncio


async def _seed_company_with_warehouses(session, count: int = 2):
    company = Company(name=f"شركة {uuid.uuid4().hex[:8]}", default_currency="IQD")
    session.add(company)
    await session.flush()

    branch = Branch(company_id=company.id, name="الفرع الرئيسي")
    session.add(branch)
    await session.flush()

    warehouses = []
    for i in range(count):
        wh = Warehouse(company_id=company.id, branch_id=branch.id, name=f"مستودع {i}")
        session.add(wh)
        warehouses.append(wh)
    await session.commit()
    for wh in warehouses:
        await session.refresh(wh)

    ctx = TenantContext(company_id=str(company.id), user_id=str(uuid.uuid4()), branch_id=str(branch.id))
    return ctx, warehouses


def _fake_product_id() -> str:
    return str(uuid.uuid4())


async def test_manual_in_movement_increases_balance(db_session):
    ctx, [wh] = await _seed_company_with_warehouses(db_session, count=1)
    product_id = _fake_product_id()

    movement = await RecordMovementUseCase(db_session).execute(
        ctx,
        RecordMovementRequest(
            warehouse_id=str(wh.id), product_id=product_id, movement_type=MovementType.IN,
            quantity=Decimal(100),
        ),
    )
    assert movement.quantity == Decimal(100)

    balance = await get_balance_row(
        db_session, company_id=ctx.company_id, warehouse_id=str(wh.id), product_id=product_id
    )
    assert balance.quantity == Decimal(100)


async def test_out_movement_cannot_exceed_balance(db_session):
    ctx, [wh] = await _seed_company_with_warehouses(db_session, count=1)
    warehouse_id = str(wh.id)
    product_id = _fake_product_id()

    await RecordMovementUseCase(db_session).execute(
        ctx,
        RecordMovementRequest(
            warehouse_id=warehouse_id, product_id=product_id, movement_type=MovementType.IN,
            quantity=Decimal(10),
        ),
    )
    with pytest.raises(InsufficientStockError):
        await RecordMovementUseCase(db_session).execute(
            ctx,
            RecordMovementRequest(
                warehouse_id=warehouse_id, product_id=product_id, movement_type=MovementType.OUT,
                quantity=Decimal(50),
            ),
        )

    # الرصيد يجب أن يبقى 10 (لا أثر جزئي للحركة الفاشلة) — نستخدم warehouse_id
    # (str محفوظ مسبقاً) وليس wh.id مباشرة، لأن rollback() يُنهي صلاحية كل
    # خصائص الكائنات المحمَّلة، والوصول لها بعدها يحتاج إعادة تحميل صريحة.
    balance = await get_balance_row(
        db_session, company_id=ctx.company_id, warehouse_id=warehouse_id, product_id=product_id
    )
    assert balance.quantity == Decimal(10)


async def test_stock_transfer_moves_quantity_between_warehouses(db_session):
    ctx, [wh_a, wh_b] = await _seed_company_with_warehouses(db_session, count=2)
    product_id = _fake_product_id()

    await RecordMovementUseCase(db_session).execute(
        ctx,
        RecordMovementRequest(
            warehouse_id=str(wh_a.id), product_id=product_id, movement_type=MovementType.IN,
            quantity=Decimal(30),
        ),
    )

    await CreateStockTransferUseCase(db_session).execute(
        ctx,
        StockTransferCreateRequest(
            from_warehouse_id=str(wh_a.id), to_warehouse_id=str(wh_b.id), product_id=product_id,
            quantity=Decimal(12),
        ),
    )

    balance_a = await get_balance_row(
        db_session, company_id=ctx.company_id, warehouse_id=str(wh_a.id), product_id=product_id
    )
    balance_b = await get_balance_row(
        db_session, company_id=ctx.company_id, warehouse_id=str(wh_b.id), product_id=product_id
    )
    assert balance_a.quantity == Decimal(18)
    assert balance_b.quantity == Decimal(12)


async def test_adjustment_can_increase_or_decrease_balance(db_session):
    ctx, [wh] = await _seed_company_with_warehouses(db_session, count=1)
    product_id = _fake_product_id()

    await RecordMovementUseCase(db_session).execute(
        ctx,
        RecordMovementRequest(
            warehouse_id=str(wh.id), product_id=product_id, movement_type=MovementType.IN,
            quantity=Decimal(50),
        ),
    )
    await CreateStockAdjustmentUseCase(db_session).execute(
        ctx,
        StockAdjustmentCreateRequest(
            warehouse_id=str(wh.id), product_id=product_id, quantity_delta=Decimal(-5),
            reason="جرد فعلي أظهر نقصاً",
        ),
    )

    balance = await get_balance_row(
        db_session, company_id=ctx.company_id, warehouse_id=str(wh.id), product_id=product_id
    )
    assert balance.quantity == Decimal(45)


async def test_balance_always_equals_sum_of_movements(db_session):
    """معيار التسليم الحرفي: رصيد كل منتج بكل مستودع = مجموع حركاته دائماً."""
    ctx, [wh_a, wh_b] = await _seed_company_with_warehouses(db_session, count=2)
    product_id = _fake_product_id()

    await RecordMovementUseCase(db_session).execute(
        ctx, RecordMovementRequest(warehouse_id=str(wh_a.id), product_id=product_id, movement_type=MovementType.IN, quantity=Decimal(100))
    )
    await RecordMovementUseCase(db_session).execute(
        ctx, RecordMovementRequest(warehouse_id=str(wh_a.id), product_id=product_id, movement_type=MovementType.OUT, quantity=Decimal(20))
    )
    await CreateStockTransferUseCase(db_session).execute(
        ctx, StockTransferCreateRequest(from_warehouse_id=str(wh_a.id), to_warehouse_id=str(wh_b.id), product_id=product_id, quantity=Decimal(15))
    )
    await CreateStockAdjustmentUseCase(db_session).execute(
        ctx, StockAdjustmentCreateRequest(warehouse_id=str(wh_b.id), product_id=product_id, quantity_delta=Decimal(3), reason="جرد")
    )

    for wh in (wh_a, wh_b):
        movements_stmt = select(StockMovement).where(
            StockMovement.company_id == ctx.company_id,
            StockMovement.warehouse_id == wh.id,
            StockMovement.product_id == product_id,
        )
        movements = (await db_session.execute(movements_stmt)).scalars().all()
        movement_sum = sum((m.quantity for m in movements), Decimal(0))

        balance = await get_balance_row(
            db_session, company_id=ctx.company_id, warehouse_id=str(wh.id), product_id=product_id
        )
        assert balance.quantity == movement_sum


async def test_reserve_then_deduct_via_port(db_session):
    ctx, [wh] = await _seed_company_with_warehouses(db_session, count=1)
    product_id = _fake_product_id()

    await RecordMovementUseCase(db_session).execute(
        ctx, RecordMovementRequest(warehouse_id=str(wh.id), product_id=product_id, movement_type=MovementType.IN, quantity=Decimal(20))
    )

    port = SqlInventoryPort(db_session)
    ref = await port.reserve_stock(
        company_id=ctx.company_id, product_id=product_id, warehouse_id=str(wh.id), quantity=Decimal(8)
    )
    assert ref.reservation_id

    # لا يزال الرصيد الفعلي 20 (الحجز لا يخصم فوراً)
    balance = await get_balance_row(db_session, company_id=ctx.company_id, warehouse_id=str(wh.id), product_id=product_id)
    assert balance.quantity == Decimal(20)

    await port.deduct_stock(
        company_id=ctx.company_id, product_id=product_id, warehouse_id=str(wh.id),
        quantity=Decimal(8), reservation_id=ref.reservation_id,
    )
    balance = await get_balance_row(db_session, company_id=ctx.company_id, warehouse_id=str(wh.id), product_id=product_id)
    assert balance.quantity == Decimal(12)


async def test_reserve_beyond_available_raises(db_session):
    ctx, [wh] = await _seed_company_with_warehouses(db_session, count=1)
    product_id = _fake_product_id()

    await RecordMovementUseCase(db_session).execute(
        ctx, RecordMovementRequest(warehouse_id=str(wh.id), product_id=product_id, movement_type=MovementType.IN, quantity=Decimal(5))
    )
    port = SqlInventoryPort(db_session)
    with pytest.raises(InsufficientStockError):
        await port.reserve_stock(
            company_id=ctx.company_id, product_id=product_id, warehouse_id=str(wh.id), quantity=Decimal(10)
        )


async def test_release_reservation_frees_available_quantity(db_session):
    ctx, [wh] = await _seed_company_with_warehouses(db_session, count=1)
    product_id = _fake_product_id()

    await RecordMovementUseCase(db_session).execute(
        ctx, RecordMovementRequest(warehouse_id=str(wh.id), product_id=product_id, movement_type=MovementType.IN, quantity=Decimal(10))
    )
    port = SqlInventoryPort(db_session)
    ref = await port.reserve_stock(
        company_id=ctx.company_id, product_id=product_id, warehouse_id=str(wh.id), quantity=Decimal(10)
    )
    # حجز كامل الرصيد — أي حجز إضافي يجب أن يفشل الآن
    with pytest.raises(InsufficientStockError):
        await port.reserve_stock(
            company_id=ctx.company_id, product_id=product_id, warehouse_id=str(wh.id), quantity=Decimal(1)
        )

    await port.release_reservation(company_id=ctx.company_id, reservation_id=ref.reservation_id)

    # بعد الإلغاء، الكمية متاحة للحجز من جديد
    ref2 = await port.reserve_stock(
        company_id=ctx.company_id, product_id=product_id, warehouse_id=str(wh.id), quantity=Decimal(10)
    )
    assert ref2.reservation_id != ref.reservation_id


async def test_stock_isolated_across_companies(db_session):
    ctx_a, [wh_a] = await _seed_company_with_warehouses(db_session, count=1)
    ctx_b, [wh_b] = await _seed_company_with_warehouses(db_session, count=1)
    product_id = _fake_product_id()

    await RecordMovementUseCase(db_session).execute(
        ctx_a, RecordMovementRequest(warehouse_id=str(wh_a.id), product_id=product_id, movement_type=MovementType.IN, quantity=Decimal(40))
    )

    balance_b = await get_balance_row(
        db_session, company_id=ctx_b.company_id, warehouse_id=str(wh_b.id), product_id=product_id
    )
    assert balance_b is None  # لا تسريب بين الشركات رغم نفس product_id
