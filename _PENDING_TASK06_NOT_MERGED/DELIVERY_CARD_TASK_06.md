> ⚠️ **وثيقة مؤرشَفة — تصف تصميماً مرفوضاً، لا التصميم الحالي المعتمد.**
> هذه البطاقة تصف نسخة `event_bus.py` مُعادة الكتابة بتوقيع
> `publish(session, event_name, payload)` تكتب Outbox مباشرة داخلها.
> هذا التصميم **رُفِض رسمياً** (قرار `MERGE-06-03` في
> `ALQAIM_V2_PACKAGE_MERGE_PLAN_REVISED.md`): `event_bus.py` الفعلي في
> الشجرة الحية أُبقي بتصميمه الأصلي من Task #6-S1
> (`publish(event_name, payload)` بلا `session`، DI عبر `contextvars`)،
> والـOutbox مفصول تماماً في `platform_core/outbox.py`
> (`enqueue_event(session, *, event_name, payload, aggregate_id)`).
> **مصدر الحقيقة الحالي:** `platform_core/outbox.py` +
> `platform_core/outbox_worker.py` الفعليَّين في الشجرة الحية، لا هذا
> الملف. أُبقي هذا الملف كاملاً بلا حذف لقيمته التاريخية (يوثّق مشاكل
> حقيقية اكتُشفت أثناء البناء الأول — تسلسل الأحداث/الـcommit،
> واكتشاف Decimal/JSON — لا تزال دروساً صالحة)، مع هذا التنبيه فقط
> ليمنع اعتماد أي قارئ لاحق على توقيع `event_bus.py` الموصوف أدناه
> كأنه ساري حالياً.

---

## بطاقة تسليم المهمة (النص الأصلي، بلا تعديل — مرجعي فقط)

- رقم المهمة: #6
- المسار: 🔐 Platform
- الفرع: task/06-event-bus-outbox-pattern
- مبني على commit: <hash — يُملأ عند فتح PR فعلي>

### الملفات/المجلدات التي تم إنشاؤها (جديدة)
- `apps/core-api/platform_core/outbox_models.py` — موديل `OutboxEvent` (event_name, payload JSONB, status, attempts, last_error, dispatched_at, next_attempt_at)
- `apps/core-api/migrations/versions/platform_20260808_0003_outbox_events.py` — migration جدول `outbox_events`
- `apps/core-api/platform_core/outbox_worker.py` — Worker دوري (asyncio task، استطلاع كل 15 ثانية) لإعادة محاولة الأحداث غير المُسلَّمة
- `apps/core-api/tests/integration/test_outbox_pattern.py` — 6 اختبارات جديدة للنمط

### الملفات/المجلدات التي تم تعديلها
- `apps/core-api/platform_core/event_bus.py` — إعادة بناء كاملة: `publish(session, event_name, payload)` يكتب outbox ضمن نفس المعاملة دون commit، و`dispatch_pending(session)` يُسلِّم الأحداث المستحقة مع Exponential Backoff عند الفشل ووسم "failed" بعد `max_attempts` (افتراضياً 8)
- `apps/core-api/platform_core/redis_bridge.py` — الحدث الوارد من Redis يُكتَب الآن عبر outbox (جلسة DB حقيقية) ثم يُسلَّم فوراً، بدل البث المباشر القديم
- `apps/core-api/main.py` — تشغيل/إيقاف `outbox_worker` ضمن `lifespan` (سطرين، نفس نمط `redis_bridge`)

### ⚠️ تعديلات خارج حدود القسم 4.2 المعلَنة — ضرورية تقنياً، تحتاج تنسيقاً مسبقاً فعلياً
القسم 4.2 يحصر مهمة 6 في "وحدة event_bus (migration + Worker/Job)". لكن معيار القبول
("الأحداث تُكتَب ضمن نفس معاملة قاعدة البيانات") لا يمكن تحقيقه دون تعديل نقاط
الاستدعاء الثلاث التي تنشر أحداثاً فعلياً — وقد اكتُشفت مشكلة حقيقية إضافية أثناء
الاختبار الفعلي (وليس افتراضاً):

