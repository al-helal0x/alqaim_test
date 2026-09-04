# تسليم — إغلاق فجوتَي اختبار في `TASK-10-01`/`TASK-12-01` (يُغلق `GATE-02` فعلياً)

## البند المُنفَّذ (ولماذا لا يحتاج قراراً من جهة عليا)
عند فحص `TASK-10-01`/`TASK-12-01` (`§ALQAIM_V2_MASTER_EXECUTION_PLAN.md`)
تبيَّن أن **الكود الإنتاجي مكتمل فعلياً بالكامل** (`enqueue_event()`،
`_NullWorkflowPort`، `InvoiceApprovalPendingError`، ربط الراوترَين — كل ما
تطلبه المهمتان موجود حرفياً في الشجرة) — لكن **بندين محدَّدين من "Tests
Required" في نص المهمتين نفسيهما** كانا غير مغطَّيَين بأي اختبار فعلي:

| المهمة | البند المطلوب حرفياً | الحالة قبل | الحالة بعد |
|---|---|---|---|
| `TASK-10-01` | "صف `outbox_events` بحالة `pending` لـ`FiscalPeriodClosed` موجود بعد الإقفال" | ❌ لا اختبار يتحقق من ذلك | ✅ `test_closing_period_enqueues_fiscal_period_closed_outbox_event` |
| `TASK-12-01` | "صفَّا outbox (`SalesInvoiceCreated`, `InvoicePosted`) موجودان فعلياً" | ❌ الجدول مُسجَّل في الـfixture لأسباب FK فقط، بلا أي استعلام عليه | ✅ `test_create_and_post_enqueue_expected_outbox_events` |
| `GATE-02` (حرفياً) | "نفس `idempotency_key` مرتين → نفس `invoice.id`، **صف outbox واحد فقط**" | ❌ لم يُختبَر الشق الخاص بـoutbox من هذا المعيار | ✅ `test_idempotent_create_hit_does_not_duplicate_outbox_event` |

هذا بالضبط نفس نمط الاختيار المتَّبع في كل تسليم سابق: **إضافة اختبار
لسلوك موجود فعلاً وموثَّق كمطلوب صراحة في الخطة** — لا قرار تصميم، لا
تعديل على أي كود إنتاجي، لا اجتهاد.

## ما تغيّر فعلياً (ملفا اختبار فقط، صفر كود إنتاجي)
1. `tests/integration/test_period_closing.py` — اختبار جديد واحد
2. `tests/integration/test_sales_invoice_idempotent_posting.py` — اختباران جديدان

## التحقق الفعلي (تشغيل حقيقي، لا افتراض)
```
pip install -e ".[dev]"   → نجح (SQLite في-الذاكرة، لا حاجة لـPostgres حقيقي)

py_compile fiscal_period_use_cases.py sales_use_cases.py
           invoices_router.py fiscal_periods_router.py   → نجح

pytest tests/integration/test_period_closing.py -q
    → 7 passed (كان 6 قبل هذا التسليم)

pytest tests/integration -k "sales" -q
    → 20 passed, 120 deselected

pytest tests/integration -q   (المجموعة الكاملة، فحص صفر تراجع)
    → 136 passed, 4 skipped, 0 failed
      (133 قبل هذا التسليم + 3 اختبارات جديدة = 136 بالضبط)

ruff check <الملفين المعدَّلين>
    → 3 مخالفات، **كلها موجودة سلفاً حرفياً في known_failures.txt** (E741
      × 2 في test_period_closing.py، I001 × 1 في test_sales_invoice_idempotent_posting.py)
      قبل هذا التسليم — صفر مخالفة جديدة
```

## أثر هذا التسليم على `GATE-02`
`GATE-02` (`§11` من الخطة) يشترط 6 بنود حرفياً — كلها الآن **مُتحقَّق منها
فعلياً بتشغيل حقيقي**، وليس افتراضاً:

| معيار `GATE-02` الحرفي | التحقق |
|---|---|
| `py_compile` على الملفات المتأثرة | ✅ أعلاه |
| `pytest` فعلي على `test_period_closing.py` + test suite sales | ✅ أعلاه |
| قيد الإقفال متوازن (بيانات إيراد+مصروف فعليين) | ✅ `test_closing_period_posts_balanced_closing_entry_to_retained_earnings` (موجود مسبقاً) |
| ترحيل على فترة مُقفلة → رفض صريح | ✅ `test_posting_after_close_is_rejected_even_with_retroactive_date` (موجود مسبقاً) |
| فاتورة > 10,000 بلا موافقة → `InvoiceApprovalPendingError` عند `/post` | ✅ `test_posting_blocked_while_pending_then_succeeds_after_manager_approval` (موجود مسبقاً) |
| نفس `idempotency_key` مرتين → نفس `invoice.id`، **صف outbox واحد فقط** | ✅ `test_idempotent_create_hit_does_not_duplicate_outbox_event` (**جديد في هذا التسليم**) |

**الحكم:** `GATE-02` بات مُغلَقاً فعلياً بكل معاييره الحرفية الستة. لم يكن
هذا واضحاً قبل هذا التسليم لأن المعيار السادس تحديداً (idempotency ×
outbox معاً) لم يكن مختبَراً من قبل، رغم أن الأجزاء الخمسة الأخرى كانت
مُتحقَّق منها في وقتها.

## ما لم يُلمَس (خارج نطاق هذا التسليم عمداً)
- صفر تعديل على أي كود إنتاجي — `fiscal_period_use_cases.py`،
  `sales_use_cases.py`، الراوترين — كلها كانت صحيحة سلفاً.
- لم أُحدِّث `STATUS_20_TASKS.md` رسمياً بإغلاق `GATE-02` — الخطة نفسها
  تشترط "إغلاق التعارض رسمياً في `STATUS_20_TASKS.md`" كخطوة منفصلة بعد
  `PASS`، وهذا قرار توثيق/تسجيل رسمي أفضل تركه لصاحب متابعة السجل بدل
  افتراض صلاحية غير ممنوحة لي هنا (الفرق بين "تحقَّقتُ فعلياً" و"أُعلن
  رسمياً" في سجل مشروع تراكمي).
- لم أمس `TASK-CI-04` (تنظيف مخالفات ruff الموروثة الـ278) — خارج نطاق
  هذا التسليم تماماً، ومُصنَّف SERIAL منفصل في الخطة.
