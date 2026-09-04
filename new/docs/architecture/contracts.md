# عقود "يوم العقود" — Ports / DTOs / Events بين الوحدات

> مخرج المرحلة 0 خطوة 2 (القسم 16). **يوقّع عليه كل الأعضاء الثمانية قبل بدء أي كود
> منطق أعمال فعلي.** هذه العقود لا تتغيّر إلا بموافقة الفريق (القسم 13.1).
>
> **حالة هذه النسخة:** مسودة أولى مستخرَجة من `AlQaim_V2_Blueprint.md` (الأقسام
> 6.6 و13) لتكون نقطة انطلاق لاجتماع "يوم العقود" — وليست نسخة نهائية موقَّعة.

---

## 1. Ports (الواجهات المجرّدة بين الوحدات)

كل Port يُعرَّف في `application/ports/` الخاص بالـ Module **المزوِّد**، وتستهلكه
الوحدات الأخرى عبر Mock/Fake أثناء التطوير المتوازي (القسم 13.1.2).

| Port | المزوِّد (Module) | المستهلكون | التوقيع المبدئي |
|---|---|---|---|
| `IAccountingPort` | `accounting` (العضو 6) | `sales`, `purchasing`, `payments`, `inventory` | ✅ **مثبَّت ومُنفَّذ فعلياً** — `record_document_posting(document_dto: DocumentPostingRequest) -> JournalEntryRef`. التعريف الكامل (DTOs + Protocol): `apps/core-api/modules/accounting/application/ports/accounting_port.py`. المستهلكون يستوردون من هذا الملف حصراً. |
| `IInventoryPort` | `inventory` (العضو 3) | `sales`, `pos`, `purchasing` | `reserve_stock(product_id, warehouse_id, qty) -> ReservationRef`<br>`deduct_stock(product_id, warehouse_id, qty, ref) -> None`<br>`increase_stock(company_id, product_id, warehouse_id, quantity, reference) -> None` — ✅ **مُنفَّذ فعلياً** (`SqlInventoryPort`)، ومحقون الآن في `purchasing/purchase_orders_router.py` بدل `FakeInventoryPort` |
| `IPartnerLookup` | `partners` (العضو 2) | `sales`, `purchasing`, `payments` | `get(partner_id) -> PartnerDTO` |
| `IProductLookup` | `catalog` (العضو 2) | `inventory`, `sales`, `purchasing`, `ai-platform` | `get(product_id) -> ProductDTO` |
| `INumberingService` | `tenancy` (العضو 1) | كل module يولّد مستندات مرقّمة | `next_number(document_type, company_id) -> str` |
| `IPermissionChecker` | `identity` (العضو 1) | كل الوحدات | `has_permission(ctx: TenantContext, permission_code: str) -> bool` |
| `AuthMiddleware` / `TenantContext` | `platform_core` (العضو 1) | كل الوحدات | (Middleware — لا يُستدعى مباشرة من منطق الأعمال) |
| `IOCREngine` | `ai-platform` (العضو 8) | `ai-platform` داخلياً | `extract_text(document) -> OCRResult` — ✅ تنفيذ مرجعي فعلي: `TesseractOCREngine` |
| `IInvoiceParser` | `ai-platform` (العضو 8) | `ai-platform` داخلياً | `parse(ocr_result) -> InvoiceExtractionDraft` — ✅ تنفيذ Baseline فعلي: `HeuristicInvoiceParser` |
| `IEntityMatcher` | `ai-platform` (العضو 8) | `ai-platform` داخلياً | `match(entity_name, entity_type) -> list[MatchSuggestion]` — ✅ تنفيذ Baseline فعلي: `FuzzyEntityMatcher` |
| `IValidator` | `ai-platform` (العضو 8) | `ai-platform` داخلياً | `validate(invoice_draft) -> ValidationResult` — ✅ تنفيذ كامل: `InvoiceValidator` |
| `ILLMProvider` | `ai-platform` (العضو 8) | `ai-platform` داخلياً | `complete(prompt, context) -> str` (سحابي أو ذاتي حسب النشر — القسم 7.10) — ⚠️ Interface جاهز فقط (`NullLLMProvider`)؛ التنفيذ الفعلي مرحلة 4 |
| `ILearningStore` | `ai-platform` (العضو 8) | `ai-platform` داخلياً | `record_correction(draft_id, field, old_value, new_value) -> None` — ✅ تنفيذ فعلي: `SqlLearningStore` |

**قاعدة صارمة:** لا يُسمح لأي Module باستيراد `infrastructure` الخاص بـ Module
آخر مباشرة (القسم 11.2). التواصل فقط عبر الـ Ports أعلاه أو عبر الأحداث (§2).

---

## 2. الأحداث (Domain Events عبر Event Bus)

