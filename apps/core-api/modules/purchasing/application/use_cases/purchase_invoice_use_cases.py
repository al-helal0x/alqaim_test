"""Use Cases لفاتورة الشراء — القسم 9. الترحيل (Post) يستدعي IAccountingPort
الحقيقي (لم يعد Fake — انظر PostPurchaseInvoiceUseCase أدناه). التكامل مبني
تماماً على نفس نمط Sales المُثبَت فعلياً (sales/application/use_cases/
sales_use_cases.py:PostSalesInvoiceUseCase)، مع القيد المحاسبي المعاكس
المناسب للمشتريات بدل المبيعات:

    مدين  1120 المخزون          (subtotal - discount)
    مدين  1130 ضريبة مدخلات مستحقة (tax_amount، فقط إن > 0)
    دائن  2100 الذمم الدائنة (الموردون)  (total_amount)

أكواد الحسابات هذه من الشجرة الافتراضية المزروعة عبر
accounting/application/use_cases/chart_of_accounts_seed_use_case.py — أي
شركة لم تُشغِّل SeedDefaultChartOfAccountsUseCase بعد سيفشل الترحيل هنا
بـ AccountNotFoundError (سلوك مقصود: لا ترحيل صامت على حساب غير موجود)."""
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.application.ports.accounting_port import (
    DocumentPostingLine,
    DocumentPostingRequest,
    IAccountingPort,
)
from modules.purchasing.application.dto.purchasing_dto import (
    PurchaseInvoiceCreateRequest,
    PurchaseOrderLineRequest,
)
from modules.purchasing.infrastructure.models.purchasing_models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
)
from modules.purchasing.infrastructure.repositories.purchasing_repository import (
    PurchaseInvoiceRepository,
    PurchaseOrderRepository,
)
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext

DOCUMENT_TYPE_PURCHASE_INVOICE = "purchase_invoice"


def _build_lines_and_totals(
    lines_req: list[PurchaseOrderLineRequest], tax_amount: Decimal, discount_amount: Decimal
) -> tuple[list[PurchaseInvoiceLine], Decimal, Decimal]:
    lines: list[PurchaseInvoiceLine] = []
    subtotal = Decimal(0)
    for line_req in lines_req:
        line_total = (line_req.quantity * line_req.unit_price).quantize(Decimal("0.0001"))
        subtotal += line_total
        lines.append(
            PurchaseInvoiceLine(
                product_id=line_req.product_id,
                description=line_req.description,
                quantity=line_req.quantity,
                unit_price=line_req.unit_price,
                line_total=line_total,
            )
        )
    total = subtotal + tax_amount - discount_amount
    return lines, subtotal, total


