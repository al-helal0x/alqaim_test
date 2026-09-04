"""قواعد نطاق catalog الصرفة — بدون أي اعتماد على DB أو Framework."""
from enum import StrEnum


class ProductType(StrEnum):
    """يطابق type[product|service] في blueprint القسم 8 (سطر 691)."""

    PRODUCT = "product"
    SERVICE = "service"


def validate_price(price) -> None:
    """قاعدة صارمة: لا أسعار سالبة (يتّسق مع منع float للمبالغ — shared_kernel.money)."""
    if price is not None and price < 0:
        raise ValueError("السعر لا يمكن أن يكون سالباً")