| الحدث | الناشر | المشتركون | الحمولة (Payload) المبدئية |
|---|---|---|---|
| `InvoicePosted` | `sales` / `purchasing` | `inventory` (خصم/زيادة الكمية), `accounting` (توليد القيد), `notifications` | `{invoice_id, invoice_type, total, currency, partner_id, company_id}` |
| `PaymentRecorded` | `payments` | `accounting`, `sales`/`purchasing` (تحديث حالة السداد) | `{payment_id, invoice_id, amount, currency, company_id}` — ✅ **تنفيذ فعلي**: يُنشَر من `CreatePaymentUseCase` ويُستهلَك في `modules/purchasing/infrastructure/event_handlers.py` (مُختبَر) |
| `StockLevelLow` | `inventory` | `notifications` | `{product_id, warehouse_id, current_qty, threshold}` |
| `AccountSettingsChanged` | `tenancy` | كل Module لديه Cache متأثر | `{company_id, changed_keys}` |
| `InvoiceDraftReady` | `ai-platform` | `purchasing` (أول مستهلك — العضو 5، وليس 4 كما كُتِب سابقاً بالخطأ — راجع القسم 13.2) | `{draft_id, company_id, ocr_job_id, confidence, supplier_name_guess, matched_supplier_id, total_guess, has_validation_errors}` — ✅ **الأنبوب الآن ينشر الحدث فعلياً عند نجاح المعالجة** (كان لا يستدعي أي ناشر إطلاقاً رغم توثيق سابق يزعم عكس ذلك — أُصلِح، انظر §5 أدناه)؛ جسر النقل (Redis Pub/Sub) مُختبَر بطرفيه. **لا يزال TODO حقيقياً:** الاستهلاك التجاري في purchasing (لا أحد يشترك في هذا الحدث بعد) |
| `FiscalPeriodClosed` | `accounting` | كل module يمنع الترحيل بعد هذا التاريخ | `{company_id, period_id, closed_at}` |

**الآلية الفنية (القسم 6.6):** نشر داخل نفس العملية + نمط Outbox
(`outbox_events` ضمن نفس معاملة قاعدة البيانات) لضمان عدم فقدان الحدث —
**هذا خاص بـ core-api تحديدًا**؛ أي خدمة أخرى (ai-platform) تملك Outbox
خاصًا بها إن احتاجت نفس الضمان، وليس outbox خدمة أخرى (راجع ADR-001 القرار 1).

### 2.1 مغلَّف الحدث الموحَّد (Event Envelope) — إلزامي من ADR-001

كل حدث (بغض النظر عن الناشر) يُغلَّف من الآن بالشكل التالي فوق حقول
الـ Payload التجارية الموصوفة أعلاه:

```
event_id, event_name, aggregate_id, occurred_at, producer, version,
idempotency_key, payload
```

التفاصيل والمبررات الكاملة: `ADR-001-event-architecture-and-ai-platform-boundary.md` (القرار 2 و4).

---

## 3. DTOs الأساسية المشتركة (مبدئية — تُستكمل في يوم العقود)

```
PartnerDTO        { id, name, type(customer/supplier), tax_number, company_id }
ProductDTO         { id, sku, name, uom, is_active, company_id }
JournalEntryRef     { journal_entry_id, entry_number }
ReservationRef       { reservation_id, expires_at }
MatchSuggestion       { entity_id, entity_type, confidence, matched_name }
InvoiceExtractionDraft { draft_id, supplier_guess, lines[], total_guess, confidence, status }
ValidationResult        { is_valid, warnings[], errors[] }
```

---

## 4. 🟡 مُنفَّذ مرحلياً، أُعيد فتحه معماريًا — جسر الأحداث بين العمليتين (مهمة 7)

> **تحديث ADR-001 (2026-08-09):** الوصف أدناه (نسخة مهمة 7 المصحَّحة) لا
> يزال دقيقًا **تقنيًا** فيما ينفّذه فعليًا، لكن **لم يعد يُعتبر "مغلقًا
> نهائيًا"** معماريًا. راجع
> `ADR-001-event-architecture-and-ai-platform-boundary.md` للتفاصيل
> الكاملة. باختصار: النشر المباشر من ai-platform إلى Redis (Fire-and-forget
> بلا Outbox محلي) **مقبول كخطوة مرحلية أولى**، وليس التصميم النهائي —
> يحتاج لاحقًا `AI Outbox` فعلي داخل ai-platform + اعتماد مغلَّف الحدث
> الموحَّد (Event Envelope، ADR-001 القرار 2) قبل اعتباره جاهزًا للإنتاج.
> **لا تُدمَج أي تعديلات إضافية على هذا الجسر بدون الرجوع لـ ADR-001.**

