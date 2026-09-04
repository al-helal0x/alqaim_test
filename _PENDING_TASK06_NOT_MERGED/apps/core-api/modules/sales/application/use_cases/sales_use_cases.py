"""Use Cases وحدة sales.

تكامل حقيقي (وليس Mock) مع IInventoryPort/IAccountingPort/IPartnerLookup/
IProductLookup/INumberingService — كلها منفَّذة فعلياً في هذه الحزمة الآن.

قرار معماري مهم موثَّق هنا صراحة (PostSalesInvoiceUseCase): كل من
IInventoryPort وIAccountingPort يعملان بنمط "كل نداء يُنهي معاملته الخاصة"
(self-committing) — هذا يعني عدم وجود ضمان Atomicity كامل عبر عدة نداءات
متتالية بدون Saga/Outbox حقيقي (غير مُنفَّذ بعد — القسم 6.6 TODO). للتخفيف
العملي من مخاطر الفشل الجزئي، الترتيب هنا هو: **حجز (reserve) ثم ترحيل محاسبي
ثم خصم فعلي (deduct) يستهلك الحجز نفسه** — الحجز لا يغيّر الرصيد الفعلي (فقط
يقلّل "المتاح")، فلو فشل الترحيل المحاسبي (مثال: فترة مالية مقفلة) لا يوجد
أي أثر فعلي على المخزون بعد، فقط يُترك الحجز لينتهي صلاحيته تلقائياً خلال
15 دقيقة. نافذة عدم الاتساق الوحيدة المتبقية هي فشل نادر لـ deduct_stock بعد
نجاح الترحيل المحاسبي (Reservation انتهت صلاحيتها بالتزامن) — موثَّقة كخطر
معروف يحتاج مراجعة يدوية إن وقعت (نادرة جداً عملياً ضمن طلب متزامن واحد).
"""
from datetime import date as date_type
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.accounting.application.ports.accounting_port import (
    DocumentPostingLine,
    DocumentPostingRequest,
    IAccountingPort,
)
from modules.catalog.application.ports.product_lookup_port import IProductLookup
from modules.inventory.application.ports.inventory_port import (
    IInventoryPort,
    InsufficientStockError,
)
from modules.partners.application.ports.partner_lookup_port import IPartnerLookup
from modules.sales.application.dto.sales_dto import (
    CreditNoteCreateRequest,
    LineItemRequest,
    QuotationCreateRequest,
    SalesInvoiceCreateRequest,
    SalesOrderCreateRequest,
)
from modules.sales.domain.rules import (
    LineInput,
    QuotationStatus,
    SalesInvoiceStatus,
    SalesOrderStatus,
    assert_valid_order_transition,
    assert_valid_quotation_transition,
    calculate_document_totals,
    calculate_line_total,
)
from modules.sales.infrastructure.models.sales_models import (
    CreditNote,
    CreditNoteLine,
    Quotation,
    QuotationLine,
    SalesInvoice,
    SalesInvoiceLine,
    SalesOrder,
    SalesOrderLine,
)
from modules.tenancy.application.ports.numbering_port import INumberingService
from platform_core.auth_middleware import TenantContext
from platform_core.event_bus import event_bus
from shared_kernel.pagination import PageParams, paginate


class PartnerNotFoundError(ValueError):
    pass


class ProductNotFoundError(ValueError):
    pass


class InvoiceNotDraftError(ValueError):
    pass


class QuotationNotAcceptedError(ValueError):
    pass


class OrderNotConfirmedError(ValueError):
    pass


async def _validate_partner(partner_lookup: IPartnerLookup, ctx: TenantContext, partner_id: str) -> None:
    partner = await partner_lookup.get(company_id=ctx.company_id, partner_id=partner_id)
    if partner is None:
        raise PartnerNotFoundError(f"الشريك {partner_id} غير موجود لهذه الشركة")


