"""Money / Currency Value Objects.

قاعدة صارمة: ممنوع استخدام float لأي مبلغ مالي في كامل المشروع (القسم 1.3 / 17)
— يُفحص عبر Linter مخصص في CI. استخدم Decimal دائماً.
"""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str  # ISO 4217, e.g. "IQD", "USD"

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError("لا يمكن جمع مبالغ بعملات مختلفة مباشرة دون تحويل صريح")
        return Money(self.amount + other.amount, self.currency)

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError("Money.amount يجب أن يكون Decimal — Float ممنوع")