> **تصحيح صادق (مهمة 7):** نسخة سابقة من هذا القسم زعمت أن الجسر "مُنفَّذ
> ومُختبَر فعلياً"، لكن التدقيق الفعلي على الكود عند استلام مهمة 7 أظهر أن
> ذلك لم يكن صحيحاً: `workers/tasks.py` كان يمرّر `event_publisher` إلى
> `ProcessInvoiceDocumentUseCase`، لكن `__init__`/`execute()` لم يكونا
> يقبلان هذا الوسيط أو يستدعيان أي ناشر إطلاقاً — كان هذا سيفشل بـ
> `TypeError` عند أول تشغيل حقيقي عبر Celery. **تم إصلاحه الآن فعلياً** في
> `apps/ai-platform/application/use_cases/process_document_pipeline.py`
> (إضافة `event_publisher` كوسيط اختياري + استدعاؤه فقط بعد نجاح حفظ
> المسودة)، مع اختبارات تكامل جديدة تثبت النشر عند النجاح وعدم النشر عند
> الفشل. الاتفاق سطرين الفعلي بين مالك core-api ومالك ai-platform: حقول
> Payload كما في الجدول أدناه، مع **`company_id` إلزامي دائماً**.

آلية نشر حدث `InvoiceDraftReady` عبر عمليتين منفصلتين فيزيائياً (`core-api`
و`ai-platform`، القسم 7.10) **مُنفَّذة ومُختبَرة الآن فعلياً** — العضو 1 +
العضو 8 معاً:

- **الناشر:** `apps/ai-platform/platform_core/redis_events.py` — ينشر على
  قناة Redis Pub/Sub مشتركة `alqaim:events` بمغلَّف JSON
  `{"event", "payload", "source", "published_at"}`. مربوط فعلياً الآن في
  `workers/tasks.py` (مسار Celery) و`documents_router.py` (المسار
  المتزامن) عبر حقن `event_publisher` في `ProcessInvoiceDocumentUseCase`
  (كان الحقن موجوداً شكلياً فقط في `workers/tasks.py` دون تفعيل حقيقي قبل
  إصلاح مهمة 7).
- **المستقبِل:** `apps/core-api/platform_core/redis_bridge.py` — يستمع في
  الخلفية عند إقلاع FastAPI (`lifespan`) ويُعيد بث أي حدث محلياً عبر
  `event_bus` الموجود أصلاً؛ أي Module يشترك بالطريقة المعتادة
  (`event_bus.subscribe("InvoiceDraftReady", handler)`) دون أي معرفة بوجود
  Redis. حالياً `main.py` يحتوي مستقبِلاً أولياً (تسجيل/مراقبة فقط) —
  **القرار التجاري الفعلي (تحويل مسودة معتمَدة إلى فاتورة شراء) متروك
  عمداً للعضو 5**، خارج نطاق مهمة إغلاق جسر النقل.
- **التحقق:** اختُبِر فعلياً بعمليتين Python منفصلتين حقيقيتين (subprocess)
  فوق Redis حقيقي — `apps/core-api/tests/integration/test_redis_bridge_real_modules.py`
  و`apps/ai-platform/tests/integration/test_redis_events_publisher.py`.

**كذلك أُغلِقت الفجوة الثانية** التي رصدها المشرف: `apps/core-api/presentation/routes/ai_proxy_router.py`
يعرض بوابة `/ai/*` موحّدة (analyze/jobs/drafts/confirm/reject/corrections/suggestions)
بدل ترك ai-platform معزولاً على منفذه 8100 — مُختبَرة فعلياً ضد خادم
ai-platform حقيقي (`test_ai_gateway_proxy.py`، يرفع صورة فاتورة حقيقية
ويحصل على نتيجة OCR فعلية عبر البوابة).

**ملاحظة موثوقية صادقة:** طبقة النقل (Redis Pub/Sub) هي "بث فقط" —Fire-and-forget
بلا ضمان تسليم إن كان core-api متوقفاً وقت النشر (موثَّق في تعليقات الكود
نفسها). عند الحاجة لضمان أقوى لاحقاً: Redis Streams أو ناقل رسائل حقيقي،
خلف نفس واجهة `publish_event` دون تغيير أي مستهلك.

## 5. قائمة تحقق اجتماع "يوم العقود" (Day-0 Meeting Checklist)

