# Module: purchasing

**المسؤول:** العضو 5 — Purchasing & Payments

## الحالة الفعلية

✅ **مُنجَز فعلياً ومُختبَر** — أمر شراء (draft→confirmed→received) + فاتورة
شراء (مستقلة أو من أمر شراء) + ترحيل محاسبي، بكل الطبقات + Migrations +
5 اختبارات integration ناجحة (`tests/integration/test_purchasing_payments_flow.py`).

## حالة الاعتماديات (محدَّثة — كانت موثَّقة كـ Fake، أُغلِقت الفجوتان الحقيقيتان)

عند بناء هذا الموديول اعتُمِد على 3 Ports عبر تنفيذات **Fake صريحة**
(`infrastructure/external/fake_ports.py`) وفق نمط "يوم العقود" (§13.1.2).
بعد توفر التنفيذ الحقيقي من أصحابها، أُغلقت الفجوتان الفعليتان التاليتان:

- **`IInventoryPort`** (العضو 3): مُستبدَل بالكامل — `SqlInventoryPort` الحقيقي
  محقون في `purchase_orders_router.py`، ويشمل الآن `increase_stock` (امتداد
  طلبه هذا الموديول، أكّده العضو 3 في تنفيذه الفعلي).
- **`IAccountingPort`** (العضو 6): **كان الأخطر** — `PostPurchaseInvoiceUseCase`
  كان يستدعي `FakeAccountingPort` التي تُرجع مرجع قيد وهمياً بثبات، أي أن
  فواتير الشراء المُرحَّلة **لم تكن تُنشئ أي قيد محاسبي حقيقي** رغم ظهورها
  بحالة `posted`. تم استبدالها بـ `SqlAccountingPort` الحقيقي (نفس نمط Sales
  تماماً)، بقيد: مدين 1120 المخزون (+1130 ضريبة مدخلات إن وُجدت) ↔ دائن 2100
  الذمم الدائنة. مُختبَر فعلياً في `test_purchasing_payments_flow.py` مع
  تحقق برمجي من توازن القيد في قاعدة البيانات (وليس فقط عدم رفع استثناء).

**لا تزال Fake:** `IPartnerLookup`/`IProductLookup` (العضو 2) — لكن غير
مستهلَكتين فعلياً من أي Use Case حالي في هذا الموديول (لا تحقق منفصل من
partner/product، الوحدة تثق بالـ id الممرَّر مباشرة)، فبقاؤهما في
`fake_ports.py` توثيقي فقط ولا يمثّل فجوة تشغيلية حقيقية حالياً.

## الجداول
purchase_orders, purchase_order_lines, purchase_invoices, purchase_invoice_lines

## APIs
```
POST   /purchase-orders                       إنشاء أمر شراء
GET    /purchase-orders                       قائمة أوامر الشراء
GET    /purchase-orders/{id}                   تفاصيل أمر شراء
POST   /purchase-orders/{id}/confirm            draft → confirmed
POST   /purchase-orders/{id}/cancel              إلغاء
POST   /purchase-orders/{id}/receive?warehouse_id=...   confirmed → received (يستدعي IInventoryPort)
POST   /purchase-invoices                        فاتورة شراء مستقلة
POST   /purchase-invoices/from-order              فاتورة من أمر شراء مُستلَم
GET    /purchase-invoices/{id}
POST   /purchase-invoices/{id}/post               draft → posted (يستدعي IAccountingPort)
```

## التكامل مع payments (حدث، وليس استيراد مباشر)
يشترك `infrastructure/event_handlers.py` في حدث `PaymentRecorded` المنشور
من موديول `payments`، ويحدّث `paid_amount` على الفاتورة المرجعية — القسم
6.6/11.2. مُختبَر فعلياً في `test_full_purchase_to_payment_flow_updates_invoice_paid_amount`.
