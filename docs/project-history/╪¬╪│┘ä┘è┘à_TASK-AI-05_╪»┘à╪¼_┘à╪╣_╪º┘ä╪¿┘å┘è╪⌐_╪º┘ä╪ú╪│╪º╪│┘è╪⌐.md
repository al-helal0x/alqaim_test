# تسليم — دمج `TASK-AI-05` (إدخال فاتورة عبر QR Code) في البنية الأساسية

## السياق

كان `TASK-AI-05a/b` قد نُفِّذا واختُبرا سابقاً بمعزل تام (حزمة `REFERENCE_ONLY`/
`OWNED` منفصلة، بلا وصول للشجرة الحقيقية — نماذج/جلسات قاعدة بيانات وهمية).
هذا التسليم هو **دمج فعلي** لذلك العمل داخل الشجرة الحقيقية الكاملة
(`AlQaim_V2_v21_phase5_merged/`)، مع كل ما يترتب على ذلك من تفاصيل لم تكن
ظاهرة في البيئة المعزولة (أنواع الحقول الحقيقية UUID، بنية `pyproject.toml`
الفعلية، Dockerfile، CI).

## التحقق الفعلي (لا افتراض) — النتيجة النهائية

```
cd apps/ai-platform && pytest -v
→ 36 passed, 1 skipped (skip موجود مسبقاً — test_redis_events_publisher.py،
  لا علاقة له بهذا التسليم), 1 warning (pydantic deprecation موجود مسبقاً
  في platform_core/config.py، لا علاقة له بهذا التسليم أيضاً)

ruff check application/use_cases/process_qr_document_use_case.py \
  infrastructure/qr_reader.py presentation/routes/documents_router.py \
  tests/integration/test_analyze_qr.py
→ All checks passed!

cd packages/qr_invoice_codec && pytest -q
→ 15 passed (من المسار الجديد بعد إعادة الهيكلة — انظر أدناه)

lint-imports (import-linter، من داخل apps/ai-platform)
→ Contracts: 1 kept, 0 broken. (application لا يزال لا يعتمد على presentation)

diff -rq apps/core-api (الأصلية مقابل بعد الدمج)
→ لا فرق إطلاقاً — TASK-AI-05c لم تُنفَّذ (مؤجَّلة كما في التسليم السابق)،
  لم يُفتَح أي ملف core-api حتى للقراءة في هذه الجلسة.
```

## ما تغيّر فعلياً (ملفات، لا وصف عام)

| الملف | نوع التغيير | لماذا |
|---|---|---|
| `packages/qr_invoice_codec/` | **جديد بالكامل** | حزمة `qr_invoice_codec` مُعاد هيكلتها (كانت أصلاً في التسليم المعزول بلا `pyproject.toml`) لتصبح حزمة Python مثبَّتة فعلياً — layout قياسي: `pyproject.toml` + `qr_invoice_codec/` (الحزمة) + `tests/` |
| `apps/ai-platform/infrastructure/qr_reader.py` | **جديد** | `PyzbarQrCodeReader` — بلا تغيير عن النسخة المعزولة |
| `apps/ai-platform/application/use_cases/process_qr_document_use_case.py` | **جديد** | `ProcessQrDocumentUseCase` — بلا تغيير منطقي عن النسخة المعزولة |
| `apps/ai-platform/presentation/routes/documents_router.py` | **إضافة صرفة** (تعديل) | `POST /documents/analyze-qr` أُضيف بعد `/documents/analyze` القائم مباشرة — صفر تعديل على أي سطر موجود مسبقاً (تحقَّق `diff` من ذلك) |
| `apps/ai-platform/tests/integration/test_analyze_qr.py` | **جديد** (أُعيدت كتابته بالكامل عن النسخة المعزولة) | يستخدم الآن `db_session` الحقيقية (fixture من `conftest.py`، SQLite في الذاكرة بمخطط `models.ai_models` الفعلي) و`CoreApiClient` الحقيقي (مموَّه بـ`respx`، نفس نمط `test_core_api_client.py`) بدل fixtures/models وهمية — تحقق حقيقي لا تقريبي |
| `apps/ai-platform/pyproject.toml` | تعديل | إضافة `qr-invoice-codec` (اسم مجرَّد) و`pyzbar` لـ`dependencies`؛ `qrcode` لـ`[dev]`؛ `pythonpath` إضافية لـ`../../packages/qr_invoice_codec` |
| `infra/docker/Dockerfile.ai-platform` | تعديل | `libzbar0` ضمن `apt-get install` الموجود؛ `COPY packages/qr_invoice_codec/` + `pip install -e` منفصل *قبل* `pip install -e ".[dev]"` |
| `.github/workflows/ci.yml` | تعديل | خطوتان جديدتان في job `python-baseline` (شرط `matrix.app == 'ai-platform'` فقط): تثبيت `qr_invoice_codec` محلياً، وتثبيت `libzbar0` — لا تعديل على `core-api` أو `pos-app-baseline` |

