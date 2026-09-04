"""قواعد نطاق sales الصرفة — بدون أي اعتماد على DB أو Framework."""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class QuotationStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class SalesOrderStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    INVOICED = "invoiced"
    CANCELLED = "cancelled"


class SalesInvoiceStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"
    PAID = "paid"
    CANCELLED = "cancelled"


# ── قاعدة موافقة المدير على فواتير البيع الكبيرة (مهمة #12) ────────────────
# قاعدة نطاق صرفة — بدون أي معرفة بمحرك workflow أو Event Bus، فقط "هل هذا
# المبلغ يحتاج موافقة؟". تُستهلَك من application/use_cases (الذي يقرر ماذا
# يفعل بالنتيجة عبر IWorkflowPort) ومن infrastructure/event_handlers على حد
# سواء، لتفادي ازدواج تعريف الحد أو أسماء الحالات في أكثر من مكان.
SALES_INVOICE_MANAGER_APPROVAL_THRESHOLD = Decimal(10000)

# entity_type/اسم التعريف تُستخدَم كمفتاح موحَّد عند التعامل مع workflow
# (workflow_definitions.name / workflow_instances.entity_type) — أي طرف آخر
# يستعلم عن حالة نفس الفاتورة (تقارير، تدقيق مستقبلاً) يستخدم نفس القيمتين.
SALES_INVOICE_APPROVAL_ENTITY_TYPE = "sales_invoice"
SALES_INVOICE_APPROVAL_DEFINITION_NAME = "sales_invoice_manager_approval"

# نسخة تبدأ مباشرة بحالة "pending_approval" (بلا حالة draft منفصلة لسير
# الموافقة نفسه — فاتورة البيع نفسها هي التي بحالة draft بالفعل في وحدة
# sales؛ سير الموافقة هنا معني فقط بقرار المدير: موافقة أو رفض).
SALES_INVOICE_APPROVAL_STATES = ["pending_approval", "approved", "rejected"]
SALES_INVOICE_APPROVAL_TRANSITIONS = [
    {"name": "approve", "from": "pending_approval", "to": "approved"},
    {"name": "reject", "from": "pending_approval", "to": "rejected"},
]


def requires_manager_approval(total_amount: Decimal) -> bool:
    """>10,000 بالضبط لا تحتاج موافقة (الحد أدنى للتفعيل هو تجاوزه صراحة،
    راجع عمود "المخرج" لمهمة #12: "فاتورة بيع > 10,000")."""
    return total_amount > SALES_INVOICE_MANAGER_APPROVAL_THRESHOLD


class CreditNoteStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"


@dataclass(frozen=True)
class LineInput:
    quantity: Decimal
    unit_price: Decimal
    tax_amount: Decimal = Decimal(0)


@dataclass(frozen=True)
class LineTotals:
    line_total: Decimal


@dataclass(frozen=True)
class DocumentTotals:
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal


def calculate_line_total(line: LineInput) -> LineTotals:
    if line.quantity <= 0:
        raise ValueError("الكمية يجب أن تكون أكبر من صفر")
    if line.unit_price < 0:
        raise ValueError("سعر الوحدة لا يمكن أن يكون سالباً")
    if line.tax_amount < 0:
        raise ValueError("مبلغ الضريبة لا يمكن أن يكون سالباً")

    base = (line.quantity * line.unit_price).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return LineTotals(line_total=base + line.tax_amount)


def calculate_document_totals(lines: list[LineInput]) -> DocumentTotals:
    if not lines:
        raise ValueError("المستند يجب أن يحتوي على سطر واحد على الأقل")

    subtotal = Decimal(0)
    tax_amount = Decimal(0)
    for line in lines:
        calculate_line_total(line)  # يتحقق من صحة كل سطر
        subtotal += (line.quantity * line.unit_price).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        tax_amount += line.tax_amount

    return DocumentTotals(subtotal=subtotal, tax_amount=tax_amount, total_amount=subtotal + tax_amount)


_QUOTATION_TRANSITIONS: dict[QuotationStatus, set[QuotationStatus]] = {
    QuotationStatus.DRAFT: {QuotationStatus.SENT, QuotationStatus.REJECTED},
    QuotationStatus.SENT: {QuotationStatus.ACCEPTED, QuotationStatus.REJECTED, QuotationStatus.EXPIRED},
    QuotationStatus.ACCEPTED: set(),
    QuotationStatus.REJECTED: set(),
    QuotationStatus.EXPIRED: set(),
}


def assert_valid_quotation_transition(current: QuotationStatus, target: QuotationStatus) -> None:
    if target not in _QUOTATION_TRANSITIONS.get(current, set()):
        raise ValueError(f"لا يمكن الانتقال من حالة عرض السعر {current.value} إلى {target.value}")


_ORDER_TRANSITIONS: dict[SalesOrderStatus, set[SalesOrderStatus]] = {
    SalesOrderStatus.DRAFT: {SalesOrderStatus.CONFIRMED, SalesOrderStatus.CANCELLED},
    SalesOrderStatus.CONFIRMED: {SalesOrderStatus.INVOICED, SalesOrderStatus.CANCELLED},
    SalesOrderStatus.INVOICED: set(),
    SalesOrderStatus.CANCELLED: set(),
}


def assert_valid_order_transition(current: SalesOrderStatus, target: SalesOrderStatus) -> None:
    if target not in _ORDER_TRANSITIONS.get(current, set()):
        raise ValueError(f"لا يمكن الانتقال من حالة أمر البيع {current.value} إلى {target.value}")
