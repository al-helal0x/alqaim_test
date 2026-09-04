# Module: reporting

**المسؤول:** العضو 6 — Accounting & Taxation

## المسؤولية
التقارير المالية الأساسية

## الجداول
—

## APIs
/reports/trial-balance, /reports/income-statement, /reports/balance-sheet

## الواجهات التي يوفرها هذا الـ Module لغيره
—

## البنية الداخلية (4 طبقات إلزامية — القسم 6.4 من الوثيقة)
```
reporting/
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
- ✅ منفَّذ ومُختبَر: `/reports/trial-balance`، `/reports/income-statement`، `/reports/balance-sheet`.
- ⚠️ balance-sheet: صافي ربح الفترة الحالية يُعرَض كسطر حقوق ملكية مؤقت لأن هذا الإصدار لا يملك بعد آلية قيود إقفال (Closing Entries) تُرحِّله فعلياً إلى "الأرباح المرحّلة" — موثَّق كـ TODO داخل `financial_statements_use_case.py`.
- ملاحظة بنيوية: هذه الوحدة تقرأ مباشرة من نماذج `accounting` (استثناء موثَّق لأن العضو 6 يملك الوحدتين معاً — وليس نمطاً عاماً لبقية الوحدات، القسم 11.2).