## اكتشاف مهم أثناء الدمج: مرجع `file:` النسبي غير موثوق عبر إصدارات pip

الخطة الأصلية للربط كانت مرجع PEP 508 مباشر داخل `dependencies`:
```
"qr-invoice-codec @ file:../../packages/qr_invoice_codec"
```
هذا **نجح فعلياً** مع pip 26.x (مُثبَّت حديثاً)، لكن **فشل صراحة** مع pip 24.0
(الإصدار المرافق فعلياً لـ Python 3.12 على Ubuntu 24.04 هنا، ومحتمل قريب مما
يشحنه `actions/setup-python` افتراضياً في CI) بخطأ:
```
pip._vendor.packaging.requirements.InvalidRequirement: Invalid URL given
```
تحقَّقتُ من هذا بتجربة فعلية على البيئتين، لا افتراضاً. **الإصلاح المعتمَد**:
اسم مجرَّد (`"qr-invoice-codec"` بلا مرجع) في `dependencies`، + خطوة تثبيت
منفصلة صريحة (`pip install -e ../../packages/qr_invoice_codec` بمسار سطر
أوامر خام، لا داخل metadata) *قبل* `pip install -e ".[dev]"` — نمط متوافق مع
كل إصدارات pip الحديثة تقريباً (تحقَّقتُ منه أيضاً فعلياً مع pip 24.0). أُضيف
في ثلاثة أماكن يجب أن تبقى متسقة: `Dockerfile.ai-platform`، `.github/workflows/ci.yml`،
والتعليق التفصيلي داخل `apps/ai-platform/pyproject.toml` نفسه (لأي مطوّر
يشغّل `pip install -e .[dev]` يدوياً محلياً بلا Docker/CI يحتاج يعرف هذا
الترتيب — أضفتُ أيضاً `pythonpath` بديلة في `[tool.pytest.ini_options]`
لتشغيل `pytest` مباشرة بلا أي تثبيت إطلاقاً، لكن هذا يحل الاختبار فقط لا
التشغيل الفعلي لـ`uvicorn main:app`).

## اكتشاف آخر: أنواع الحقول الحقيقية UUID لا `str`

النسخة المعزولة السابقة استخدمت نماذج وهمية بحقول `str`. النماذج الحقيقية
(`models/ai_models.py`) تستخدم `UUID(as_uuid=True)` لـ `company_id` و
`matched_supplier_id`. تحقَّقتُ فعلياً (لا افتراضاً) أن `ProcessQrDocumentUseCase`
يعمل بلا أي تعديل مطلوب: SQLAlchemy مع `postgresql.UUID(as_uuid=True)` يحوّل
نص UUID صالح لـ`uuid.UUID` تلقائياً عند الـbind — نفس السلوك المُستخدَم أصلاً
في `process_document_pipeline.py` و`documents_router.py` القائمين (يمرَّران
`company_id: str` مباشرة لـ`OcrJob`/`InvoiceExtractionDraft` بلا تحويل صريح
أيضاً). **شرط**: قيمة `company_id` الممرَّرة يجب أن تكون نص UUID صالح الشكل
فعلياً (مثال: `"11111111-1111-1111-1111-111111111111"`) — ليست أي نص عشوائي؛
اختُبر هذا الشرط ضمنياً في كل اختبارات `test_analyze_qr.py` الجديدة.

