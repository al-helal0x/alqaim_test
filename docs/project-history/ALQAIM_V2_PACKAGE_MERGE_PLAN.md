# AlQaim V2 — خطة دمج الحزمتين — **مُعدَّلة إلى تقرير تحقُّق** (2026-08-13)

> **⚠️ تغيير جوهري في طبيعة هذا المستند:** النسخة الأصلية كانت خطة
> **مستقبلية** (لا تنفيذ فيها، كما نصَّت صراحة). بفحص مباشر للكود الحالي
> في الحزمة (`AlQaim_V2_v11_merged`، الأساس نفسه المُستخدَم في
> `ALQAIM_V2_MASTER_EXECUTION_PLAN.md` و`docs/architecture/ADR-003`)
> تبيَّن أن **كل مهمة MERGE-06/10/12 أدناه مُنفَّذة فعلياً بالفعل** —
> ملفاً بملف، وليس افتراضاً. لذلك أُعيدت كتابة هذا المستند من "خطة
> تنفيذ" إلى **"تقرير تحقُّق ملف-بملف"**: كل بند من الخطة الأصلية يحمل
> الآن حالته الفعلية المُتحقَّق منها (✅ / ⚠️ / ❌)، مع الانحرافات
> الحقيقية المكتشَفة عن التصميم المكتوب أصلاً — لا حذف لأي بند، فقط
> تحديث حالته بدليل.
>
> **المصدر:** فحص مباشر لملفات `apps/core-api/platform_core/*.py`،
> `modules/accounting/.../fiscal_period_use_cases.py`،
> `modules/sales/.../sales_use_cases.py`، `main.py`، ومجلد `tests/`، +
> `STATUS_20_TASKS.md §14-15` (سجل الدمج التاريخي لنفس هذا التعارض
> بالضبط، بتفاصيل مطابقة لما اكتُشف هنا).

---

## 1. الحكم العام

**القرار الحاسم في §2 من النسخة الأصلية (إعادة تصنيع الوصلة فوق العقد
الرسمي، لا دمج أي حزمة كما هي) طُبِّق فعلياً وبنجاح.** التوقيع المجمَّد
`enqueue_event(session, *, event_name, payload, aggregate_id)` موجود
حرفياً، `event_bus.py` بقي بتصميمه الأصلي بلا `session` كما اشترطت
MERGE-06-03، ومنطق الإقفال المحاسبي وموافقة المدير منقولان بلا تحريف عن
المنطق التجاري الصحيح. **لكن الفحص المباشر كشف 3 انحرافات حقيقية عن
التصميم المكتوب في هذه الخطة نفسها** (القسم 3 أدناه) — لم تُكتشَف من
قبل لأنها لا تمنع نجاح الاختبارات الوظيفية القائمة (100 passed)، لكنها
تعني أن **`GATE-01` بصيغته الحرفية في `ALQAIM_V2_MASTER_EXECUTION_PLAN.md §11`
غير مُغلَق رسمياً بعد**.

---

## 2. حالة كل MERGE-Task (تحقُّق ملف-بملف)

| Task | الحالة الفعلية | الدليل |
|---|---|---|
| `MERGE-06-01` (بناء `outbox.py`) | ✅ **منجَز، مطابق للعقد حرفياً** | `platform_core/outbox.py` موجود، التوقيع مطابق `INTERFACE_CONTRACT_OUTBOX.md` بالحرف، `session.add()` + `flush()` بلا `commit()` داخلي كما هو مشروط |
| `MERGE-06-02` (إعادة توصيل `outbox_worker.py`) | ⚠️ **منجَز مع انحرافين** | راجع القسم 3.1 و3.2 أدناه |
| `MERGE-06-03` (رفض `event_bus.py` المُعاد كتابته) | ✅ **منجَز تماماً** | `event_bus.py` الحالي بتوقيعه الأصلي `publish(event_name, payload)` بلا `session` — لا أثر لإصدار A إطلاقاً |
| `MERGE-06-04` (إعادة توصيل `redis_bridge.py`) | ⚠️ **لم يُنفَّذ كما خُطِّط — حُلَّ بطريقة مختلفة تماماً** | راجع القسم 3.3 أدناه — هذا أهم انحراف مكتشَف |
| `MERGE-06-05` (سطرا `main.py`) | ✅ **منجَز حرفياً** | `start_outbox_worker()`/`stop_outbox_worker()` في `lifespan`، بعد `set_event_bus()` — الترتيب مطابق |
| `MERGE-10-01` (إعادة توصيل منطق الإقفال) | ✅ **منجَز** | `fiscal_period_use_cases.py`: `_post_closing_entry`, حساب `3200`, `RetainedEarningsAccountMissingError`, و`enqueue_event()` بدل `event_bus.publish(session,...)` — جميعها موجودة، مُتحقَّقة أيضاً في `STATUS_20_TASKS.md §15` (100 passed) |
| `MERGE-12-01` (إعادة توصيل موافقة المدير) | ✅ **منجَز** | `sales_use_cases.py`: `InvoiceApprovalPendingError`, فحص `approval_state`, `enqueue_event()` في نقطتَي `SalesInvoiceCreated`/`InvoicePosted` — موجودة ومختبَرة |
| `MERGE-06-06` (إعادة بناء اختبارات Outbox) | ❌ **لم يُنفَّذ — فجوة حقيقية** | راجع القسم 3.4 أدناه |

