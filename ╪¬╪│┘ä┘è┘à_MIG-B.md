# Task MIG-B — إصلاح إنشاء ENUM مزدوج (accounting + taxation)

**الحالة:** 🟠 Integration Blocking — يمنع `alembic upgrade head` على Postgres حقيقي
**مستقلة تمامًا** عن MIG-A وMIG-C — لا تشارك أي ملف معهما.

## المشكلة
كلا الملفين يستدعي `ENUM.create(bind, checkfirst=True)` صراحة، ثم يستخدم
نفس متغيّر الـ ENUM كنوع عمود مباشرة في `op.create_table(...)`. SQLAlchemy
يحاول ضمنيًا إنشاء النوع مرة ثانية عند تجميع DDL الجدول. الخطأ الفعلي:
`DuplicateObjectError: type "account_type" already exists` (وبالمثل
`e_invoice_submission_status` في taxation).

## الحل
أضف `create_type=False` لتعريف الـ ENUM نفسه، بما أنك تُنشئه/تحذفه يدويًا
بالفعل عبر `.create()`/`.drop()`:

```python
ACCOUNT_TYPE_ENUM = postgresql.ENUM(
    "asset", "liability", "equity", "revenue", "expense",
    name="account_type",
    create_type=False,   # ← الإضافة المطلوبة: الإنشاء/الحذف يدوي عبر .create()/.drop() أدناه فقط
)
```
طبّق نفس التعديل على `NORMAL_BALANCE_ENUM` في نفس الملف، وعلى
`SUBMISSION_STATUS_ENUM` في `taxation_20260804_0004_initial_schema.py`.

**تحقَّق أن `downgrade()` في كلا الملفين لا يزال يستدعي `.drop(bind, checkfirst=True)` بنفس الترتيب — `create_type=False` لا يغيّر سلوك الحذف اليدوي.**

## ✅ مسموح تعديل
`accounting_20260804_0003_initial_schema.py`،
`taxation_20260804_0004_initial_schema.py` — فقط إضافة `create_type=False`
لتعريفات الـ ENUM الثلاثة. لا تغيّر أي عمود آخر ولا أي جدول.

## 🚫 ممنوع
أي migration أخرى · `event_bus.py` · `outbox_models.py`/outbox migration ·
أي شيء في `modules/*` أو `apps/ai-platform` · تغيير `revision`/`down_revision`.

## معيار القبول
- [ ] الثلاثة تعريفات ENUM تحمل `create_type=False`
- [ ] `python -m py_compile` على كلا الملفين ينجح بلا خطأ
- [ ] `downgrade()` في كلا الملفين لم يتغيّر منطقه
- [ ] لا تغيير على أي عمود/جدول آخر
