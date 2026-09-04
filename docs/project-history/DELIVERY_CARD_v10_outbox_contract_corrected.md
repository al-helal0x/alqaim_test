# تسليم v10 — إعادة بناء تنفيذ #6×#11×#12×#10 وفق العقد المجمَّد

## ⚠️ لماذا لم يكن "دمج v9 + files__5_" مباشرة كافياً
`AlQaim_V2_v9_conflict_resolved.zip` و`files__5_.zip` **ليسا نظيرين
مستقلين قابلين للدمج الحرفي** — كلاهما مبنيّ فوق نفس القاعدة
(`AlQaim_V2_merged_local_test_v8.zip`، الموجودة داخل الحزمة الثانية)، لكن
v9 استخدم معمارية سبق أن **نُسخت صراحة** في التوزيع الجديد
(`INTERFACE_CONTRACT_OUTBOX.md`) قبل أن يُوزَّع على الأعضاء الثلاثة:

| | v9 (القديم، المرفوض الآن) | العقد المجمَّد (files__5_، المعتمَد) |
|---|---|---|
| مكان منطق Outbox | داخل `event_bus.py` نفسه | ملف منفصل جديد `outbox.py` |
| `event_bus.py` | أُعيد فتحه ودُمج فيه Outbox | **يبقى مغلقاً** (Task #6-S1 فقط)، لا يُلمس إطلاقاً |
| نشر الحدث | `event_bus.publish(session, ...)` + `dispatch_pending(session)` فوري | `enqueue_event(session, event_name=, payload=, aggregate_id=)` ثم Worker خلفي مستقل يستطلع لاحقاً |
| `enqueue_event()` | غير موجود إطلاقاً في الكود | نقطة الدخول الوحيدة المسموحة من أي use case |

كل من Track2 وTrack3 في `files__5_` يحذّران صراحةً: أي نسخة مرجعية تستخدم
`event_bus.publish(session, ...)` القديم "**غير صحيحة الآن**". لذلك بُنيت
هذه النسخة من الصفر فوق v8 النظيفة، لا فوق v9.

## ما بُنيَ فعلياً (الأعضاء الثلاثة لم يسلّموا نواتج جاهزة — فقط حزم مهام
## بملف أساس + تعليمات؛ التنفيذ الفعلي تمّ هنا)

**Track 1 — Outbox Core:**
- `platform_core/outbox.py` (جديد) — `enqueue_event()` بالتوقيع المجمَّد حرفياً
- `platform_core/outbox_worker.py` (جديد) — استطلاع كل ثانيتين، Exponential Backoff عند الفشل (حد أقصى 5 دقائق)، لا يلمس `event_bus.py`
- `main.py` — `start_outbox_worker()`/`stop_outbox_worker()` بنفس نمط `redis_bridge` الموجود مسبقًا
- `event_bus.py` و`redis_bridge.py` — **بلا أي تعديل** (طابقا v8 حرفياً — تحقّق `diff` أدناه)

**فجوة اكتُشفت ولم تكن جزءاً من أي Track (الثلاثة ممنوعون من لمس migrations):**
عقد `enqueue_event()` يفرض `aggregate_id` إلزامياً، لكن جدول `outbox_events`
(في `platform_20260809_0002`) لا يحتوي عموداً له. أُضيفت migration تالية
`platform_20260812_0003_outbox_events_add_aggregate_id.py` (عمود Nullable
+ فهرس) بدل تعديل migration مُطبَّقة أصلاً.

**Track 2 — Sales:** `sales_use_cases.py` أُعيد بناؤه فوق أساس Track2
الصحيح (Idempotency #11) + دمج منطق موافقة المدير (#12) من
`version_task12_workflow_approval.py` + استبدال **كل** نداءات
`event_bus.publish()` (وجدت اثنين: `SalesInvoiceCreated` و`InvoicePosted`،
ليس واحداً فقط كما ورد في الفجوة الموثَّقة أصلاً) بـ `enqueue_event()` قبل
الـ commit. كما تم وصل `invoices_router.py` (`WorkflowPortAdapter` + معالجة
409) — هذا الجزء خارج نطاق Track2 نفسه لكنه توصيل ضروري وليس له علاقة
بالـ Outbox، فأعدت استخدامه من v9 مباشرة مع **تصحيح خطأ ترتيب `except`**
كان موجوداً هناك: `except (..., ValueError)` جاء قبل
`except (InvoiceApprovalPendingError, InvoiceApprovalRejectedError)` —
بما أن الصنفين يرثان من `ValueError`، كانا سيُلتقَطان بصمت كـ 422 بدل 409
ولن يصل الشرط الثاني إطلاقاً. أُعيد الترتيب.

**Track 3 — Fiscal Period:** `fiscal_period_use_cases.py` أُعيد بناؤه فوق
`version_task10_di_refactor.py` (أساس #10 الصحيح) + استبدال
`event_bus.publish()` المباشر بعد الـ commit بـ `enqueue_event()` قبله.

**قرار مقصود لم يُنفَّذ (وثّقته بدل تنفيذه بصمت):** README حزمة Track3
تسمح بحذف معامل `event_bus: EventBus` غير المستخدَم من `__init__`. لم
أحذفه — حذفه يكسر توقيع الاستدعاء في `fiscal_periods_router.py` و8 مواضع
اختبار في `test_period_closing.py`/`test_accounting_posting.py`، وتحديثها
بأمان يحتاج مراجعة كل اختبار (هل يفترض نشراً فورياً؟) وليس مجرد حذف
معامل. تحقَّقتُ فعلياً أن لا اختبار حالي يقرأ من `test_event_bus` بعد
`ClosePeriodUseCase` (`grep` أدناه) — فالمعامل الآن حَرْفي التوقيع فقط
(vestigial)، موثَّق بتعليق داخل الكود.

**فجوة أخرى غير مرتبطة بأي Track، مُصلَحة من v9 مباشرة:**
`modules/purchasing/infrastructure/event_handlers.py` كان مفقوداً فعلياً
من شجرة v8 (يستورده `main.py` عند الإقلاع → `ModuleNotFoundError` فوري) —
غير مرتبط بعقد Outbox إطلاقاً، أعدت الملف كما هو من v9.

## التحقق الفعلي المُنجَز (وحدوده)
- ✅ `py_compile` على كل ملف في الشجرة (باستثناء migrations القديمة غير المُعدَّلة) — بلا خطأ
- ✅ `pyflakes` على كل ملف في الشجرة (باستثناء tests) — صفر أسماء غير معرَّفة (هذا ما كشف نداء `event_bus.publish()` المنسي الثاني في `InvoicePosted`)
- ✅ `diff -rq` كامل ضد v8 — فقط 9 ملفات تغيّرت، بالضبط المتوقَّع (`event_bus.py`/`redis_bridge.py` غير مُتأثرين)
- ✅ راجعتُ يدوياً `tests/integration/test_sales_invoice_manager_approval.py` الموجود مسبقاً — توقيعات `StartManagerApprovalForSalesInvoiceUseCase`/`PostSalesInvoiceUseCase` التي بنيتها تطابقه حرفياً
- ✅ `grep` تأكيدي: لا اختبار حالٍ يعتمد على نشر فوري لـ `InvoicePosted`/`SalesInvoiceCreated`/`FiscalPeriodClosed` (لذا نقل النشر إلى Outbox لن يكسر أي اختبار قائم)
- ❌ **لم يُشغَّل pytest فعلياً على Postgres حقيقي** — لا بيئة تشغيل متاحة هنا. هذا يبقى الفحص الحاسم النهائي قبل أي دمج فعلي، تماماً كما في التسليمات السابقة.
- ❌ لم أكتب اختبار جديد لـ `outbox_worker.py` نفسه (الاستطلاع/Backoff) — لا يوجد اختبار له إطلاقاً حالياً في أي من الحزمتين.

## معيار قبول عام — الحالة
- `alembic heads` → رأس واحد (`platform_20260812_0003` هو الأحدث فوق `platform_20260809_0002` فوق ما قبلها) — لم يُشغَّل alembic فعلياً هنا، بلا بيئة Postgres، لكن السلسلة سليمة بنيوياً (`down_revision` صحيح، لا تفرّع)
- `alembic upgrade head` من Fresh DB — **غير مُتحقَّق فعلياً** (نفس القيد أعلاه)
