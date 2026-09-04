# Module: notifications

**المسؤول:** العضو 12 (Workflow + Notifications + Audit)

## الحالة الفعلية
✅ **إشعارات مستهلَكة من Event Bus مُنجَزة ومُختبَرة فعلياً** للحدثين
المُعلَنين صراحة كمستهلِك لهما في `docs/architecture/contracts.md` §2:
`InvoicePosted` و`StockLevelLow`. **لا اشتراك في أي حدث آخر** — تحديداً لا
اشتراك في `PaymentRecorded` رغم قربه المنطقي، لأنه غير موثَّق كمستهلِك من
notifications في العقود الموقَّعة.

## الجداول
`notifications`

## APIs
```
GET  /notifications?is_read=&page=&page_size=&sort=
POST /notifications/{id}/read
```
لا صلاحية RBAC مخصَّصة على أي منهما — كل مستخدم مصادَق عليه يرى إشعارات
شركته فقط، ضمنياً عبر `ctx.company_id` القادم من التوكن.

## آلية الإنشاء
`CreateNotificationFromEventUseCase` مسجَّل في `main.py` كمشترك في
`InvoicePosted`/`StockLevelLow` فقط، عبر قاموس `_TEMPLATES` صريح يُترجم كل
حدث لعنوان/نص عربي بشري. أي حدث آخر (أو حدث بلا `company_id`) يُتجاهَل بصمت.

## قرار متعمَّد: لا حقل `user_id`
الإشعار على مستوى الشركة كاملة (كل مستخدمي `company_id` يرونه)، لا توجيه
لمستخدم بعينه. توجيه فردي يحتاج معرفة "من يجب أن يُبلَّغ" لكل نوع حدث —
منطق أعمال أوسع (مثلاً: مدير المخزون فقط لـ `StockLevelLow`) خارج نطاق هذه
الجولة. TODO صريح لجولة لاحقة، وليس نسياناً.

## ملاحظة صادقة
حدث `StockLevelLow` موثَّق في `contracts.md` §2 بحمولة **بلا** `company_id`
صراحةً (`{product_id, warehouse_id, current_qty, threshold}`). الاشتراك به
هنا لن يُنتج إشعارات فعلياً حتى يُضيف الناشر (`inventory`) `company_id`
لحمولته — نفس فجوة `InvoiceDraftReady` الموثَّقة سابقاً في
`modules/integrations/README.md`. الاختبار `test_stock_level_low_creates_notification_with_expected_text`
في حزمتي يمرّر `company_id` يدوياً في الحمولة الوهمية لاختبار منطق القالب
بمعزل عن هذه الفجوة — لا يُثبت أن الناشر الفعلي يفعل ذلك.

## البنية الداخلية (4 طبقات إلزامية — القسم 6.4 من الوثيقة)
```
notifications/
├── domain/            # فارغة عمداً في هذه الجولة
│   ├── entities/
│   ├── value_objects/
│   └── rules/
├── application/
│   ├── use_cases/       # notifications_use_cases.py
│   ├── dto/             # notifications_dto.py
│   └── ports/            # فارغ
├── infrastructure/
│   ├── repositories/    # notifications_repository.py
│   ├── external/         # فارغ
│   └── models/           # notifications_models.py
└── presentation/
    └── routes/            # notifications_router.py
```

## قاعدة الاستيراد (إلزامية)
`presentation → application → domain` و `infrastructure → application/domain` فقط.
ممنوع أن يستورد `domain` من `infrastructure` أو `presentation`.
ممنوع استيراد `infrastructure` الخاص بـ module آخر مباشرة — التواصل فقط عبر الواجهة المعلنة (Ports) أو الأحداث (Events).