---

## 3. الانحرافات الثلاثة الحقيقية المكتشَفة (تفصيل)

### 3.1 — `outbox_worker.py`: لا يوجد `status="failed"` بعد `max_attempts`

**ما خُطِّط له هنا (وفي `TASK-06-02`/`GATE-01` من الخطة الرئيسية):**
بعد 8 محاولات فاشلة، الصف يتحوّل `status="failed"` ويتوقف عن إعادة
المحاولة (يبقى في الجدول لتدخل يدوي).

**ما هو موجود فعلياً في `outbox_worker.py`:**
```python
backoff = min(2**row.attempts, MAX_BACKOFF_SECONDS)  # MAX_BACKOFF_SECONDS = 300
row.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)
```
لا يوجد أي شرط `if row.attempts >= 8: row.status = "failed"`. الصف يبقى
`pending` **إلى الأبد**، يُعاد استطلاعه كل ≤300 ثانية بلا حد أقصى
للمحاولات. **الأثر:** حدث فاشل بشكل دائم (مثلاً payload تالف يرفضه كل
مشترك دوماً) لا يتحوّل أبداً لحالة تحتاج تدخلاً يدوياً — يبقى يُعاد
تجربته صامتاً للأبد، وهذا يخالف معيار `Failure handling` المنصوص في
`ALQAIM_V2_MASTER_EXECUTION_PLAN.md §9.1` حرفياً.

**كذلك:** `POLL_INTERVAL_SECONDS = 2` في الكود الفعلي، وليس 15 ثانية
كما ورد في الخطة الرئيسية — فرق تنفيذي غير موثَّق، غير خطير بحد ذاته
(استطلاع أسرع فقط)، لكنه يعني أن أي توثيق مستقبلي لسلوك النظام يجب أن
يعتمد على الكود لا على القيمة المكتوبة في أي خطة.

### 3.2 — Backoff بصيغة مختلفة عن العقد المكتوب

المخطَّط: `min(30 * 2**attempts, 3600)`. الفعلي: `min(2**attempts, 300)`.
النتيجتان مختلفتان عملياً (سقف 5 دقائق مقابل ساعة، وبداية أبطأ في النسخة
المخطَّطة). **ليس خطأً وظيفياً**، لكنه انحراف غير موثَّق عن رقم محدَّد
في العقد — يحتاج قراراً صريحاً: إما تحديث الخطة الرئيسية لتطابق الكود،
أو تعديل الكود ليطابق الخطة. **لم يُحسَم هنا — يُرفَع كقرار مفتوح.**

### 3.3 — `redis_bridge.py`: لا يمرّ عبر `outbox.enqueue_event()` إطلاقاً

**هذا أهم انحراف.** الخطة الأصلية (MERGE-06-04) اشترطت أن `redis_bridge.py`
يستدعي `outbox.enqueue_event()` عند استلام حدث من `ai-platform`، مع
ترك سؤال `aggregate_id` مفتوحاً كنقطة قرار.

**ما هو موجود فعلياً:** `redis_bridge.py` **يعيد البث محلياً مباشرة**:
```python
await event_bus.publish(event_name, payload)   # التوقيع القديم، بلا outbox إطلاقاً
```
لا استدعاء لـ`outbox.enqueue_event()` في أي مكان بالملف. الحدث القادم
من Redis Pub/Sub (مثل `InvoiceDraftReady`) **لا يُكتَب أبداً كصف outbox
محلي** — الاعتماد على أن Redis نفسه (Pub/Sub) هو آلية التسليم، والنشر
المحلي بعد الاستلام نشر فوري في-الذاكرة فقط، بلا ضمان بقاء إضافي.

**الأثر العملي:** إن انهار `core-api` بين استلام الرسالة من Redis
وانتهاء تنفيذ كل الـ handlers المحليين المشتركين في الحدث، **يُفقَد
الحدث نهائياً** — Redis Pub/Sub لا يعيد تسليم رسائل `PUBLISH` العادية
لمشترك غاب لحظياً (بخلاف Redis Streams). هذا **يخالف مبدأ At-least-once**
المنصوص صراحة كهدف للـOutbox في `ALQAIM_V2_MASTER_EXECUTION_PLAN.md §9.1`
— لكن **فقط لأحداث AI القادمة عبر Redis**، لا الأحداث المحلية (Sales/
Fiscal) التي تمر عبر `outbox.py` الحقيقي بشكل صحيح.

