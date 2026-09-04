"""Use Cases لأمر الشراء — القسم 4/9. كل الحسابات المالية بـ Decimal حصراً
(Float ممنوع — القسم 17)."""
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from modules.purchasing.application.dto.purchasing_dto import PurchaseOrderCreateRequest
from modules.purchasing.infrastructure.models.purchasing_models import (
    PurchaseOrder,
    PurchaseOrderLine,
)
from modules.purchasing.infrastructure.repositories.purchasing_repository import (
    PurchaseOrderRepository,
)
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext

DOCUMENT_TYPE_PURCHASE_ORDER = "purchase_order"


class CreatePurchaseOrderUseCase:
    """ينشئ أمر شراء بحالة draft. الترقيم عبر INumberingService الحقيقي
    (وحدة tenancy — العضو 1، مبنية ومُختبَرة فعلياً في هذه الحزمة)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, request: PurchaseOrderCreateRequest
    ) -> PurchaseOrder:
        numbering = SqlNumberingService(self._session)
        order_number = await numbering.next_number(
            company_id=ctx.company_id, document_type=DOCUMENT_TYPE_PURCHASE_ORDER
        )

        lines: list[PurchaseOrderLine] = []
        subtotal = Decimal(0)
        for line_req in request.lines:
            line_total = (line_req.quantity * line_req.unit_price).quantize(Decimal("0.0001"))
            subtotal += line_total
            lines.append(
                PurchaseOrderLine(
                    product_id=line_req.product_id,
                    description=line_req.description,
                    quantity=line_req.quantity,
                    unit_price=line_req.unit_price,
                    line_total=line_total,
                )
            )

        total = subtotal + request.tax_amount - request.discount_amount

        order = PurchaseOrder(
            company_id=ctx.company_id,
            branch_id=request.branch_id,
            supplier_id=request.supplier_id,
            order_number=order_number,
            status="draft",
            currency_code=request.currency_code,
            subtotal=subtotal,
            tax_amount=request.tax_amount,
            discount_amount=request.discount_amount,
            total_amount=total,
            lines=lines,
        )
        self._session.add(order)
        await self._session.commit()
        await self._session.refresh(order, attribute_names=["lines"])
        return order


class ConfirmPurchaseOrderUseCase:
    """draft → confirmed. لا تعديل على أمر مؤكَّد إلا عبر إلغاء وإعادة إنشاء
    (سياسة مبسّطة للـ MVP — تعديل جزئي مؤجَّل لمرحلة لاحقة)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, order_id: str) -> PurchaseOrder:
        order = await PurchaseOrderRepository(self._session).get_by_id(
            order_id, company_id=ctx.company_id
        )
        if order is None:
            raise ValueError("أمر الشراء غير موجود أو لا يعود لشركتك")
        if order.status != "draft":
            raise ValueError(f"لا يمكن تأكيد أمر شراء بحالة '{order.status}'")

        order.status = "confirmed"
        order.version += 1
        await self._session.commit()
        await self._session.refresh(order, attribute_names=["lines"])
        return order


class CancelPurchaseOrderUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, order_id: str) -> PurchaseOrder:
        order = await PurchaseOrderRepository(self._session).get_by_id(
            order_id, company_id=ctx.company_id
        )
        if order is None:
            raise ValueError("أمر الشراء غير موجود أو لا يعود لشركتك")
        if order.status == "received":
            raise ValueError("لا يمكن إلغاء أمر شراء مُستلَم بالكامل")

        order.status = "cancelled"
        order.version += 1
        await self._session.commit()
        await self._session.refresh(order, attribute_names=["lines"])
        return order


class ReceivePurchaseOrderUseCase:
    """confirmed → received. يستدعي IInventoryPort.increase_stock لكل بند —
    مُنفَّذ فعلياً الآن عبر SqlInventoryPort (modules/inventory)، مُحقَناً من
    الـ router. FakeInventoryPort يبقى متاحاً فقط لاختبارات لا تتحقق من
    stock_balances (انظر infrastructure/external/fake_ports.py)."""

    def __init__(self, session: AsyncSession, inventory_port) -> None:
        self._session = session
        self._inventory_port = inventory_port

    async def execute(self, ctx: TenantContext, order_id: str, *, warehouse_id: str) -> PurchaseOrder:
        order = await PurchaseOrderRepository(self._session).get_by_id(
            order_id, company_id=ctx.company_id
        )
        if order is None:
            raise ValueError("أمر الشراء غير موجود أو لا يعود لشركتك")
        if order.status != "confirmed":
            raise ValueError(f"لا يمكن استلام أمر شراء بحالة '{order.status}' — يجب تأكيده أولاً")

        for line in order.lines:
            await self._inventory_port.increase_stock(
                company_id=ctx.company_id,
                product_id=str(line.product_id),
                warehouse_id=warehouse_id,
                quantity=line.quantity,
                reference=f"purchase_order:{order.id}",
            )

        order.status = "received"
        order.version += 1
        await self._session.commit()
        await self._session.refresh(order, attribute_names=["lines"])
        return order
