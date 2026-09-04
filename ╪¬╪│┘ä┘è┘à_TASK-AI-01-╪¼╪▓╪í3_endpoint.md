# تسليم — جزء ثالث من `TASK-AI-01`: الـ Endpoint الفعلي + تصحيح ملاحظة سابقة

**التاريخ:** 2026-08-13، فوق نفس commit، بعد الجزأين الأول والثاني مباشرة
(130 passed, 4 skipped بعد هذا التسليم — كان 120 قبله).

## تصحيح صريح لملاحظة خاطئة في بطاقتَي التسليم السابقتين

كلا البطاقتين السابقتين ذكرتا أن الـEndpoint الفعلي متوقف على "قرارات بنية
تحتية غير محسومة (Base URL، مصادقة بين الخدمتين، معالجة timeout)". **هذا
غير دقيق** — عند الفحص الفعلي هذه المرة تبيَّن أن بوابة كاملة لـ`ai-platform`
**موجودة ومُطبَّقة فعلاً**:

- `platform_core/ai_gateway_client.py` — عميل httpx جاهز (`base_url` من
  `Settings.ai_platform_base_url`، timeout مضبوط).
- `presentation/routes/ai_proxy_router.py` — مسارات proxy فعلية تستخدمه،
  منها `GET /drafts/{draft_id}` تحديداً (نفس ما يحتاجه `TASK-AI-01`).

**الدرس:** الاعتماد على بطاقات تسليم سابقة (حتى لو كتبتُها أنا نفسي) بدل
إعادة الفحص الفعلي في كل مرة يُنتِج استنتاجات خاطئة — نفس المبدأ الذي
يُلزم به `تسليم_TASK-06-05.md` نفسه ("لا افتراض"). هذا التصحيح مكتوب صراحة
بدل السكوت عنه.

## ما نُفِّذ

### 1) Endpoint فعلي: `POST /purchase-invoices/ai-upload`

في `modules/purchasing/presentation/routes/purchase_invoices_router.py`
(إضافة فقط — صفر تعديل على المسارات الموجودة). يجلب المسودة عبر
`get_ai_platform_client()` الموجودة فعلاً (نفس نمط `ai_proxy_router.py`
حرفياً)، ثم يمرّرها لدالة التجميع أدناه. `DraftMappingError` → 422 صريح،
أخطاء الشبكة/404 من `ai-platform` تُمرَّر كما هي (503 لو تعذّر الوصول
تماماً) — بلا إنشاء فاتورة جزئية في كل الحالات.

### 2) دالة تجميع صرفة (Orchestration) — قابلة للاختبار الكامل بلا شبكة

`modules/purchasing/application/use_cases/resolve_purchase_invoice_from_ai_draft.py`
(جديد بالكامل) — تستقبل مسودة **جاهزة** (dict)، لا تجلبها بنفسها، وتُجمِّع
الجزأين المُسلَّمين سابقاً (`build_purchase_invoice_request_from_ai_draft`
+ `CreatePurchaseInvoiceFromAiDraftUseCase`).

**قرار عتبة الثقة لمطابقة المنتج:** بدل اختراع رقم جديد، أُعيد استخدام
**نفس** الرقم `0.92` المستخدَم فعلياً وحرفياً في `ai-platform` لمطابقة
المورد تلقائياً (`process_document_pipeline.py`) — اتساق مع سابقة قائمة في
نفس الكودبيس، موثَّق صراحة في الملف كإعادة استخدام لا قرار جديد. عتبة
سياسة رسمية معلَنة **تبقى مؤجَّلة** كما في البطاقتين السابقتين — هذا مجرد
تطبيق متحفِّظ يعيد استخدام قرار موجود بدل الانتظار بلا فعل شيء.

**⚠️ فجوة مكتشَفة أثناء الفحص (توثيق، لا افتراض):**
`extracted_payload["line_matches"]` في `ai-platform` تُبنى **فقط** إن كان
`known_products` غير فارغ وقت المعالجة — إن كان فارغاً، تبقى `[]` كاملة
بينما `lines` تبقى ممتلئة. **لا ضمان أن الطولين متساويان أو أن المحاذاة
بالـindex صحيحة.** القرار المتَّبع هنا متحفِّظ عمداً: عدم تساوي الطولين →
لا مطابقات إطلاقاً (يؤدي لرفض 422 صريح بدل فاتورة خاطئة صامتة) — نفس مبدأ
"لا إنشاء جزئي" المُلزَم في الخطة.

### 3) 🐛 خطأ حقيقي مُكتشَف ومُصحَّح (كان يمنع الـEndpoint من العمل، ويمنع
الـEndpoint الموجود أصلاً `POST /purchase-invoices` من العمل أيضاً)

عند اختبار الـEndpoint الجديد فعلياً عبر `main.app` (ASGITransport، وليس
استدعاء use case مباشرة)، فشل بخطأ pydantic: حقول `id`/`supplier_id`/
`purchase_order_id` في `PurchaseInvoiceResponse`/`PurchaseOrderResponse`
معرَّفة كـ`str`، لكن SQLAlchemy (`UUID(as_uuid=True)`) يُعيد كائنات
`uuid.UUID` فعلية — Pydantic v2 **لا يحوّلها تلقائياً**.

