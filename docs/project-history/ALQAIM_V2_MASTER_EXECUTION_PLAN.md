# AlQaim V2 — MASTER EXECUTION PLAN

**مصدر الحقيقة:** `ALQAIM_V2_CURRENT_STATE_AND_ROADMAP.md` (2026-08-12) + فحص كود مباشر أثناء إعداد هذه الخطة.
**قاعدة الحوكمة:** `Code → Tests → Verification → Documentation`. لا "تم ✅" بلا Verification فعلي.
**كل معلومة غير مؤكَّدة في التقرير المصدر تُعلَّم صراحةً:** `⚠️ غير مثبت — يحتاج فحص كود قبل الاعتماد`.

---

# 1. Executive Decision

نفّذ حسم #6×#10×#11×#12 بجلسة عمل واحدة متسلسلة (ليس توزيعاً موازياً)، ببناء **Outbox Core أولاً كأساس مستقل**، ثم دمج #10 و#12 بالتوازي المُتحكَّم فوقه (ملفان منفصلان تماماً، لا تشارك حالة)، مع Gate تحقق حقيقي (تشغيل pytest فعلي، ليس py_compile فقط) بعد كل خطوة. توازِ Walk-in Customer مع كل ما سبق فوراً (معزول تماماً). أجّل AI→Purchasing حتى Gate-02، لكن ابنِ نسخته الأولى **بدون** انتظار Outbox الكامل — استدعاء مباشر متزامن كافٍ لإثبات الـVertical Slice، والتحويل لنمط Outbox لاحقاً كتحسين موثوقية منفصل.

---

# 2. Current State (ملخص تنفيذي، مرجعه التقرير المصدر)

| العنصر | الحالة |
|---|---|
| Outbox (`outbox_events` جدول) | 🟢 Migration موجودة فعلياً (`platform_20260809_0002_outbox_events.py`) |
| Outbox (منطق enqueue/dispatch) | 🔴 غير موجود — 3 محاولات فشلت (Tracks 1/2/3، مُثبَت بـ`diff` فارغ) |
| #10 Fiscal Closing (منطق صحيح) | 🟡 مكتوب في `_CONFLICTS/fiscal_period_use_cases_task6_vs_task10/version_task10_di_refactor.py`، غير مدموج في الشجرة الحية |
| #12 Sales Approval (منطق صحيح) | 🟡 مكتوب في `_CONFLICTS/sales_use_cases_task6_vs_task12/version_task12_workflow_approval.py`، غير مدموج |
| #11 Idempotency | 🟢 مدموج فعلياً في الشجرة الحية، مستقل عن #6 كلياً |
| Walk-in Customer | 🔴 مفقود، `pos_repository.dart` يفرض `partnerId` إلزامياً |
| AI→Purchasing endpoint | 🔴 غير موجود |
| CI (`.github/workflows/`) | 🔴 غير موجود |
| `ADR-003` | 🔴 مُشار إليه في `PRODUCT_VISION.md` لكن غير موجود فعلياً في أي حزمة |

---

# 3. Target State (نهاية هذه الخطة)

1. `outbox_events` تُكتَب/تُسلَّم فعلياً عبر مسار واحد مُتفَق عليه، مُختبَر بـ integration tests حقيقية (ليس py_compile فقط).
2. إقفال فترة محاسبية ينتج قيداً حقيقياً متوازناً، ينقل الصافي لحساب `3200`، ويمنع أي ترحيل لاحق على الفترة.
3. فاتورة > 10,000 تُحجَب عن الترحيل حتى موافقة مدير، عبر state machine حقيقية.
4. بيع نقدي في POS بلا اختيار عميل يدوي.
5. صورة فاتورة → OCR → مراجعة → اعتماد → عملية شراء حقيقية في المخزون والمحاسبة، على الأقل بمسار متزامن (لا يشترط Outbox الكامل).
6. CI حقيقي يعمل على كل PR، يفصل inherited failures عن جديدة.
7. قرار صريح موثَّق بشأن `ADR-003` (استعادة أو حذف الإشارة).

---

# 4. Principles

- **لا "تم ✅" إلا بعد السلسلة الكاملة:** `PLANNED → IMPLEMENTED → TESTED → INTEGRATED → VERIFIED → ACCEPTED`.
- **STOP THE LINE:** أي Gate يفشل يوقف كل عمل فوق نتيجته — لا فتح مهام جديدة فوق أساس غير مُتحقَّق منه.
- **لا توزيع موازٍ على تعارض محاسبي متعدد الأبعاد** إلا بعد إثبات عزل الملفات الكامل (راجع قسم 10 — Parallelization Policy).
- **الملف الذي بنى عليه فريق سابق قراره الحقيقي هو `_CONFLICTS/`، ليس النسخة "المدموجة" في `main`** — كل Task أدناه يشير للمصدر الصحيح صراحة.

---

# 5. Dependency Analysis (اختبار هندسي للترتيب المقترَح)

### 5.1 هل Outbox يجب أن يسبق #10؟
**جزئياً، لا كلياً.** منطق قيد الإقفال نفسه (حساب صافي الإيراد/المصروف، `assert_balanced`, الترحيل لحساب `3200`, منع الترحيل اللاحق) **لا يعتمد على Outbox إطلاقاً** — عمليات SQL/Domain rules صرفة. الاعتماد الوحيد الفعلي هو نشر حدث `FiscalPeriodClosed`. **القرار:** ابنِ منطق الإقفال ونشر الحدث معاً فوق Outbox Core، لكن لا تنتظر Outbox لبدء تصميم/كتابة منطق الإقفال نفسه — التصميم يمكن أن يبدأ فوراً، فقط الدمج النهائي (استدعاء `enqueue_event`) ينتظر `GATE-01`.

### 5.2 هل Outbox يجب أن يسبق #12؟
**نفس المنطق تماماً.** State machine الموافقة مستقلة كلياً عن آلية نشر `SalesInvoiceCreated`/`InvoicePosted`.

### 5.3 هل #11 له Dependency مباشر على #6؟
**لا، مؤكَّد بالكود.** Idempotency تعتمد على قيد `UNIQUE` على مستوى قاعدة البيانات، مدموجة فعلياً بلا أي علاقة بـOutbox. **لا عمل مطلوب — فقط لا تكسرها أثناء دمج #10/#12.**

### 5.4 هل #10 يجب أن يُدمَج قبل أو بعد #12؟
**لا ترتيب إلزامي بينهما — ملفان منفصلان تماماً، لا حالة مشتركة، لا استيراد متبادل.** CONTROLLED PARALLEL بشرط الاعتماد على نفس واجهة النشر المجمَّدة دون تعديلها من أي منهما.

### 5.5 هل يمكن تنفيذ Walk-in Customer بالتوازي بأمان؟
**نعم، بلا أي تحفظ.** `apps/pos-app` Flutter، لا يتشارك أي ملف مع `apps/core-api`. **SAFE PARALLEL كامل، يبدأ فوراً.**

### 5.6 هل AI→Purchasing فعلاً يجب أن ينتظر اكتمال Outbox؟
**لا — هذا افتراض التقرير المصدر، وأعدّله هنا صراحة.** أقل مسار لإثبات الـVertical Slice:
```
ai-platform (موجود) → استدعاء API متزامن (HTTP مباشر، ليس عبر Redis+Outbox)
  → purchasing.CreatePurchaseInvoiceFromDraft (جديد) → accounting/inventory (موجود)
```
هذا يثبت الحلقة الكاملة **بدون أي اعتماد على Outbox**. الاعتماد الحقيقي على Outbox يظهر فقط لتحسين الموثوقية (فصل زمني، تحمّل انقطاع الاتصال) — **تحسين لاحق، وليس شرطاً للحلقة الوظيفية.**
**القرار:** ابنِ `ai-upload` بنداء متزامن أولاً (Phase 3)، أضف الفصل عبر Outbox لاحقاً كتحسين موثوقية منفصل بعد Working Product.

