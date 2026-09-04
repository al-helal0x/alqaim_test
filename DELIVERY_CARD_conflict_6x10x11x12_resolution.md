# تسليم — حسم تعارض #6 × #10 × #11 × #12

**تاريخ:** أُنتِج بمساعدة Claude بناءً على طلب صريح من صاحب المشروع، فوق حزمة
`AlQaim_V2_merged_local_test_v8.zip`، باتباع ترتيب الحسم المعتمَد في
`docs/architecture/ADR-001-event-architecture-and-ai-platform-boundary.md`
(القرار 3).

## ما تغيّر

| الملف | التغيير |
|---|---|
| `apps/core-api/platform_core/event_bus.py` | دمج Task #6-S1 (DI عبر contextvars) مع Task #6 (Outbox Pattern) في ملف واحد |
| `apps/core-api/platform_core/outbox_worker.py` | جديد — worker دوري لإعادة محاولة أحداث outbox غير المُسلَّمة |
| `apps/core-api/platform_core/redis_bridge.py` | محدَّث ليكتب عبر outbox بدل النشر المباشر |
| `apps/core-api/modules/purchasing/infrastructure/event_handlers.py` | **أُعيد إنشاؤه** — كان مفقوداً بالكامل رغم استيراده في `main.py` (باگ إقلاع `ModuleNotFoundError` مستقل عن هذا التعارض، اكتُشف أثناء هذا الدمج) |
| `apps/core-api/modules/accounting/application/use_cases/fiscal_period_use_cases.py` | تعارض #10 محسوم — منطق الإقفال الحقيقي + نشر outbox-style |
| `apps/core-api/modules/sales/application/use_cases/sales_use_cases.py` | تعارض #12 محسوم — بوابة موافقة المدير + نشر outbox-style لكلا الحدثين |
| `apps/core-api/modules/sales/presentation/routes/invoices_router.py` | حقن `WorkflowPortAdapter` حقيقي في مسار `/post` + معالجة استثناءي الموافقة (409) |
| `apps/core-api/main.py` | ربط `start_outbox_worker`/`stop_outbox_worker` في lifespan |
| `apps/core-api/tests/integration/test_event_bus_isolation.py` | محدَّث للتوقيع الجديد `publish(session, ...)` |
| `apps/core-api/tests/integration/test_redis_event_bridge.py` | محدَّث — يستدعي `dispatch_pending` صراحة بعد `publish` (التسليم لم يعد فورياً ضمن `publish` نفسها) |

## ما لم يتغيّر عمداً

- `_CONFLICTS/` و`_PENDING_TASK06_NOT_MERGED/` تُركا في مكانهما كسجل تاريخي —
  لم تُحذف، فالملفات الفعلية في الشجرة الرئيسية هي المصدر الحي الآن.
- `test_audit.py`, `test_period_closing.py`, `test_purchasing_payments_flow.py`,
  `test_accounting_posting.py` — لا تستدعي `event_bus.publish()` مباشرة، فلم
  تحتج تعديلاً.

## ما لم يُتحقَّق منه بعد (محدودية معروفة)

**لم يُشغَّل `pytest` فعلياً على أي بيئة حقيقية.** كل التحقق في هذا الدمج
كان `python3 -m py_compile` على كامل الشجرة (بما فيها `tests/`) + تتبّع
يدوي لكل نقطة استدعاء متأثرة. هذا لا يكتشف: أخطاء منطقية وقت التشغيل، تعارض
schema فعلي على قاعدة بيانات، أو مشاكل توقيت/تزامن في outbox/dispatch_pending.

**الخطوة التالية الموصى بها:** تشغيل
```
cd apps/core-api
pip install -e ".[dev]"
pytest tests/integration -x -v
```
على بيئة بشبكة فعلية، مع Postgres+Redis حقيقيين لتغطية `test_redis_event_bridge.py`
(يتخطى نفسه تلقائياً لو Redis غير متاح).