**تحقَّقت أن هذا خطأ موجود مسبقاً في `POST /purchase-invoices` نفسه** (لا
علاقة بهذا التسليم تحديداً) — كتبت اختبار HTTP مؤقت للـEndpoint القديم
فأعاد **نفس الخطأ بالضبط**. السبب: لم يوجد أي اختبار HTTP حقيقي عبر
Router فعلي لهذه الوحدة من قبل (فقط اختبارات use case مباشرة تتجاوز
pydantic validation كلياً) — تماماً كما يوثّق `shared_kernel/pydantic_types.py`
نفسه حرفياً كسبب وجوده: *"لم يظهر سابقاً لأن لا اختبار كان يمر فعلياً عبر
Router حقيقي."*

**الإصلاح:** الحل **موجود فعلاً وجاهز** في `shared_kernel/pydantic_types.py`
(`UUIDStr`) ومُستخدَم بالفعل في `catalog_dto.py` — لم يُطبَّق ببساطة على
`purchasing_dto.py`. غيّرت 6 حقول (`id`/`product_id`/`supplier_id`/
`purchase_order_id` عبر `PurchaseOrderLineResponse`/`PurchaseOrderResponse`/
`PurchaseInvoiceResponse`) من `str` إلى `UUIDStr` — **حقول Response DTOs
فقط، لا شيء في Request DTOs** (لا تحتاج تحويلاً، مُدخلة من العميل كـstr
أصلاً). إصلاح آمن، محدود، ومطابق تماماً لنمط مُثبَت في نفس المشروع.

## اختبارات

| الملف | العدد | يغطي |
|---|---|---|
| `test_resolve_purchase_invoice_from_ai_draft.py` | 6 | دالة التجميع الصرفة: مسودة صالحة، حالة غير `approved`، لا مورد مطابَق، ثقة منتج منخفضة، عدم تطابق طول `line_matches`، idempotency عبر التجميع |
| `test_purchase_invoice_ai_upload_endpoint.py` | 4 | **مستوى HTTP فعلي** عبر `main.app` (`ASGITransport`)، مع محاكاة حدود الشبكة الخارجية لـ`ai-platform` فقط (`httpx.MockTransport`) — إنشاء ناجح، رفض 422 بلا مورد، تمرير 404 من `ai-platform` كما هو، idempotency عند استدعاءين متتاليين لنفس `draft_id` |

**عن المحاكاة (mock) في اختبارات الـEndpoint:** الحد الوحيد المُحاكى هو
اتصال الشبكة الخارجي لـ`ai-platform` — نفس القيد الذي يجعل
`test_ai_gateway_proxy.py` الموجودة أصلاً **تُخطَّى تلقائياً** بلا خادم
حقيقي (`TEST_BASELINE.md`). محاكاة هذا الحد فقط (لا أي جزء من منطق
core-api نفسه) تتيح تغطية سلوك الـEndpoint الفعلي (routing، صلاحيات،
معالجة أخطاء) محلياً — اختبار حقيقي بخادم `ai-platform` فعلي يبقى مطلوباً
لاحقاً ضمن `TASK-AI-03` (E2E الكامل = `GATE-03`)، خارج نطاق هذا الجزء.

## التحقق الفعلي (لا افتراض)

```
python3 -m py_compile <كل الملفات الجديدة/المعدَّلة> main.py   → نجح على الجميع

pytest tests/integration/test_resolve_purchase_invoice_from_ai_draft.py -v
    → 6 passed

pytest tests/integration/test_purchase_invoice_ai_upload_endpoint.py -v
    → 4 passed

pytest tests/integration/ -q
    → 130 passed, 4 skipped, 0 failed
      (120 + 6 + 4 = 130 — لا صفر تراجع)

ruff check <الملفات الجديدة/المعدَّلة>
    → إصلاح تلقائي واحد (ترتيب import، لا علاقة بالمنطق) + مخالفات
      RUF001/RUF002 المعروفة سلفاً (رموز عربية غامضة)، لا فئة جديدة
```

## لم يُلمَس (عمداً)

- `CreatePurchaseInvoiceUseCase`, `CreatePurchaseInvoiceFromOrderUseCase`,
  `PostPurchaseInvoiceUseCase` — صفر تعديل منطقي (فقط DTO الاستجابة
  المشتركة أُصلِح، لا الـuse cases نفسها).
- `ai_proxy_router.py`, `ai_gateway_client.py` — صفر تعديل، استُخدِما كما هما.
- `apps/ai-platform/*` بالكامل — صفر تعديل.

## المتبقي فعلياً من `TASK-AI-01`

**قرار سياسة واحد فقط الآن:** عتبة الثقة الرسمية المُعلَنة لمطابقة
المنتج/المورد تلقائياً (يُعاد استخدام `0.92` حالياً باتساق، لكنه ليس
"قراراً" رسمياً موثَّقاً بعد — يحتاج صاحب قرار ليُعلَن كسياسة). لا شيء
تقني آخر متبقٍّ في `TASK-AI-01` نفسها.

**التالي منطقياً حسب الخطة:** `TASK-AI-02` (تأكيد أن فاتورة AI تمر بنفس
مسار الترحيل العادي — تكامل واختبار فقط، لا بناء جديد) ثم `TASK-AI-03`
(اختبار E2E الكامل = `GATE-03` نفسه — يحتاج خادم `ai-platform` حقيقي
يعمل فعلياً، بيئة غير متاحة محلياً هنا).
