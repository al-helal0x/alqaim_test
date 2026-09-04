# تسليم — دمج PKG-A/B/C/D في الشجرة الأساسية (2026-08-16)

**السياق:** 4 حزم عمل مُسلَّمة معزولة (A/B/C/D) بلا رؤية كاملة للشجرة. هذا
الملف يوثّق ما دُمج فعلياً، ما تحقَّق منه بتشغيل حقيقي (لا افتراض)، وما
تبقّى — بعد امتلاك الشجرة الكاملة التي لم تكن متاحة لمنفّذي الحزم الأصليين.

---

## PKG-A — AI Vertical Slice (`GATE-03`)

**مُنجَز فعلياً:**
- إصلاح `job_id → draft_id` في `ai-platform` (تحقُّق `diff` دقيق، صفر انحراف عن المُسلَّم).
- **21/21 اختبار `ai-platform` ناجح** ضد Redis حقيقي (ثبَّتُّ Redis وPostgres 16 محلياً).
- **`alembic upgrade head` ناجح على Postgres حقيقي** لكلا `ai-platform`و`core-api` — أول مرة يُختبَر بها هذا المشروع ضد Postgres فعلياً وليس SQLite فقط.
- **`PKG-A1` مُحقَّق فعلياً:** شغّلت `ai-platform` و`core-api` كعمليتين حيّتين منفصلتين معاً، و`/health` ناجح لكليهما.

**🔴 اكتشاف حقيقي يمنع `GATE-03` (لا حل عجول له):**
رفعت صورة فاتورة فعلية عبر OCR حي (Tesseract، ثقة 94.69%) — نجح الاستخراج
تماماً، لكن `matched_supplier_id: null` دائماً، لأن `/ai/documents/analyze`
الحقيقي **لا يمرّر** `known_products`/`known_suppliers` لخط الأنابيب إطلاقاً
(معاملان اختياريان مُعرَّفان في الكود، غير مُستخدَمين من أي مسار حقيقي). أي
فاتورة حقيقية عبر هذا المسار **سترفض دائماً بـ422** عند
`/purchase-invoices/ai-upload`. هذه فجوة تكامل معمارية بين الخدمتين (كيف
يصل `ai-platform` لكتالوج/شركاء `core-api`؟) — تحتاج قرار تصميم من صاحب
القرار (نداء HTTP مزامن؟ تمرير القائمة ضمن طلب الرفع نفسه؟)، وليست شيئاً
يُصلَح بترقيع.

---

## PKG-B — Walk-in Customer

**مُنجَز فعلياً ومُدمَج بالكامل:**
- صُحِّح `down_revision` للـmigration + تسجيل `partners_walkin_router` في `main.py` (كما طلبت الحزمة نفسها).
- **صلاحية `pos.sale.create` كانت مفقودة تماماً من seed migrations — أُضيفت** (فجوة حقيقية، لم تكن الحزمة تعلم بها لغياب رؤيتها لملفات seed الفعلية).
- **3 أخطاء حقيقية في اختبارات الحزمة نفسها اكتُشِفت وأُصلحت:**
  1. `migrations/env.py` يتجاهل `TEST_DATABASE_URL` المُمرَّر برمجياً (يقرأ فقط من `ALQAIM_DATABASE_URL`).
  2. محرك async بنطاق `module` يتصادم مع نطاق event loop لـ`pytest-asyncio` (نطاق `function`).
  3. إدراج SQL خام لجدول `companies` ناقص أعمدة `name`/`created_at`/`updated_at` (NOT NULL في المخطط الحقيقي).
- **🔴 خطأ حرج اكتُشِف عند تشغيل السويت الكاملة (لا عند اختبارات الحزمة فقط):** الفهرس الفريد الجزئي يستخدم `postgresql_where=` فقط بلا `sqlite_where=` — على SQLite (تبني عليها كل اختبارات المشروع الأخرى) يتحول فعلياً لـ**UNIQUE كامل** على `company_id`، يكسر أي شركة بأكثر من partner واحد. **صُحِّح** بإضافة `sqlite_where=` بنفس الشرط.
- **النتيجة: 9/9 اختبار walk-in ناجح ضد Postgres حقيقي فعلياً** (بما فيها اختبار race condition حقيقي)، + السويت الكامل **147 passed, 0 regressions**.

---

## PKG-C — Production Hardening