**لماذا هذا مهم الآن تحديداً:** هذا بالضبط المسار الذي سيُبنى عليه
**AI→Purchasing Vertical Slice** (الأولوية الفعلية التالية للمشروع حسب
`ADR-003 §3`). إن استمر هذا التصميم، فحدث `InvoiceDraftReady` نفسه —
محور الحلقة الحرجة في `PRODUCT_VISION.md §6` — معرَّض لفقدان صامت عند
انهيار مؤقت. **يحتاج قراراً صريحاً قبل أو أثناء `TASK-AI-01`**: إما (أ)
قبول هذه الفجوة لأن `TASK-AI-01..03` في الخطة الرئيسية أصلاً تعتمد
استدعاء API متزامناً مباشراً لا Redis (`§5.6` من الخطة الرئيسية — قد
يجعل هذا الانحراف غير ذي أثر عملي على الحلقة الحرجة تحديداً)، أو (ب)
توصيل `redis_bridge.py` بـ`outbox.enqueue_event()` فعلياً كتحسين
موثوقية منفصل لاحق كما نصَّت `ADR-003 §2` أصلاً بخصوص AI Outbox.

### 3.4 — لا يوجد `test_outbox_pattern.py` مستقل

لا ملف بهذا الاسم في `tests/integration/`. سيناريوهات `GATE-01` الإلزامية
الأربعة من `ALQAIM_V2_MASTER_EXECUTION_PLAN.md §13`:
```
Transaction succeeds → Event exists
Transaction fails    → Event does not exist
Worker fails         → Event remains retryable
Event delivered twice → Consumer remains safe (at-least-once)
```
**غير مُختبَرة بشكل معزول ومباشر بأي ملف مخصَّص.** التغطية الوحيدة
الموجودة غير مباشرة عبر `test_sales_invoice_idempotent_posting.py`
(يتحقق من إنشاء صف outbox كأثر جانبي ضمن اختبار idempotency، وليس
اختباراً لسلوك الـWorker نفسه: rollback، retry، عدم-تسليم-مزدوج).
**النتيجة:** `100 passed` الموثَّقة في `STATUS_20_TASKS.md §15` **لا
تشمل** الاختبارات الأربعة الإلزامية لـGATE-01 بصيغتها الحرفية.

**إيجابي واحد مؤكَّد:** `test_event_bus_isolation.py` و
`test_redis_event_bridge.py` بالفعل بنسختهما الأصلية النظيفة (لا أثر
لافتراض A الخاطئ فيهما) — MERGE-06-06 نجح جزئياً في هذا الشق تحديداً،
فقط الملف الجديد (`test_outbox_pattern.py`) لم يُنشأ.

---

## 4. الحكم النهائي على `GATE-01`

| معيار `GATE-01` (من الخطة الرئيسية §11) | الحالة |
|---|---|
| `py_compile` على `outbox.py`+`outbox_worker.py`+`main.py` | ✅ (كل الملفات صالحة بنائياً، مؤكَّد بتشغيل مباشر) |
| `pytest tests/integration/test_outbox_pattern.py -v` | ❌ **الملف غير موجود** |
| rollback حقيقي (فشل بعد enqueue وقبل commit) | ⚠️ غير مُختبَر بملف مخصَّص، لكن المنطق (`session.add()`+`flush()` بلا commit داخلي) يجعله صحيحاً تصميمياً |
| retry (attempts+1، pending حتى max_attempts) | ❌ **لا `max_attempts` فعلياً — القسم 3.1** |

**الحكم:** `GATE-01` **غير مُغلَق رسمياً** بمعايير الخطة الرئيسية
الحرفية، رغم أن الأساس الوظيفي (منطق الإقفال + الموافقة + Idempotency)
يعمل فعلياً ومختبَر جيداً بطرق أخرى (100 passed). هذا **لا يوقف** العمل
على Walk-in Customer أو AI→Purchasing (لا اعتماد تقني مباشر بينهما وبين
هذه الفجوة تحديداً — راجع القسم 3.3 لملاحظة خاصة بـAI)، لكنه **دَين
تقني موثَّق يجب إغلاقه قبل الاعتماد النهائي على Outbox في أي مسار
موثوقية حرج مستقبلي**.

---

## 5. التوصية

1. **لا حاجة لإعادة أي عمل من MERGE-06-01/03/05/10-01/12-01** — منجزة
   وصحيحة، لا تُمَس.
2. **مهمة قصيرة ومحدودة جديدة** (تُقترَح تسميتها `TASK-06-05` في الخطة
   الرئيسية، خارج Critical Path الحالي): إضافة `max_attempts=8 →
   status="failed"` في `outbox_worker.py` + كتابة `test_outbox_pattern.py`
   بالسيناريوهات الأربعة. حجم العمل صغير (تعديل شرط واحد + ملف اختبار
   واحد) — لا يبرر تأجيل Walk-in Customer/AI→Purchasing، لكن يجب عدم
   إعلان `GATE-01` "منجَز ✅" في أي وثيقة حتى تُغلَق.
