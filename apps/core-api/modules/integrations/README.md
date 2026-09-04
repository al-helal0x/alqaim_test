# Module: integrations

**المسؤول:** العضو 13 (Documents + Integrations + Platform Admin)

## الحالة الفعلية
✅ **Webhooks الصادرة مُنجَزة ومُختبَرة فعلياً** — النطاق الأوسع المذكور في
الوصف الأصلي (Import/Export) **مؤجَّل عمداً**، خارج نطاق هذا التسليم.

## الجداول
webhook_subscriptions, webhook_deliveries

## APIs
```
POST   /webhooks                       (يُعيد secret مرة واحدة فقط عند الإنشاء)
GET    /webhooks
DELETE /webhooks/{id}                  (إلغاء تفعيل، وليس حذفاً فعلياً)
GET    /webhooks/{id}/deliveries       (سجل محاولات التسليم — للتشخيص)
```

## آلية البث
`DispatchEventToWebhooksUseCase` مسجَّل في `main.py` كمشترك في Event Bus
لأحداث `InvoicePosted` و`PaymentRecorded` (الأحداث الوحيدة التي تحمل
`company_id` فعلياً في حمولتها حتى الآن). كل حمولة تُوقَّع بـ HMAC-SHA256
على سر الاشتراك (`X-AlQaim-Signature: sha256=...`) — راجع
`infrastructure/external/httpx_webhook_sender.py`.

## ملاحظة صادقة
`InvoiceDraftReady` غير مُشترَك به بعد — حمولته الحالية (راجع
`docs/architecture/contracts.md` §4) لا تحمل `company_id` مباشرة.


## البنية الداخلية (4 طبقات إلزامية — القسم 6.4 من الوثيقة)
```
integrations/
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
