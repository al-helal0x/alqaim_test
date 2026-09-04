# tests/

- `unit/`        → Domain layer (بدون DB) — تغطية >90% مطلوبة (القسم 11.6)
- `integration/` → Application + Infrastructure (Repository حقيقي/Test DB)
- `e2e/`         → API layer end-to-end (Happy Path + أهم حالات الفشل لكل Endpoint)

لا يُدمَج أي PR يخفّض نسبة تغطية الاختبارات الإجمالية.

## تشغيل اختبارات integration الحالية (Skeleton العضو 1 — تعمل فعلياً الآن)

```bash
cd apps/core-api
pip install -e ".[dev]" --break-system-packages
PYTHONPATH=. pytest tests/integration/ -v
```

تستخدم SQLite في الذاكرة (وليس Postgres) لتشغيل سريع بلا بنية تحتية —
`tests/integration/conftest.py` يستبدل نوع عمود UUID وقت الاختبار فقط،
والإنتاج يبقى على Postgres حصراً كما في `platform_core/database.py`.

**ما تغطيه هذه الاختبارات فعلياً الآن (وليس نظرياً):**
- `test_bootstrap_flow.py`: تسجيل شركة جديدة + إنشاء مستخدم Owner + دخول
  ناجح + رفض كلمة مرور خاطئة + ترقيم مستندات فريد تحت 20 طلباً متتالياً.
- `test_tenant_isolation_and_rbac.py`: منح صلاحية Owner تلقائياً عند
  التسجيل، رفض صلاحية عند انتحال `company_id` لشركة أخرى، ومنع إنشاء
  مستودع داخل فرع يعود لشركة أخرى.
