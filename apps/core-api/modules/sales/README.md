# Module: sales

**المسؤول:** العضو 4 — Sales & POS

## المسؤولية
عروض أسعار/أوامر بيع/فواتير بيع/إشعارات دائن

## الجداول
quotations, sales_orders, invoices(type=sale), invoice_lines, credit_notes

## APIs
/quotations/*, /sales-orders/*, /sales-invoices/*, /credit-notes/*

## الواجهات التي يوفرها هذا الـ Module لغيره
- حدث `SalesInvoiceCreated` عبر Event Bus (يُنشَر من `CreateSalesInvoiceUseCase`
  بعد commit — `{invoice_id, company_id, partner_id, total_amount, currency}`).

## تكامل فعلي مع workflow (مهمة #12)
فاتورة بيع بإجمالي > 10,000 تحتاج موافقة مدير قبل الترحيل:
1. `CreateSalesInvoiceUseCase` تنشر `SalesInvoiceCreated` بعد إنشاء الفاتورة.
2. `sales/infrastructure/event_handlers.py:handle_sales_invoice_created`
   (مُسجَّل في `apps/core-api/main.py`) يستدعي
   `StartManagerApprovalForSalesInvoiceUseCase` — إن تجاوز `total_amount`
   `SALES_INVOICE_MANAGER_APPROVAL_THRESHOLD` (`domain/rules`، حالياً 10,000)
   يبدأ نسخة موافقة على محرك workflow العام عبر `IWorkflowPort`
   (`modules.workflow.application.ports.workflow_port`) — لا استيراد مباشر
   لأي شيء من `workflow/infrastructure` في طبقة sales.
3. `PostSalesInvoiceUseCase` يستعلم عن حالة آخر نسخة موافقة لهذه الفاتورة
   عبر نفس الـ Port قبل أي حجز/ترحيل، ويرفض الترحيل (`InvoiceApprovalPendingError`
   / `InvoiceApprovalRejectedError` ← `403` على مستوى `invoices_router.py`)
   ما دامت النسخة `pending_approval` أو `rejected`.

`workflow_port` معامل **اختياري** في `PostSalesInvoiceUseCase` (افتراضي
`_NullWorkflowPort` بلا أي تأثير) — أي مسار قائم لا يُمرِّره صراحة (مثال:
`modules/pos` عند البيع المباشر — خارج نطاق ملفات هذه المهمة) يستمر بسلوكه
السابق دون أي تغيير أو كسر.

## البنية الداخلية (4 طبقات إلزامية — القسم 6.4 من الوثيقة)
```
sales/
├── domain/            # كيانات وقواعد صرفة — بدون أي اعتماد على DB أو Framework
│   ├── entities/
│   ├── value_objects/
│   └── rules/
├── application/        # Use Cases + DTOs + Ports (واجهات مجردة فقط)
│   ├── use_cases/
│   ├── dto/
│   └── ports/
├── infrastructure/     # SQLAlchemy repos, تنفيذ الـ Ports, نداءات خارجية
│   ├── repositories/
│   ├── external/
│   └── models/
└── presentation/        # FastAPI routers فقط — بدون أي منطق أعمال
    └── routes/
```

## قاعدة الاستيراد (إلزامية)
`presentation → application → domain` و `infrastructure → application/domain` فقط.
ممنوع أن يستورد `domain` من `infrastructure` أو `presentation`.
ممنوع استيراد `infrastructure` الخاص بـ module آخر مباشرة — التواصل فقط عبر الواجهة المعلنة (Ports) أو الأحداث (Events).