async def _validate_products(
    product_lookup: IProductLookup, ctx: TenantContext, lines: list[LineItemRequest]
) -> None:
    for line in lines:
        product = await product_lookup.get(company_id=ctx.company_id, product_id=line.product_id)
        if product is None:
            raise ProductNotFoundError(f"المنتج {line.product_id} غير موجود لهذه الشركة")
        if not product.is_active:
            raise ProductNotFoundError(f"المنتج {product.name} غير نشط ولا يمكن بيعه")


def _to_line_inputs(lines: list[LineItemRequest]) -> list[LineInput]:
    return [LineInput(quantity=l.quantity, unit_price=l.unit_price, tax_amount=l.tax_amount) for l in lines]


async def _get_owned(session: AsyncSession, model, ctx: TenantContext, entity_id: str, label: str):
    stmt = select(model).where(model.id == entity_id, model.company_id == ctx.company_id)
    entity = (await session.execute(stmt)).scalar_one_or_none()
    if entity is None:
        raise ValueError(f"{label} غير موجود أو لا يعود لشركتك")
    return entity


# ── Quotations ───────────────────────────────────────────────────────────


class CreateQuotationUseCase:
    def __init__(
        self,
        session: AsyncSession,
        partner_lookup: IPartnerLookup,
        product_lookup: IProductLookup,
        numbering_service: INumberingService,
    ) -> None:
        self._session = session
        self._partner_lookup = partner_lookup
        self._product_lookup = product_lookup
        self._numbering_service = numbering_service

    async def execute(self, ctx: TenantContext, request: QuotationCreateRequest) -> Quotation:
        await _validate_partner(self._partner_lookup, ctx, request.partner_id)
        await _validate_products(self._product_lookup, ctx, request.lines)
        totals = calculate_document_totals(_to_line_inputs(request.lines))

        number = await self._numbering_service.next_number(
            company_id=ctx.company_id, document_type="quotation"
        )
        quotation = Quotation(
            company_id=ctx.company_id,
            branch_id=ctx.branch_id,
            partner_id=request.partner_id,
            quotation_number=number,
            status=QuotationStatus.DRAFT.value,
            currency=request.currency,
            subtotal=totals.subtotal,
            tax_amount=totals.tax_amount,
            total_amount=totals.total_amount,
        )
        self._session.add(quotation)
        await self._session.flush()

        for line in request.lines:
            line_total = calculate_line_total(
                LineInput(quantity=line.quantity, unit_price=line.unit_price, tax_amount=line.tax_amount)
            )
            self._session.add(
                QuotationLine(
                    quotation_id=quotation.id,
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    tax_amount=line.tax_amount,
                    line_total=line_total.line_total,
                )
            )

        await self._session.commit()
        return await _reload_quotation(self._session, quotation.id)


class UpdateQuotationStatusUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, quotation_id: str, target_status: QuotationStatus
    ) -> Quotation:
        quotation = await _get_owned(self._session, Quotation, ctx, quotation_id, "عرض السعر")
        assert_valid_quotation_transition(QuotationStatus(quotation.status), target_status)
        quotation.status = target_status.value
        await self._session.commit()
        return await _reload_quotation(self._session, quotation.id)


class ListQuotationsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, params: PageParams) -> tuple[list[Quotation], int]:
        stmt = (
            select(Quotation)
            .where(Quotation.company_id == ctx.company_id, Quotation.deleted_at.is_(None))
            .options(selectinload(Quotation.lines))
        )
        return await paginate(self._session, stmt, Quotation, params)


class GetQuotationUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, quotation_id: str) -> Quotation:
        return await _reload_quotation(self._session, quotation_id, company_id=ctx.company_id)


async def _reload_quotation(session: AsyncSession, quotation_id, *, company_id: str | None = None) -> Quotation:
    stmt = select(Quotation).where(Quotation.id == quotation_id).options(selectinload(Quotation.lines))
    if company_id is not None:
        stmt = stmt.where(Quotation.company_id == company_id)
    quotation = (await session.execute(stmt)).scalar_one_or_none()
    if quotation is None:
        raise ValueError("عرض السعر غير موجود أو لا يعود لشركتك")
    return quotation


