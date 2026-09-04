"""قاعدة نطاق صِرفة (Domain Rule): توازن القيد. لا تعتمد على SQLAlchemy أو
FastAPI عمداً (القسم 6.4 — Domain لا يعتمد على Infrastructure/Presentation)
حتى تبقى قابلة للاختبار بمعزل تام وقابلة لإعادة الاستخدام من أي طبقة أعلى.
"""
from dataclasses import dataclass
from decimal import Decimal


class UnbalancedJournalEntryError(ValueError):
    """يُرفع عندما لا يتساوى مجموع المدين مع مجموع الدائن لقيد ما."""

    def __init__(self, total_debit: Decimal, total_credit: Decimal) -> None:
        self.total_debit = total_debit
        self.total_credit = total_credit
        super().__init__(
            f"القيد غير متوازن: مجموع المدين={total_debit} \u2260 مجموع الدائن={total_credit}"
        )


class EmptyJournalEntryError(ValueError):
    """قيد بلا أسطر إطلاقاً — غير مسموح، لا معنى له محاسبياً."""


@dataclass(frozen=True)
class JournalLineAmounts:
    debit: Decimal
    credit: Decimal


def assert_balanced(lines: list[JournalLineAmounts]) -> None:
    """يفحص أن مجموع المدين = مجموع الدائن عبر كل أسطر القيد.

    يُستدعى إلزامياً من RecordDocumentPostingUseCase قبل أي كتابة لقاعدة
    البيانات (القسم 13 — معيار التسليم: "أي حدث تشغيلي يولّد قيداً متوازناً
    صحيحاً تلقائياً").
    """
    if not lines:
        raise EmptyJournalEntryError("لا يمكن ترحيل قيد بلا أسطر")

    total_debit = sum((line.debit for line in lines), Decimal(0))
    total_credit = sum((line.credit for line in lines), Decimal(0))

    if total_debit != total_credit:
        raise UnbalancedJournalEntryError(total_debit, total_credit)

    if total_debit == Decimal(0):
        raise ValueError("لا يمكن ترحيل قيد بمبلغ صفري بالكامل")


def assert_line_amount_valid(debit: Decimal, credit: Decimal) -> None:
    """كل سطر يجب أن يحمل مدين أو دائن (وليس كلاهما، وليس لا شيء)."""
    if debit < 0 or credit < 0:
        raise ValueError("لا يُسمح بمبالغ سالبة في أسطر القيد")
    if debit > 0 and credit > 0:
        raise ValueError("سطر القيد لا يمكن أن يحمل مدين ودائن معاً")
    if debit == 0 and credit == 0:
        raise ValueError("سطر القيد يجب أن يحمل مبلغاً (مدين أو دائن)")