3. **قرار صريح مطلوب بخصوص `redis_bridge.py` (القسم 3.3)** قبل الاعتماد
   الكامل على `InvoiceDraftReady` في الإنتاج — إن كان `TASK-AI-01..03`
   سيستخدم فعلاً استدعاء API متزامناً مباشراً (لا Redis) كما ورد في
   `ALQAIM_V2_MASTER_EXECUTION_PLAN.md §5.6`، فهذه الفجوة **لا تؤثر على
   الحلقة الحرجة الأولى** ويمكن تأجيلها لتحسين الموثوقية اللاحق كما
   خطَّطت `ADR-003 §2` أصلاً. يُوصى بتوثيق هذا القرار صراحة عند فتح
   `TASK-AI-01` لا تركه ضمنياً.

**لا تُدمَج هذه الخطة كملف تنفيذ مستقبلي بعد الآن — دورها الآن أرشيفي/
تحقُّقي، ويُستبدَل كمرجع التنفيذ الحي بـ`ALQAIM_V2_MASTER_EXECUTION_PLAN.md`
و`docs/architecture/ADR-003-vertical-slice-strategy.md`.**

---
---

# ملحق تاريخي — النص الأصلي الكامل للخطة كما كُتب قبل التحقُّق (بلا حذف)

> **لماذا هذا الملحق موجود:** المراجعة الأولى لهذا المستند لخّصت الخطة
> الأصلية إلى أحكام (✅/⚠️/❌) وأسقطت التفاصيل التنفيذية (جداول A/B،
> أكواد Before/After، خريطة الملفات، المنطق الاقتصادي للقرار) دون
> الإفصاح عن ذلك صراحة — وهو تقصير جرى تصحيحه بناءً على سؤال مباشر.
> **كل ما يلي منسوخ حرفياً بلا تلخيص ولا حذف** من النسخة الأصلية
> المرفوعة، للحفاظ على قيمتها التاريخية/التعليمية الكاملة لأي عضو يحتاج
> فهم *كيف ولماذا* اتُّخذ كل قرار دمج، لا فقط حالته النهائية. **حالة كل
> بند هنا مقابل الكود الفعلي موثَّقة أعلاه في القسم 2-4 من هذا المستند
> (تقرير التحقُّق) — هذا الملحق مرجعي فقط، لا يُحدَّث بتغيّر الكود.**

## 1. تحديد الحزمتين بدقة

| الحزمة | المحتوى الفعلي | الدور في هذه الخطة |
|---|---|---|
| **A** — `AlQaim_V2_v9_conflict_resolved.zip` | تنفيذي كامل سبق بناؤه في هذه المحادثة: منطق #10 (إقفال حقيقي) و#12 (موافقة مدير) **مكتوب ومُختبَر (`py_compile` + منطق يدوي)**، لكن مُوصَّل عبر إعادة كتابة `event_bus.py` نفسه بتوقيع `publish(session, event_name, payload)` | **مصدر المنطق التجاري (Domain Logic Source)** |
| **B** — `files__5_.zip` | `INTERFACE_CONTRACT_OUTBOX.md` (العقد المجمَّد الرسمي: `enqueue_event()` في `outbox.py` منفصل، `event_bus.py` ممنوع لمسه) + Track1/2/3 (مُثبَت سابقاً أنها **فارغة فعلياً** — لا `outbox.py`، Track2/Track3 مطابقان بايتاً للنسخ القديمة) | **مصدر العقد المعماري الرسمي (Contract Source) فقط — لا منطق قابل للاستخدام منها** |

**التناقض الجوهري الذي هذه الخطة تحله:** الحزمة A تحتوي المنطق الصحيح لكن بسلك (Wiring) مخالف للعقد الرسمي في الحزمة B. الحزمة B تحتوي العقد الصحيح لكن بلا أي منطق فعلي خلفه. **لا حزمة منهما جاهزة للدمج المباشر في `main` بمفردها.**

---

## 2. القرار الحاسم (Executive Decision)

**لا تُدمَج أي من الحزمتين كما هي.** الدمج الصحيح هو **إعادة تصنيع الوصلة (Rewiring)**: يُستخرَج المنطق التجاري من الحزمة A (البند 3.2/3.3 أدناه)، **يُعاد توصيله بالكامل** فوق العقد الرسمي من الحزمة B (`outbox.py`/`enqueue_event`، وليس `event_bus.py` المُعاد كتابته)، مع بناء `outbox.py` و`outbox_worker.py` الفعليَّين من الصفر — لأن الحزمة B لم تسلّمهما فعلياً رغم وجود العقد.

هذا **يطابق تماماً** `TASK-06-01..04` + `TASK-10-01` + `TASK-12-01` في `ALQAIM_V2_MASTER_EXECUTION_PLAN.md` — هذه الخطة هي **تفصيل تنفيذي إضافي** لتلك المهام تحديداً، موجَّه لإعادة استخدام العمل الموجود في الحزمة A بدل إعادة كتابته من الصفر.

---

## 3. الفحص الفعلي: ماذا يُستخرَج من كل حزمة، وماذا يُهمَل

### 3.1 من الحزمة B — يُستخرَج فقط (لا كود، عقد فقط)

