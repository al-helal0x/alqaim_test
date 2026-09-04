## بطاقة تسليم المهمة

- رقم المهمة: #14
- المسار: 📱 Clients (تنسيق `LineItemRequest` بين pos-app والمبيعات)
- الفرع: `task/14-pos-line-item-contract-and-walkin-partner` (اسمي فقط — لا فرع Git فعلي)
- مبني على: نفس نسخة الكود بعد دمج مهمتَي 7 و11 (لا تقاطع ملفات معهما إطلاقاً)

### ما اكتُشف فعلياً عند القراءة (وليس افتراضاً)
قرأت `LineItemRequest` الحقيقي في `sales_dto.py` مباشرة، ووجدت أن
`pos-app` كان مبنياً على افتراضين خاطئين موثَّقين في `STATUS.md` نفسه
كـ TODO مفتوح:
1. `unit_price` **إلزامي** فعلياً (`Field(ge=0)` بلا `default`) — pos-app
   افترضه اختيارياً ظناً أن السيرفر يحسبه من الكتالوج؛ هذا **غير صحيح**.
2. `tax_amount` حقل رابع في `LineItemRequest` الفعلي كان **غائباً بالكامل**
   من نسخة pos-app.

وسؤال "عميل نقدي افتراضي" (walk-in) كان TODO آخر موثَّق في نفس الملف —
لا يوجد أي مفهوم مماثل في الكود (لا seed، لا عمود خاص، لا endpoint) في كل
من `identity`/`partners`/`pos`.

### الملفات/المجلدات التي تم إنشاؤها (جديدة)
- `apps/pos-app/lib/data/models/partner_dto.dart` — مطابقة لِـ
  `PartnerResponse`/`Page[PartnerResponse]` الفعليين (حقول id/name/partner_type فقط)
- `apps/pos-app/lib/data/repositories/walk_in_partner_repository.dart` —
  يحسم سؤال العميل النقدي بالكامل من جهة العميل (تفصيل القرار وسببه
  موثَّق داخل الملف نفسه بالكامل)
- `apps/pos-app/test/walk_in_partner_repository_test.dart` — 3 اختبارات
  (عميل موجود مسبقاً، إنشاء عميل جديد، استخدام القيمة المخزَّنة محلياً بلا
  أي طلب شبكة)

### الملفات/المجلدات التي تم تعديلها
- `apps/pos-app/lib/data/models/pos_sync_dto.dart` — `PosSaleLineDto`:
  `unitPrice` أصبح إلزامياً (كان `double?`)، أُضيف `taxAmount` (افتراضي 0)
- `apps/pos-app/lib/data/local/app_database.dart` — عمود `unit_price` في
  `LocalSaleItems` أصبح غير قابل للـ null، عمود `tax_amount` جديد،
  `schemaVersion` من 2 إلى 3 مع `MigrationStrategy.onUpgrade` يضيف العمود
  الجديد ويُصلح أي صف قديم بقيمة `unit_price` فارغة (نظرياً بحتاً، لا
  مستخدمين فعليين بعد)
- `apps/pos-app/lib/data/repositories/pos_repository.dart` —
  `createDraftSale`/`buildSyncPayload` تُمرِّر `taxAmount`، وإزالة `?? 0`
  الزائدة بعد أن أصبح `unitPrice` إلزامياً
- `apps/pos-app/lib/core/auth/session_storage.dart` — مفتاح تخزين جديد
  `pos_walk_in_partner_id` (يُمسَح مع بقية الجلسة عند `clear()`)
- `apps/pos-app/lib/core/di/providers.dart` — `walkInPartnerRepositoryProvider`
- `apps/pos-app/test/pos_repository_test.dart` — اختبارا JSON round-trip
  لـ `tax_amount`/`unit_price` + اختبار حفظ `tax_amount` عبر `buildSyncPayload`
- `apps/pos-app/STATUS.md` — نقل السؤالين المفتوحين من "TODO" إلى "محسوم"،
  مع شرح القرار وأثره

