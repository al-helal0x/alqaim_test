# تسليم — جزء صغير وآمن من `TASK-AI-01` (تكامل AI↔Purchasing)

**التاريخ:** 2026-08-13، فوق نفس commit المُوثَّق في `تسليم_TASK-06-05.md`
و`TEST_BASELINE.md` (106 passed, 4 skipped قبل هذا التسليم).

## لماذا هذه المهمة تحديداً

بحسب `PROJECT_STATUS_SUMMARY.md §7` و`ALQAIM_V2_MASTER_EXECUTION_PLAN.md`،
**تكامل AI↔Purchasing (`TASK-AI-01/02/03` → `GATE-03`) هو العقبة الفعلية
المتبقية أمام إغلاق المشروع** الآن بعد أن أصبح `GATE-01` مغلَقاً فعلياً
(`تسليم_TASK-06-05.md`) وباقي CI Baseline موثَّقاً (`TEST_BASELINE.md`).
هذا هو السطر الحرفي في الملخص:

> تكامل AI↔Purchasing غير مُغلَق نهائيًا (#7/#8/#9) — استخراج الفواتير
> بالذكاء الاصطناعي يعمل تقنيًا لكن غير معتمَد كامل الموثوقية للإنتاج

`TASK-AI-01` نفسها (endpoint كامل + استدعاء شبكي حقيقي لـ`ai-platform` +
Idempotency + قرار عتبة الثقة لمطابقة المورد/المنتج تلقائياً) مهمة كبيرة
بعدة قرارات سياسة مفتوحة. بنفس منهج `تسليم_TASK-06-05.md` (اختيار **أقل
جزء مخاطرة** بدل تنفيذ كل شيء دفعة واحدة)، هذا التسليم يحل **جزءاً واحداً
فقط، آمناً بالكامل**: خطوة #3 من `TASK-AI-01` كما وردت حرفياً في الخطة:

> "تحويل حقول المسودة لـ`PurchaseInvoiceCreateRequest` الحالي، استدعاء use
> case الموجود (لا إعادة بناء)"

## ما وُجِد فعلياً عند الفحص (قبل كتابة أي كود)

- `apps/ai-platform/application/dto/ai_dto.py::DraftResponse` — شكل
  استجابة المسودة المعتمَدة فعلياً: `id`, `status`, `extracted_payload: dict`,
  `matched_supplier_id`.
- `apps/ai-platform/application/use_cases/process_document_pipeline.py` —
  المفاتيح الفعلية داخل `extracted_payload`: `supplier_name_guess`,
  `currency_guess`, `tax_guess`, `discount_guess`, `total_guess`, `lines`
  (كل بند: `description`, `quantity`, `unit_price`, `line_total`,
  `confidence`), `line_matches`, `supplier_matches`.
- `apps/ai-platform/services/entity_matching/entity_matcher.py` — **لا يوجد
  ثابت (constant) لعتبة ثقة مطابقة المنتج مُعرَّف في أي مكان.** عتبة
  `0.92` لمطابقة المورد التلقائية مكتوبة مباشرة (hardcoded) في
  `process_document_pipeline.py` فقط لهذا الغرض الضيق، وليست قراراً
  عاماً موثَّقاً كسياسة. **هذا بالضبط نفس نمط قرار backoff formula
  المؤجَّل في `تسليم_TASK-06-05.md`** — قرار سياسة يحتاج صاحب قرار، لا
  "تنفيذ" تقني وحيد صحيح.
- `apps/core-api/modules/purchasing/application/dto/purchasing_dto.py::
  PurchaseInvoiceCreateRequest` — موجود وجاهز فعلاً، لا يحتاج تعديلاً.

## ما نُفِّذ

ملف واحد جديد (صفر لمس لكود إنتاجي موجود):

`apps/core-api/modules/purchasing/application/use_cases/build_purchase_invoice_from_ai_draft.py`

دالة تحويل **صرفة** (pure function): `build_purchase_invoice_request_from_ai_draft(...)`
تُدخِل `extracted_payload` + `branch_id` + `supplier_id` (جاهز، محسوم مسبقاً
من طرف المستدعي) + `product_id_by_line_index` (جاهز أيضاً، محسوم مسبقاً)،
وتُخرِج `PurchaseInvoiceCreateRequest` صالحاً للتمرير مباشرة لـuse case
الفاتورة الموجود فعلاً — **بلا أي تعديل عليه**.

**قرار تصميم متعمَّد:** الدالة **لا تقرر** أي عتبة ثقة لمطابقة المورد أو
المنتج تلقائياً — تستقبل `supplier_id`/`product_id_by_line_index` جاهزين
فقط، وترفض (`DraftMappingError`) لو كانا فارغين. هذا يفصل بوضوح بين:
(أ) التحويل الميكانيكي البحت (منجَز هنا)، و(ب) قرار "متى نثق بالمطابقة
التلقائية كفاية" (مؤجَّل عمداً، يحتاج صاحب قرار — تماماً كقرار backoff).

اختبارات: `apps/core-api/tests/integration/test_build_purchase_invoice_from_ai_draft.py`
— 8 اختبارات وحدة صرفة (لا `session`، لا قاعدة بيانات):

| # | السيناريو |
|---|---|
| 1 | مسودة صالحة كاملة → `PurchaseInvoiceCreateRequest` صحيح |
| 2 | لا مورد مطابَق → `DraftMappingError`، لا فاتورة جزئية |
| 3 | لا `branch_id` → `DraftMappingError` |
| 4 | لا بنود إطلاقاً → `DraftMappingError` |
| 5 | بند واحد بلا منتج مطابَق (من أصل بندين) → فشل التحويل **كاملاً**، لا فاتورة جزئية |
| 6 | بند ناقص الكمية/السعر → `DraftMappingError` |
| 7 | كمية صفر/سالبة → مرفوضة |
| 8 | `currency_guess` غائب → افتراضي `IQD` |

## التحقق الفعلي (لا افتراض)

```
python3 -m py_compile build_purchase_invoice_from_ai_draft.py \
                       test_build_purchase_invoice_from_ai_draft.py   → نجح

pytest tests/integration/test_build_purchase_invoice_from_ai_draft.py -v
    → 8 passed

pytest tests/integration/ -q
    → 114 passed, 4 skipped, 0 failed
      (106 + 8 جديدة = 114 — لا صفر تراجع عن TEST_BASELINE.md)
```

## لم يُلمَس (عمداً، خارج نطاق هذا الجزء تحديداً)

- `PurchaseInvoiceCreateRequest`, `purchase_invoice_use_cases.py`,
  `purchase_invoices_router.py` — صفر تعديل.
- `apps/ai-platform/*` بالكامل — صفر تعديل.

## المتبقي فعلياً من `TASK-AI-01` (لم يُنفَّذ هنا، بوضوح)

1. الـ`Endpoint` الفعلي `POST /purchasing/invoices/ai-upload`.
2. استدعاء شبكي حقيقي لـ`ai-platform` لجلب `DraftResponse`.
3. **قرار عتبة الثقة** لمطابقة المورد/المنتج تلقائياً (سياسة، يحتاج صاحب قرار).
4. Idempotency فعلي بـ`draft_id` (منع فاتورتين لنفس المسودة).
5. `TASK-AI-02` (تأكيد الترحيل) و`TASK-AI-03` (اختبار E2E الكامل = `GATE-03`).

**لماذا التوقف هنا:** كل بند من الخمسة أعلاه إما يحتاج قرار سياسة من صاحب
المشروع (البند 3) أو يحتاج بيئة شبكة/تكامل حقيقية (البنود 1/2/4/5) بدل
تحويل ميكانيكي صرف — نفس منطق التوقف المتبع حرفياً في `تسليم_TASK-06-05.md`
عند `redis_bridge.py`/قرار backoff.
