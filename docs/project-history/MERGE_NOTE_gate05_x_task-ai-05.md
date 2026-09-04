# ملاحظة الدمج: GATE05_RUNBOOK × TASK-AI-05

تم دمج الحزمتين المرفوعتين في نسخة نهائية واحدة. هذا سجل بقرارات الدمج.

## الأساس المُعتمَد
تم اعتماد حزمة **TASK-AI-05** (`...merged/`) كأساس، للأسباب التالية:
- تحتوي على ميزة QR الكاملة غير الموجودة في GATE05: حزمة `packages/qr_invoice_codec`،
  `apps/ai-platform/infrastructure/qr_reader.py`،
  `apps/ai-platform/application/use_cases/process_qr_document_use_case.py`، ونقطة النهاية
  `POST /documents/analyze-qr`، مع اختبار التكامل `test_analyze_qr.py`.
- أسماء الملفات العربية سليمة الترميز (UTF-8)، بينما نفس الملفات في حزمة GATE05 كانت
  بأسماء تالفة (escaped `#Uxxxx`) بسبب مشكلة ترميز عند إنشاء ذلك الأرشيف.

## ما تم ترحيله من GATE05_RUNBOOK فوق هذا الأساس
1. **`apps/core-api/main.py`** — نسخة GATE05 تضيف `CORSMiddleware` غير الموجود في TASK-AI-05.
2. **`scripts/load/k6_sales_invoice_create.js`** — نسخة GATE05 تحمل إصلاحاً حقيقياً مؤرَّخاً
   2026-08-17 (تصحيح المسار من `/sales/invoices` إلى `/sales-invoices` الصحيح المسجَّل فعلياً
   في `main.py`، وإضافة `WAREHOUSE_ID` المطلوب) — نسخة TASK-AI-05 كانت تحمل النسخة القديمة
   المعطوبة (404 على كل طلب).
3. **`invoice.png`** و **`results_invoice_create.json`** — أدلة/مخرجات اختبار من جلسة إغلاق
   البوابة (Gate 05 closure)، غير موجودة في TASK-AI-05، أُبقيت للمرجعية.

## ما تم استبعاده عمداً
- مجلدات `__pycache__`، `.pyc`، `.ruff_cache`، `.pytest_cache` — ملفات بناء/تخزين مؤقت لا تخص
  الكود المصدري، وكانت موجودة (بشكل غير متسق) في كلا الأرشيفين الأصليين.

## ملفات لم تتعارض (طابقت في الحزمتين)
باقي الشجرة (apps/desktop، apps/web، apps/pos-app، packages/api-types، packages/i18n،
packages/ui-kit، docs/، infra/k8s، إلخ) كانت متطابقة بين الحزمتين ولم تحتج قراراً.

## التحقق
- فحص syntax لجميع ملفات `.py` في الحزمة النهائية: **لا أخطاء**.
- فحص صحة كل ملفات `.json`: **سليمة**.
- عدد الملفات النهائي: 798 ملفاً (796 من قاعدة TASK-AI-05 + ملفا الإغلاق من GATE05).
