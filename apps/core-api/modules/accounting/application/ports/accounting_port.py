"""IAccountingPort — Port المُعلَن في contracts.md، القسم §1. **أهم واجهة في
النظام**: تستهلكها sales/purchasing/payments/inventory عبر Mock بداية ثم
التنفيذ الفعلي هنا (modules/accounting/application/use_cases/journal_use_cases.py
:RecordDocumentPostingUseCase).

توقيع نهائي (Frozen — لا يتغيّر إلا بموافقة الفريق الثمانية، القسم 13.1):

    record_document_posting(document_dto: DocumentPostingRequest) -> JournalEntryRef

الوحدات المستهلكة تستورد فقط من هذا الملف (application/ports) — ممنوع
استيراد أي شيء من accounting/infrastructure مباشرة (القسم 11.2).
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class DocumentPostingLine:
    """سطر واحد ضمن مستند يراد ترحيله (فاتورة بيع، فاتورة شراء، دفعة...).

    account_code: كود الحساب في شجرة حسابات الشركة (مثال: "1100" لحساب
    الذمم المدينة). كل Module مستهلك (Sales/Purchasing/...) يجب أن يعرف
    أكواد الحسابات التي يرحّل عليها عادة عبر إعدادات الشركة، وليس Hardcoded.
    """

    account_code: str
    debit: Decimal = Decimal(0)
    credit: Decimal = Decimal(0)
    description: str | None = None
    cost_center_code: str | None = None


@dataclass(frozen=True)
class DocumentPostingRequest:
    """DTO الموحَّد الذي يُمرَّر من أي Module تشغيلي إلى `record_document_posting`."""

    company_id: str
    entry_date: str  # ISO date "YYYY-MM-DD"
    source_document_type: str  # e.g. "sales_invoice", "purchase_invoice", "payment"
    source_document_id: str
    currency: str
    lines: list[DocumentPostingLine] = field(default_factory=list)
    memo: str | None = None


@dataclass(frozen=True)
class JournalEntryRef:
    """قيمة الإرجاع القياسية — يحتفظ بها المستدعي كمرجع للقيد الناتج."""

    journal_entry_id: str
    entry_number: str


class IAccountingPort(Protocol):
    async def record_document_posting(
        self, document_dto: DocumentPostingRequest
    ) -> JournalEntryRef: ...
