# Module: taxation

**المسؤول:** العضو 6 — Accounting & Taxation

## المسؤولية
ضرائب/فوترة إلكترونية

## الجداول
tax_rates, e_invoice_submissions

## APIs
/tax-rates/*

## الواجهات التي يوفرها هذا الـ Module لغيره
—

## البنية الداخلية (4 طبقات إلزامية — القسم 6.4 من الوثيقة)
```
taxation/
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

## الحالة (محدَّثة)
- ✅ منفَّذ: `tax_rates` (CRUD + حساب ضريبة `/tax-rates/calculate`)، `e_invoice_submissions` كسجل تتبّع بحالة `pending`.
- ⏳ الإرسال الفعلي لبوابة فوترة إلكترونية حكومية **غير منفَّذ** — Blueprint لم يحدد مزوّداً/بروتوكولاً. ينتظر قراراً من الفريق قبل بناء `infrastructure/external/`.
