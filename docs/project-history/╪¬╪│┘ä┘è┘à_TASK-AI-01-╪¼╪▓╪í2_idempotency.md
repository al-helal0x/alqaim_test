# تسليم — جزء آمن ثانٍ من `TASK-AI-01`: Idempotency بـ `ai_draft_id`

**التاريخ:** 2026-08-13، فوق نفس commit، بعد
`تسليم_TASK-AI-01-جزء1_mapping.md` مباشرة (114 passed, 4 skipped قبل هذا
التسليم).

## العقبة التالية بعد الجزء الأول

بطاقة التسليم السابقة (`تسليم_TASK-AI-01-جزء1_mapping.md`) عدّدت المتبقي
فعلياً من `TASK-AI-01` بترتيب صريح:

1. الـEndpoint الفعلي
2. استدعاء شبكي حقيقي لـ`ai-platform`
3. **قرار عتبة الثقة** لمطابقة المورد/المنتج تلقائياً — **قرار سياسة، ليس
   عملاً تقنياً، مؤجَّل عمداً** (نفس منطق قرار backoff formula المؤجَّل في
   `تسليم_TASK-06-05.md` — لا صاحب قرار محدَّد لهذا البند بعد)
4. Idempotency فعلي بـ`draft_id`
5. `TASK-AI-02`/`TASK-AI-03` (تحتاج بيئة تكامل حقيقية)

البند #3 لا يمكن تنفيذه من طرف واحد (قرار عمل)، والبنود #1/#2/#5 تحتاج
بنية شبكة/تكامل حقيقية غير متاحة هنا. **البند #4 (Idempotency) هو الوحيد
المتبقي القابل للتنفيذ الآمن الكامل بلا أي قرار سياسة معلَّق** — بالضبط
كما وصفته الخطة الرئيسية حرفياً: *"Idempotency: `draft_id` كـ
`idempotency_key` — يمنع فاتورتين لنفس المسودة."* هذا هو موضوع هذا التسليم.

## ما وُجِد فعلياً عند الفحص (قبل كتابة أي كود)

