"""تنفيذات Fake/Mock كانت مؤقتة لـ Ports اعتمدت عليها Purchasing قبل اكتمال
الوحدات الحقيقية — تماماً وفق نمط "يوم العقود" (§13.1.2): "كل عضو يؤكد أنه
يمتلك Mock/Fake كافٍ للبدء بالتطوير دون انتظار أحد".

**تحديث الحالة (بعد إغلاق فجوتي التكامل الحقيقيتين):**
- `IInventoryPort.increase_stock` أُضيف فعلياً في التنفيذ الحقيقي
  (`modules/inventory/.../inventory_repository.py:SqlInventoryPort`) —
  المسار الفعلي (`purchase_orders_router.py`) يستخدمه مباشرة الآن.
  `FakeInventoryPort` هنا يبقى فقط لاختبارات لا تحتاج رصيد مخزون حقيقي.
- `IAccountingPort` **لم يعد Fake إطلاقاً** — `purchase_invoices_router.py`
  يستخدم `SqlAccountingPort` الحقيقي (نفس نمط Sales تماماً). حُذفت
  `FakeAccountingPort` من هذا الملف لأن استخدامها الوحيد كان يخفي عن
  الفريق أن فواتير الشراء لم تكن تُنشئ قيداً محاسبياً حقيقياً — إبقاؤها هنا
  بلا استخدام كان سيصبح مصدر التباس لاحقاً (قد يستوردها عضو جديد بالخطأ).

`FakePartnerLookup`/`FakeProductLookup` أدناه غير مستهلَكتَين حالياً من أي
Use Case فعلي في Purchasing (الوحدة لا تتحقق من partner/product عبر Lookup
منفصل حالياً، بل تثق بالـ id الممرَّر مباشرة) — تبقيان موثَّقتين هنا فقط
كمرجع تاريخي لما كان مخطَّطاً، وقابلتان للحذف الآمن إن احتاج الفريق ذلك.
"""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PartnerDTO:
    id: str
    name: str
    partner_type: str  # customer | supplier | both
    is_active: bool = True


@dataclass
class ProductDTO:
    id: str
    sku: str
    name: str
    is_active: bool = True


@dataclass
class JournalEntryRef:
    journal_entry_id: str
    entry_number: str


class FakePartnerLookup:
    """IPartnerLookup مؤقت — العضو 2 لم يُسلِّم بعد وحدة partners الفعلية في
    هذه الحزمة. أي `partner_id` يُمرَّر يُقبل كموجود وفعّال (لا تحقق حقيقي)."""

    async def get(self, partner_id: str) -> PartnerDTO:
        return PartnerDTO(id=partner_id, name=f"Supplier({partner_id[:8]})", partner_type="supplier")


class FakeProductLookup:
    """IProductLookup مؤقت — نفس السبب أعلاه لوحدة catalog."""

    async def get(self, product_id: str) -> ProductDTO:
        return ProductDTO(id=product_id, sku=f"SKU-{product_id[:6]}", name=f"Product({product_id[:8]})")


class FakeInventoryPort:
    """IInventoryPort مؤقت — **متبقٍّ هنا فقط لاختبارات لا تحتاج رصيد مخزون
    حقيقي** (مثل اختبار تدفّق الدفع الذي لا يتحقق من stock_balances). العضو 3
    سلّم `SqlInventoryPort` الحقيقي فعلياً (انظر
    `modules/inventory/infrastructure/repositories/inventory_repository.py`)
    وهو المستخدَم الآن في المسار الفعلي (`purchase_orders_router.py`) —
    زيادة المخزون هنا تبقى وهمية عمداً، لا تُسجَّل في أي جدول حركات."""

    async def increase_stock(
        self,
        *,
        company_id: str,
        product_id: str,
        warehouse_id: str,
        quantity: Decimal,
        reference: str,
    ) -> None:
        return None
