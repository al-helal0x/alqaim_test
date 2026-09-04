# Module: data_migration

**المسؤول:** غير مُسنَد بعد — يُقترَح إسناده لنفس مسؤول `integrations`
(العضو 13) بما أن README الأصلي لـ `integrations` ذكر Import/Export كنطاق
مؤجَّل، أو لعضو جديد مخصَّص — قرار فريق لا قرار تقني.

## الحالة الفعلية
🔴 **هيكل ملفات فقط (Scaffold)** — لا منطق فعلي يعمل بعد. كل use case يحوي
`raise NotImplementedError` بدل تنفيذ حقيقي. راجع
`docs/DATA_MIGRATION_BUILD_PLAN.md` لترتيب المهام الفعلي (`TASK-MIG-00` وما
بعدها) قبل البدء.

**تحديث مطلوب في `modules/integrations/README.md`**: عبارة "Import/Export
مؤجَّل عمداً" هناك أصبحت غير دقيقة بعد إضافة هذا الموديول — يجب تعديلها
لتشير إلى `data_migration` بدل ترك القارئ يظن أن النطاق ما زال داخل
`integrations`.

## الجداول
`data_migration_import_jobs`, `data_migration_import_batches`,
`data_migration_import_row_errors` — لم يُنشَأ أي Alembic migration بعد
(راجع `TASK-MIG-02`).

## APIs (مخطَّطة، جزء منها فقط مُسجَّل في main.py حتى الآن)
```
POST /data-migration/jobs                    إنشاء مهمة استيراد (تسجيل مصدر فقط)
POST /data-migration/jobs/{id}/discover       اكتشاف الجداول/الأعمدة
POST /data-migration/jobs/{id}/mapping        [TODO] حفظ تعيين الحقول
POST /data-migration/jobs/{id}/preview        [TODO] معاينة بلا كتابة فعلية
POST /data-migration/jobs/{id}/commit         [TODO] الترحيل الفعلي بدفعات
GET  /data-migration/jobs/{id}                [TODO]
GET  /data-migration/jobs/{id}/errors         [TODO]
GET  /data-migration/export                   [TODO] تصدير احترافي (Excel/PDF)
```

## البنية الداخلية (4 طبقات إلزامية — نفس القسم 6.4 المطبَّق على كل موديول)
```
data_migration/
├── domain/
│   ├── entities/          ImportJob, TableDescriptor, FieldMapping, ImportError
│   ├── value_objects/     SourceType, ImportStatus, TargetEntity
│   └── rules/             انتقالات الحالة المسموحة فقط
├── application/
│   ├── use_cases/         إنشاء، اكتشاف، معاينة، ترحيل، تصدير
│   ├── dto/                Pydantic request/response
│   └── ports/              SourceConnector (Protocol عام)
├── infrastructure/
│   ├── connectors/          MssqlConnector, CsvExcelConnector, GenericSqlConnector
│   ├── mapping_profiles/    ملفات JSON قابلة لإعادة الاستخدام لكل إصدار مصدر
│   ├── exporters/            excel_exporter, pdf_exporter
│   ├── models/                SQLAlchemy
│   └── repositories/
└── presentation/
    └── routes/
```

## قاعدة الاستيراد (إلزامية)
`presentation → application → domain` و `infrastructure → application/domain` فقط.
ممنوع أن يستورد `domain` من `infrastructure` أو `presentation` — يُفرَض تلقائياً
عبر عقد `import-linter` الموجود فعلياً في `pyproject.toml`
(`root_packages = ["platform_core", "shared_kernel", "modules"]` يغطي أي
موديول جديد تحت `modules.*` بلا أي تعديل إضافي مطلوب في الإعداد).
ممنوع استيراد `infrastructure` الخاص بموديول آخر مباشرة — فقط عبر use case
الهدف (مثال: `modules.partners.application.use_cases.create_partner`) أو
الأحداث (Events).

## ملاحظة أمنية صادقة
`connection_ref` في `ImportJob` يجب ألا يخزّن أي كلمة مرور نصية صريحة. آلية
إدارة الأسرار الفعلية (Vault/متغيرات بيئة مشفَّرة) **غير محسومة بعد** — قرار
مطلوب في `TASK-MIG-02` قبل أي استخدام في بيئة تحوي بيانات عميل حقيقية.
