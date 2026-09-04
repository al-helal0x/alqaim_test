# Module: workflow

**المسؤول:** العضو 12 (Workflow + Notifications + Audit)

## الحالة الفعلية
✅ **محرك حالات عام (State Machine) قابل للربط بأي كيان مُنجَز ومُختبَر
فعلياً** — تعريف/بدء نسخة/تنفيذ انتقال مع تحقق صارم من صحة الانتقال.
✅ **أول استهلاك فعلي من موديول آخر (مهمة #12، sales)** عبر `IWorkflowPort`
— راجع القسم أدناه. **لا اشتراك في Event Bus من طرف workflow نفسها** (لا
يزال — راجع القرار أدناه).

## الجداول
`workflow_definitions`, `workflow_instances`

## APIs
```
POST /workflow/definitions                        (صلاحية: workflow.definition.manage)
GET  /workflow/definitions?entity_type=
POST /workflow/instances                           (بدء نسخة جديدة)
GET  /workflow/instances?entity_type=&entity_id=
POST /workflow/instances/{id}/transition            (صلاحية: workflow.instance.transition)
```

## قاعدة تحقق إلزامية
أي انتقال (`transition_name`) غير معرَّف في `definition.transitions` **لحالة
النسخة الحالية تحديداً** (وليس فقط غير معرَّف إطلاقاً) يرفع `ValueError` ←
`400 Bad Request` على مستوى الـ Router. لا فشل صامت ولا تجاهل.

كذلك: عند إنشاء تعريف، أي انتقال يشير لحالة (`from`/`to`) غير موجودة في
`states` يُرفَض عند التحقق (Pydantic validator في `WorkflowDefinitionCreateRequest`)
قبل أن يصل لقاعدة البيانات أصلاً.

## قرار معماري متعمَّد: لا استهلاك لأحداث Event Bus هذه الجولة
`workflow` **لا تشترك** في أي حدث من `docs/architecture/contracts.md` §2
مباشرة، ولا يزال هذا القرار قائماً بعد مهمة #12 أدناه. هي خدمة عامة
(Approval Engine) تُستدعى صراحة عبر API/Port من أي وحدة أخرى تحتاج سير
موافقات — لا تشترك هي نفسها في أي حدث لتقرر متى تبدأ نسخة.

## أول استهلاك فعلي: مهمة #12 (sales → workflow)
`sales` تستهلك `workflow` الآن فعلياً عبر Port جديد
`IWorkflowPort` (`application/ports/workflow_port.py`) + Adapter
(`infrastructure/adapters/workflow_port_adapter.py`) — **وليس** عبر اشتراك
`workflow` في حدث؛ الاتجاه معكوس تماماً كما في القرار أعلاه: `sales` هي من
تشترك في حدثها الداخلي `SalesInvoiceCreated`، ومعالِجها هو من يستدعي
`IWorkflowPort` صراحة إن تجاوزت الفاتورة 10,000 (راجع
`modules/sales/application/use_cases/sales_use_cases.py:StartManagerApprovalForSalesInvoiceUseCase`
و`modules/sales/infrastructure/event_handlers.py`).

السيناريو الفعلي المُغلَق الآن: "فاتورة بيع > 10,000 تحتاج موافقة مدير" —
`workflow_instance` يُنشأ تلقائياً بحالة `pending_approval` (تعريف
`sales_invoice_manager_approval`، `entity_type=sales_invoice`)، ولا يمكن
ترحيل الفاتورة (`PostSalesInvoiceUseCase`) وهي بهذه الحالة. الموافقة/الرفض
تتمّان عبر الـ API العام الموجود مسبقاً:
`POST /workflow/instances/{id}/transition` بـ `transition_name` = `approve`
أو `reject` (يتطلب صلاحية `workflow.instance.transition` — نفس آلية RBAC
الموجودة، بلا أي إضافة جديدة لها في هذه المهمة).

## البنية الداخلية (4 طبقات إلزامية — القسم 6.4 من الوثيقة)
```
workflow/
├── domain/            # فارغة عمداً في هذه الجولة
│   ├── entities/
│   ├── value_objects/
│   └── rules/
├── application/
│   ├── use_cases/       # workflow_use_cases.py
│   ├── dto/             # workflow_dto.py
│   └── ports/            # workflow_port.py (IWorkflowPort — أول Port نُصدِّره، مهمة #12)
├── infrastructure/
│   ├── repositories/    # workflow_repository.py
│   ├── external/         # فارغ
│   ├── adapters/         # workflow_port_adapter.py (WorkflowPortAdapter — تنفيذ IWorkflowPort، مهمة #12)
│   └── models/           # workflow_models.py
└── presentation/
    └── routes/            # workflow_router.py
```

## قاعدة الاستيراد (إلزامية)
`presentation → application → domain` و `infrastructure → application/domain` فقط.
ممنوع أن يستورد `domain` من `infrastructure` أو `presentation`.
ممنوع استيراد `infrastructure` الخاص بـ module آخر مباشرة — التواصل فقط عبر الواجهة المعلنة (Ports) أو الأحداث (Events).