| المصدر | الاستخدام |
|---|---|
| `INTERFACE_CONTRACT_OUTBOX.md` | التوقيع الحرفي لـ`enqueue_event(session, *, event_name, payload, aggregate_id)` — **مصدر الحقيقة الوحيد للتوقيع** |
| `outbox_models.py` (داخل Track1) | **مطابق فعلياً** لـ`outbox_models.py` الموجود أصلاً في قاعدة v8 نفسها (خارج أي حزمة) — لا تغيير، لا استخراج مطلوب |

**كل شيء آخر في الحزمة B يُهمَل صراحة:**
- `DELIVERY_CARD_TASK_06.md` (داخل Track1) — يصف تصميماً قديماً متروكاً يناقض `README_المهمة.md` في نفس المجلد. **لا يُستخدَم، ويُوصى بحذفه من أي حزمة مستقبلية لتفادي تضليل لاحق.**
- Track2 (`sales_use_cases.py`) — **مطابق بايتاً** للنسخة قبل بدء العمل. لا شيء يُستخرَج.
- Track3 (`fiscal_period_use_cases.py`) — **مطابق بايتاً** لنسخة ما قبل Task #10 أصلاً. لا شيء يُستخرَج، بل هو تراجع لو دُمِج.

### 3.2 من الحزمة A — يُستخرَج بعد "تفكيك" (Business Logic فقط، لا الوصلة)