### 5.7 أقل مجموعة تغييرات لإنتاج Vertical Slice حقيقي؟
`TASK-06-01..04` + `TASK-10-01` + `TASK-12-01` + `TASK-WI-01` + `TASK-AI-01..03` — بدون أي عمل على CI enforcement أو Reporting المتقدم؛ تلك تأتي بعد Vertical Slice، ليست شرطاً له.

---

# 6. Dependency Graph

```
                    ┌─────────────────────┐
                    │  TASK-06-01..04      │
                    │  Outbox Core         │
                    └──────────┬───────────┘
                               │ (GATE-01)
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
        ┌────────────────┐         ┌────────────────┐
        │  TASK-10-01     │         │  TASK-12-01     │
        │  Fiscal Closing │ (لا تشارك حالة) │ Sales Approval  │
        └────────┬────────┘         └────────┬────────┘
                 └─────────────┬─────────────┘
                               │ (GATE-02)
                               ▼
                    ┌─────────────────────┐
                    │  TASK-AI-01..03       │
                    │  AI→Purchasing (sync) │
                    └──────────┬───────────┘
                               │ (GATE-03)
                               ▼
                    ┌─────────────────────┐
                    │  WORKING PRODUCT      │
                    │  (E2E Acceptance)     │
                    └──────────┬───────────┘
                               │
                               ▼
                    CI Baseline → Testing Strategy Rollout →
                    Production Hardening → Production Candidate

  [بالتوازي منذ البداية، معزول تماماً]
  TASK-WI-01a → TASK-WI-01b → TASK-WI-01c → GATE-WI      ← سلسلة داخلية مستقلة، لا تعتمد على أي عقدة أعلاه ولا تعتمد عليها
```

---

# 7. Critical Path

```
TASK-06-01 → TASK-06-02 → TASK-06-03 → TASK-06-04 → GATE-01
   → [TASK-10-01 ∥ TASK-12-01] → GATE-02
   → TASK-AI-01 → TASK-AI-02 → TASK-AI-03 → GATE-03
   → WORKING PRODUCT E2E TESTS → GATE-04(WP)
   → CI-04 → CI-05 → GATE-04(CI)
   → PRODUCTION HARDENING
```

- **ما يؤخر المشروع:** GATE-01 (Outbox) — #10/#12 ينتظرانه جزئياً (النشر فقط).
  > 🟢 **مُحدَّث 2026-08-14:** `GATE-01` **مُغلَق فعلياً** (`TASK-06-05`،
  > راجع `STATUS_20_TASKS.md §18`). `TASK-AI-01` **مُنجَزة بالكامل** و
  > `TASK-AI-02` **VERIFIED** (فجوة مخزون موثَّقة، فُتحت كـ`TASK-AI-02b`
  > منفصلة — راجع `STATUS_20_TASKS.md §19`). ما يؤخر المشروع الآن فعلياً:
  > `TASK-AI-03` فقط (E2E الكامل = `GATE-03`)، وهي تحتاج بيئة `ai-platform`
  > حقيقية قيد التشغيل غير متاحة محلياً حتى الآن.
- **ما لا يؤثر على Critical Path:** `TASK-WI-01` بالكامل، و`TASK-CI-01..03`.
- **أكبر مخاطر Schedule:** تكرار فشل Tracks 1/2/3 إذا أُعيد التوزيع الموازي على TASK-10/TASK-12 دون Gate صارم بينهما — لذلك **GATE-02 إلزامي**، حتى لو بدا كلا الملفين "جاهزين".

---

# 8. Phase Plan

## Phase 0 — Outbox Core Foundation

**Phase Goal:** آلية outbox واحدة موثوقة، مُختبَرة فعلياً (rollback حقيقي، retry حقيقي).

**Why Now?** كل مسار محاسبي حرج يحتاج نشر أحداث موثوق. بناؤه أولاً مرة واحدة يمنع تكرار فشل Tracks 1/2/3.

**Dependencies:** لا شيء (جدول `outbox_events` موجود مسبقاً عبر migration).

**Inputs:** `platform_core/outbox_models.py` (موجود، لا تعديل)، `platform_core/event_bus.py` (موجود، DI فقط).

**Outputs:** `platform_core/outbox.py`، `platform_core/outbox_worker.py`، wiring في `main.py`.

**Tasks:** `TASK-06-01` → `TASK-06-02` → `TASK-06-03` → `TASK-06-04`.

**Parallelization:** **SERIAL ONLY** داخلياً.

**Verification Gate:** `GATE-01`.

---

## Phase 1 — Accounting Conflict Resolution (#10 + #12)

**Phase Goal:** إقفال فترة حقيقي + حجب موافقة مدير، مدموجان في الشجرة الحية ومُختبَران.

**Why Now?** أقدم Blocker محاسبي موثَّق في المشروع.

**Dependencies:** `GATE-01` (لواجهة النشر فقط).

**Inputs:** `_CONFLICTS/fiscal_period_use_cases_task6_vs_task10/version_task10_di_refactor.py`، `_CONFLICTS/sales_use_cases_task6_vs_task12/version_task12_workflow_approval.py` — **المصدران الصحيحان**، وليس النسخ الحالية في `main`.

**Outputs:** `fiscal_period_use_cases.py` و`sales_use_cases.py` محدَّثان، مربوطان بـ`outbox.enqueue_event`.

**Tasks:** `TASK-10-01`، `TASK-12-01`.

**Parallelization:** **CONTROLLED PARALLEL** — ملفان مختلفان، بشرط: (أ) لا أحد يعدّل `outbox.py`، (ب) `GATE-02` يُشغَّل على الاثنين معاً.

**Verification Gate:** `GATE-02`.

---

## Phase 2 — Walk-in Customer (بالتوازي منذ البداية)

**Phase Goal:** بيع نقدي في POS بلا اختيار عميل يدوي.

**Why Now?** معزول تماماً، منخفض المخاطر، قرار منتجي معتمَد مسبقاً.

**Dependencies:** لا شيء. يبدأ فوراً بالتوازي مع Phase 0/1.

**Tasks:** `TASK-WI-01a` → `TASK-WI-01b` → `TASK-WI-01c` (تسلسل داخلي إلزامي: migration ← endpoint ← Flutter)، + `TASK-GOV-01` (توثيق، مستقل تماماً).