class CreatePurchaseInvoiceUseCase:
    """فاتورة شراء مستقلة (بلا أمر شراء سابق) — القسم 4 (شراء مباشر شائع
    في المشتريات الصغيرة/اليومية)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, request: PurchaseInvoiceCreateRequest
    ) -> PurchaseInvoice:
        numbering = SqlNumberingService(self._session)
        invoice_number = await numbering.next_number(
            company_id=ctx.company_id, document_type=DOCUMENT_TYPE_PURCHASE_INVOICE
        )

        lines, subtotal, total = _build_lines_and_totals(
            request.lines, request.tax_amount, request.discount_amount
        )

        invoice = PurchaseInvoice(
            company_id=ctx.company_id,
            branch_id=request.branch_id,
            supplier_id=request.supplier_id,
            purchase_order_id=None,
            invoice_number=invoice_number,
            status="draft",
            currency_code=request.currency_code,
            subtotal=subtotal,
            tax_amount=request.tax_amount,
            discount_amount=request.discount_amount,
            total_amount=total,
            lines=lines,
        )
        self._session.add(invoice)
        await self._session.commit()
        await self._session.refresh(invoice, attribute_names=["lines"])
        return invoice


class CreatePurchaseInvoiceFromOrderUseCase:
    """ينسخ بنود أمر شراء مُستلَم (received) إلى فاتورة شراء جديدة — يمنع
    الفوترة على أمر لم يُستلَم بعد (تسلسل منطقي إلزامي: draft→confirmed→received→invoiced)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, purchase_order_id: str) -> PurchaseInvoice:
        order = await PurchaseOrderRepository(self._session).get_by_id(
            purchase_order_id, company_id=ctx.company_id
        )
        if order is None:
            raise ValueError("أمر الشراء غير موجود أو لا يعود لشركتك")
        if order.status != "received":
            raise ValueError("لا يمكن إصدار فاتورة إلا لأمر شراء بحالة 'received'")

        numbering = SqlNumberingService(self._session)
        invoice_number = await numbering.next_number(
            company_id=ctx.company_id, document_type=DOCUMENT_TYPE_PURCHASE_INVOICE
        )

        invoice_lines = [
            PurchaseInvoiceLine(
                product_id=line.product_id, description=line.description,
                quantity=line.quantity, unit_price=line.unit_price, line_total=line.line_total,
            )
            for line in order.lines
        ]

        invoice = PurchaseInvoice(
            company_id=ctx.company_id,
            branch_id=order.branch_id,
            supplier_id=order.supplier_id,
            purchase_order_id=order.id,
            invoice_number=invoice_number,
            status="draft",
            currency_code=order.currency_code,
            subtotal=order.subtotal,
            tax_amount=order.tax_amount,
            discount_amount=order.discount_amount,
            total_amount=order.total_amount,
            lines=invoice_lines,
        )
        self._session.add(invoice)
        await self._session.commit()
        await self._session.refresh(invoice, attribute_names=["lines"])
        return invoice


class PostPurchaseInvoiceUseCase:
    """draft → posted. يستدعي IAccountingPort.record_document_posting الحقيقي
    (كان Fake سابقاً — انظر توثيق أعلى الملف) — **قاعدة صارمة (القسم 17):
    لا ترحيل بدون قيد محاسبي حقيقي متوازن مقابل**. عند فشل الترحيل المحاسبي
    (حساب غير موجود، فترة مالية مقفلة/غير معرَّفة...) يُرفَع الاستثناء قبل
    أي `commit`، فتبقى الفاتورة `draft` ولا يُسجَّل أي `journal_entry_ref`
    جزئي — نفس ضمان Atomicity المعتمد في Sales."""

    def __init__(self, session: AsyncSession, accounting_port: IAccountingPort) -> None:
        self._session = session
        self._accounting_port = accounting_port

    async def execute(self, ctx: TenantContext, invoice_id: str) -> PurchaseInvoice:
        invoice = await PurchaseInvoiceRepository(self._session).get_by_id(
            invoice_id, company_id=ctx.company_id
        )
        if invoice is None:
            raise ValueError("فاتورة الشراء غير موجودة أو لا تعود لشركتك")
        if invoice.status != "draft":
            raise ValueError(f"لا يمكن ترحيل فاتورة بحالة '{invoice.status}'")

        goods_value = invoice.subtotal - invoice.discount_amount
        posting_lines = [
            DocumentPostingLine(
                account_code="1120", debit=goods_value, credit=Decimal(0),
                description=f"مخزون وارد بفاتورة شراء {invoice.invoice_number}",
            ),
            DocumentPostingLine(
                account_code="2100", debit=Decimal(0), credit=invoice.total_amount,
                description=f"ذمم دائنة لفاتورة شراء {invoice.invoice_number}",
            ),
        ]
        if invoice.tax_amount > 0:
            posting_lines.insert(
                1,
                DocumentPostingLine(
                    account_code="1130", debit=invoice.tax_amount, credit=Decimal(0),
                    description=f"ضريبة مدخلات فاتورة شراء {invoice.invoice_number}",
                ),
            )

        journal_ref = await self._accounting_port.record_document_posting(
            DocumentPostingRequest(
                company_id=ctx.company_id,
                entry_date=datetime.now(UTC).date().isoformat(),
                source_document_type=DOCUMENT_TYPE_PURCHASE_INVOICE,
                source_document_id=str(invoice.id),
                currency=invoice.currency_code,
                lines=posting_lines,
                memo=f"ترحيل فاتورة شراء {invoice.invoice_number}",
            )
        )

        invoice.status = "posted"
        invoice.journal_entry_ref = journal_ref.entry_number
        invoice.version += 1
        await self._session.commit()
        await self._session.refresh(invoice, attribute_names=["lines"])
        return invoice


