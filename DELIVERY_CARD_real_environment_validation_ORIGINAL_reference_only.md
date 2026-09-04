# تسليم — Real Environment Validation (Postgres + Redis حقيقيان فعلياً)

**تاريخ:** أُنتِج بمساعدة Claude بناءً على طلب صريح من صاحب المشروع، فوق حزمة
`AlQaim_V2_v9_conflict_resolved.zip` (نتيجة حسم تعارض #6×#10×#11×#12).
يغلق تحديداً النقطة التي تركها ذلك التسليم صراحةً "لم تُتحقَّق منها بعد":
تشغيل `pytest`/`alembic` فعلياً على بيئة حقيقية، لا `py_compile` فقط.

راجع `STATUS_20_TASKS.md` §14 للسرد الكامل بالتفصيل. هذه البطاقة ملخَّص
عملي للمطوِّر التالي.

## ما تغيّر

| الملف | التغيير |
|---|---|
| `apps/core-api/modules/payments/application/use_cases/payments_use_cases.py` | 🆕 **كان مفقوداً بالكامل** — `ModuleNotFoundError` عند إقلاع `main.py` فعلياً. أُعيد بناؤه (`CreatePaymentUseCase`، `CreateBankAccountUseCase`، `CreateReceiptUseCase`) من عقد DTO/repository/router/الاختبار الفعلي |
| `apps/core-api/tests/integration/conftest.py` | إصلاح شيم UUID/JSONB لـ SQLite: `with_variant("sqlite", ...)` بدل استبدال `col.type` مباشرة (كان يُلوِّث اتصالات Postgres حقيقية لاحقة في نفس العملية) — بيئة اختبار فقط، صفر تعديل على كود إنتاجي |
| `apps/core-api/tests/integration/test_sales_invoice_idempotent_posting.py` | نفس إصلاح الشيم مطبَّق على جداول الظل المحلية لهذا الملف + إضافة `outbox_events` لقائمة الجداول المُنشأة (Task #6 لم تكن مدموجة وقت كتابة هذا الملف) |
| `apps/core-api/tests/integration/test_sales_and_pos.py` | `test_cannot_post_invoice_twice` → `test_reposting_already_posted_invoice_is_idempotent_noop`: كان يختبر عكس عقد #11 الرسمي (idempotency على الترحيل) بالضبط |

## كيف تحقَّقت (لا افتراض — تشغيل فعلي، 3 مرات متتالية من DB نظيفة)

```bash
# Postgres 16 + Redis حقيقيان (apt-get install postgresql redis-server)
cd apps/core-api
python -m alembic upgrade head          # من DB فارغة تماماً
python -m pytest tests/integration -q   # ALQAIM_DATABASE_URL/ALQAIM_REDIS_URL حقيقيان
python -c "import main; print(len(main.app.routes))"   # يتأكد من إقلاع main.py فعلياً
```

**النتيجة (ثابتة عبر 3 تشغيلات متتالية من drop/create):**
```
alembic upgrade head → رأس واحد فقط: platform_20260809_0002، 57 جدولاً
pytest tests/integration → 102 passed, 2 skipped, 0 failed
main.py → 42 route، صفر أخطاء استيراد
```

تأكَّدت أيضاً مباشرة عبر `psql` أن صف `outbox_events` المكتوب فعلياً من
`test_redis_bridge_real_modules.py` (الاختبار الوحيد الذي يفتح اتصال
Postgres حقيقي عبر `platform_core.database.AsyncSessionLocal`، محاكاةً
لعملية ai-platform منفصلة عبر Redis) محفوظ بنوع `uuid` أصلي
(`pg_typeof(id) = uuid`)، لا `varchar` — هذا كان بالضبط العطل المُكتشَف
والمُصلَح في `conftest.py`.

## ما لم يتغيّر عمداً

- لا تعديل على أي كود إنتاجي في `platform_core/` أو `modules/*/application`
  سوى الملف المفقود `payments_use_cases.py` نفسه (لم يكن هناك كود سابق
  ليُعدَّل — الملف لم يكن موجوداً إطلاقاً).
- `CreateReceiptUseCase` عمداً **لا تنشر أي حدث outbox** — موثَّق صراحةً في
  تعليق الملف نفسه: لا يوجد بعد أي معالج مسجَّل في `sales` يستهلك حدث قبض
  مقابل (خلافاً لـ `PaymentRecorded` الذي له معالج فعلي في
  `purchasing/infrastructure/event_handlers.py`). تحديث `paid_amount` على
  فاتورة بيع مرجعية من سند قبض يبقى عملاً لاحقاً صريحاً، لا نقصاً غير موثَّق.

## ما لم يُتحقَّق منه بعد (محدودية معروفة)

- `flutter test`/`dart analyze` على #13 (`apps/pos-app`) — خارج نطاق
  core-api تماماً، لم يُلمَس في هذه الدفعة.
- لا نشر فعلي (staging/production) — كل التحقق أعلاه محلي على حاوية تطوير.
- بيئة الاختبار (`conftest.py`) تعتمد الآن على `with_variant()` بدلاً من
  استبدال مباشر — سلوك SQLAlchemy 2.0 الموثَّق (`with_variant` يُعيد نسخة
  جديدة من نفس الكائن لا غلافاً منفصلاً)، مُتحقَّق منه مباشرة بسكربت مستقل
  قبل الاعتماد عليه، لكن يستحق الانتباه لو تغيّرت نسخة SQLAlchemy مستقبلاً.