**Parallelization:** **SAFE PARALLEL كامل** بالنسبة لبقية الخطة (لا حالة مشتركة مع #6/#10/#12/AI) — لكن **SERIAL ONLY داخلياً** (a→b→c، كل خطوة تحتاج سابقتها فعلياً موجودة).

**Verification Gate:** `GATE-WI` (مستقل).

---

## Phase 3 — AI → Purchasing Vertical Slice (Synchronous)

**Phase Goal:** صورة فاتورة → مراجعة → اعتماد → عملية شراء حقيقية، بمسار متزامن.

**Why Now?** "الميزة المميِّزة" المطلوب إثباتها أولاً حسب `PRODUCT_VISION.md §6`، ولا تحتاج Outbox كاملاً (5.6).

**Dependencies:** لا يحتاج `GATE-01` تقنياً؛ يُفضَّل بعد `GATE-02` تنظيمياً (فريق واحد متفرّغ).

**Tasks:** `TASK-AI-01` → `TASK-AI-02` → `TASK-AI-03`.

**Parallelization:** **SERIAL ONLY**.

**Verification Gate:** `GATE-03`.

---

## Phase 4 — CI Baseline

**Phase Goal:** CI حقيقي يعمل، يفصل inherited failures عن جديدة.

**Why Now:** لا يعتمد تقنياً على أي Phase أعلاه — يبدأ من اليوم الأول بالتوازي؛ enforcement الكامل فقط يُؤجَّل.

**Tasks:** `TASK-CI-01` → `TASK-CI-02` → `TASK-CI-03` → `TASK-CI-04` → `TASK-CI-05`.

**Parallelization:** `01..03` SAFE PARALLEL. `04` SERIAL بعد `02/03`. `05` SERIAL بعد `GATE-03`.

**Verification Gate:** `GATE-04`.

---

# 9. تعارض #6×#10×#11×#12 — Integration Plan كاملة

## 9.1 — #6 Outbox

| البند | القرار |
|---|---|
| **Event model** | `OutboxEvent` (موجود فعلاً — لا تعديل) |
| **Event envelope** | `enqueue_event(session, *, event_name: str, payload: dict, aggregate_id: str)` — يطابق `INTERFACE_CONTRACT_OUTBOX.md` الموجود مسبقاً حرفياً |
| **Persistence** | كتابة صف `status="pending"` ضمن نفس `session`، **بلا `commit()` داخلي** |
| **Transaction boundary** | العملية التجارية + صف outbox = معاملة واحدة ذرّية |
| **Enqueue** | دالة واحدة في `platform_core/outbox.py` (جديد)، بلا Class |
| **Worker** | `platform_core/outbox_worker.py` (جديد) — استطلاع كل 15 ثانية |
| **Retry** | `min(30 * 2**attempts, 3600)` ثانية backoff |
| **Failure handling** | بعد `max_attempts=8`: `status="failed"`، يبقى في الجدول لتدخل يدوي |
| **Idempotency** | مسؤولية كل Handler بذاته، ليست مسؤولية Outbox |
| **Delivery semantics** | **At-least-once صراحة** — يُوثَّق في `contracts.md` |
| **Observability** | Logging عند كل تحوّل حالة فقط، لا metrics في هذه المرحلة |
| **Tests** | `TASK-06-04` |

## 9.2 — #10 Fiscal Closing

| السؤال | الإجابة (من `version_task10_di_refactor.py`) |
|---|---|
| السلوك الحالي | `is_closed=True` فقط — بلا قيد محاسبي |
| السلوك المطلوب | قيد إقفال حقيقي يُصفّر الإيرادات/المصروفات، ينقل الصافي لحساب `3200` |
| كيف يتم الإقفال | `_post_closing_entry()` يحسب صافي كل حساب ضمن مدى الفترة، `assert_balanced()` **قبل** أي كتابة |
| الأرباح المرحّلة | حساب بكود ثابت `3200`؛ غير موجود → `RetainedEarningsAccountMissingError` صريح |
| منع الترحيل بعد الإغلاق | **موجود ومربوط فعلياً** في `RecordDocumentPostingUseCase._find_open_period` — لا عمل إضافي |
| علاقته بـOutbox | `enqueue_event()` **ضمن نفس معاملة قيد الإقفال، قبل commit الوحيد** — ذرّية كاملة (قرار محسوم هنا صراحة، وليس commit-ثم-commit) |
| كيف نختبره | `TASK-10-01` Tests |

## 9.3 — #11 Sales Idempotency (تأكيد، لا عمل جديد)

| السؤال | الإجابة |
|---|---|
| مكان الـunique constraint | قيد `UNIQUE` على مستوى الفاتورة — ⚠️ اسم العمود/الجدول الدقيق يحتاج تأكيد مباشر من `sales_models.py` قبل أي تعديل |
| حدود الـidempotency | مستوى Create فقط، وPost منفصل يتحقق من `status==POSTED` |
| عند retry | `IntegrityError` → `rollback()` → إعادة الفاتورة الموجودة |
| تفاعله مع #12 | فاتورة `pending_approval` تُعيد idempotent أيضاً |
| تفاعله مع Outbox | لا تفاعل مباشر — rollback يُلغي أي صف outbox في نفس المعاملة الخاسرة تلقائياً |
| إثبات عدم التكرار | نفس `idempotency_key` مرتين → نفس `invoice.id`، صف outbox واحد فقط |

## 9.4 — #12 Sales Approval

| البند | القرار (من `version_task12_workflow_approval.py`) |
|---|---|
| State machine | `pending_approval → approved/rejected` عبر `IWorkflowPort` فقط |
| متى تحتاج موافقة | `total_amount > 10,000` |
| من يوافق | خارج `sales_use_cases.py` — مسؤولية `modules/workflow` — ⚠️ يحتاج فحص مباشر قبل اعتماد تفاصيل الصلاحيات |
| قبل الموافقة | `DRAFT` → عند التجاوز، `/post` يُحجَب بـ`InvoiceApprovalPendingError` (409) |
| بعد الموافقة | `/post` يسمح بالترحيل الطبيعي |
| الأحداث الناتجة | `SalesInvoiceCreated` (عند الإنشاء) + `InvoicePosted` (عند الترحيل) |
| تفاعله مع Idempotency | الفحص يحدث بعد فحص idempotency، لا قبله |
| تفاعله مع Outbox | كلا الحدثين عبر `enqueue_event()` ضمن نفس معاملة كل عملية |

## 9.5 Dependency Graph لهذا التعارض تحديداً

```
outbox.py (enqueue_event)  ←── واجهة مجمَّدة، لا تُعدَّل من هنا فصاعداً
        │
        ├──→ fiscal_period_use_cases.py (#10)   ──┐
        │                                          ├─→ GATE-02 → main
        └──→ sales_use_cases.py (#11+#12)       ──┘
```

---

# 10. Parallelization Policy

### SAFE PARALLEL
- `TASK-WI-01a/b/c` — لا حالة مشتركة مع #6/#10/#12/AI (لكن تسلسل داخلي إلزامي بينها، راجع Phase 2).
- `TASK-GOV-01` — توثيق بحت، لا كود.
- `TASK-CI-01..03` — قراءة/تقرير فقط، لا يعدّل منطقاً تجارياً.

### CONTROLLED PARALLEL
- `TASK-10-01` و`TASK-12-01` — ملفان منفصلان، يعتمدان على نفس الواجهة المجمَّدة، يحتاجان `GATE-02` مشتركاً بعد الدمج معاً. **الشرط الحاسم الذي فشلت فيه Tracks 1/2/3:** تشغيل الاختبارات فعلياً بعد الدمج المشترك، لا الاكتفاء بتسليم ملف مع بطاقة "✅".

### SERIAL ONLY
- `TASK-06-01..04` — نفس الملفين الجديدين يُبنيان تراكمياً.
- `TASK-AI-01..03` — كل خطوة API تبني فوق التي قبلها.

### FORBIDDEN PARALLEL
- **أي توزيع لـ#10/#12/#6 على أكثر من عضو بمعزل تام (بلا Gate مشترك، بلا تشغيل اختبارات فعلي)** — بالضبط ما فشل في Tracks 1/2/3. لا يُسمح بتكراره تحت أي مسمّى ("عقد مجمَّد" أو غيره) بدون Gate تحقق حقيقي إلزامي.

---

# 11. Verification Gates

### GATE-01 (بعد Phase 0)
```text
Required:
- python3 -m py_compile على outbox.py + outbox_worker.py + main.py
- pytest tests/integration/test_outbox_pattern.py -v
- اختبار rollback حقيقي: فشل بعد enqueue وقبل commit → لا صف outbox يُكتَب
- اختبار retry: handler يرمي استثناء → attempts+1, status يبقى pending حتى max_attempts

PASS → Continue إلى Phase 1
FAIL → STOP THE LINE، لا بدء أي عمل على #10/#12
```

### GATE-02 (بعد Phase 1، #10+#12 معاً)
```text
Required:
- py_compile على fiscal_period_use_cases.py + sales_use_cases.py + الراوترات المتأثرة
- pytest فعلي على test_period_closing.py + test suite الخاص بـsales
- قيد الإقفال متوازن (Debit==Credit) على بيانات اختبار بها إيراد ومصروف فعليين
- ترحيل على فترة مُقفلة → رفض صريح
- فاتورة > 10,000 بلا موافقة → InvoiceApprovalPendingError عند /post
- نفس idempotency_key مرتين → نفس invoice.id، صف outbox واحد فقط

PASS → Continue إلى Phase 3 + إغلاق التعارض رسمياً في STATUS_20_TASKS.md
FAIL → STOP THE LINE، لا اعتماد أي بطاقة "✅" حتى المرور
```

### GATE-WI (مستقل)
```text
Required:
- alembic upgrade فعلي لـmigration الـpartial unique index (TASK-WI-01a) — يُختبَر
  بمحاولة إدخال صفَّي walk-in متزامنَين لنفس الشركة → الثاني يُرفَض على مستوى DB
- pytest على endpoint الـwalk-in الجديد (TASK-WI-01b)
- flutter test على pos-app (TASK-WI-01c)
- الأربعة سيناريوهات E2E السلوكية بالحرف (§2.2 بند 4 من قرار_استعادة_العميل_النقدي):
  1) شركة جديدة، لا يوجد Walk-in → يُنشأ تلقائياً، البيع يتم
  2) Walk-in موجود مسبقاً → يُستخدَم نفسه، لا سجل جديد
  3) شركة A/B → Walk-in كل شركة معزول تماماً عن الأخرى
  4) بيع نقدي مقابل بيع آجل → Credit يُلزِم اختيار Partner صريح، لا يجوز أن يتحول "عميل نقدي" لثغرة تحايل على حدود الائتمان

PASS → دمج فوراً (لا ينتظر أي Gate آخر)
FAIL → لا يوقف أي Phase أخرى، لكن **لا اعتماد نهائي (v8 → Approved) قبل مرور الأربعة سيناريوهات تحديداً** — هذا شرط الاعتماد المنصوص عليه صراحة في قرار_استعادة_العميل_النقدي §7
```

### GATE-03 (بعد Phase 3)
```text
Required:
- E2E: صورة فاتورة اختبار حقيقية → مسودة → اعتماد يدوي → عملية شراء ظاهرة + قيد محاسبي + حركة مخزون
- رفض المسودة → لا عملية شراء تُنشأ إطلاقاً

PASS → إعلان Vertical Slice مكتمل رسمياً
FAIL → STOP THE LINE على أي عمل AI إضافي (ممنوع أصلاً قبل هذا الـGate بحسب PRODUCT_VISION.md §9)
```

### GATE-04 (CI)
```text
Required:
- كل اختبارات GATE-01/02/WI/03 تعمل ضمن CI نفسه، لا محلياً فقط
- lint يميّز inherited failures عن جديدة

PASS → رفع enforcement تدريجياً
FAIL → إصلاح CI نفسه أولاً
```

---

# 12. Detailed Task Breakdown

## TASK-06-01 — تعريف Event Envelope وكتابة `enqueue_event()`

**الهدف:** دالة واحدة تكتب صف `outbox_events` ضمن معاملة قائمة، بلا commit داخلي.

**المشكلة التي يحلها:** غياب أي آلية outbox فعلية — 3 محاولات سابقة لم تُسلِّم هذا الملف إطلاقاً.

**Dependency:** لا شيء.

**Preconditions:** جدول `outbox_events` موجود فعلياً — تأكَّد بـ`alembic history` قبل البدء.

**Files المتوقَّع تعديلها:** `apps/core-api/platform_core/outbox.py` (جديد).

**Files الممنوع لمسها:** `platform_core/event_bus.py`، `platform_core/outbox_models.py`.

**التنفيذ خطوة بخطوة:**
1. أنشئ `platform_core/outbox.py`.
2. عرّف `async def enqueue_event(session: AsyncSession, *, event_name: str, payload: dict, aggregate_id: str) -> None:`
3. بناء `OutboxEvent(event_name=..., payload=..., status="pending", attempts=0, next_attempt_at=datetime.now(UTC))` — يجب ضبط `next_attempt_at` صراحة.
4. `session.add(event)` ثم `await session.flush()` — بدون `commit()`.
5. الدالة تعيد `None` (توقيع مجمَّد).

**Tests Required:**
- تكتب صفاً بحالة `pending` فعلياً.
- استدعاء بلا `commit()` لاحق → rollback يدوي → لا صف في الجدول.

**Acceptance Criteria:**
- [ ] الدالة بالتوقيع المجمَّد بالحرف.
- [ ] لا `commit()` داخل الدالة.
- [ ] `next_attempt_at` مضبوطة دائماً.

**Definition of Done:** IMPLEMENTED + TESTED.

**Verification Commands:**
```bash
python3 -m py_compile apps/core-api/platform_core/outbox.py
pytest apps/core-api/tests/integration/test_outbox_pattern.py::test_enqueue_writes_pending_row -v
```

**Rollback/Failure Considerations:** ملف جديد بالكامل — فشل هذه المهمة لا يؤثر على أي كود قائم.

---

## TASK-06-02 — `outbox_worker.py`: الاستطلاع الدوري والتسليم

**الهدف:** Worker يلتقط صفوف `pending` ويحوّلها لـ`dispatched` عبر `EventBus.publish()` الفعلي.

**Dependency:** `TASK-06-01` مكتملة ومُتحقَّق منها.

**Files المتوقَّع تعديلها:** `apps/core-api/platform_core/outbox_worker.py` (جديد).

**Files الممنوع لمسها:** `event_bus.py` (استخدم `get_event_bus()` فقط، لا تعدّله).

**التنفيذ خطوة بخطوة:**
1. `async def _poll_loop()`: كل 15 ثانية، `SELECT ... WHERE status='pending' AND next_attempt_at <= now() ORDER BY created_at LIMIT 100`.
2. لكل صف: `get_event_bus().publish(event.event_name, event.payload)` (التوقيع القديم الحالي — لا تغيّره هنا).
3. نجاح → `status="dispatched"`, `dispatched_at=now()`.
4. فشل → `attempts += 1`, `last_error=str(exc)[:2000]`, `next_attempt_at = now() + backoff`. `attempts>=8` → `status="failed"`.
5. `start_outbox_worker()`/`stop_outbox_worker()` بنمط `redis_bridge.py` الموجود.

**Tests Required:**
- صف `pending` مستحق → يُلتقَط ويتحول `dispatched`.
- Handler يرمي استثناء → `attempts=1`, يبقى `pending`.
- بعد 8 محاولات فاشلة → `status="failed"`، لا حذف.
- حدث بلا مشتركين → `dispatched` فوراً دون خطأ.

**Definition of Done:** IMPLEMENTED + TESTED.

**Verification Commands:**
```bash
pytest apps/core-api/tests/integration/test_outbox_pattern.py -v
```

---

## TASK-06-03 — Wiring في `main.py`

**الهدف:** تشغيل/إيقاف الـWorker ضمن `lifespan`.

**Dependency:** `TASK-06-02`.

**Files المتوقَّع تعديلها:** `apps/core-api/main.py` (سطران، نمط `start_redis_bridge()`).

**التنفيذ:**
1. `from platform_core.outbox_worker import start_outbox_worker, stop_outbox_worker`
2. في `lifespan`: `start_outbox_worker()` بعد `set_event_bus(...)` مباشرة.
3. `await stop_outbox_worker()` في `finally`، قبل `reset_event_bus`.

**Tests Required:** اختبار lifespan فعلي يتحقق أن الـWorker بدأ.

**Definition of Done:** IMPLEMENTED + TESTED + INTEGRATED.

---

## TASK-06-04 — Test Suite الشامل لـOutbox

**Files:** `apps/core-api/tests/integration/test_outbox_pattern.py` (جديد).

**Tests Required:**
- Transaction succeeds → Event exists.
- Transaction fails → Event does not exist.
- Event delivered twice → Consumer يبقى آمناً (at-least-once).

**GATE-01 يعتمد على نجاح هذا الملف بالكامل.**

---

## TASK-10-01 — دمج منطق الإقفال المحاسبي الحقيقي

**الهدف:** استبدال `fiscal_period_use_cases.py` الحالي بمنطق `version_task10_di_refactor.py` + ربطه بـ`enqueue_event()`.

**Dependency:** `GATE-01` (لواجهة النشر).

**Files المتوقَّع تعديلها:** `fiscal_period_use_cases.py`، `fiscal_periods_router.py`.

**Files الممنوع لمسها:** `outbox.py`، `modules/sales/*`.

**التنفيذ خطوة بخطوة:**
1. انسخ `_post_closing_entry()`, `_closing_net_by_account()`, `RetainedEarningsAccountMissingError`, `FiscalPeriodAlreadyClosedError` من `version_task10_di_refactor.py` حرفياً.
2. `execute()`: تحقق `is_closed` → `_post_closing_entry()` → `enqueue_event(...)` **قبل** commit الوحيد → `commit()` واحد لكل شيء معاً (قيد + إقفال + outbox) — ذرّية كاملة، لا commit-ثم-commit.
3. تحديث الراوتر لتمرير أي dependency جديدة.

**Tests Required:**
- إقفال بها نشاط → قيد متوازن، صافي منقول لـ`3200`.
- إقفال بلا نشاط → لا قيد، الفترة تُقفَل رغم ذلك.
- إقفال فترة مُقفلة أصلاً → `FiscalPeriodAlreadyClosedError`.
- حساب `3200` غير موجود بها نشاط → `RetainedEarningsAccountMissingError`، لا قيد جزئي.
- ترحيل مستند على فترة مُقفلة → رفض (يتحقق من منطق موجود مسبقاً).
- صف `outbox_events` بحالة `pending` لـ`FiscalPeriodClosed` موجود بعد الإقفال.

**Definition of Done:** IMPLEMENTED + TESTED + INTEGRATED (مع TASK-12-01 ضمن GATE-02) + VERIFIED + ACCEPTED.

**Verification Commands:**
```bash
python3 -m py_compile apps/core-api/modules/accounting/application/use_cases/fiscal_period_use_cases.py
pytest apps/core-api/tests/integration/test_period_closing.py -v
```

---

## TASK-12-01 — دمج منطق موافقة المدير

**الهدف:** استبدال `sales_use_cases.py` بمنطق `version_task12_workflow_approval.py` مدموجاً فوق قاعدة #11.

**Dependency:** `GATE-01`.

**Files المتوقَّع تعديلها:** `sales_use_cases.py`، `invoices_router.py`.

**Files الممنوع لمسها:** `modules/accounting/*`، `outbox.py`.

**التنفيذ خطوة بخطوة:**
1. ابدأ من نسخة #11 الحالية (idempotency موجودة — لا تفقدها).
2. أضف `_NullWorkflowPort`، `InvoiceApprovalPendingError`، `InvoiceApprovalRejectedError`، `requires_manager_approval`.
3. `CreateSalesInvoiceUseCase.execute()`: قبل commit الوحيد، `enqueue_event(..., event_name="SalesInvoiceCreated", ...)`.
4. `PostSalesInvoiceUseCase.__init__`: أضف `workflow_port: IWorkflowPort | None = None`.
5. `execute()`: بعد فحص idempotency وقبل الحجز، افحص `approval_state` → ارفض عند الحاجة.
6. `InvoicePosted` عبر `enqueue_event()` قبل commit الترحيل.
7. الراوتر: حقن Adapter حقيقي في `/post` فقط، معالجة الاستثناءين بـ409.

**⚠️ تحقق قبل البدء:** هل `SALES_INVOICE_APPROVAL_*` موجودة فعلاً في `domain/rules/__init__.py` الحالي؟ إن لا، أضفها ضمن هذه المهمة.

**Tests Required:**
- ≤10,000 → `/post` ينجح مباشرة.
- >10,000 بلا موافقة → 409.
- بعد موافقة → `/post` ينجح.
- طلب مرفوض → 409 دائماً.
- idempotency لا تزال تعمل.
- صفَّا outbox (`SalesInvoiceCreated`, `InvoicePosted`) موجودان فعلياً.

**Definition of Done:** مطابق لـTASK-10-01، ضمن نفس `GATE-02`.

**Verification Commands:**
```bash
python3 -m py_compile apps/core-api/modules/sales/application/use_cases/sales_use_cases.py apps/core-api/modules/sales/presentation/routes/invoices_router.py
pytest apps/core-api/tests/integration -k "sales" -v
```

---

## TASK-WI-01 — استعادة العميل النقدي (Walk-in Customer)

**⚠️ مُحدَّثة بالكامل** بعد مراجعة ثانية موثَّقة في `قرار_استعادة_العميل_النقدي (1).md` — النسخة أدناه **تلغي وتحل محل** أي وصف سابق لهذه المهمة في هذه الخطة. الفرق الجوهري: هذه لم تعد مهمة Flutter فقط — أصبحت 3 مهام فرعية (Backend Migration + Backend Endpoint + Flutter)، لأن المراجعة الثانية اكتشفت أن الحل السابق (تمييز بالاسم، صلاحية `partners.partner.create` للكاشير) غير كافٍ فعلياً على مستوى قاعدة البيانات والصلاحيات.

**الهدف:** بيع نقدي في POS بلا اختيار عميل يدوي، **مع ضمانات صحيحة على مستوى DB والصلاحيات، لا منطق تطبيقي فقط.**

**التصنيف الحوكمي:** 🟣 **Product Behavior Regression** — تصنيف جديد يُضاف رسمياً لقاموس المشروع (منفصل عن ADR المعماري، راجع `TASK-GOV-01` أدناه)، أولوية أعلى من Technical Debt العادي لأنه يمس Workflow يومي أساسي.

### TASK-WI-01a — Migration: تمييز نظامي + Partial Unique Index

**المشكلة التي يحلها:** لا يوجد اليوم أي حماية DB-level ضد تكرار "عميل نقدي" — القيد الوحيد الحالي هو `UniqueConstraint(company_id, tax_number)`، والعميل النقدي بلا رقم ضريبي أصلاً، فلا حماية فعلية. كما أن التعرّف عبر الاسم (`name == 'عميل نقدي'`) ليس Business Identifier صالحاً (يكسر لو غيّرت شركة الاسم المعروض لاحقاً).

**Files المتوقَّع تعديلها:** migration جديدة في `apps/core-api/migrations/versions/`، `modules/partners/infrastructure/models/partner_models.py`.

**التنفيذ خطوة بخطوة:**
1. أضف عمود `is_system_managed: bool = False` إلى `Partner` model (أو قيمة جديدة ضمن `partner_type` — التوصية: عمود منفصل، أوضح دلالياً وأسهل استعلاماً من تحميل `partner_type` بمعنى إضافي).
2. Migration: `ADD COLUMN is_system_managed boolean NOT NULL DEFAULT false`.
3. Migration: `CREATE UNIQUE INDEX ... ON partners (company_id) WHERE is_system_managed = true` (Partial Unique Index — يمنع أكثر من "عميل نقدي" واحد لكل شركة على مستوى DB، وليس منطقاً تطبيقياً قابلاً للسباق).
4. الاسم المعروض (`'عميل نقدي'`) يبقى مجرد `name` عادي — **لا دلالة نظامية له بعد الآن.**

**Database Changes:** عمود جديد + Partial Unique Index (تفصيل أعلاه).

**Tests Required:**
- محاولة إدخال صفَّين بـ`is_system_managed=true` لنفس `company_id` (متزامنَين أو متتاليَين) → الثاني يُرفَض بخطأ DB صريح (`IntegrityError`)، **ليس** فحصاً تطبيقياً فقط.
- صفّان بـ`is_system_managed=true` لشركتين مختلفتين → كلاهما يُقبَل.

**Acceptance Criteria:** [ ] الـIndex موجود فعلياً بعد `alembic upgrade head`، [ ] الاختبار أعلاه يفشل الإدخال الثاني فعلياً على قاعدة بيانات حقيقية (ليس SQLite تخيلياً إن كان behavior مختلفاً — ⚠️ تحقق أن Partial Index مدعوم بنفس السلوك على SQLite المستخدَم في الاختبارات أو استخدم Postgres للاختبار هذا تحديداً).

**Definition of Done:** IMPLEMENTED + TESTED + VERIFIED (تشغيل فعلي على قاعدة حقيقية).

---

### TASK-WI-01b — Endpoint مخصَّص بصلاحية `pos.sale.create`

**المشكلة التي يحلها:** الكاشير من منظور العمل "يطلب العميل النقدي"، لا "ينشئ عميلاً" — لكن نقطة الإنشاء الوحيدة حالياً (`POST /partners`) محمية بصلاحية `partners.partner.create` التي لا علاقة لها منطقياً بدور الكاشير.

**Dependency:** `TASK-WI-01a` (يحتاج العمود موجوداً أولاً).

**Files المتوقَّع تعديلها:** `modules/partners/presentation/routes/` (endpoint جديد، مثال `POST /partners/walk-in`)، أو معالجة ضمنية داخل `POST /pos/sales` — **القرار بين الخيارين متروك لمنفِّذ المهمة بناءً على فحص مباشر لـ`pos/presentation/routes/` الحالي؛ كلاهما مقبول ما دام لا يُغيَّر عقد `POST /partners` العام.**

**Files الممنوع لمسها:** عقد `POST /partners` العام (`partners_router.py`) — **لا تغيير في صلاحيته أو سلوكه الحالي.**

**التنفيذ خطوة بخطوة:**
1. Endpoint جديد، محمي بـ`pos.sale.create` (وليس `partners.partner.create`).
2. منطق find-or-create ضمن نفس الـendpoint: `SELECT ... WHERE company_id=? AND is_system_managed=true` → موجود؟ أعد الـid. غير موجود؟ `INSERT` مع الاعتماد على `TASK-WI-01a`'s unique index كخط الدفاع الأخير ضد السباق (لو فشل الإدخال بـ`IntegrityError` بسبب سباق حقيقي، أعد البحث والإرجاع بدل رفع الخطأ للمستخدم — نفس نمط `IntegrityError` handling المستخدَم فعلاً في idempotency #11).
3. **⚠️ قرار احتياطي موثَّق مسبقاً في قرار_استعادة_العميل_النقدي §3:** لو تبيّن أن استحداث endpoint جديد خارج نطاق الوقت المتاح لهذه المهمة تحديداً، يُسمح مؤقتاً بإبقاء `partners.partner.create` **مع توثيق صريح كـTechnical Debt** — لا يُغيَّر Authorization Contract الحالي بدون فحص كامل لأثره على أدوار أخرى.

**Security/Tenancy Considerations:** الاستعلام مفلتَر بـ`company_id` من `TenantContext` الحالي — لا فرق عن أي endpoint آخر في المشروع.

**Tests Required:**
- استدعاء بصلاحية `pos.sale.create` فقط (بلا `partners.partner.create`) → ينجح.
- استدعاء متكرر لنفس الشركة → نفس الـid دائماً، لا سجل جديد.
- سباق حقيقي (طلبان شبه-متزامنين، اختبار تكامل) → واحد ينجح بالإدخال، الآخر يُعالِج `IntegrityError` ويُعيد نفس الـid — **لا فشل ظاهر للمستخدم في كلا الحالتين.**

**Definition of Done:** IMPLEMENTED + TESTED + INTEGRATED.

---

### TASK-WI-01c — Flutter: استهلاك الـEndpoint في POS

**Dependency:** `TASK-WI-01b`.

**Files المتوقَّع تعديلها:** `apps/pos-app/lib/data/repositories/` (منطق استدعاء الـendpoint الجديد بدل `POST /partners` العام)، `apps/pos-app/lib/features/pos/` (تدفق الشاشة).

**السلوك الحالي:** `pos_repository.dart` يفرض `partnerId` إلزامياً.

**السلوك المطلوب:**
```
فتح POS → إضافة منتجات → الدفع
    → البيع Cash أم Credit؟
        Cash   → استدعاء endpoint الـwalk-in تلقائياً (TASK-WI-01b) → إتمام البيع
        Credit → إلزام اختيار Partner محدد صراحةً (كما هو حالياً، بلا تغيير)
```

**⚠️ فرق جوهري عن الوصف الأولي في هذه الخطة:** التمييز الآن هو **Cash مقابل Credit**، وليس فقط "عميل محدد أم لا" — بند إلزامي رقم 4 من القرار المرجعي يمنع صراحة أن يصبح "عميل نقدي" ثغرة للتحايل على حدود الائتمان في بيع آجل.

**التنفيذ خطوة بخطوة:**
1. استبدل أي استدعاء لـ`POST /partners` لغرض الـwalk-in باستدعاء endpoint `TASK-WI-01b` حصراً.
2. خزّن الـid محلياً (cache) لتفادي استدعاء متكرر لكل عملية بيع.
3. شاشة الدفع: زر الدفع في مسار **Cash فقط** لا يُعطَّل بغياب اختيار عميل يدوي؛ مسار **Credit يبقى معطَّلاً** حتى اختيار Partner صريح — لا تغيير هناك.

**Tests Required (Unit، تكميلية لسيناريوهات E2E في GATE-WI):**
- بيع Cash كامل بلا اختيار → ينجح، `partner_id` محفوظ فعلياً.
- بيع Credit بلا اختيار → **يُرفَض/الزر معطَّل** — Regression test صريح ضد بند 4.
- اختيار يدوي في بيع Cash (لو أراد الكاشير تحديد عميل حقيقي رغم كونه نقدياً) لا يزال يعمل — لا يُفرَض الـwalk-in قسراً.

**Definition of Done:** IMPLEMENTED + TESTED.

---

**Definition of Done لـTASK-WI-01 ككل:** الثلاثة أعلاه (a+b+c) مكتملة + الأربعة سيناريوهات E2E السلوكية في `GATE-WI` تمر فعلياً + موثَّق كـ"🟣 Product Behavior Regression Fix" في `STATUS_20_TASKS.md` (**ليس** "Regression Fix" عام كما في الصياغة الأولى لهذه الخطة — التصنيف الدقيق مُلزَم الآن).

---

## TASK-GOV-01 — توثيق تصنيف 🟣 Product Behavior Regression كسياسة Governance مستقلة

**الهدف:** إضافة رسمية لقاموس حوكمة المشروع — مطلوبة صراحة كبند إلزامي (#5) في `قرار_استعادة_العميل_النقدي (1).md §7`، وليست جزءاً تقنياً من TASK-WI-01 نفسها.

**Dependency:** لا شيء تقني — **SAFE PARALLEL كامل، توثيق فقط.**

**Files المتوقَّع تعديلها:** وثيقة Governance جديدة (مثال: `docs/architecture/GOVERNANCE-product-behavior-regression.md`) — **منفصلة عن `ADR-002` ولا تُدمَج داخله**، مع إشارة من `ADR-002` إليها.

**التنفيذ خطوة بخطوة:**
1. وثّق التعريف: 🟣 Product Behavior Regression ≠ Technical Regression (نظام معطَّل) ≠ Architecture Decision (ADR).
2. وثّق القاعدة الإلزامية: `OLD MODULE → Behavior Inventory → (Preserve / Intentionally Change / Intentionally Remove) → NEW MODULE → Regression Verification (E2E سلوكي، ليس Unit فقط) → Approval`.
3. أضف سطر إشارة واحد في `ADR-002` يشير لهذه الوثيقة الجديدة، بلا دمج المحتوى.

**Acceptance Criteria:** [ ] الوثيقة موجودة، [ ] `ADR-002` يشير إليها، [ ] `TASK-WI-01` نفسها مذكورة كأول تطبيق فعلي لهذا التصنيف.

**Definition of Done:** IMPLEMENTED (توثيق) — لا "TESTED" لوثيقة نصية، ينتهي عند ACCEPTED من مالك الحوكمة.

**ملاحظة استراتيجية:** القرار المرجعي نفسه يحذّر أن AlQaim مقبلة على إعادة بناء وحدات أكبر (Purchasing، Accounting، AI workflows) حيث **نفس الفخ قابل للتكرار** — الكود يعمل والاختبارات تمر، لكن سلوكاً تجارياً معتمَداً يضيع بصمت. توثيق هذا التصنيف الآن ليس تنظيفاً شكلياً، بل **إجراء وقائي مباشر** لباقي هذه الخطة نفسها.

---

## TASK-AI-01 — `POST /purchasing/invoices/ai-upload`

> ✅ **مُنجَزة بالكامل (2026-08-13/14).** المسار الفعلي `POST
> /purchase-invoices/ai-upload` (لاحظ: `/purchase-invoices` هو الـprefix
> الفعلي المسجَّل في `main.py`، لا `/purchasing/invoices` كما ورد في نص
> المهمة أصلاً). راجع `STATUS_20_TASKS.md §19.1` والبطاقات الثلاث
> `تسليم_TASK-AI-01-جزء{1,2,3}_*.md` للتفصيل الكامل.

**الهدف:** نقطة استقبال تستدعي `ai-platform` وتُنشئ فاتورة شراء من مسودة معتمَدة.

**Dependency:** لا يعتمد على `GATE-01` (راجع 5.6).

**⚠️ يحتاج فحص مباشر لواجهة `ai-platform` الفعلية (شكل استجابة مسودة معتمَدة) قبل تصميم الـpayload بدقة.**

**Files المتوقَّع تعديلها:** `modules/purchasing/presentation/routes/` (جديد)، `modules/purchasing/application/use_cases/CreatePurchaseInvoiceFromDraft` (جديد).

**التنفيذ خطوة بخطوة:**
1. Endpoint يستقبل `draft_id` (اعتماده مسؤولية `ai-platform`، لا يُعاد هنا). ✅
2. استدعاء متزامن لجلب بيانات المسودة الكاملة. ⚠️ يحتاج تأكيد: هل `ai-platform` عملية منفصلة فعلياً؟ ✅ **مؤكَّد فعلياً**: بوابة `platform_core/ai_gateway_client.py` كانت موجودة أصلاً ومُستخدَمة مسبقاً (`ai_proxy_router.py`) — أُعيد استخدامها كما هي.
3. `CreatePurchaseInvoiceFromDraft`: تحويل حقول المسودة لـ`PurchaseInvoiceCreateRequest` الحالي، استدعاء use case الموجود (لا إعادة بناء). ✅ (`build_purchase_invoice_from_ai_draft.py`)
4. مورد غير موجود/غير مطابَق → 422 صريح، لا إنشاء جزئي. ✅ مُختبَر فعلياً.

**Idempotency:** `draft_id` كـ`idempotency_key` — يمنع فاتورتين لنفس المسودة. ✅ (`source_ai_draft_id` + `UNIQUE(company_id, source_ai_draft_id)`)

**Tests Required:**
- مسودة كاملة → فاتورة شراء تُنشأ، مرئية في purchasing. ✅
- نفس `draft_id` مرتين → فاتورة واحدة فقط. ✅
- مورد غير معروف → 422، لا فاتورة جزئية. ✅

---

## TASK-AI-02 — تأكيد الربط بالمخزون/المحاسبة

> ✅ **VERIFIED جزئياً (2026-08-14)، بالضبط كما يسمح "Definition of Done"
> أدناه.** راجع `STATUS_20_TASKS.md §19.2` و`تسليم_TASK-AI-02_verification_and_gap.md`.

**الهدف:** التأكد أن فاتورة الشراء من `TASK-AI-01` تمر بنفس مسار الترحيل العادي — **لا بناء جديد، فقط تكامل واختبار.**

**Tests Required:** فاتورة AI → ترحيل → قيد متوازن ✅ + حركة مخزون صحيحة 🔴 **فجوة مُثبَتة، غير موجودة إطلاقاً — راجع `TASK-AI-02b` أدناه**.

**Definition of Done:** VERIFIED فقط (فجوة مكتشَفة هنا تُفتَح كـTask منفصلة، لا تُحَل ضمنياً). ✅ **هذا بالضبط ما حدث.**

---

## 🆕 TASK-AI-02b — حركة مخزون لفواتير AI بلا أمر شراء (مفتوحة، 2026-08-14)

**لماذا فُتحت:** فاتورة AI (`TASK-AI-01`) بلا `purchase_order_id` دائماً —
والمخزون في المسار العادي يزيد فقط عند **استلام أمر شراء**
(`ReceivePurchaseOrderUseCase`)، لا عند ترحيل الفاتورة. لا توجد أي خطوة
استلام يمكن أن تُشغِّل الزيادة لفواتير AI حالياً.

**⛔ لا تبدأ التنفيذ قبل حسم قرارين (نفس مبدأ قرار backoff/`redis_bridge.py`
المؤجَّلين سابقاً — قرار عمل، ليس تفصيلاً تقنياً):**
1. متى تُضاف حركة المخزون؟ عند ترحيل فاتورة AI؟ عند إنشائها من المسودة؟
2. أي `warehouse_id`؟ مسودة AI الحالية (`extracted_payload`) **لا تحتوي
   أي حقل مستودع إطلاقاً** — هذا قرار بيانات/واجهة جديد (هل يُطلَب من
   المستخدم عند رفع الفاتورة؟ افتراضي للفرع؟).

**Dependency:** `TASK-AI-01` (مُنجَزة ✅).

---

## TASK-AI-03 — اختبار E2E الكامل

> ⬜ **لم تبدأ (2026-08-14).** تحتاج خادم `ai-platform` حقيقي فعلياً قيد
> التشغيل — بيئة غير متاحة محلياً حتى الآن (نفس قيد الاختبارات الخمسة
> المتخطّاة في `TEST_BASELINE.md`: `test_ai_gateway_proxy.py`،
> `test_redis_bridge_real_modules.py`، `test_redis_event_bridge.py`).
> **هذا وحده هو ما يُبقي `GATE-03` مفتوحاً الآن.**

**Tests Required:**
```
1. رفع صورة فاتورة اختبار واقعية → ai-platform → مسودة
2. محاكاة اعتماد محاسب (API مباشر)
3. TASK-AI-01 endpoint → فاتورة شراء
4. ترحيل → قيد محاسبي + حركة مخزون
5. تتبّع كامل (audit trail) من الصورة حتى القيد
```

**هذا الاختبار وحده هو `GATE-03`.**

---

## TASK-CI-01..05 — CI Baseline

| Task | الوصف | Parallelization |
|---|---|---|
| `TASK-CI-01` | `.github/workflows/ci.yml` أساسي: pytest + ruff check (تقرير فقط، لا فشل PR) | SAFE PARALLEL |
| `TASK-CI-02` | تشغيل الاختبارات الحالية، توثيق أي فشل موجود أصلاً (Baseline) | SAFE PARALLEL، بعد CI-01 |
| `TASK-CI-03` | `ruff check .`، توثيق الـ278 مخالفة الموروثة كـ`known_failures.txt` | SAFE PARALLEL، بعد CI-01 |
| `TASK-CI-04` | إصلاح ما يمنع تشغيل الاختبارات فقط — ليس تنظيف الـ278 | SERIAL بعد CI-02/03 |
| `TASK-CI-05` | إلزامي تدريجياً: فشل PR على مخالفات **جديدة** فقط | SERIAL، **بعد GATE-03 فقط** |

---

# 13. Testing Strategy

| النوع | التغطية المطلوبة |
|---|---|
| Unit | Domain rules بمعزل عن قاعدة البيانات |
| Integration | كل use case مع SQLite في الذاكرة |
| Database | قيود UNIQUE/NOT NULL تُختبَر فعلياً |
| API | `ai-upload` عبر client حقيقي (FastAPI TestClient) |
| Contract | توقيع `enqueue_event()` محمي باختبار صريح |
| E2E | `TASK-AI-03` |
| **Accounting invariants** | **`Debit == Credit` على كل قيد، بلا استثناء** — fixture مشترك |
| Idempotency | مغطاة في TASK-10-01/12-01/AI-01 |
| Multi-tenancy | Company A لا تصل لبيانات Company B — على الأقل للـendpoints الجديدة؛ ⚠️ التغطية الشاملة على الوحدات القديمة خارج نطاق هذه الخطة |
| Security | صلاحيات الكاشير (TASK-WI-01) |
| Failure/Retry | مغطاة في TASK-06-04 |
| Regression | Walk-in customer لا يكسر الاختيار اليدوي |
| Performance | خارج نطاق هذه الخطة — بعد Working Product |

### Outbox — سيناريوهات إلزامية:
```
Transaction succeeds → Event exists
Transaction fails    → Event does not exist
Worker fails         → Event remains retryable
Event delivered twice → Consumer remains safe (at-least-once)
```

---

# 14. Team Ownership Matrix

| Task | Owner | Dependency | Parallel? | Integration Gate |
|---|---|---|---|---|
| TASK-06-01..04 | عضو Platform | لا شيء | لا (Serial) | GATE-01 |
| TASK-10-01 | عضو Accounting | GATE-01 | نعم (Controlled مع TASK-12-01) | GATE-02 |
| TASK-12-01 | عضو Sales | GATE-01 | نعم (Controlled مع TASK-10-01) | GATE-02 |
| TASK-WI-01a | عضو Backend (Partners) | لا شيء | نعم (Safe) | GATE-WI |
| TASK-WI-01b | عضو Backend (Partners) | TASK-WI-01a | لا (Serial بعد a) | GATE-WI |
| TASK-WI-01c | عضو POS/Flutter | TASK-WI-01b | لا (Serial بعد b) | GATE-WI |
| TASK-GOV-01 | مالك الحوكمة (Governance owner) | لا شيء | نعم (Safe، توثيق فقط) | — (ACCEPTED فقط) |
| TASK-AI-01..03 | عضو AI/Purchasing | اختياري GATE-02 | لا (Serial) | GATE-03 |
| TASK-CI-01..04 | عضو DevOps | لا شيء | نعم (Safe) | GATE-04 |
| TASK-CI-05 | عضو DevOps | GATE-03 | لا | GATE-04 |

**قواعد الملكية:**
- **مالك `outbox.py`:** عضو Platform فقط — أي تعديل لاحق من عضو آخر يمر عبر مراجعته.
- **مالك Contract:** نفس عضو Platform.
- **مالك Final Verification لكل Gate:** شخص مختلف عن منفِّذ الـTask نفسه — درس مباشر من فشل Tracks 1/2/3.
- **المراجعة:** أي دمج TASK-10-01/TASK-12-01 يحتاج مراجعة متبادلة بين العضوين قبل GATE-02.

---

# 15. ADR-003 — قرار الحوكمة المفقود

**الوضع:** `PRODUCT_VISION.md` يستشهد بـ`ADR-003` كمرجع اعتماد رسمي — غير موجود فعلياً.

### Option A — استعادة/إنشاء ADR-003
إيجابي: يحافظ على تسلسل الحوكمة الموثَّق. سلبي: كتابة ADR بأثر رجعي لقرار غير موجود = توثيق وهمي.

### Option B — إزالة المرجع من PRODUCT_VISION.md
إيجابي: صدق فوري. سلبي: تفقد الوثيقة سندها الرسمي المذكور.

**التوصية:** اكتب `ADR-003` الآن بمحتوى حقيقي يعكس القرارات الفعلية في هذه الخطة (ترتيب #6→(#10∥#12)→AI، مبدأ عدم التوسع قبل إثبات الحلقة — **موجود فعلاً كسلوك متبع في PRODUCT_VISION.md §9**)، بتاريخ اعتماد هذه الخطة نفسها، لا تاريخاً وهمياً سابقاً. **خارج Critical Path — يُنفَّذ بالتوازي، لا يحجب شيئاً.**

---

# 16. Roadmap

## NOW
`TASK-06-01..04` + `TASK-WI-01a→b→c` (بالتوازي مع كل شيء، تسلسلي داخلياً) + `TASK-GOV-01` + `TASK-CI-01..03` (بالتوازي)

## NEXT
`TASK-10-01 ∥ TASK-12-01` بعد GATE-01 → `TASK-AI-01..03` بعد GATE-02 → `TASK-CI-04` بعد Baseline

## LATER
`TASK-CI-05` بعد GATE-03، Reporting المتقدم، Costing على بيانات حقيقية، Offline Sync POS الفعلي، كل ما في قسم LATER من التقرير المصدر

## NEVER / NON-GOAL (حالياً)
أي توسيع AI بعد OCR قبل GATE-03 · Microservices extraction · تحسينات معمارية لا تخدم Gates مباشرة · **إعادة محاولة توزيع موازٍ بمعزل تام على أي تعارض محاسبي مستقبلي دون Gate صارم — محظور بشكل دائم بعد فشل Tracks 1/2/3**

---

# 17. Definition of Working Product → E2E Acceptance Tests

| # | العملية | Acceptance Test |
|---|---|---|
| 1 | تسجيل دخول + إنشاء شركة/فرع | شركة + فرع + مستودع افتراضي يظهر فعلياً |
| 2 | دورة شراء كاملة | PO→PI→قيد متوازن→حركة مخزون صحيحة |
| 3 | دورة بيع + Walk-in | بيع نقدي بلا اختيار يدوي (TASK-WI-01) |
| 4 | إقفال فترة محاسبية | TASK-10-01 |
| 5 | تقرير مالي يعكس الإقفال | رصيد 3200 محدَّث، لا صافي ربح مؤقت |
| 6 | AI → Purchasing كامل | TASK-AI-03 |

**لا "Working Product" إلا بعد مرور الستة فعلياً، متتالية، على بيئة واحدة.**

---

# 18. Production Readiness Checklist

| المحور | الحالة المتوقَّعة بعد هذه الخطة |
|---|---|
| Functional | ✅ |
| Accounting | ✅ |
| Inventory | 🟡 يحتاج تحققاً إضافياً خارج هذه الخطة |
| Security | 🟡 جزئي |
| Multi-tenancy | 🔴 خارج نطاق هذه الخطة — Task منفصلة موصى بها |
| AI | ✅ (موجود، غير مهدَّد) |
| Reliability | ✅ (at-least-once موثَّق) |
| Backup/Restore | 🔴 خارج نطاق هذه الخطة |
| Observability | 🟡 حد أدنى فقط |
| Performance | 🔴 Phase منفصلة لاحقة |
| CI/CD | ✅ بعد TASK-CI-05 |
| Error handling | ✅ ضمن نطاق المهام |
| Auditability | ✅ ضمن TASK-AI-03 |

**هذه الخطة تُنتج Working Product، وليس Production-Ready كاملاً.**

---

# 19. Risk Register

| الخطر | الاحتمال | الأثر | التخفيف |
|---|---|---|---|
| تكرار فشل Tracks 1/2/3 على TASK-10/12 | متوسط | حرج | GATE-02 إلزامي + مراجعة متبادلة + منع التوقيع الذاتي |
| غموض توقيت `enqueue_event` | منخفض | متوسط | حُسم صراحة: معاملة واحدة (9.2/TASK-10-01) |
| صلاحيات `modules/workflow` غير مؤكَّدة | متوسط | متوسط | ⚠️ مُعلَّم في TASK-12-01 |
| واجهة `ai-platform` غير مؤكَّدة | متوسط | متوسط | ⚠️ مُعلَّم في TASK-AI-01 |
| Race condition في Walk-in Customer | منخفض | منخفض | قيد UNIQUE + إعادة بحث عند فشل |
| رفع CI enforcement مبكراً يحجب Vertical Slice | متوسط لو خُولف الترتيب | متوسط | TASK-CI-05 مقفول خلف GATE-03 |

---

# EXECUTION ORDER

```text
01 → TASK-06-01   (enqueue_event)
02 → TASK-06-02   (outbox_worker)
03 → TASK-06-03   (main.py wiring)
04 → TASK-06-04   (test suite شامل)
05 → GATE-01      ← لا تتجاوز قبل نجاح pytest فعلي

    [بالتوازي منذ البداية]
    ── TASK-WI-01a → TASK-WI-01b → TASK-WI-01c → GATE-WI
    ── TASK-GOV-01 (توثيق، أي وقت)
    ── TASK-CI-01 → TASK-CI-02 → TASK-CI-03

06 → TASK-10-01  ∥  TASK-12-01   (عضوان مختلفان، بلا لمس outbox.py)
07 → GATE-02      ← يشمل الاثنين معاً

08 → TASK-AI-01
09 → TASK-AI-02
10 → TASK-AI-03
11 → GATE-03      ← إعلان Vertical Slice مكتمل رسمياً

12 → القسم 17 (E2E الست) على بيئة واحدة متتالية
13 → إعلان "Working Product" رسمياً

14 → TASK-CI-04 → TASK-CI-05 → GATE-04
15 → TASK-15 (ADR-003)، بالتوازي مع أي شيء أعلاه

16 → Production Hardening (Multi-tenancy شامل، Backup فعلي، Performance) — Phase منفصلة خارج نطاق هذه الخطة
```

**لا تنتقل لأي رقم قبل التالي دون مرور الـGate المذكور فعلياً — لا استثناءات.**
