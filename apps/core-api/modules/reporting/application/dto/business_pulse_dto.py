"""DTOs — لوحة "نبض الشركة اليومي" (TASK-BI-01).

نطاق هذه الحزمة عمداً محدود بالمؤشرات الخمسة المتفَق عليها في بطاقة
المهمة، بلا أي حقل إضافي "قد يفيد لاحقاً" (تفادي Scope Creep من داخل
المهمة نفسها — نفس المبدأ الموثَّق في TASK-BI-01.md).

ملاحظة صريحة: `product_id` في `TopProductRow` بلا اسم منتج مرافق، لأن
تحويله لاسم يتطلب الاعتماد على وحدة `catalog` (خارج نطاق الوحدات المرجعية
المسموح قراءتها في هذه المهمة). هذا قيد مقصود موثَّق، لا سهو — يُفتح كمهمة
تحسين لاحقة منفصلة عند الحاجة.
"""
from decimal import Decimal

from pydantic import BaseModel


class SalesTrendPoint(BaseModel):
    """نقطة واحدة في خط زمن المبيعات — يوم واحد، إجمالي الفواتير المرحَّلة فيه فقط."""

    day: str  # YYYY-MM-DD
    total_amount: Decimal


class TopProductRow(BaseModel):
    """أحد أعلى 5 منتجات مبيعاً بالقيمة، ضمن نطاق الفترة المطلوبة."""

    product_id: str
    total_quantity: Decimal
    total_amount: Decimal


class CashAccountBalance(BaseModel):
    """رصيد حساب بنكي/صندوق واحد = الرصيد الافتتاحي + مقبوضات مؤكَّدة - مدفوعات مؤكَّدة."""

    bank_account_id: str
    name: str
    currency_code: str
    balance: Decimal


class LowStockItem(BaseModel):
    """أدنى 5 عناصر مخزوناً (بالكمية) ضمن كل المستودعات.

    ملاحظة صريحة: هذا "الأقل كمية"، وليس "تحت حد إعادة الطلب" — حقل حد
    إعادة الطلب غير متاح لهذه المهمة (يعيش في وحدة catalog، خارج النطاق
    المرجعي المسموح به هنا). فرق مقصود عن الطموح الأصلي في الدراسة، مُوثَّق
    لا مُخفى.
    """

    product_id: str
    warehouse_id: str
    quantity: Decimal


class ReceivablesAging(BaseModel):
    """أعمار الذمم المدينة — أساسها تاريخ إنشاء الفاتورة المرحَّلة (created_at)،
    لا due_date (الحقل غير موجود في نموذج SalesInvoice الحالي)."""

    bucket_0_30: Decimal
    bucket_31_60: Decimal
    bucket_61_plus: Decimal


class BusinessPulseResponse(BaseModel):
    company_id: str
    period_days: int
    generated_at: str  # ISO-8601

    sales_trend: list[SalesTrendPoint]
    sales_total_current_period: Decimal
    sales_total_previous_period: Decimal

    top_products: list[TopProductRow]

    cash_accounts: list[CashAccountBalance]
    cash_total: Decimal

    low_stock_items: list[LowStockItem]

    receivables_aging: ReceivablesAging