## نقاط لم تتغيّر عن التسليم السابق (لا تزال مفتوحة)

هذه القرارات المفتوحة نفسها من بطاقة التسليم السابقة (`تسليم_TASK-AI-05...`
إن وُجدت، أو الرد السابق مباشرة في هذه المحادثة) **لم تُحسَم هنا** — الدمج
لم يغيّر المنطق، فقط مكانه:

1. **مطابقة المورد عبر `sup.n` (الاسم) لا `sup.tax`** — عقد `core-api`
   الحالي لـ`/internal/partners/known-suppliers` لا يعيد رقماً ضريبياً بعد.
   لا يزال قراراً مفتوحاً يحتاج تنسيقاً مع مالك `core-api`.
2. **`co` يُطابَق مع `company_id` الطلب حرفياً** — راجع الملاحظة الأمنية في
   `process_qr_document_use_case.py` (تعليق `CompanyMismatchError`)؛ هذا
   التفسير الحرفي لِـ"رفض صريح لو لم يطابق" في بطاقة المهمة الأصلية، رغم
   وجود توتر ظاهري مع وصف الحقل نفسه ("company_id أو tax_number **المورّد**")
   — لم يُحسَم هذا التوتر، التنفيذ يتبع الاختبار الأمني المطلوب حرفياً.
3. **الاختبار اليدوي بكاميرا هاتف حقيقية (GATE-QR)** — لا يزال غير منفَّذ
   (لا كاميرا فعلية متاحة في أي بيئة تنفيذ استخدمتها). البديل الآلي
   (`TestPyzbarQrCodeReader::test_reads_real_qr_image_end_to_end`) الآن
   يعمل داخل الشجرة الحقيقية بنفس `pyzbar`/`libzbar0` الذي سيُستخدَم في
   الإنتاج فعلياً (لا بيئة معزولة كما سابقاً) — أقرب تقريب ممكن، يبقى
   الاختبار اليدوي الفعلي مطلوباً قبل إغلاق `GATE-QR` نهائياً.
4. **`TASK-AI-05c` (مولّد QR في core-api)** — لا تزال غير منفَّذة، لم يُفتَح
   `invoices_router.py` حتى للقراءة في هذه الجلسة.

## مخالفات `ruff` المتبقية (موثَّقة، غير مخفية)

```
packages/qr_invoice_codec: 7 مخالفات متبقية بعد --fix، كلها RUF001/RUF002
  ("ambiguous ا/×") — نفس الفئة المُوثَّقة مسبقاً كمعروفة ومقبولة في هذا
  المستودع لأي ملف عربي المحتوى كثيف (راجع تعليق apps/ai-platform/pyproject.toml
  "19 مخالفة" وapps/core-api/pyproject.toml "322 مخالفة" — نفس النمط تماماً،
  لا شيء جديد أو غير مسبوق هنا). لم أُخفِها بـ# noqa جماعي — تُركت ليلتقطها
  scripts/generate_lint_baseline.sh مع الدفعة القادمة من baseline، بنفس آلية
  بقية المشروع (scripts/check_lint_against_baseline.py).
```

## قبل الإنتاج — ما تبقى فعلاً (بصراحة)

- تشغيل `scripts/generate_lint_baseline.sh` لتحديث baseline بما يشمل
  `packages/qr_invoice_codec/` (لم أُشغِّله هنا — خارج نطاق هذا الدمج، لم
  يُطلَب صراحة).
- اختبار كاميرا هاتف حقيقي (بند 3 أعلاه).
- حسم القرارين المفتوحين (بندان 1 و2 أعلاه) مع صاحب القرار/مالك core-api.
- `docker compose up --build ai-platform` فعلياً (لم أُشغِّل Docker هنا —
  لا محرك Docker متاح في بيئة التنفيذ التي استخدمتها؛ التحقق تم عبر محاكاة
  يدوية دقيقة لكل أمر داخل `Dockerfile.ai-platform` بنفس الترتيب والمسارات
  النسبية، لا عبر بناء الصورة فعلياً — الفرق موثَّق هنا بصراحة، ليس افتراضاً
  مموَّهاً كتحقق كامل).