# ── Sales Orders ─────────────────────────────────────────────────────────


class CreateSalesOrderUseCase:
    """يُنشئ أمر بيع مباشرة، أو من عرض سعر مقبول (accepted) عبر تمرير quotation_id."""

    def __init__(
        self,
        session: AsyncSession,
        partner_lookup: IPartnerLookup,
        product_lookup: IProductLookup,
        numbering_service: INumberingService,
    ) -> None:
        self._session = session
        self._partner_lookup = partner_lookup
        self._product_lookup = product_lookup
        self._numbering_service = numbering_service

    async def execute(self, ctx: TenantContext, request: SalesOrderCreateRequest) -> SalesOrder:
        await _validate_partner(self._partner_lookup, ctx, request.partner_id)
        await _validate_products(self._product_lookup, ctx, request.lines)

        if request.quotation_id is not None:
            quotation = await _get_owned(self._session, Quotation, ctx, request.quotation_id, "عرض السعر")
            if quotation.status != QuotationStatus.ACCEPTED.value:
                raise QuotationNotAcceptedError("لا يمكن تحويل عرض سعر لأمر بيع إلا بعد قبوله (accepted)")

        totals = calculate_document_totals(_to_line_inputs(request.lines))
        number = await self._numbering_service.next_number(
            company_id=ctx.company_id, document_type="sales_order"
        )
        order = SalesOrder(
            company_id=ctx.company_id,
            branch_id=ctx.branch_id,
            partner_id=request.partner_id,
            quotation_id=request.quotation_id,
            order_number=number,
            status=SalesOrderStatus.DRAFT.value,
            currency=request.currency,
            subtotal=totals.subtotal,
            tax_amount=totals.tax_amount,
            total_amount=totals.total_amount,
        )
        self._session.add(order)
        await self._session.flush()

        for line in request.lines:
            line_total = calculate_line_total(
                LineInput(quantity=line.quantity, unit_price=line.unit_price, tax_amount=line.tax_amount)
            )
            self._session.add(
                SalesOrderLine(
                    sales_order_id=order.id,
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    tax_amount=line.tax_amount,
                    line_total=line_total.line_total,
                )
            )

        await self._session.commit()
        return await _reload_order(self._session, order.id)


class UpdateSalesOrderStatusUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, order_id: str, target_status: SalesOrderStatus
    ) -> SalesOrder:
        order = await _get_owned(self._session, SalesOrder, ctx, order_id, "أمر البيع")
        assert_valid_order_transition(SalesOrderStatus(order.status), target_status)
        order.status = target_status.value
        await self._session.commit()
        return await _reload_order(self._session, order.id)


class ListSalesOrdersUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, params: PageParams) -> tuple[list[SalesOrder], int]:
        stmt = (
            select(SalesOrder)
            .where(SalesOrder.company_id == ctx.company_id, SalesOrder.deleted_at.is_(None))
            .options(selectinload(SalesOrder.lines))
        )
        return await paginate(self._session, stmt, SalesOrder, params)


