"""قواعد نطاق inventory الصرفة — بدون أي اعتماد على DB أو Framework."""
from decimal import Decimal
from enum import StrEnum


class MovementType(StrEnum):
    """يطابق movement_type[in|out|transfer|adjustment] — blueprint القسم 8، سطر 693."""

    IN = "in"
    OUT = "out"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"


def validate_quantity_positive(quantity: Decimal) -> None:
    """كمية أي حركة مخزون (in/out/transfer) يجب أن تكون موجبة تماماً —
    الإشارة (in/out) تُحدَّد عبر movement_type وليس عبر سالب/موجب في الكمية
    (blueprint القسم 8.4: Check Constraint على quantity لنوع in تحديداً،
    ونعمم نفس المبدأ على كل الحركات لتفادي غموض `-5` = هل هي خطأ إدخال أم OUT؟).
    """
    if quantity is None or quantity <= 0:
        raise ValueError("الكمية يجب أن تكون أكبر من صفر")
