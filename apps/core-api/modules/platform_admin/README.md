# Module: platform_admin

**المسؤول:** العضو 13 (Documents + Integrations + Platform Admin)

## الحالة الفعلية
✅ **مُنجَز فعلياً ومُختبَر** — سرد كل الشركات على المنصة + تعليق/تفعيل شركة.

## الجداول
— (لا جدول جديد؛ يعيد استخدام `companies.is_active` الموجود منذ
`platform_20260804_0001`)

## APIs
```
GET  /platform-admin/companies              (كل الشركات — عابر لكل tenants)
POST /platform-admin/companies/{id}/suspend
POST /platform-admin/companies/{id}/activate
```

## ⚠️ استثناء معماري متعمَّد — اقرأ قبل التعديل
هذه الوحدة الوحيدة في النظام التي **لا** تُقيَّد استعلاماتها بـ
`ctx.company_id` — غرضها إدارة الشركات نفسها. التوثيق الكامل لسبب هذا
الاستثناء وحدوده في
`application/use_cases/platform_admin_use_cases.py` (بداية الملف). قصور
معروف: لا مفهوم "صلاحية عابرة للشركات" أصيل في `TenantContext` بعد — الحل
الحالي يعتمد فقط على صلاحية `platform_admin.company.manage`، وهذا يستحق
تصميماً أنضج لاحقاً.


## البنية الداخلية (4 طبقات إلزامية — القسم 6.4 من الوثيقة)
```
platform_admin/
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