- `PurchaseInvoice` (في `purchasing_models.py`) **لا يملك أي عمود
  idempotency حالياً** — بخلاف `SalesInvoice` التي تملك `idempotency_key`
  فعلياً (مهمة #11).
- النمط الكامل المُثبَت فعلاً وموجود حرفياً في `sales_use_cases.py`:
  فحص مبكر بمفتاح → إن وُجد أعد نفس السجل → إن لم يوجد أنشئ → عند
  `IntegrityError` (سباق حقيقي) `rollback` ثم إعادة فحص المفتاح مرة أخرى
  قبل إعادة رفع الخطأ. اعتُمد **حرفياً** بلا تعديل على الفكرة.
- **⚠️ ملاحظة حرجة من `migrations/versions/sales_20260809_0001_*.py` نفسها
  (مكتوبة صراحة في تعليقها):** اختبارات SQLite في الذاكرة تُنشئ الجداول من
  تعريف الـORM مباشرة، فـ**لا تكشف غياب migration حقيقية**. أي: تعديل
  الـmodel وحده كافٍ لنجاح الاختبارات محلياً حتى لو نُسيت الـmigration —
  وهذا بالضبط ما حدث سابقاً مع مهمة #11 نفسها. رُوعِي هذا صراحة هنا: كل من
  الـmodel والـmigration عُدِّلا معاً في هذا التسليم، لا أحدهما فقط.

## ما نُفِّذ

| الملف | التغيير |
|---|---|
| `modules/purchasing/infrastructure/models/purchasing_models.py` | عمود جديد `source_ai_draft_id` (نصّي، Nullable) + `UniqueConstraint(company_id, source_ai_draft_id)` على `PurchaseInvoice` فقط |
| `migrations/versions/purchasing_20260813_0001_add_purchase_invoice_ai_draft_id.py` | migration جديدة (`down_revision = platform_20260812_0003`، رأس واحد بعدها — تحقَّق منه فعلياً عبر `alembic.script.ScriptDirectory`) |
| `modules/purchasing/infrastructure/repositories/purchasing_repository.py` | إضافة `PurchaseInvoiceRepository.get_by_ai_draft_id(...)` فقط — صفر تعديل على أي method موجودة |
| `modules/purchasing/application/use_cases/create_purchase_invoice_from_ai_draft_use_case.py` | **جديد بالكامل** — `CreatePurchaseInvoiceFromAiDraftUseCase`، يستدعي `_build_lines_and_totals` الموجودة فعلاً في `purchase_invoice_use_cases.py` (لا إعادة بناء)، بلا أي تعديل على `CreatePurchaseInvoiceUseCase` الأصلية |

**قرار تصميم متعمَّد:** `use case` **منفصل تماماً** عن
`CreatePurchaseInvoiceUseCase` الأصلية بدل تعديلها — يمنع أي أثر جانبي على
مسار الفاتورة اليدوي/من أمر شراء الموجود فعلاً ويعمل بلا مشاكل. الـDTO
المشترك (`PurchaseInvoiceCreateRequest`) لم يُعدَّل أيضاً — `ai_draft_id`
يُمرَّر كوسيط منفصل صريح لهذا الـuse case فقط.

**لم يُضَف:** نشر حدث Outbox عند الإنشاء — `CreatePurchaseInvoiceUseCase`
الأصلية نفسها لا تنشر أي حدث حالياً عند الإنشاء (فقط عند الترحيل لاحقاً
عبر use case آخر)، فالحفاظ على نفس السلوك هنا بدل توسيع غير مطلوب ضمن
نطاق هذا الجزء تحديداً.

اختبارات: `apps/core-api/tests/integration/test_create_purchase_invoice_from_ai_draft.py`
— 6 اختبارات:

| # | السيناريو |
|---|---|
| 1 | إنشاء فاتورة، `source_ai_draft_id` محفوظ بشكل صحيح |
| 2 | **نفس `draft_id` مرتين → نفس الفاتورة، لا ازدواج** (جوهر الميزة) |
| 3 | `draft_id` مختلف → فاتورتان منفصلتان |
| 4 | نفس `draft_id` بين شركتين مختلفتين → لا تعارض (القيد مركّب مع `company_id`) |
| 5 | `ai_draft_id` فارغ → `ValueError`، بلا لمس قاعدة البيانات |
| 6 | فاتورة شراء عادية (`CreatePurchaseInvoiceUseCase` الأصلية، بلا AI) → `source_ai_draft_id` يبقى `None`، **لا كسر للمسار الموجود** |

## التحقق الفعلي (لا افتراض)

```
python3 -m py_compile purchasing_models.py purchasing_repository.py \
    create_purchase_invoice_from_ai_draft_use_case.py \
    purchasing_20260813_0001_add_purchase_invoice_ai_draft_id.py \
    test_create_purchase_invoice_from_ai_draft.py main.py     → نجح على الجميع

pytest tests/integration/test_create_purchase_invoice_from_ai_draft.py -v
    → 6 passed

pytest tests/integration/ -q
    → 120 passed, 4 skipped, 0 failed
      (114 + 6 جديدة = 120 — لا صفر تراجع)

python3 -c "from alembic.script import ScriptDirectory; ..."
    → HEADS: ['purchasing_20260813_0001']   (رأس واحد، بلا تفرّع)

ruff check <الملفات المعدَّلة/الجديدة فقط>
    → 3 مخالفات RUF001/RUF002 (رموز عربية غامضة داخل docstrings) — **نفس
      الفئة المعروفة والمقبولة أصلاً في `known_failures.txt`** (18 مثيلاً
      RUF002 مسجَّلة مسبقاً لنفس السبب في ملفات أخرى من المشروع)، وليست
      فئة مخالفة جديدة. لا حاجة لإجراء (report-only أصلاً حسب `TASK-CI-01`).
```

## لم يُلمَس (عمداً)

- `CreatePurchaseInvoiceUseCase`, `CreatePurchaseInvoiceFromOrderUseCase`,
  `PostPurchaseInvoiceUseCase`, `PurchaseInvoiceCreateRequest`,
  `purchase_invoices_router.py` — صفر تعديل.
- `apps/ai-platform/*` بالكامل — صفر تعديل.

## المتبقي فعلياً من `TASK-AI-01` بعد هذين الجزأين

فقط: (1) الـEndpoint، (2) الاستدعاء الشبكي لـ`ai-platform`، (3) قرار عتبة
الثقة (سياسة، يحتاج صاحب قرار). الآن بوجود كل من دالة التحويل (الجزء
الأول) و`use case` الإنشاء الآمن مع idempotency (هذا الجزء)، الـEndpoint
نفسه أصبح عملياً **تجميعاً رقيقاً (thin wiring)** للاثنين معاً + استدعاء
HTTP واحد — لا منطق أعمال جديد متبقٍّ فيه.

**لماذا التوقف هنا رغم ذلك:** الـEndpoint يحتاج قرارات تتعلق بالبنية
التحتية الفعلية (Base URL لـ`ai-platform`، مصادقة بين الخدمتين، معالجة
timeout/فشل شبكي) لم تُحسَم في أي وثيقة مشروع حتى الآن — نفس معيار التوقف
المتبع حرفياً في التسليمين السابقين (لا "تنفيذ" بلا حسم مسبق لما يحتاج
حسماً).
