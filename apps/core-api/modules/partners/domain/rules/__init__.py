"""قواعد نطاق partners الصرفة — بدون أي اعتماد على DB أو Framework."""
from enum import StrEnum


class PartnerType(StrEnum):
    """يطابق partner_type في contracts.md وblueprint القسم 8 (سطر 700-701)."""

    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    BOTH = "both"


def validate_credit_limit(credit_limit) -> None:
    """حد الائتمان لا يمكن أن يكون سالباً — قاعدة نطاق صرفة."""
    if credit_limit is not None and credit_limit < 0:
        raise ValueError("حد الائتمان لا يمكن أن يكون سالباً")


# PKG-B2: الاسم المعروض لِـ"العميل النقدي" — نص عرض بحت (name عادي في DB،
# راجع PKG-B1)، وليس مُعرِّفاً نظامياً. مركزي هنا (domain) بدل تكراره في
# use case أو router، تماشياً مع كون هذا سلوكاً/قاعدة عمل وليس تفصيل تنفيذ.
WALK_IN_PARTNER_NAME = "عميل نقدي"