**IDOR (`PKG-C1`) — من قوالب `NotImplementedError` إلى تفعيل حقيقي:**
- بنيت `conftest.py` حقيقياً: تسجيل شركتين فعليتين عبر `POST /auth/register-company` الحقيقي (JWT حقيقي، بلا أي تجاوز على طبقة المصادقة).
- **اكتشافان حقيقيان أثناء التفعيل:**
  1. `require_permission` يستورد `AsyncSessionLocal` مباشرة متجاوزاً `Depends(get_db_session)` — يحتاج استبدال `AsyncSessionLocal` نفسه، لا `dependency_overrides` وحدها.
  2. `RegisterCompanyUseCase` يمنح Owner كل صف *موجود فعلياً* في جدول `permissions` وقت التسجيل — لكن جدول الاختبار (SQLite من `Base.metadata` مباشرة) يبدأ فارغاً بلا أي seed حقيقي، فيُمنح Owner صفر صلاحيات ما لم تُزرَع صراحة. زُرعت كل أكواد الصلاحيات المُستخدَمة فعلياً (استخراج بـ`grep` من كامل الشجرة، لا افتراضاً).
  3. **🔴 خطأ حرج ثانٍ من نوع "تسريب state عالمي" اكتُشِف عند تشغيل السويت الكاملة:** استبدال `AsyncSessionLocal` (في هذا الملف **و**`test_purchase_invoice_receive_inventory_endpoint.py` من جلسة سابقة) لم يكن يُستعاد بعد كل اختبار — كسر 11 اختباراً غير متعلقة بـIDOR إطلاقاً (`test_sales_invoice_idempotent_posting.py`). **صُحِّح بـtry/finally في كلا الملفين.**
  4. **🔴 خطأ حرج ثالث، مختلف تماماً:** تصادم اسم module `conftest` — بلا `__init__.py`، وضع `prepend` الافتراضي لـpytest يُحمِّل `tests/integration/conftest.py` و`tests/integration/idor/conftest.py` تحت **نفس الاسم** `conftest` في `sys.modules`، فيكسر استيراداً مطلَقاً هشاً موجوداً *مسبقاً* في `test_sales_invoice_idempotent_posting.py` (`from conftest import _swap_pg_only_types_for_sqlite`). **صُحِّح بإضافة `tests/integration/idor/__init__.py`** (يجعل اسم module مؤهَّلاً بالكامل، لا تصادم).
  5. `partner_type: "vendor"` (قيمة غير صالحة في قالب أحد الاختبارات — الصحيح `supplier`) — صُحِّح.
- **النتيجة الفعلية بعد كل الإصلاحات:** أول اختبارين IDOR (partners) يعملان فعلياً — واحد ناجح (عزل GET حقيقي مُثبَت)، والآخر يكشف **ملاحظة API حقيقية غير أمنية**: `UpdatePartnerUseCase` يرفض التعديل عبر الشركات بشكل صحيح تماماً (لا تسريب، لا تعديل غير مصرَّح)، لكن الـRouter يُرجِع 400 بدل 404/403 لكل `ValueError` (اتفاقية أكواد حالة، لا ثغرة أمنية).
- **🟡 متبقٍّ (غير مُكمَل):** 9 من 11 ملف IDOR الباقية لم تُشغَّل/تُصحَّح بعد — بعضها يحتاج فقط تصحيح بيانات payload (نفس نمط `test_idor_pos.py`: `warehouse_id` مفقود)، وبعضها يحتاج seed بيانات إضافية موثَّق مسبقاً في القالب نفسه (`test_idor_purchasing_orders.py`/`test_idor_sales_invoices.py`: `vendor_id`/`product_id` حقيقيين).

**لم يُدمَج بعد:** `docker-compose.selfhosted.yml`، سكربتات `backup_db.sh`/`test_backup_restore.sh`، سكربتات k6 لاختبار الحمل، `ci.yml`، `audit_tenancy_isolation.py`. تقاريرها الأصلية (`PKG-C2`/`PKG-C4`) موثَّقة وصادقة بما تحقَّق فعلياً هناك (راجعها مباشرة، لم تُعَد صياغتها).

---

## PKG-D — التوثيق والجودة

لم يُدمَج بعد في هذه الجلسة. `FINDING_pkg-d1_not_applicable.md` يوثّق أن ملف
الخطة المرجعي المفقود عُولج فعلياً (README يُحيل الآن لـ`ALQAIM_V2_MASTER_EXECUTION_PLAN.md`).
اختبارات Flutter (`PKG-D2`) لم تُراجَع أو تُدمَج، ولا التوفيق مع تغييرات
PKG-B3 المفترضة على سلوك شاشة البيع (Walk-in) — PKG-B3 نفسها (طبقة Flutter)
لم تُدمَج في هذه الجلسة أصلاً (فقط `apps/core-api` من PKG-B دُمجت).

---

## التحقق النهائي لهذا التسليم

```
apps/core-api: pytest tests/integration/ modules/partners/tests/ -q
    → 147 passed, 11 failed (IDOR templates غير مكتملة, غير أمنية), 13 skipped, 4 errors
      (نفس الـ11 فشل/4 أخطاء IDOR أعلاه فقط — صفر تراجع فعلي عن الأساس السابق)

apps/ai-platform: pytest tests/ -q  → 21 passed, 0 skipped (Redis حقيقي)

alembic heads (core-api) → رأس واحد: pos_20260816_0001
ruff check <كل الملفات المُدمَجة/الجديدة> → صفر مخالفات
```
