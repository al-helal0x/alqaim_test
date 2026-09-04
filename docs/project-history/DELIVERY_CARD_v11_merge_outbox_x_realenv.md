# تسليم v11 — دمج `v10_outbox_contract_corrected` × `real_environment_validated`

## ⚠️ لماذا لم يكن الدمج نسخ-ولصق مباشراً

الحزمتان **ليستا فرعين مستقلين قابلين للدمج الحرفي**. كلاهما بُني فوق نفس
القاعدة (`AlQaim_V2_v9_conflict_resolved.zip`)، لكنهما تفرَّعا في اتجاهين
متعارضين معمارياً على نفس المشكلة (نمط Outbox، مهمة #6):

| | `v10_outbox_contract_corrected` | `real_environment_validated` |
|---|---|---|
| بُني فوق | `INTERFACE_CONTRACT_OUTBOX.md` (عقد مجمَّد، مُوزَّع على 3 أعضاء) | `v9_conflict_resolved.zip` مباشرة، **قبل** ذلك العقد |
| مكان منطق Outbox | `platform_core/outbox.py` منفصل — `enqueue_event()` | داخل `event_bus.py` نفسه — `publish(session, ...)` |
| `event_bus.py` | **غير مُعدَّل** عن v8 (نشر فوري، بلا session) | أُعيد بناؤه بالكامل |
| هذا بالضبط... | ...ما يفرضه العقد المجمَّد | ...نفس المعمارية التي رفضها v9 والعقد المجمَّد صراحةً |

بعبارة أخرى: `real_environment_validated` أعاد فتح نفس القرار المعماري
الذي حسمه العقد المجمَّد قبله (بلا علم به — التسلسل الزمني بين الحزمتين لا
يسمح بذلك). **القرار في هذا الدمج: الإبقاء على معمارية `outbox.py` المنفصل**
لأنها المطابقة فعلياً لما وافق عليه الأعضاء الثلاثة، وتوثيق هذا القرار هنا
بدل تنفيذه بصمت.

## ما دُمِج فعلياً من `real_environment_validated`

كل ما يلي إصلاحات **مستقلة عن الخلاف المعماري أعلاه** — لا علاقة لها بمكان
منطق Outbox، فأُعيد استخدامها مباشرة أو بتكييف بسيط:

1. **`modules/payments/application/use_cases/payments_use_cases.py`** (ملف
   كامل مفقود من كلتا الحزمتين قبل هذا الدمج) — أُعيد بناؤه، لكن نشر
   `PaymentRecorded` أُعيد ربطه بـ `event_bus.publish(event_name, payload)`
   المباشر (معمارية هذه الشجرة)، لا `enqueue_event()`. راجع تعليق أعلى
   الملف للتفاصيل الكاملة عن سبب عدم استخدام Outbox هنا تحديداً.
2. **`tests/integration/conftest.py`** — إصلاح شيم UUID/JSONB لـ SQLite
   (`with_variant` بدل استبدال `col.type` مباشرة) — بيئة اختبار فقط.
3. **`tests/integration/test_sales_invoice_idempotent_posting.py`** — نفس
   الإصلاح مركزياً + تسجيل جدول `outbox_events` في جداول الظل المحلية.
4. **`tests/integration/test_sales_and_pos.py`** — تصحيح اختبار كان يختبر
   عكس عقد #11 (idempotency على الترحيل) المعتمَد فعلياً.

## ما لم يُدمَج، ولماذا

كل ملف في `real_environment_validated` مبني فوق `event_bus.py` المُعاد بناؤه
(معماريته المرفوضة): `main.py`، `event_bus.py`، `outbox_worker.py`،
`redis_bridge.py`، `outbox_models.py`، `fiscal_period_use_cases.py`،
`sales_use_cases.py`، `invoices_router.py`، `test_event_bus_isolation.py`،
`test_redis_event_bridge.py`. نسخ أيٍّ منها هنا سيكسر التوافق مع بقية الشجرة
فوراً (توقيع `publish()` مختلف تماماً). راجع `STATUS_20_TASKS.md` §15
للتفاصيل الكاملة، بند-ببند.

## التحقق الفعلي بعد الدمج

- ✅ `py_compile` على كل ملف في الشجرة — بلا خطأ.
- ✅ `pyflakes` على كل ملف خارج tests/migrations — صفر أسماء غير معرَّفة.
- ✅ `import main` فعلياً (لا `py_compile` فقط) — يُقلِع بنجاح، **42 route**.
- ✅ `pytest tests/integration -q` على SQLite في-الذاكرة — **100 passed, 4 skipped, 0 failed** (الأربعة المتخطاة: Redis غير متاح في بيئة التحقق هذه، نفس نمط `pytest.skip` الموروث).
- ❌ لم يُشغَّل ضد Postgres/Redis حقيقيين فعلياً في بيئة توليد هذا الدمج (لا بنية تحتية متاحة هنا) — القيد نفسه الموروث من `v10_outbox_contract_corrected` §14. `real_environment_validated` (قبل تفرُّع الشجرتين) كان قد أثبت أن مجموعة اختبارات مشابهة (102 حالة قبل هذا الدمج، العدد يختلف هنا لأن اختباري event_bus/redis من تلك الحزمة لم يُدمَجا) تمر فعلياً على بنية تحتية حقيقية — يبقى هذا مرجعاً تاريخياً لا تحقُّقاً لهذه الشجرة تحديداً.
