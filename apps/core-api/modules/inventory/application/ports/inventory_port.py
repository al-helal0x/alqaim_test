"""IInventoryPort — Port مُعلَن للاستهلاك من sales/pos/purchasing (contracts.md §1).

التوقيع الأساسي (reserve_stock/deduct_stock) موصوف في contracts.md كـ "توقيع
مبدئي" (بخلاف IAccountingPort المثبَّت صراحة) — أُضيف هنا `release_reservation`
كامتداد غير مكسِر: ضروري عملياً لأي دورة حياة حقيقية (إلغاء عرض سعر/طلب محجوز
يجب أن يُعيد الكمية للمتاح)، ولا يغيّر توقيع الطريقتين الأصليتين. يبقى قابلاً
للنقاش في "يوم العقود" كأي امتداد على توقيع غير مجمَّد.

قاعدة صارمة: الوحدات المستهلكة تستدعي هذا الـ Port فقط، ولا تستورد
`modules.inventory.infrastructure` مباشرة أبداً (القسم 11.2).
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class ReservationRef:
    """يطابق ReservationRef في contracts.md §3: { reservation_id, expires_at }."""

    reservation_id: str
    expires_at: str  # ISO datetime


class InsufficientStockError(ValueError):
    """لا كمية كافية متاحة (رصيد ناقص الحجوزات النشطة) لتلبية الطلب."""


class ReservationNotFoundError(ValueError):
    pass


class IInventoryPort(Protocol):
    async def reserve_stock(
        self, *, company_id: str, product_id: str, warehouse_id: str, quantity: Decimal
    ) -> ReservationRef: ...

    async def deduct_stock(
        self,
        *,
        company_id: str,
        product_id: str,
        warehouse_id: str,
        quantity: Decimal,
        reservation_id: str | None = None,
    ) -> None: ...

    async def release_reservation(self, *, company_id: str, reservation_id: str) -> None: ...

    async def increase_stock(
        self,
        *,
        company_id: str,
        product_id: str,
        warehouse_id: str,
        quantity: Decimal,
        reference: str,
    ) -> None:
        """يزيد الرصيد المتاح (بدون Reservation) — تُستخدَم عند استلام بضاعة فعلية
        (أمر شراء مُستلَم، تسوية جرد بالزيادة، إلخ). أُضيفت هذه الطريقة استجابةً
        لاستخدام فعلي من Purchasing (`ReceivePurchaseOrderUseCase`) كان يعمل ضد
        `fake_ports.FakeInventoryPort` فقط دون مقابل حقيقي هنا — كان سيتسبب
        بـ AttributeError فور استبدال الـ Fake بالتنفيذ الحقيقي. التوقيع هنا
        يطابق ما استقر عليه استهلاك Purchasing فعلياً، مع إضافة `company_id`
        (غائب في نسخة Purchasing الأصلية) لضمان عزل المستأجرين مثل بقية طرق
        هذا الـ Port."""
        ...
