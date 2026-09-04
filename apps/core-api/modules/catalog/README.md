# Module: catalog

**المسؤول:** العضو 2 — Master Data (Partners & Catalog)

## المسؤولية
Products, Categories, UoM, Price Lists

## الجداول
product_categories, units_of_measure, products, price_lists, price_list_items

## APIs
/products/*, /categories/*, /units-of-measure/*, /price-lists/*

## الواجهات التي يوفرها هذا الـ Module لغيره
IProductLookup.get(product_id)

## البنية الداخلية (4 طبقات إلزامية — القسم 6.4 من الوثيقة)
```
catalog/
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