class ReceivePurchaseInvoiceInventoryUseCase:
    """`TASK-AI-02b` — يزيد رصيد المخزون لبنود فاتورة شراء **بلا أمر شراء
    مرتبط** (فواتير AI أو فواتير شراء مباشرة يدوية) بعد ترحيلها محاسبياً.

    القرار المعتمَد (`قرار_مطلوب_TASK-AI-02b.md`، التوصية غير المُلزِمة
    المعتمَدة صراحةً من صاحب القرار): خطوة "استلام" صريحة منفصلة، تطابق
    مفهوم `ReceivePurchaseOrderUseCase` القائم فعلياً حرفياً — `warehouse_id`
    معامل صريح من المُستدعي في كل مرة (لا استنتاج، لا بنية جديدة)، لأن
    `extracted_payload` من ai-platform لا يحتوي حقل مستودع إطلاقاً.

    شرطان إلزاميان يمنعان ازدواج/تضارب حركة المخزون مع المسار العادي:
    1. `purchase_order_id is None` — فاتورة مرتبطة بأمر شراء تُستلَم عبر
       `ReceivePurchaseOrderUseCase` نفسه (عند استلام الأمر)؛ استدعاء هذا
       هذا Use Case عليها يعني مضاعفة نفس الكمية فعلياً في المخزون.
    2. `status == "posted"` — نفس منطق رفض الخيار (ب) في وثيقة القرار:
       زيادة المخزون قبل الترحيل المحاسبي تعني مخزوناً "موجوداً" لفاتورة
       غير مُلزِمة محاسبياً بعد (قد تُلغى قبل الترحيل).

    Idempotency: `inventory_received_at` غير NULL يمنع استدعاءً ثانياً على
    نفس الفاتورة (خطأ صريح، بنفس نمط `status != 'confirmed'` في
    `ReceivePurchaseOrderUseCase` — لا تكرار صامت لزيادة المخزون)."""

    def __init__(self, session: AsyncSession, inventory_port) -> None:
        self._session = session
        self._inventory_port = inventory_port

    async def execute(
        self, ctx: TenantContext, invoice_id: str, *, warehouse_id: str
    ) -> PurchaseInvoice:
        invoice = await PurchaseInvoiceRepository(self._session).get_by_id(
            invoice_id, company_id=ctx.company_id
        )
        if invoice is None:
            raise ValueError("فاتورة الشراء غير موجودة أو لا تعود لشركتك")
        if invoice.purchase_order_id is not None:
            raise ValueError(
                "هذه الفاتورة مرتبطة بأمر شراء — استلام المخزون يتم عبر "
                "استلام أمر الشراء نفسه، لا عبر هذا المسار"
            )
        if invoice.status != "posted":
            raise ValueError(
                f"لا يمكن استلام بضاعة فاتورة بحالة '{invoice.status}' — يجب ترحيلها محاسبياً أولاً"
            )
        if invoice.inventory_received_at is not None:
            raise ValueError("تم استلام بضاعة هذه الفاتورة مسبقاً")

        for line in invoice.lines:
            await self._inventory_port.increase_stock(
                company_id=ctx.company_id,
                product_id=str(line.product_id),
                warehouse_id=warehouse_id,
                quantity=line.quantity,
                reference=f"purchase_invoice:{invoice.id}",
            )

        invoice.inventory_received_at = datetime.now(UTC)
        invoice.version += 1
        await self._session.commit()
        await self._session.refresh(invoice, attribute_names=["lines"])
        return invoice
