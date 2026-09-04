# تسليم — `TASK-AI-02b`: خطوة استلام صريحة لحركة مخزون فواتير الشراء عبر AI

## القرار المعتمَد (من صاحب القرار، رداً على `قرار_مطلوب_TASK-AI-02b.md`)
- **القرار الأول (متى؟):** الخيار (ج) — خطوة "استلام" صريحة جديدة، تحاكي
  `ReceivePurchaseOrderUseCase` القائم فعلياً لكن بلا `purchase_order_id`.
- **القرار الثاني (من أين `warehouse_id`؟):** الخيار (أ) — حقل صريح إلزامي
  يُدخله المستخدم عند الاستلام (نفس نمط `ReceivePurchaseOrderUseCase`).

كلاهما مطابق حرفياً للتوصية غير المُلزِمة في وثيقة تفكيك القرار — صفر
اجتهاد إضافي هنا، تنفيذ مباشر لما اعتمده صاحب القرار.

## ما تغيّر فعلياً

| الملف | التغيير |
|---|---|
| `modules/purchasing/infrastructure/models/purchasing_models.py` | عمود جديد `PurchaseInvoice.inventory_received_at` (nullable، `DateTime(timezone=True)`) — NULL يعني "لم تُستلَم بضاعتها بعد"، ويُستخدَم أيضاً كحارس idempotency |
| `migrations/versions/purchasing_20260815_0001_...py` | migration للعمود الجديد (رأس جديد فوق `purchasing_20260813_0001`) |
| `migrations/versions/purchasing_20260815_0002_...py` | seed لصلاحية `purchasing.invoice.receive_inventory` (نفس نمط `purchasing_20260806_0004`) |
| `modules/purchasing/application/use_cases/purchase_invoice_use_cases.py` | `ReceivePurchaseInvoiceInventoryUseCase` جديد — يستدعي `IInventoryPort.increase_stock` لكل بند، بثلاث حراسات صريحة (تفصيل أدناه) |
| `modules/purchasing/application/dto/purchasing_dto.py` | `PurchaseInvoiceResponse.inventory_received_at: datetime \| None` |
| `modules/purchasing/presentation/routes/purchase_invoices_router.py` | `POST /purchase-invoices/{id}/receive-inventory?warehouse_id=...` — نفس نمط `POST /purchase-orders/{id}/receive` حرفياً |
| `tests/integration/test_ai_invoice_posting_and_inventory_gap.py` | الاختبار الذي كان يُثبِت الفجوة (`test_ai_invoice_posting_does_not_move_inventory_documents_gap`) أُعيد تسميته وعكس تأكيده ليُثبِت **الإصلاح** (`test_ai_invoice_receive_inventory_closes_the_gap`)، + 3 اختبارات جديدة للحراسات الثلاث |

## الحراسات الثلاث في `ReceivePurchaseInvoiceInventoryUseCase` (ولماذا)

1. **`purchase_order_id is None`** — فاتورة مرتبطة بأمر شراء تُستلَم عبر
   `ReceivePurchaseOrderUseCase` نفسه (عند استلام الأمر)؛ السماح باستدعاء
   هذا الـUse Case عليها أيضاً يعني مضاعفة نفس الكمية في المخزون. مُختبَر
   فعلياً بدورة حياة أمر شراء كاملة (إنشاء → تأكيد → استلام → فوترة → ترحيل
   → محاولة استلام ثانية عبر المسار الجديد → `ValueError`).
2. **`status == "posted"`** — يمنع تكرار نفس المشكلة التي رُفض بسببها
   الخيار (ب) في وثيقة القرار: زيادة مخزون قبل التزام محاسبي فعلي.
3. **`inventory_received_at is None`** (idempotency) — استدعاء ثانٍ على نفس
   الفاتورة يُرفَض صراحة، لا زيادة مخزون مزدوجة صامتة — نفس فلسفة idempotency
   المتَّبعة في كل مكان آخر بالمشروع (مهمة #11، `TASK-AI-01` جزء 2).

## التحقق الفعلي (لا افتراض)

```
pytest tests/integration/test_ai_invoice_posting_and_inventory_gap.py -q
    → 6 passed (كان 3 قبل هذا التسليم)

pytest tests/integration/ -q
    → 139 passed, 4 skipped, 0 failed
      (136 baseline بعد GATE-02 + 3 جديدة = 139 — صفر تراجع)

alembic heads (فحص برمجي للسلسلة) → رأس واحد فقط: purchasing_20260815_0002

ruff check <كل الملفات المعدَّلة/الجديدة> → صفر مخالفات

py_compile على كل الملفات الجديدة/المعدَّلة → صفر أخطاء
```

## الأثر على طابور العمل

- 🟢 الفجوة الوحيدة المتبقية في `TASK-AI-02` (`STATUS_20_TASKS.md §19.2`)
  مغلقة الآن فعلياً ومُختبَرة.
- `GATE-03` (E2E الكامل عبر `TASK-AI-03`) يبقى المتبقي الوحيد على المسار
  الحرج لإغلاق تكامل AI↔Purchasing بالكامل — يحتاج خادم `ai-platform`
  حقيقي قيد التشغيل فعلياً، بيئة غير متاحة في بيئة التطوير الحالية (نفس
  القيد الموثَّق سابقاً لـ`test_ai_gateway_proxy.py`/الاختبارات الخمسة
  المتخطّاة في `TEST_BASELINE.md`).
- لا اختبار HTTP فعلي عبر Router لهذا الـEndpoint الجديد بعد (مثل
  `test_purchase_invoice_ai_upload_endpoint.py` لجزء 3 من `TASK-AI-01`) —
  الاختبارات هنا على مستوى Use Case مباشرة (نفس مستوى تغطية
  `ReceivePurchaseOrderUseCase` الأصلي). يمكن إضافته كتحسين لاحق منفصل
  إن رغب صاحب القرار.

---

## تحديث لاحق (نفس اليوم) — إضافة اختبار HTTP فعلي عبر Router

البند المذكور أعلاه كـ"تحسين لاحق ممكن" نُفِّذ فعلياً: ملف جديد
`tests/integration/test_purchase_invoice_receive_inventory_endpoint.py`،
بنفس نمط `test_purchase_invoice_ai_upload_endpoint.py` حرفياً (ASGITransport
+ override لجلسة DB، **بلا أي محاكاة/mock** — هذا الـEndpoint لا يستدعي أي
حد خارجي، بخلاف `/ai-upload`). 4 اختبارات جديدة:
- نجاح الاستلام عبر HTTP فعلي (200 + `inventory_received_at` مملوء).
- استدعاء ثانٍ على نفس الفاتورة → 400 (idempotency عبر HTTP).
- فاتورة `draft` غير مُرحَّلة → 400.
- بلا صلاحية `purchasing.invoice.receive_inventory` → 403.

### التحقق الفعلي المُحدَّث
```
pytest tests/integration/test_purchase_invoice_receive_inventory_endpoint.py -v
    → 4 passed

pytest tests/integration/ -q
    → 143 passed, 4 skipped, 0 failed (139 + 4 جديدة = 143 — صفر تراجع)

ruff check tests/integration/test_purchase_invoice_receive_inventory_endpoint.py
    → صفر مخالفات (بعد تصحيح رمز عربي غامض RUF002 في التوثيق، لا علاقة بالمنطق)

py_compile → صفر أخطاء
```

الآن تغطية `TASK-AI-02b` كاملة على مستويين (Use Case + HTTP عبر Router)،
بنفس مستوى تغطية `TASK-AI-01` تماماً.
