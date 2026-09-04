# Module: documents

**المسؤول:** العضو 13 (Documents + Integrations + Platform Admin)

## الحالة الفعلية
✅ **مُنجَز فعلياً ومُختبَر** — رفع/سرد/تنزيل/حذف مرفقات عامة قابلة للربط
بأي كيان في أي Module آخر عبر (`entity_type`, `entity_id`) بدل مفتاح خارجي
صريح لكل نوع مستند.

## الجداول
documents

## APIs
```
POST   /documents                          (multipart/form-data: entity_type, entity_id, file)
GET    /documents?entity_type=&entity_id=
GET    /documents/{id}/download
DELETE /documents/{id}
```

## الواجهات التي يوفرها هذا الـ Module لغيره
`IFileStorage` (application/ports/file_storage_port.py) — التنفيذ الحالي
`LocalFileStorage` (قرص محلي، راجع `platform_core/config.py` لتفسير عدم
استخدام MinIO/S3 بعد رغم وجود إعداداته من البداية). أي Module آخر يحتاج رفع
ملفات يمكنه استهلاك نفس الـ Port لاحقاً.

## قيد معروف
حد أقصى 25MB لكل ملف (`MAX_UPLOAD_SIZE_BYTES` في `documents_use_cases.py`).
لا فحص فيروسات/محتوى — خارج نطاق هذا التسليم.


## البنية الداخلية (4 طبقات إلزامية — القسم 6.4 من الوثيقة)
```
documents/
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
