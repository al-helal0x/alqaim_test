"""Use Cases وحدة pos.

يعيد استخدام Application Layer الخاص بـ sales مباشرة (CreateSalesInvoiceUseCase/
PostSalesInvoiceUseCase) بدل تكرار منطق الفوترة — كلا الوحدتين ملك نفس العضو
(4)، وهذا بالضبط النمط المسموح صراحة في القسم 11.2: "التواصل بين الوحدات عبر
الواجهة العامة المعلنة للـ Module (application layer)"، وليس عبر infrastructure.
"""
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.application.ports.accounting_port import IAccountingPort
from modules.catalog.application.ports.product_lookup_port import IProductLookup
from modules.inventory.application.ports.inventory_port import (
    IInventoryPort,
    InsufficientStockError,
)
from modules.partners.application.ports.partner_lookup_port import IPartnerLookup
from modules.pos.application.dto.pos_dto import (
    CloseSessionRequest,
    OpenSessionRequest,
    PosSaleRequest,
    PosSyncRequest,
)
from modules.pos.domain.rules import PosSessionStatus, PosSyncItemStatus
from modules.pos.infrastructure.models.pos_models import PosSession, PosSyncQueueItem
from modules.sales.application.dto.sales_dto import SalesInvoiceCreateRequest
from modules.sales.application.use_cases.sales_use_cases import (
    CreateSalesInvoiceUseCase,
    PartnerNotFoundError,
    PostSalesInvoiceUseCase,
    ProductNotFoundError,
)
from modules.tenancy.application.ports.numbering_port import INumberingService
from platform_core.auth_middleware import TenantContext


class SessionNotOpenError(ValueError):
    pass


class OpenPosSessionUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: OpenSessionRequest) -> PosSession:
        pos_session = PosSession(
            company_id=ctx.company_id,
            branch_id=ctx.branch_id,
            warehouse_id=request.warehouse_id,
            opened_by=ctx.user_id,
            opening_cash=request.opening_cash,
            status=PosSessionStatus.OPEN.value,
            opened_at=datetime.now(UTC),
        )
        self._session.add(pos_session)
        await self._session.commit()
        await self._session.refresh(pos_session)
        return pos_session


class ClosePosSessionUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, session_id: str, request: CloseSessionRequest
    ) -> PosSession:
        stmt = select(PosSession).where(
            PosSession.id == session_id, PosSession.company_id == ctx.company_id
        )
        pos_session = (await self._session.execute(stmt)).scalar_one_or_none()
        if pos_session is None:
            raise ValueError("الجلسة غير موجودة أو لا تعود لشركتك")
        if pos_session.status != PosSessionStatus.OPEN.value:
            raise SessionNotOpenError("الجلسة مغلقة بالفعل")

        pos_session.status = PosSessionStatus.CLOSED.value
        pos_session.closing_cash = request.closing_cash
        pos_session.closed_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(pos_session)
        return pos_session


class SyncPosSalesUseCase:
    """يعالج كل عملية بيع في الدفعة بشكل مستقل: فشل عملية واحدة (مثال: رصيد
    غير كافٍ) لا يوقف معالجة البقية — الجهاز يحتاج معرفة نتيجة كل عملية على
    حدة ليقرر ماذا يعرض للكاشير (القسم 41: Simulated Offline resilience)."""

    def __init__(
        self,
        session: AsyncSession,
        partner_lookup: IPartnerLookup,
        product_lookup: IProductLookup,
        numbering_service: INumberingService,
        inventory_port: IInventoryPort,
        accounting_port: IAccountingPort,
    ) -> None:
        self._session = session
        self._partner_lookup = partner_lookup
        self._product_lookup = product_lookup
        self._numbering_service = numbering_service
        self._inventory_port = inventory_port
        self._accounting_port = accounting_port

    async def execute(
        self, ctx: TenantContext, request: PosSyncRequest
    ) -> list[tuple[PosSyncQueueItem, str | None]]:
        stmt = select(PosSession).where(
            PosSession.id == request.session_id, PosSession.company_id == ctx.company_id
        )
        pos_session = (await self._session.execute(stmt)).scalar_one_or_none()
        if pos_session is None:
            raise ValueError("الجلسة غير موجودة أو لا تعود لشركتك")
        if pos_session.status != PosSessionStatus.OPEN.value:
            raise SessionNotOpenError("لا يمكن مزامنة مبيعات على جلسة مغلقة")

        results: list[tuple[PosSyncQueueItem, str | None]] = []
        for sale in request.sales:
            results.append(await self._process_one(ctx, pos_session, sale))
        return results

    async def _process_one(
        self, ctx: TenantContext, pos_session: PosSession, sale: PosSaleRequest
    ) -> tuple[PosSyncQueueItem, str | None]:
        existing_stmt = select(PosSyncQueueItem).where(
            PosSyncQueueItem.company_id == ctx.company_id,
            PosSyncQueueItem.client_reference == sale.client_reference,
        )
        existing = (await self._session.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None and existing.status == PosSyncItemStatus.PROCESSED.value:
            invoice_number = None
            if existing.sales_invoice_id is not None:
                from modules.sales.infrastructure.models.sales_models import SalesInvoice

                inv_stmt = select(SalesInvoice.invoice_number).where(
                    SalesInvoice.id == existing.sales_invoice_id
                )
                invoice_number = (await self._session.execute(inv_stmt)).scalar_one_or_none()
            return existing, invoice_number  # نفس العملية سابقاً — لا نعيد إنشاء فاتورة (Idempotency)

        queue_item = existing or PosSyncQueueItem(
            company_id=ctx.company_id,
            session_id=pos_session.id,
            client_reference=sale.client_reference,
            payload=sale.model_dump(mode="json"),
            status=PosSyncItemStatus.PENDING.value,
        )
        if existing is None:
            self._session.add(queue_item)
            await self._session.flush()

        try:
            invoice = await CreateSalesInvoiceUseCase(
                self._session, self._partner_lookup, self._product_lookup, self._numbering_service
            ).execute(
                ctx,
                SalesInvoiceCreateRequest(
                    partner_id=sale.partner_id,
                    warehouse_id=str(pos_session.warehouse_id),
                    currency=sale.currency,
                    discount_amount=sale.discount_amount,
                    lines=sale.lines,
                ),
            )
            invoice = await PostSalesInvoiceUseCase(
                self._session, self._inventory_port, self._accounting_port
            ).execute(ctx, str(invoice.id))
        except (PartnerNotFoundError, ProductNotFoundError, InsufficientStockError, ValueError) as exc:
            queue_item.status = PosSyncItemStatus.FAILED.value
            queue_item.error_message = str(exc)
            queue_item.processed_at = datetime.now(UTC)
            await self._session.commit()
            await self._session.refresh(queue_item)
            return queue_item, None

        queue_item.status = PosSyncItemStatus.PROCESSED.value
        queue_item.sales_invoice_id = invoice.id
        queue_item.processed_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(queue_item)
        return queue_item, invoice.invoice_number
