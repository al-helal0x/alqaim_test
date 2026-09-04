# Module: inventory

**المسؤول:** العضو 3 — Inventory

## المسؤولية
أرصدة، حركات، تحويلات، تسويات، طرق تقييم، Barcode/QR

## الجداول
stock_movements, stock_balances, stock_transfers, stock_adjustments

## APIs
/inventory/movements, /inventory/balances, /inventory/transfers, /inventory/adjustments, /inventory/barcode/{code}

## الواجهات التي يوفرها هذا الـ Module لغيره
IInventoryPort.reserve_stock(...), IInventoryPort.deduct_stock(...)

## البنية الداخلية (4 طبقات إلزامية — القسم 6.4 من الوثيقة)
```
inventory/
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
