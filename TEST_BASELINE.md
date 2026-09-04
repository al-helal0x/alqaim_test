# TASK-CI-02 — Test Baseline (توثيق الفشل الموجود أصلاً قبل أي CI enforcement)

**المصدر:** `ALQAIM_V2_MASTER_EXECUTION_PLAN.md §12` — "تشغيل الاختبارات
الحالية، توثيق أي فشل موجود أصلاً (Baseline)". SAFE PARALLEL، بعد
`TASK-CI-01`.

**التاريخ:** 2026-08-13 — نفس commit المُوثَّق في `تسليم_TASK-06-05.md`
(بعد إضافة `test_outbox_pattern.py` وحذف `main.py.orig`).

## النتيجة الفعلية (تشغيل مباشر، لا افتراض)

| التطبيق | الأمر | النتيجة |
|---|---|---|
| `apps/core-api` | `pytest -v` | **106 passed, 4 skipped, 0 failed** |
| `apps/ai-platform` | `pytest -v` | **18 passed, 1 skipped, 0 failed** |

**لا يوجد أي اختبار فاشل موروث حالياً في أي من التطبيقين.** هذا Baseline
"نظيف" استثنائياً — على عكس ما توحي به بعض الوثائق الأقدم (مثال:
`ADR-002` يذكر عائق 🟠 اكتُشف ومُعالِج فوراً وقتها بخصوص `conftest.py`؛
تلك المشكلة محلولة فعلياً الآن، ولا أثر لها في هذا التشغيل).

## التفصيل: الاختبارات المتخطّاة (Skipped) — ليست فشلاً، توثيقاً لسبب التخطي

### `apps/core-api` (4 اختبارات)
جميعها اختبارات تكامل حقيقي تحتاج عملية `ai-platform` منفصلة فعلياً
قيد التشغيل (وليست SQLite/mock) — تُخطَّى عمداً في بيئة محلية بلا تلك
الخدمة:
- `test_ai_gateway_proxy.py::test_gateway_client_reaches_real_ai_platform_health`
- `test_ai_gateway_proxy.py::test_gateway_proxies_document_analysis_to_real_ai_platform`
- `test_redis_bridge_real_modules.py::test_real_bridge_receives_event_from_separate_ai_platform_process`
- `test_redis_event_bridge.py::test_event_published_on_redis_is_received_by_local_bridge`

### `apps/ai-platform` (1 اختبار)
- `test_redis_events_publisher.py::test_publish_event_sends_correct_envelope_on_shared_channel`
  — يحتاج Redis حقيقي متصل، بنفس منطق التخطي أعلاه.

**ملاحظة لـ`TASK-CI-04` لاحقاً:** هذه الاختبارات الخمسة تحديداً تحتاج
بنية تحتية حقيقية (Redis + عملية `ai-platform` منفصلة) لا تتوفر في بيئة
CI البسيطة الحالية (`TASK-CI-01`). قرار تفعيلها لاحقاً (عبر `docker-compose`
في CI مثلاً) خارج نطاق `TASK-CI-02` — توثيق فقط هنا، لا تغيير.

**ملاحظة لـ`TASK-CI-05` المستقبلية (خلف `GATE-03`)**: بما أن Baseline الحالي **نظيف تماماً (0 فشل)**، فإن تفعيل `pytest` كبوابة
إلزامية (fail PR) لاحقاً في `TASK-CI-05` **لن يحتاج فصل inherited failures
عن جديدة على مستوى pytest** — كل الفشل المستقبلي سيكون بالتعريف "جديداً".
هذا يخالف افتراض الخطة الأصلي (أن هناك فشلاً موروثاً يحتاج فصلاً) — الفصل
اللازم فعلياً هو فقط على مستوى `ruff` (راجع `known_failures.txt` في كل
تطبيق، 78 + 3 مخالفة موروثة فعلياً، وليس pytest).

---

## تحديث لاحق (2026-08-14) — بعد `TASK-AI-01` + `TASK-AI-02`

هذا القسم لا يُعيد كتابة الـBaseline الأصلي أعلاه (يبقى كما هو كمرجع
تاريخي لحظة `TASK-CI-02`) — فقط يُسجِّل آخر عدّ فعلي بعد إضافات لاحقة.
راجع `STATUS_20_TASKS.md §19` للتفصيل الكامل.

| `apps/core-api` | `pytest -v` | **133 passed, 4 skipped, 0 failed** |
|---|---|---|

الفرق عن الـBaseline الأصلي (106 → 133 = +27 اختباراً): `TASK-AI-01`
(3 أجزاء: 8+6+10 = 24 اختباراً) + `TASK-AI-02` (3 اختبارات). **لا صفر
تراجع** — نفس الاختبارات الخمسة المتخطّاة أعلاه لا تزال بنفس السبب
بالضبط (بنية تحتية حقيقية غير متاحة محلياً).
