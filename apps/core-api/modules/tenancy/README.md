# Module: tenancy

**المسؤول:** العضو 1 — Platform & Foundation Lead

## المسؤولية
Companies, Branches, Warehouses, Settings, Numbering

## الجداول
companies, branches, warehouses, system_settings, numbering_sequences

## APIs
/companies/*, /branches/*, /warehouses/*, /settings/*

## الواجهات التي يوفرها هذا الـ Module لغيره
TenantContext, INumberingService.next_number(document_type)

## البنية الداخلية (4 طبقات إلزامية — القسم 6.4 من الوثيقة)
```
tenancy/
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
