# Module: payments

**المسؤول:** العضو 5 — Purchasing & Payments

## الحالة الفعلية
✅ **مُنجَز فعلياً ومُختبَر** — حسابات بنكية، سندات صرف (تنشر حدث
`PaymentRecorded`)، سندات قبض. الترقيم عبر `INumberingService` الحقيقي
(وحدة tenancy).

## الجداول
bank_accounts, payments, receipts

## APIs
```
POST /bank-accounts     GET /bank-accounts
POST /payments            (ينشر حدث PaymentRecorded عند وجود reference_invoice_id)
POST /receipts
```

## ملاحظة تصميم مقصودة
`Payment`/`Receipt` لا يستوردان جداول `purchasing`/`sales` مباشرة (القسم
11.2) — الربط بفاتورة مرجعية يتم فقط عبر `reference_invoice_id` + حدث
`PaymentRecorded` يستهلكه الطرف المعني (انظر
`modules/purchasing/infrastructure/event_handlers.py`).
