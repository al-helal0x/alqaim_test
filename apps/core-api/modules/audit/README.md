# Module: audit

**المسؤول:** العضو 12 (Workflow + Notifications + Audit)

## الحالة الفعلية
✅ **تسجيل تدقيق شامل لكل الأحداث الستة المُعلَنة في `docs/architecture/contracts.md`
§2 مُنجَز ومُختبَر فعلياً.** لا صلاحية للكتابة عبر API — الكتابة الوحيدة هي
عبر Event Bus (`RecordAuditLogUseCase`، مُسجَّل في `main.py`).

## الجداول
`audit_log_entries`

## APIs
```
GET /audit/logs?event_name=&page=&page_size=&sort=   (صلاحية: audit.log.view)
```
لا `POST`/`DELETE` — عمداً. السجل يُكتَب فقط عبر Event Bus، وإلا فقد
المصداقية كسجل تدقيق قابل للثقة.

## آلية التسجيل
`RecordAuditLogUseCase` مسجَّل في `main.py` كمشترك في **الأحداث الستة كاملة**
(`InvoicePosted`, `PaymentRecorded`, `StockLevelLow`, `AccountSettingsChanged`,
`InvoiceDraftReady`, `FiscalPeriodClosed`) — وظيفته التسجيل الشامل غير
الانتقائي، عكس `notifications`. أي حمولة بلا `company_id` تُهمَل بصمت (لا
يمكن نطاقها لأي شركة) — نفس منطق `DispatchEventToWebhooksUseCase` للعضو 13.

## ملاحظة صادقة
لا حقل `actor_user_id` منفصل حالياً — أغلب الأحداث الحالية في `contracts.md`
§2 لا تحمل هوية فاعل (`user_id`) في حمولتها، فقط `company_id` ومعرِّفات
الكيانات. لم أُضِف حقلاً لن يُملأ أبداً؛ إن أضافت الوحدات الناشرة `user_id`
لاحقاً لحمولاتها، يمكن إضافته بـ migration منفصلة.

كذلك: حدث `StockLevelLow` موثَّق في `contracts.md` §2 بحمولة **بلا**
`company_id` صراحةً (`{product_id, warehouse_id, current_qty, threshold}`).
إن لم يُضِفه الناشر الفعلي (`inventory`) لحمولته، الاشتراك به هنا لن يُنتج
سجلات فعلياً رغم كونه مشتركاً به تقنياً — راجع `MAIN_PY_PATCH.md` في جذر
حزمة التسليم لتفاصيل هذه الفجوة (تماماً كفجوة `InvoiceDraftReady` الموثَّقة
سابقاً في `modules/integrations/README.md`).

## البنية الداخلية (4 طبقات إلزامية — القسم 6.4 من الوثيقة)
```
audit/
├── domain/            # فارغة عمداً في هذه الجولة — لا قواعد أعمال صرفة
│   ├── entities/       # تتجاوز "سجّل حدثاً بحمولته كما وصل" (نفس حال domain/
│   ├── value_objects/  # في integrations — راجع الملف المرجعي)
│   └── rules/
├── application/        # Use Cases + DTOs
│   ├── use_cases/       # audit_use_cases.py
│   ├── dto/             # audit_dto.py
│   └── ports/            # فارغ — لا واجهات خارجية تحتاجها هذه الوحدة
├── infrastructure/     # SQLAlchemy repo + models
│   ├── repositories/    # audit_repository.py
│   ├── external/         # فارغ
│   └── models/           # audit_models.py
└── presentation/        # FastAPI router فقط
    └── routes/            # audit_router.py
```

## قاعدة الاستيراد (إلزامية)
`presentation → application → domain` و `infrastructure → application/domain` فقط.
ممنوع أن يستورد `domain` من `infrastructure` أو `presentation`.
ممنوع استيراد `infrastructure` الخاص بـ module آخر مباشرة — التواصل فقط عبر الواجهة المعلنة (Ports) أو الأحداث (Events).