async def _reload_order(session: AsyncSession, order_id, *, company_id: str | None = None) -> SalesOrder:
    stmt = select(SalesOrder).where(SalesOrder.id == order_id).options(selectinload(SalesOrder.lines))
    if company_id is not None:
        stmt = stmt.where(SalesOrder.company_id == company_id)
    order = (await session.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise ValueError("أمر البيع غير موجود أو لا يعود لشركتك")
    return order


# ── Sales Invoices ───────────────────────────────────────────────────────


class CreateSalesInvoiceUseCase:
    """يُنشئ فاتورة Draft — مباشرة أو من أمر بيع مؤكَّد (confirmed)."""

    def __init__(
        self,
        session: AsyncSession,
        partner_lookup: IPartnerLookup,
        product_lookup: IProductLookup,
        numbering_service: INumberingService,
    ) -> None:
        self._session = session
        self._partner_lookup = partner_lookup
        self._product_lookup = product_lookup
        self._numbering_service = numbering_service

    async def execute(self, ctx: TenantContext, request: SalesInvoiceCreateRequest) -> SalesInvoice:
        await _validate_partner(self._partner_lookup, ctx, request.partner_id)
        await _validate_products(self._product_lookup, ctx, request.lines)

        if request.sales_order_id is not None:
            order = await _get_owned(self._session, SalesOrder, ctx, request.sales_order_id, "أمر البيع")
            if order.status != SalesOrderStatus.CONFIRMED.value:
                raise OrderNotConfirmedError("لا يمكن فوترة أمر بيع إلا بعد تأكيده (confirmed)")

        totals = calculate_document_totals(_to_line_inputs(request.lines))
        if request.discount_amount > totals.subtotal:
            raise ValueError("مبلغ الخصم لا يمكن أن يتجاوز المجموع الفرعي")

        number = await self._numbering_service.next_number(
            company_id=ctx.company_id, document_type="sales_invoice"
        )
        invoice = SalesInvoice(
            company_id=ctx.company_id,
            branch_id=ctx.branch_id,
            warehouse_id=request.warehouse_id,
            partner_id=request.partner_id,
            sales_order_id=request.sales_order_id,
            invoice_number=number,
            status=SalesInvoiceStatus.DRAFT.value,
            currency=request.currency,
            subtotal=totals.subtotal,
            discount_amount=request.discount_amount,
            tax_amount=totals.tax_amount,
            total_amount=totals.subtotal - request.discount_amount + totals.tax_amount,
        )
        self._session.add(invoice)
        await self._session.flush()

        for line in request.lines:
            line_total = calculate_line_total(
                LineInput(quantity=line.quantity, unit_price=line.unit_price, tax_amount=line.tax_amount)
            )
            self._session.add(
                SalesInvoiceLine(
                    sales_invoice_id=invoice.id,
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    tax_amount=line.tax_amount,
                    line_total=line_total.line_total,
                )
            )

        if request.sales_order_id is not None:
            order.status = SalesOrderStatus.INVOICED.value

        await self._session.commit()
        return await _reload_invoice(self._session, invoice.id)


class PostSalesInvoiceUseCase:
    """الترحيل الفعلي: حجز فالمحاسبة فالخصم (انظر تعليق أعلى الملف). أهم Use Case
    في هذه الوحدة — يمثّل "معيار التسليم" (مسودة→مرحّلة) للعضو 4."""

    def __init__(
        self,
        session: AsyncSession,
        inventory_port: IInventoryPort,
        accounting_port: IAccountingPort,
    ) -> None:
        self._session = session
        self._inventory_port = inventory_port
        self._accounting_port = accounting_port

    async def execute(self, ctx: TenantContext, invoice_id: str) -> SalesInvoice:
        invoice = await _reload_invoice(self._session, invoice_id, company_id=ctx.company_id)
        if invoice.status != SalesInvoiceStatus.DRAFT.value:
            raise InvoiceNotDraftError("لا يمكن ترحيل فاتورة إلا وهي بحالة draft")

        # المرحلة 1: حجز كل الأسطر أولاً (لا يغيّر الرصيد الفعلي بعد)
        reservations: list[tuple[str, str]] = []  # (product_id, reservation_id)
        try:
            for line in invoice.lines:
                ref = await self._inventory_port.reserve_stock(
                    company_id=ctx.company_id,
                    product_id=str(line.product_id),
                    warehouse_id=str(invoice.warehouse_id),
                    quantity=line.quantity,
                )
                reservations.append((str(line.product_id), ref.reservation_id))
        except InsufficientStockError:
            # تعويض: إلغاء أي حجوزات نجحت قبل السطر الذي فشل
            for _, reservation_id in reservations:
                await self._inventory_port.release_reservation(
                    company_id=ctx.company_id, reservation_id=reservation_id
                )
            raise

        # المرحلة 2: الترحيل المحاسبي
        posting_lines = [
            DocumentPostingLine(
                account_code="1110", debit=invoice.total_amount, credit=Decimal(0),
                description=f"فاتورة بيع {invoice.invoice_number}",
            ),
            DocumentPostingLine(
                account_code="4100", debit=Decimal(0),
                credit=invoice.subtotal - invoice.discount_amount,
                description=f"إيراد فاتورة بيع {invoice.invoice_number}",
            ),
        ]
        if invoice.tax_amount > 0:
            posting_lines.append(
                DocumentPostingLine(
                    account_code="2200", debit=Decimal(0), credit=invoice.tax_amount,
                    description=f"ضريبة مخرجات فاتورة {invoice.invoice_number}",
                )
            )

        journal_ref = await self._accounting_port.record_document_posting(
            DocumentPostingRequest(
                company_id=ctx.company_id,
                entry_date=date_type.today().isoformat(),
                source_document_type="sales_invoice",
                source_document_id=str(invoice.id),
                currency=invoice.currency,
                lines=posting_lines,
                memo=f"ترحيل فاتورة بيع {invoice.invoice_number}",
            )
        )

        # المرحلة 3: الخصم الفعلي يستهلك الحجوزات نفسها
        for product_id, reservation_id in reservations:
            line = next(l for l in invoice.lines if str(l.product_id) == product_id)
            await self._inventory_port.deduct_stock(
                company_id=ctx.company_id,
                product_id=product_id,
                warehouse_id=str(invoice.warehouse_id),
                quantity=line.quantity,
                reservation_id=reservation_id,
            )

        invoice.status = SalesInvoiceStatus.POSTED.value
        invoice.journal_entry_id = journal_ref.journal_entry_id

        # مهمة 6 (Outbox): الحدث يُكتَب ضمن نفس معاملة الترحيل قبل الـ
        # commit — إما يُحفَظ ترحيل الفاتورة والحدث معاً أو لا شيء.
        await event_bus.publish(
            self._session,
            "InvoicePosted",
            {
                "invoice_id": str(invoice.id),
                "invoice_type": "sale",
                "total": str(invoice.total_amount),
                "currency": invoice.currency,
                "partner_id": str(invoice.partner_id),
                "company_id": ctx.company_id,
            },
        )
        await self._session.commit()

        # محاولة تسليم فورية (best effort) — أي فشل يلتقطه outbox_worker لاحقاً
        await event_bus.dispatch_pending(self._session)

        return await _reload_invoice(self._session, invoice.id)


class CancelDraftSalesInvoiceUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, invoice_id: str) -> SalesInvoice:
        invoice = await _reload_invoice(self._session, invoice_id, company_id=ctx.company_id)
        if invoice.status != SalesInvoiceStatus.DRAFT.value:
            raise InvoiceNotDraftError("لا يمكن إلغاء فاتورة إلا وهي بحالة draft — استخدم إشعار دائن لفاتورة مرحّلة")
        invoice.status = SalesInvoiceStatus.CANCELLED.value
        await self._session.commit()
        return await _reload_invoice(self._session, invoice.id)


class ListSalesInvoicesUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, params: PageParams) -> tuple[list[SalesInvoice], int]:
        stmt = (
            select(SalesInvoice)
            .where(SalesInvoice.company_id == ctx.company_id, SalesInvoice.deleted_at.is_(None))
            .options(selectinload(SalesInvoice.lines))
        )
        return await paginate(self._session, stmt, SalesInvoice, params)


async def _reload_invoice(session: AsyncSession, invoice_id, *, company_id: str | None = None) -> SalesInvoice:
    stmt = (
        select(SalesInvoice).where(SalesInvoice.id == invoice_id).options(selectinload(SalesInvoice.lines))
    )
    if company_id is not None:
        stmt = stmt.where(SalesInvoice.company_id == company_id)
    invoice = (await session.execute(stmt)).scalar_one_or_none()
    if invoice is None:
        raise ValueError("الفاتورة غير موجودة أو لا تعود لشركتك")
    return invoice


# ── Credit Notes ─────────────────────────────────────────────────────────


class CreateAndPostCreditNoteUseCase:
    """إشعار دائن مبسّط: يُنشأ ويُرحَّل محاسبياً في خطوة واحدة (بعكس الفاتورة).
    لا يعيد الكمية للمخزون تلقائياً في هذا الإصدار — IInventoryPort الحالي لا
    يوفّر عملية "إعادة استلام" مقابلة (موثَّق كقيد معروف؛ يحتاج توسيع الـ Port
    مستقبلاً، مثال: `receive_stock`)."""

    def __init__(
        self, session: AsyncSession, accounting_port: IAccountingPort, numbering_service: INumberingService
    ) -> None:
        self._session = session
        self._accounting_port = accounting_port
        self._numbering_service = numbering_service

    async def execute(self, ctx: TenantContext, request: CreditNoteCreateRequest) -> CreditNote:
        invoice = await _reload_invoice(self._session, request.invoice_id, company_id=ctx.company_id)
        if invoice.status != SalesInvoiceStatus.POSTED.value:
            raise InvoiceNotDraftError("لا يمكن إصدار إشعار دائن إلا لفاتورة مرحّلة (posted)")

        totals = calculate_document_totals(_to_line_inputs(request.lines))
        if totals.total_amount > invoice.total_amount:
            raise ValueError("قيمة إشعار الدائن لا يمكن أن تتجاوز قيمة الفاتورة الأصلية")

        number = await self._numbering_service.next_number(
            company_id=ctx.company_id, document_type="credit_note"
        )
        credit_note = CreditNote(
            company_id=ctx.company_id,
            invoice_id=invoice.id,
            partner_id=invoice.partner_id,
            credit_note_number=number,
            status="draft",
            currency=invoice.currency,
            total_amount=totals.total_amount,
        )
        self._session.add(credit_note)
        await self._session.flush()

        for line in request.lines:
            line_total = calculate_line_total(
                LineInput(quantity=line.quantity, unit_price=line.unit_price, tax_amount=line.tax_amount)
            )
            self._session.add(
                CreditNoteLine(
                    credit_note_id=credit_note.id,
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    line_total=line_total.line_total,
                )
            )

        journal_ref = await self._accounting_port.record_document_posting(
            DocumentPostingRequest(
                company_id=ctx.company_id,
                entry_date=date_type.today().isoformat(),
                source_document_type="credit_note",
                source_document_id=str(credit_note.id),
                currency=invoice.currency,
                lines=[
                    DocumentPostingLine(
                        account_code="4200", debit=totals.subtotal, credit=Decimal(0),
                        description=f"مردودات مبيعات — إشعار دائن {number}",
                    ),
                    DocumentPostingLine(
                        account_code="1110", debit=Decimal(0), credit=totals.total_amount,
                        description=f"إشعار دائن {number}",
                    ),
                ]
                + (
                    [
                        DocumentPostingLine(
                            account_code="2200", debit=totals.tax_amount, credit=Decimal(0),
                            description=f"تخفيض ضريبة مخرجات — إشعار دائن {number}",
                        )
                    ]
                    if totals.tax_amount > 0
                    else []
                ),
                memo=f"إشعار دائن {number} لفاتورة {invoice.invoice_number}",
            )
        )

        credit_note.status = "posted"
        credit_note.journal_entry_id = journal_ref.journal_entry_id
        await self._session.commit()
        await self._session.refresh(credit_note)
        return credit_note