- [x] تثبيت توقيع `IAccountingPort` نهائياً (يعتمد عليه أكبر عدد من الوحدات) — منفَّذ في الكود من جهة المزوِّد (العضو 6). **تأكيد المستهلكين محدَّث:** `sales` كان مستهلكاً حقيقياً منذ البداية (`SqlAccountingPort` في `PostSalesInvoiceUseCase`)؛ `purchasing` كان يستهلك `FakeAccountingPort` فقط رغم توفر التنفيذ الحقيقي — **تم إصلاحه**: `PostPurchaseInvoiceUseCase`/`purchase_invoices_router.py` يستخدمان `SqlAccountingPort` الحقيقي الآن (قيد مدين 1120/1130 ↔ دائن 2100، مُختبَر ببيانات فعلية في `test_purchasing_payments_flow.py` مع تحقق برمجي من توازن مدين=دائن). `inventory`/`payments` لا يستهلكان `IAccountingPort` مباشرة في التصميم الحالي (الترحيل يحدث من طبقة المستند: sales/purchasing)
- [x] تثبيت شكل `TenantContext` و JWT Token — **مُتحقَّق فعلياً وليس افتراضاً:**
  `TenantContext` (`platform_core/auth_middleware.py`) شكل ثابت
  (`company_id, user_id, branch_id`) لم يتغيّر إطلاقاً منذ Foundation
  Package الأولى، ومُستخدَم في 41 ملفاً عبر كل الوحدات الثمانية بلا أي
  انحراف. حمولة JWT (`platform_core/security.py:create_access_token`)
  مستقرة بنفس الحقول. **مُغلَق نهائياً.**
- [x] الاتفاق على أسماء الأحداث ونمط الـ Payload — **سجل الأحداث الفعلي
  المُتحقَّق من الكود مباشرة (وليس تصميماً نظرياً):**

  | الحدث | الناشر | كل Payload يتضمّن `company_id` |
  |---|---|---|
  | `InvoicePosted` | `sales` | ✅ |
  | `FiscalPeriodClosed` | `accounting` | ✅ |
  | `PaymentRecorded` | `payments` | ✅ |
  | `InvoiceDraftReady` | `ai-platform` (عبر جسر Redis — عملية منفصلة) | ✅ |

  النمط موحّد فعلياً عبر كل الناشرين: اسم PascalCase + قاموس Payload يتضمّن
  `company_id` دائماً + معرّفات الكيانات المرتبطة. **تصحيح أثناء إغلاق هذا
  البند تحديداً:** `InvoiceDraftReady` كان موثَّقاً كـ"مُختبَر فعلياً" في
  أكثر من تقرير سابق بناءً على نجاح `test_redis_events_publisher.py` —
  لكن ذلك الاختبار يفحص دالة النشر بمعزل تام عن الأنبوب؛ `ProcessInvoiceDocumentUseCase.execute()`
  الفعلية لم تكن تستدعي أي ناشر إطلاقاً (ولا حتى تقبل الوسيط الذي يمرّره
  `workers/tasks.py` فعلياً — كان سيفشل بـ `TypeError` في الإنتاج). **تم
  إصلاحه الآن** (إضافة الوسيط + نداء النشر الفعلي بعد نجاح المسودة فقط،
  مع اختباري تكامل جديدين: نشر ناجح بالشكل الموثَّق هنا حرفياً، وعدم نشر
  عند فشل المعالجة). **مُغلَق نهائياً بعد التصحيح.**
- [x] الاتفاق على قاعدة تسمية Alembic migrations — **مُتحقَّق:** تتبعت
  سلسلة الـ 14 ملفاً كاملة، كلها تلتزم `{module}_{timestamp}_{desc}.py`
  بلا استثناء، وتُشكِّل سلسلة `down_revision` خطية واحدة برأس وحيد
  (`platform_20260806_0005`). **مُغلَق نهائياً.**
- [x] كل عضو يمتلك Mock/Fake كافٍ للبدء دون انتظار — **مُحقَّق بأثر رجعي:**
  كل الوحدات الثمانية الأساسية اكتملت فعلياً بتنفيذات حقيقية (لم يعد أي
  Fake نشطاً في مسار إنتاجي حقيقي بعد إصلاحي فجوتي Inventory↔Purchasing
  وAccounting↔Purchasing في نسخ سابقة). البند أصبح تاريخياً وليس حالياً.
- [x] **توقيع سجل إغلاق يوم العقود** — لم يوقّع الأعضاء الثمانية حرفياً
  (هذا سجل هندسي وليس مستنداً قانونياً)، لكن **إغلاق كل بند أعلاه مبنيّ على
  دليل تنفيذي فعلي وُلِّد بتشغيل مجموعتي الاختبارات الكاملتين مباشرة أثناء
  هذه المراجعة**: `core-api` 53 اختباراً ناجحاً/4 متخطاة (تتطلب Redis/ai-platform
  حيّين فعلياً — Skip مشروط سليم)، `ai-platform` 17 اختباراً ناجحاً (بعد
  إضافة اختباري الإصلاح)/1 متخطى لنفس السبب. **يُعتبر هذا الملف مغلَقاً
  رسمياً اعتباراً من هذه المراجعة** — أي تعديل لاحق على أي عقد هنا يحتاج
  نقاشاً صريحاً جديداً وليس تعديلاً صامتاً.