- `modules/sales/application/use_cases/sales_use_cases.py` — نشر `InvoicePosted` انتقل إلى ما قبل الـ commit (كان بعده).
- `modules/accounting/application/use_cases/fiscal_period_use_cases.py` — نفس الشيء لحدث `FiscalPeriodClosed`.
- `modules/payments/application/use_cases/payments_use_cases.py` — نفس الشيء لحدث `PaymentRecorded`، **وتحويل `amount` من `Decimal` إلى `str`** في الحمولة: اكتُشف أثناء تشغيل `tests/integration/test_purchasing_payments_flow.py` فعلياً أن `Decimal` غير قابل للتسلسل إلى JSON (outbox_events.payload الآن JSONB حقيقي، وليس تمريراً مباشراً في الذاكرة كما كان سابقاً) — فشل `StatementError: Object of type Decimal is not JSON serializable`.
- `modules/purchasing/infrastructure/event_handlers.py` (`apply_payment_to_invoice`) — نتيجة مباشرة للنقطة السابقة: المستهلك كان يفترض أن `amount` تصل `Decimal`؛ عُدِّل ليحوّلها `Decimal(str(...))` عند الاستلام بدل الاعتماد على النوع الوارد.

**يجب أن يوافق مالكو مسارات sales/accounting/payments/purchasing على هذه التعديلات
تحديداً قبل الدمج** — لم يُفترَض ذلك، بل هو ذكر صريح وفق البند 4.1.4 من البروتوكول.

### الاختبارات المضافة/المعدَّلة
- `apps/core-api/tests/integration/test_outbox_pattern.py` (جديد) — يغطي: كتابة outbox بلا تسليم فوري، الذرّية الفعلية (rollback يُفقِد الحدث تماماً)، تسليم ناجح ووسم dispatched، إعادة محاولة مع backoff عند فشل مؤقت، وسم "failed" بعد تجاوز الحد الأقصى، حدث بلا مشتركين يُسلَّم بنجاح فوراً.
- `apps/core-api/tests/integration/test_redis_event_bridge.py` — محدَّث ليطابق توقيع `publish(session, ...)` الجديد + `dispatch_pending` صريحة.
- `apps/core-api/tests/integration/test_redis_bridge_real_modules.py` — أُضيف تحقق `_database_available()` صريح: هذا الاختبار أصبح يحتاج Postgres حقيقياً متاحاً (وليس Redis فقط) لأن `redis_bridge.py` صار يكتب عبر outbox — يُتخطى تلقائياً بدل الفشل إن لم تتوفر قاعدة بيانات.
- `apps/core-api/tests/integration/conftest.py` — إضافة استيراد `platform_core.outbox_models` لتسجيل جدول outbox_events في بيئة اختبار SQLite.

### Migrations
- `platform_20260808_0003_outbox_events.py` — جدول `outbox_events` (revision يبني فوق آخر رأس فعلي في السلسلة: `wfna_20260808_0002`)

### التوثيق المحدَّث
- لا يوجد بعد — تحديث `contracts.md` (توثيق شكل outbox_events كعقد داخلي) مؤجَّل عمداً لمهمة 18 كما هو مخطَّط.

### اعتماديات هذه المهمة
- تعتمد على: لا شيء (مستقلة تقنياً)، لكنها تلمس ملفات من مسارات AI↔Purchasing (مهمة 7/8 القادمة ستستخدم نفس `event_bus.publish` الجديد لنشر `InvoiceDraftReady` — يجب على منفذ مهمة 7 استخدام التوقيع الجديد `publish(session, event_name, payload)` مباشرة، وليس التوقيع القديم)
- تُبنى عليها: مهمة 7 (توقيع `publish` الجديد)، مهمة 18 (توثيق العقد في contracts.md)

### التحقق المحلي قبل التسليم
- [x] تشغيل الاختبارات محلياً وناجحة — `79 passed, 2 skipped` (المتخطّيان يحتاجان Redis فعلياً، غير متعلقين بهذه المهمة)
- [x] `ruff check` نظيف تماماً على كل الملفات الجديدة/المعدَّلة الخاصة بهذه المهمة تحديداً (تحقَّق يدوياً؛ `ruff check .` على كامل المستودع يفشل مسبقاً بـ278 مخالفة موروثة كما هو موثَّق في `.github/workflows/ci.yml` — خارج نطاق هذه المهمة، مهمة 4)
- [x] `lint-imports` (import-linter) ناجح — "Domain لا يعتمد على Infrastructure أو Presentation: KEPT"
- [ ] لا تعديل خارج المسارات المصرَّح بها في القسم 4.2 — **مخالَف عمداً وموثَّق أعلاه**، ضرورة تقنية غير قابلة للتفادي، يحتاج موافقة صريحة من مالكي المسارات الأخرى
- [x] كل بند في عمود "المخرج" الخاص بالمهمة محقَّق فعلياً: جدول `outbox_events` ✅، الكتابة ضمن نفس المعاملة ✅ (مُثبَتة باختبار rollback فعلي) ✅، Worker دوري لإعادة محاولة الأحداث غير المُسلَّمة ✅