| الملف | ما يُستخرَج (منطق صافٍ) | ما يُرفَض (وصلة مخالفة للعقد) |
|---|---|---|
| `fiscal_period_use_cases.py` | `_post_closing_entry()`, `_closing_net_by_account()`, `RetainedEarningsAccountMissingError`, `FiscalPeriodAlreadyClosedError`, فحص `is_closed`, نقل الصافي لحساب `3200` | استدعاء `self._event_bus.publish(self._session, "FiscalPeriodClosed", ...)` و`dispatch_pending` — **يُستبدَل بالكامل** بـ`enqueue_event(...)` |
| `sales_use_cases.py` | `_NullWorkflowPort`, `InvoiceApprovalPendingError`, `InvoiceApprovalRejectedError`, `StartManagerApprovalForSalesInvoiceUseCase` (المنطق الداخلي: فحص `requires_manager_approval`, استدعاء `workflow_port.ensure_approval_started`), فحص `approval_state` في `PostSalesInvoiceUseCase.execute()` | كل استدعاء `event_bus.publish(self._session, ...)` و`event_bus.dispatch_pending(...)` — **يُستبدَل** بـ`enqueue_event(...)` |
| `invoices_router.py` | حقن `WorkflowPortAdapter(session)` في مسار `/post`، معالجة `InvoiceApprovalPendingError`/`InvoiceApprovalRejectedError` بـ409 | لا شيء يُرفَض — هذا الملف **لا يستدعي** `event_bus`/`outbox` مباشرة، يبقى كما هو حرفياً |
| `purchasing/infrastructure/event_handlers.py` (ملف جديد أُنشئ في A) | **كامل الملف يُستخرَج بلا تعديل** — يعالج ثغرة `ModuleNotFoundError` حقيقية غير متعلقة بتصميم Outbox إطلاقاً (كان الملف مفقوداً من `main` أصلاً) |
| `event_bus.py` | **لا شيء يُستخرَج — الملف بأكمله يُرفَض.** يخالف `TASK-06-01`/`Files الممنوع لمسها` في الخطة الرئيسية صراحة (العقد الرسمي يمنع تعديل `event_bus.py`، ويبقيه بتوقيعه القديم `publish(event_name, payload)` بلا `session`) |
| `outbox_worker.py` (من A) | **يُستخدَم كنقطة انطلاق فقط** — منطقه (استطلاع دوري، backoff أسّي، `max_attempts=8`) صحيح ومطابق لتصميم `TASK-06-02`، لكن يحتاج تعديلاً واحداً: يستدعي حالياً `event_bus.dispatch_pending(session)` (دالة لم تعد موجودة في `event_bus.py` الأصلي/الصحيح) — **يُستبدَل الاستدعاء الداخلي** بمنطق قراءة outbox + `get_event_bus().publish(event_name, payload)` مباشرة (التوقيع القديم الصحيح، بلا `session`) |
| `redis_bridge.py` | البنية العامة (استطلاع Redis Pub/Sub، مغلَّف JSON) صحيحة | استدعاءات `event_bus.publish(session, ...)`/`dispatch_pending` — **تُستبدَل** بـ`enqueue_event(...)` + منطق تسليم يستخدم `outbox.py` الجديد |
| `main.py` | سطرا `start_outbox_worker()`/`stop_outbox_worker()` في `lifespan`، بعد `set_event_bus()` — **يُستخرَجان بلا تعديل**، الترتيب صحيح | لا شيء آخر يُرفَض من هذا الملف |
| `test_event_bus_isolation.py` | **يُرفَض بالكامل** — مبني على افتراض أن `event_bus.publish()` نفسه يكتب Outbox، وهذا مخالف للعقد الرسمي. **يُعاد لنسخته الأصلية قبل أي تعديل** (لأن `event_bus.py` نفسه يعود لتصميم #6-S1 الأصلي بلا outbox داخله) |
| `test_redis_event_bridge.py` | **يُرفَض بالكامل** لنفس السبب — يُعاد بناؤه لاحقاً ضمن `TASK-06-04` بمنطق مختلف (اختبار `redis_bridge.py` المُعاد توصيله) |

---

## 4. خطة الدمج التفصيلية (MERGE-TASKS، تُنفَّذ بترتيب `TASK-06→10∥12` من الخطة الرئيسية)

### MERGE-06-01 — بناء `outbox.py` الفعلي (لم يوجد في أي من الحزمتين)

**المصدر:** لا يوجد كود مصدر جاهز في أي حزمة — **العقد فقط** من `INTERFACE_CONTRACT_OUTBOX.md` (الحزمة B). يُبنى من الصفر بالتوقيع الحرفي.

**لماذا لا يُستخرَج من الحزمة A:** منطق كتابة outbox في A موجود *داخل* `event_bus.py.publish()` (توقيع `publish(session, event_name, payload)` بلا `aggregate_id`) — **توقيع مختلف عن العقد الرسمي** (الذي يتطلب `aggregate_id` صراحة ويفصل الدالة في ملف مستقل). لا يمكن نسخه حرفياً، فقط الاستفادة من فكرة "لا commit داخلي" و"`next_attempt_at` صريحة غير NULL" (درسان مستفادان فعلياً من تجربة A، رغم رفض الكود نفسه).

**Files:** `platform_core/outbox.py` (جديد).

**التفاصيل الكاملة:** مطابقة لـ`TASK-06-01` في `ALQAIM_V2_MASTER_EXECUTION_PLAN.md` — لا تكرار هنا.

---

### MERGE-06-02 — إعادة توصيل `outbox_worker.py` من A

**المصدر:** `outbox_worker.py` من الحزمة A — **إعادة استخدام 90% من المنطق**، مع تعديل نقطة الاتصال الوحيدة.

**التعديل المطلوب تحديداً:**
```python
# في نسخة A (مرفوض):
async def _run_once() -> None:
    async with AsyncSessionLocal() as session:
        dispatched = await event_bus.dispatch_pending(session)   # ← هذه الدالة لم تعد موجودة

# في النسخة المُعاد توصيلها (مطلوب):
async def _run_once() -> None:
    async with AsyncSessionLocal() as session:
        dispatched = await outbox.dispatch_pending(session)      # ← من outbox.py الجديد (MERGE-06-01)،
                                                                    #   وليس من event_bus
```
باقي الملف (`POLL_INTERVAL_SECONDS=15`, `_poll_loop`, `start_outbox_worker`/`stop_outbox_worker`) **يُنقَل حرفياً بلا تعديل** — هذا الجزء صحيح فعلياً في A ولا علاقة له بموقع دالة `dispatch_pending`.

**Files:** `platform_core/outbox_worker.py`.

---

### MERGE-06-03 — رفض `event_bus.py` المُعاد كتابته، استعادة النسخة الأصلية (#6-S1)

**القرار:** `event_bus.py` من الحزمة A **لا يُدمَج إطلاقاً**. يبقى `event_bus.py` بتصميمه الأصلي (DI عبر contextvars فقط، `publish(event_name, payload)` بلا `session`) — **كما كان قبل أي عمل في هذه المحادثة**، مطابقاً لِـ`README_المهمة.md` (الحزمة B، داخل Track1): *"أُغلقت في Task #6-S1، لا تُعاد فتحها"*.

**أثر هذا القرار على باقي ملفات A:** كل استدعاء `event_bus.publish(session, ...)` أو `event_bus.dispatch_pending(...)` في أي ملف آخر من A (fiscal، sales، redis_bridge) **باطل تلقائياً** ويجب استبداله — هذا بالضبط موضوع `MERGE-10-01`/`MERGE-12-01`/`MERGE-06-04` أدناه.

---

### MERGE-06-04 — إعادة توصيل `redis_bridge.py` من A

**المصدر:** البنية العامة من A (استطلاع Redis، فك JSON، إعادة البث) — **صحيحة وتُستخرَج**.

**التعديل المطلوب:**
```python
# مرفوض (A):
async with AsyncSessionLocal() as session:
    await event_bus.publish(session, event_name, payload)
    await session.commit()
    await event_bus.dispatch_pending(session)

# مطلوب (بعد إعادة التوصيل):
async with AsyncSessionLocal() as session:
    await outbox.enqueue_event(session, event_name=event_name, payload=payload,
                                aggregate_id=payload.get("invoice_id") or payload.get("draft_id") or "unknown")
    await session.commit()
    await outbox.dispatch_pending(session)
```
**⚠️ نقطة تحتاج قراراً صريحاً غير موجود في أي من الحزمتين:** ما هو `aggregate_id` الصحيح لحدث قادم من Redis (مصدره `ai-platform`، خارج أي معاملة أعمال محلية)؟ **غير مثبت في أي مصدر — يحتاج تحديد صريح عند التنفيذ الفعلي، وليس افتراضاً هنا.**

**Files:** `platform_core/redis_bridge.py`.

---

### MERGE-06-05 — استعادة سطري `main.py` من A

**المصدر:** سطرا `start_outbox_worker()`/`stop_outbox_worker()` في `lifespan`، بعد `set_event_bus()` — **يُنقَلان حرفياً بلا أي تعديل**، الترتيب والاستيراد صحيحان فعلياً في A.

**Files:** `main.py`.

---

### MERGE-10-01 — إعادة توصيل منطق الإقفال المحاسبي (من A، فوق `outbox.py` الجديد)

**المصدر:** منطق `fiscal_period_use_cases.py` بالكامل من A **باستثناء** استدعاء النشر.

**التعديل المطلوب تحديداً (السطر الوحيد الذي يتغيّر فعلياً):**
```python
# مرفوض (A):
await self._event_bus.publish(self._session, "FiscalPeriodClosed", {...})
await self._session.commit()
await self._event_bus.dispatch_pending(self._session)

# مطلوب:
await outbox.enqueue_event(self._session, event_name="FiscalPeriodClosed",
                            payload={...}, aggregate_id=str(period.id))
await self._session.commit()
await outbox.dispatch_pending(self._session)
```
**كل شيء آخر في الملف (`_post_closing_entry`, `_closing_net_by_account`, معالجة `RetainedEarningsAccountMissingError`, `FiscalPeriodAlreadyClosedError`, فحص `is_closed`) يُنقَل حرفياً بلا أي تعديل — هذا هو "استخراج المنطق الصافي" المقصود في البند 3.2.**

**Files:** `fiscal_period_use_cases.py`، `fiscal_periods_router.py` (لا تعديل متوقَّع — كان يمرّر `event_bus` بالفعل بشكل يبقى متوافقاً طالما الحقن نفسه صحيح).

**Tests:** مطابقة لِـ`TASK-10-01` في الخطة الرئيسية — الاختبارات المطلوبة نفسها، لا تغيير.

---

### MERGE-12-01 — إعادة توصيل منطق موافقة المدير (من A، فوق `outbox.py` الجديد)

**المصدر:** منطق `sales_use_cases.py` بالكامل من A **باستثناء** نقطتَي النشر.

**التعديل المطلوب (نقطتان فقط):**
```python
# 1) في CreateSalesInvoiceUseCase.execute() — مرفوض (A):
await event_bus.publish(self._session, "SalesInvoiceCreated", {...})
# مطلوب:
await outbox.enqueue_event(self._session, event_name="SalesInvoiceCreated",
                            payload={...}, aggregate_id=str(invoice.id))

# 2) في PostSalesInvoiceUseCase.execute() — مرفوض (A):
await event_bus.publish(self._session, "InvoicePosted", {...})
...
await event_bus.dispatch_pending(self._session)
# مطلوب:
await outbox.enqueue_event(self._session, event_name="InvoicePosted",
                            payload={...}, aggregate_id=str(invoice.id))
...
await outbox.dispatch_pending(self._session)
```
**كل شيء آخر (`_NullWorkflowPort`, `InvoiceApprovalPendingError`, `InvoiceApprovalRejectedError`, `StartManagerApprovalForSalesInvoiceUseCase` بتوقيعها المُصحَّح `__init__(workflow_port)` + `execute(payload)` — راجع الملاحظة أدناه — وفحص `approval_state` في `PostSalesInvoiceUseCase`) يُنقَل حرفياً.**

**⚠️ ملاحظة دمج داخلية مهمة (اكتُشفت أثناء بناء A نفسها، تنطبق هنا أيضاً):** `StartManagerApprovalForSalesInvoiceUseCase` يجب أن تطابق التوقيع الذي يتوقعه `modules/sales/infrastructure/event_handlers.py` الموجود مسبقاً في قاعدة v8 (خارج أي حزمة): `__init__(workflow_port)` **بلا** `session`، وميثود `execute(payload)` **وليس** `handle(payload)`. هذا صحيح فعلاً في نسخة A النهائية (بعد تصحيح ذاتي حدث أثناء بنائها) — يُنقَل كما هو.

**Files:** `sales_use_cases.py`، `invoices_router.py` (ينتقل بلا تعديل — لا يستدعي `event_bus`/`outbox` مباشرة).

**Tests:** مطابقة لِـ`TASK-12-01` في الخطة الرئيسية.

---

### MERGE-06-06 — إعادة بناء اختبارات Outbox من الصفر (لا نقل من A)

**القرار:** `test_event_bus_isolation.py` و`test_redis_event_bridge.py` من الحزمة A **تُرفَضان بالكامل** ولا تُنقَلان — كلتاهما مبنيتان على افتراض أن `event_bus.publish()` يكتب Outbox مباشرة، وهذا لم يعد صحيحاً بعد `MERGE-06-03`.

**الإجراء:** `test_event_bus_isolation.py` **يُعاد لنسخته الأصلية** (ما قبل أي تعديل في هذه المحادثة — يختبر فقط عزل الـcontextvars، لا علاقة له بـOutbox أصلاً). اختبارات Outbox الفعلية (rollback حقيقي، retry، delivered-twice) تُبنى من الصفر في ملف جديد `test_outbox_pattern.py`، مطابقة تماماً لمواصفات `TASK-06-04` في الخطة الرئيسية.

`test_redis_event_bridge.py` يُعاد بناؤه لاحقاً ضمن نفس `TASK-06-04`، بمنطق يطابق `MERGE-06-04` أعلاه (`outbox.enqueue_event` بدل `event_bus.publish`).

---

## 5. جدول الملفات النهائي (خارطة دمج كاملة، ملف بملف)

| الملف | القرار | المصدر |
|---|---|---|
| `platform_core/outbox.py` | 🆕 يُبنى من الصفر | العقد (B) فقط، لا كود مصدر |
| `platform_core/outbox_worker.py` | ♻️ إعادة توصيل (تعديل سطر واحد) | A |
| `platform_core/event_bus.py` | ⛔ **لا دمج — يبقى الأصلي (#6-S1)، لا من A ولا من B** | لا شيء (حالة ما قبل أي تعديل) |
| `platform_core/redis_bridge.py` | ♻️ إعادة توصيل (3 أسطر) | A |
| `modules/purchasing/infrastructure/event_handlers.py` | ✅ نقل حرفي بلا تعديل | A |
| `modules/accounting/application/use_cases/fiscal_period_use_cases.py` | ♻️ إعادة توصيل (سطر نشر واحد) | A |
| `modules/accounting/presentation/routes/fiscal_periods_router.py` | ✅ لا تعديل | A (بلا تغيير أصلاً) |
| `modules/sales/application/use_cases/sales_use_cases.py` | ♻️ إعادة توصيل (نقطتا نشر) | A |
| `modules/sales/presentation/routes/invoices_router.py` | ✅ نقل حرفي بلا تعديل | A |
| `main.py` | ✅ نقل حرفي (سطرا lifespan فقط) | A |
| `tests/integration/test_event_bus_isolation.py` | ⛔ رفض نسخة A، استعادة الأصلية | لا شيء (حالة ما قبل أي تعديل) |
| `tests/integration/test_redis_event_bridge.py` | 🆕 إعادة بناء كاملة | جديد، ضمن TASK-06-04 |
| `tests/integration/test_outbox_pattern.py` | 🆕 جديد بالكامل | جديد، ضمن TASK-06-04 |
| Track1/2/3 (الحزمة B بأكملها ما عدا العقد) | ⛔ إهمال كامل، لا نقل لأي ملف | — |
| `DELIVERY_CARD_TASK_06.md` (داخل Track1) | ⛔ يُحذَف/يُؤرشَف — يناقض `README_المهمة.md` في نفس المجلد | — |

---

## 6. ترتيب التنفيذ (عند اعتماد هذه الخطة، يتبع `EXECUTION ORDER` في الخطة الرئيسية حرفياً)

```text
MERGE-06-01 → MERGE-06-02 → MERGE-06-03 → MERGE-06-04 → MERGE-06-05 → MERGE-06-06
   → GATE-01 (كما هو معرَّف في الخطة الرئيسية، بلا تعديل)
   → MERGE-10-01 ∥ MERGE-12-01   (Controlled Parallel، بلا لمس outbox.py، كما في TASK-10-01/TASK-12-01)
   → GATE-02
```

**لا فرق عن `EXECUTION ORDER` في الخطة الرئيسية بعد `GATE-01`** — هذه الخطة تحل محل `TASK-06-01..04` فقط بنسخة "إعادة توصيل" بدل "بناء من الصفر"، لتوفير الوقت المُستثمَر فعلياً في الحزمة A. لا تُدخِل أي مسار تنفيذ جديد لم يكن في الخطة الرئيسية.

---

## 7. لماذا هذا أفضل من تجاهل الحزمة A والبناء من الصفر بالكامل

المنطق التجاري في A (`_post_closing_entry`, `StartManagerApprovalForSalesInvoiceUseCase`, معالجة idempotency+approval معاً) **مطابق فعلياً** لما يطلبه `TASK-10-01`/`TASK-12-01` في الخطة الرئيسية — الفحص المصدري (`_CONFLICTS/version_task10_di_refactor.py` و`version_task12_workflow_approval.py`) هو نفسه ما بُني عليه A أصلاً. **إعادة الكتابة من الصفر ستنتج نفس المنطق تقريباً، بجهد مكرَّر بلا داعٍ.** الفرق الوحيد الحقيقي بين A والعقد الرسمي هو **موقع دالة النشر** (داخل `event_bus.py` مقابل `outbox.py` منفصل) — وهذا فرق ميكانيكي محدود (سطر إلى ثلاثة أسطر لكل نقطة نشر)، وليس فرقاً في التصميم المحاسبي/الموافقاتي نفسه.
