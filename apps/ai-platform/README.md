# apps/ai-platform

خدمة الذكاء الاصطناعي المستقلة — الاستثناء المعماري المتعمَّد الوحيد (القسم 6.12/7.10).

**المسؤول:** العضو 8 — AI Platform Lead.

## الحالة الفعلية الحالية (وليس الخطة النهائية)

يغطي هذا التسليم **المرحلة الأولى فقط من خطة القسم 7.13** (ضمن MVP):
"OCR + استخراج الحقول الأساسية، مطابقة منتج/مورد بسيطة، تحقق منطقي أساسي،
شاشة مراجعة بشرية إلزامية — لا ترحيل تلقائي بدون موافقة بشرية إطلاقاً."

| الخدمة (Port) | الحالة | التنفيذ الفعلي | الحدود المعروفة (موثَّقة داخل كل ملف) |
|---|---|---|---|
| `IDocumentPreprocessor` | ✅ يعمل | OpenCV (Denoise + Adaptive Threshold + Deskew) | — |
| `IOCREngine` | ✅ يعمل | Tesseract (ara+eng) — مُختبَر فعلياً على صور PIL حقيقية | جودة أقل من PaddleOCR/سحابي على تخطيطات معقدة (القسم 7.12) |
| `IInvoiceParser` | ✅ يعمل (Baseline) | Regex/كلمات مفتاحية عربي+إنجليزي | ليس Document Understanding حقيقياً (LayoutLM/سحابي) — لا يدمج الموقع المكاني للنص |
| `IEntityMatcher` | ✅ يعمل (Baseline) | Fuzzy String Matching (rapidfuzz) | ليس مطابقة دلالية بـ Embeddings — "كولا" لن تُطابَق مع "Coca-Cola" بدون تشابه حروف |
| `IValidator` | ✅ يعمل بالكامل | فحوصات القسم 7.5 الكاملة (تطابق الإجمالي، قيم سالبة، عملة، رقم مفقود) | — |
| `ILearningStore` | ✅ يعمل | تخزين فعلي في `ai_learning_feedback` | حلقة إعادة الضبط الدوري (Fine-tuning) غير مبنية بعد — مرحلة 2 |
| `ILLMProvider` | ⚠️ Interface فقط | `NullLLMProvider` يفشل بوضوح بدل الادّعاء | ميزة مرحلة 4 أصلاً حسب القسم 7.13 — ليست MVP |
| `IRecommendationService` | ⚠️ منطق أولي بسيط | Reorder Point كلاسيكي شفاف | ميزة مرحلة 3 أصلاً حسب القسم 7.13 — ليست MVP |
| Pipeline الكامل (7.11) | ✅ يعمل من صورة حتى Draft | `application/use_cases/process_document_pipeline.py` | حدث `InvoiceDraftReady` عبر Event Bus بين الخدمتين لم يُثبَّت آلياً بعد (TODO موثَّق في `workers/tasks.py`) — بانتظار بند contracts.md |

**التحقق:** 15/15 اختبار ناجح فعلياً، منها 3 اختبارات end-to-end تولّد صورة
فاتورة حقيقية وتشغّل عليها الأنبوب كاملاً — انظر `tests/README.md`.

## البنية
```
services/
├── preprocessing/    # OpenCvPreprocessor
├── ocr/               # TesseractOCREngine
├── invoice_parser/    # HeuristicInvoiceParser
├── entity_matching/   # FuzzyEntityMatcher
├── validation/        # InvoiceValidator
├── learning/           # SqlLearningStore
├── llm_gateway/        # NullLLMProvider (Interface جاهز، بانتظار مرحلة 4)
└── recommendation/     # SimpleReorderRecommendationService (بانتظار مرحلة 3)
application/
├── ports/ai_ports.py           # كل الـ Protocols (القسم 7.9) + DTOs المشتركة
└── use_cases/process_document_pipeline.py   # الأنبوب الكامل (القسم 7.11)
models/ai_models.py              # جداول قاعدة بيانات ai-platform المستقلة (8.5)
migrations/                       # Alembic خاص بقاعدة بيانات ai-platform وحدها
presentation/routes/              # /ai/documents/*, /ai/drafts/*, /ai/entities/*
workers/tasks.py                   # Celery — غلاف رقيق حول نفس Use Case
```

## العقد مع بقية النظام
- التواصل عبر Job Queue (Redis/Celery) + Event Bus فقط — لا اعتماد تنفيذي
  مباشر من/إلى `core-api`. **ملاحظة صريحة:** آلية نشر حدث `InvoiceDraftReady`
  الفعلية بين عمليتي `core-api` و`ai-platform` المنفصلتين لم تُثبَّت بعد في
  `docs/architecture/contracts.md` — هذا لا يزال أهم عنق زجاجة لإكمال الربط
  الكامل مع العضو 4 (Sales/Purchasing)، وليس نقصاً تقنياً في هذه الخدمة.
- أول مستهلك مخطَّط: العضو 4 (Purchasing) عبر حدث `InvoiceDraftReady`.

## تشغيل محلي
```bash
cd apps/ai-platform
pip install -e ".[dev]" --break-system-packages
apt-get install -y tesseract-ocr tesseract-ocr-ara
PYTHONPATH=. uvicorn main:app --reload --port 8100
```

## مبدأ ثابت (مُطبَّق فعلياً وليس تعليقاً فقط)
`InvoiceExtractionDraft.status` يبدأ دائماً بـ `pending_review` في الكود —
لا مسار برمجي واحد يعتمد فاتورة تلقائياً (انظر `process_document_pipeline.py`).