### القرار المُتَّخذ بخصوص "عميل نقدي افتراضي" ولماذا
**لم يُعدَّل أي عقد** (`sales_dto.py`/`pos_dto.py` كما هما — `partner_id`
يبقى إلزامياً). الحل بالكامل من جهة `pos-app`:
`WalkInPartnerRepository.resolveWalkInPartnerId()` يبحث عن Partner باسم
قياسي ثابت `"عميل نقدي"` عبر `GET /partners` الموجود مسبقاً (لا صلاحية
خاصة مطلوبة لهذا المسار في `partners_router.py` الفعلي)، وينشئه عبر
`POST /partners` إن لم يوجد، ثم يخزّن النتيجة محلياً فلا تتكرر العملية.
**متطلب تشغيلي (وليس تعديل كود)**: دور مستخدم جهاز الكاشير يحتاج صلاحية
`partners.partner.create` عند أول تشغيل فقط.

كان البديل (جعل `partner_id` اختيارياً على السيرفر) ممكناً لكنه رُفض عمداً
— تفصيل الأسباب كاملاً داخل تعليق `WalkInPartnerRepository` نفسه (تجاوز
حدود المهمة + فقدان قابلية ربط تقارير الذمم بعميل نقدي واحد موحَّد).

### ⚠️ قيد تحقق مهم — غير مثل مهمتَي 7 و11
**لا يوجد Dart/Flutter SDK في بيئة التنفيذ** (تأكدت: لا `dart`، لا طريقة
تثبيت عبر apt ضمن الشبكة المسموحة). لذلك:
- ❌ لم أُشغِّل `flutter test` فعلياً — لا تأكيد تشغيلي حقيقي لأي من
  الاختبارات الستة الجديدة/المعدَّلة
- ❌ لم أُشغِّل `dart analyze` أو `dart run build_runner build`
  (`app_database.g.dart` غير مُولَّد أصلاً في هذا التسليم — نفس القيد
  المذكور مسبقاً في `STATUS.md` من الجولة السابقة، لم يتغيّر)
- ✅ الشيء الوحيد الذي تحققت منه آلياً: توازن الأقواس/الحاضنات في كل ملف
  Dart لمسته (فحص برمجي بسيط بـ Python، ليس بديلاً عن compiler حقيقي)
- ✅ راجعت التوقيعات والأنواع يدوياً بعناية (خصوصاً `implements SessionStorage`
  في ملف الاختبار، و`HttpClientAdapter.fetch` في Dio 5.4.3) لكن هذا تحقق
  يدوي بشري، وليس ضمانة تصريف (compilation) ناجح

**قبل الدمج، يحتاج فريق pos-app فعلياً**: `flutter pub get` ثم
`dart run build_runner build` (لتوليد `app_database.g.dart` بالحقول
الجديدة) ثم `flutter test` — لا شيء من هذا حدث في هذه الجلسة.

### Migrations
- لا يوجد على core-api (لم يُعدَّل أي شيء في `apps/core-api/`)
- محلي فقط: `AppDatabase.schemaVersion` 2→3 (Drift، على الجهاز)

### التوثيق المحدَّث
- `apps/pos-app/STATUS.md`

### اعتماديات هذه المهمة
- تعتمد على: لا شيء (لم تلمس core-api إطلاقاً)
- تُبنى عليها: أي شاشة كاشير مستقبلية (سلة/دفع) — ستستخدم
  `WalkInPartnerRepository` و`PosSaleLineDto` الجديدين مباشرة

### التحقق المحلي قبل التسليم
- [ ] تشغيل الاختبارات محلياً وناجحة — **لم يحدث فعلياً** (انظر القيد أعلاه)
- [ ] CI أخضر على الفرع — لم يُشغَّل CI حقيقي
- [x] لا تعديل خارج المسارات المصرَّح بها — كل الملفات داخل `apps/pos-app/`
      فقط؛ `sales_dto.py` لم يُلمَس لأنه كان صحيحاً مسبقاً (لا حاجة لتعديله)
- [x] كل بند في عمود "المخرج": توحيد الشكل الافتراضي ✅ (مبني على الكود
      الفعلي لا تخمين)، حسم سؤال العميل النقدي الافتراضي ✅ — **لكن كلاهما
      غير مُتحقَّق منه بالتشغيل الفعلي**، فقط بالقراءة والمراجعة اليدوية
