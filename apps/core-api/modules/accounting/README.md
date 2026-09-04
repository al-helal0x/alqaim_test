# Module: accounting

**المسؤول:** العضو 6 — Accounting & Taxation

## المسؤولية
شجرة حسابات/قيود/سنوات وفترات مالية/مراكز تكلفة

## الجداول
accounts, journal_entries, journal_entry_lines, fiscal_years, fiscal_periods, cost_centers

## APIs
/accounts/*, /journal-entries/*, /fiscal-periods/*

## الواجهات التي يوفرها هذا الـ Module لغيره
IAccountingPort.record_document_posting(document_dto) -> JournalEntryRef  ★ أهم واجهة في النظام

## البنية الداخلية (4 طبقات إلزامية — القسم 6.4 من الوثيقة)
```
accounting/
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
- ✅ منفَّذ فعلياً: شجرة الحسابات (يدوياً عبر `/accounts` أو بزرع شجرة افتراضية جاهزة عبر `/accounts/seed-defaults`)، القيود اليدوية والتلقائية (`IAccountingPort`)، السنوات/الفترات المالية وإقفالها.
- ✅ 16 اختبار تكامل تمر: توازن القيد، منع الترحيل على فترة مقفلة، منع الإزراع المكرر لشجرة الحسابات، اتساق قائمة الدخل مع الميزانية العمومية.
- ⏳ لم يُبنَ بعد: آلية قيود الإقفال السنوية (Closing Entries) التي ترحّل صافي الربح فعلياً إلى "الأرباح المرحّلة" — انظر TODO في `modules/reporting/application/use_cases/financial_statements_use_case.py`.

