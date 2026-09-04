"""نقطة دخول core-api — Modular Monolith (القسم 6.1/6.2).

يبقى هذا الملف بسيطاً جداً عمداً: سطر تسجيل Router واحد لكل Module
لتقليل احتمال تعارض الدمج بين الأعضاء (القسم 15.2).

── Task #6-S1 — Event Bus Lifecycle & Dependency Injection ─────────────────
التعديل الوحيد في هذا الملف هو **آلية تركيب/تسجيل الاشتراكات (Wiring)**:
كانت الاشتراكات الستة تُسجَّل مباشرة عند وقت استيراد الملف على الكائن
العالمي `event_bus` (سطور 143، 159، 178، 216، 223 تقريباً في النسخة
السابقة) — وهذا ما كان يُسرِّب المشتركين إلى كل الاختبارات الأخرى (راجع
README_المهمة.md وADR-001 القرار 6).

الآن: كل الاشتراكات نفسها (نفس الأسماء، نفس المعالجات، نفس ترتيبها)
انتقلت داخل دالة `wire_event_subscriptions(bus)` تُستدعى مرة واحدة فقط عند
بداية `lifespan` التطبيق، على EventBus جديد يُنشأ لكل تشغيل تطبيق
(Application-scoped). لا إضافة/حذف/تعديل لأي اشتراك تجاري، ولا اسم حدث،
ولا شكل payload — طابِق النسخة المرجعية `main.py.مرجع_للقراءة_فقط` سطراً
بسطر لهذا الجزء.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from platform_core.config import get_settings
from platform_core.event_bus import EventBus, reset_event_bus, set_event_bus
from platform_core.logging_config import configure_logging
from platform_core.outbox_worker import start_outbox_worker, stop_outbox_worker
from platform_core.redis_bridge import start_redis_bridge, stop_redis_bridge

settings = get_settings()
configure_logging(settings.environment)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # EventBus Application-scoped — نسخة واحدة جديدة لكل تشغيل تطبيق، وليس
    # Singleton عالمي يُنشأ عند وقت الاستيراد (Task #6-S1). تُربَط بالسياق
    # الحالي *قبل* تسجيل أي اشتراك حتى يعمل `event_bus` Facade في
    # platform_core.event_bus بشكل صحيح لأي كود يستورده مباشرة.
    bus = EventBus()
    token = set_event_bus(bus)
    app.state.event_bus = bus
    wire_event_subscriptions(bus)

    # جسر Redis Pub/Sub مع ai-platform (العضو 1 + العضو 8 — يُغلق فجوة
    # InvoiceDraftReady الموثَّقة سابقاً في contracts.md §4)
    start_redis_bridge()

    # Outbox Worker (تنفيذ #6x#11x#12x#10، Track 1) — يستطلع outbox_events
    # دورياً ويسلّم الأحداث المضمونة التي كتبها enqueue_event() عبر use
    # cases مختلفة (sales/accounting إلخ). مستقل تماماً عن Redis bridge
    # أعلاه (ذاك يجسر بين عمليتين، هذا يضمن عدم فقدان حدث داخل نفس العملية).
    start_outbox_worker()
    try:
        yield
    finally:
        await stop_outbox_worker()
        await stop_redis_bridge()
        reset_event_bus(token)


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


# ── تسجيل Routers كل Module (يُفعَّل تباعاً مع اكتمال كل وحدة) ──────────────
from modules.accounting.presentation.routes.accounts_router import router as accounts_router
from modules.accounting.presentation.routes.fiscal_periods_router import (
    router as fiscal_periods_router,
)
from modules.accounting.presentation.routes.journal_entries_router import (
    router as journal_entries_router,
)
from modules.catalog.presentation.routes.categories_router import router as categories_router
from modules.catalog.presentation.routes.internal_catalog_router import (
    router as internal_catalog_router,
)
from modules.catalog.presentation.routes.price_lists_router import router as price_lists_router
from modules.catalog.presentation.routes.products_router import router as products_router
from modules.catalog.presentation.routes.uom_router import router as uom_router
from modules.data_migration.presentation.routes.data_migration_router import (
    router as data_migration_router,
)
from modules.documents.presentation.routes.documents_router import router as documents_router
from modules.identity.presentation.routes.auth_router import router as auth_router
from modules.identity.presentation.routes.users_router import router as users_router
from modules.integrations.presentation.routes.webhooks_router import router as webhooks_router
from modules.inventory.presentation.routes.adjustments_router import (
    router as inventory_adjustments_router,
)
from modules.inventory.presentation.routes.balances_router import (
    router as inventory_balances_router,
)
from modules.inventory.presentation.routes.movements_router import (
    router as inventory_movements_router,
)
from modules.inventory.presentation.routes.transfers_router import (
    router as inventory_transfers_router,
)
from modules.partners.presentation.routes.internal_partners_router import (
    router as internal_partners_router,
)
from modules.partners.presentation.routes.partners_router import router as partners_router
from modules.partners.presentation.routes.partners_walkin_router import (
    router as partners_walkin_router,
)
from modules.payments.presentation.routes.bank_accounts_router import (
    router as bank_accounts_router,
)
from modules.payments.presentation.routes.payments_router import router as payments_router
from modules.payments.presentation.routes.receipts_router import router as receipts_router
from modules.platform_admin.presentation.routes.platform_admin_router import (
    router as platform_admin_router,
)
from modules.pos.presentation.routes.pos_router import router as pos_router
from modules.purchasing.presentation.routes.purchase_invoices_router import (
    router as purchase_invoices_router,
)
from modules.purchasing.presentation.routes.purchase_orders_router import (
    router as purchase_orders_router,
)
from modules.reporting.presentation.routes.reports_router import router as reports_router
from modules.sales.presentation.routes.credit_notes_router import router as credit_notes_router
from modules.sales.presentation.routes.invoices_router import router as sales_invoices_router
from modules.sales.presentation.routes.quotations_router import router as quotations_router
from modules.sales.presentation.routes.sales_orders_router import router as sales_orders_router
from modules.taxation.presentation.routes.tax_rates_router import router as tax_rates_router
from modules.tenancy.presentation.routes.branches_router import router as branches_router
from modules.tenancy.presentation.routes.companies_router import router as companies_router
from modules.tenancy.presentation.routes.numbering_router import router as numbering_router
from modules.tenancy.presentation.routes.warehouses_router import router as warehouses_router
from presentation.routes.ai_proxy_router import router as ai_proxy_router

app.include_router(auth_router, prefix="/auth", tags=["identity"])
app.include_router(users_router, prefix="/users", tags=["identity"])
app.include_router(companies_router, prefix="/companies", tags=["tenancy"])
app.include_router(branches_router, prefix="/branches", tags=["tenancy"])
app.include_router(warehouses_router, prefix="/warehouses", tags=["tenancy"])
app.include_router(numbering_router, prefix="/numbering", tags=["tenancy"])
app.include_router(accounts_router, prefix="/accounts", tags=["accounting"])
app.include_router(journal_entries_router, prefix="/journal-entries", tags=["accounting"])
app.include_router(fiscal_periods_router, prefix="/fiscal-periods", tags=["accounting"])
app.include_router(reports_router, prefix="/reports", tags=["reporting"])
app.include_router(tax_rates_router, prefix="/tax-rates", tags=["taxation"])
app.include_router(partners_router, prefix="/partners", tags=["partners"])
app.include_router(partners_walkin_router, prefix="/partners", tags=["partners"])
app.include_router(products_router, prefix="/products", tags=["catalog"])
app.include_router(categories_router, prefix="/categories", tags=["catalog"])
app.include_router(uom_router, prefix="/units-of-measure", tags=["catalog"])
app.include_router(price_lists_router, prefix="/price-lists", tags=["catalog"])
app.include_router(
    data_migration_router, prefix="/data-migration/jobs", tags=["data_migration"]
)
# مسارات داخلية (خدمة-لخدمة) — بلا prefix لأن المسار الكامل معرَّف داخل كل
# router نفسه (/internal/...)؛ محمية بـget_service_context لا get_current_context
# (TASK-AI-04 القسم 3.3، الخيار أ). راجع README_عضو-1.md.
app.include_router(internal_partners_router, tags=["internal"])
app.include_router(internal_catalog_router, tags=["internal"])
app.include_router(inventory_movements_router, prefix="/inventory/movements", tags=["inventory"])
app.include_router(inventory_balances_router, prefix="/inventory/balances", tags=["inventory"])
app.include_router(inventory_transfers_router, prefix="/inventory/transfers", tags=["inventory"])
app.include_router(inventory_adjustments_router, prefix="/inventory/adjustments", tags=["inventory"])
app.include_router(quotations_router, prefix="/quotations", tags=["sales"])
app.include_router(sales_orders_router, prefix="/sales-orders", tags=["sales"])
app.include_router(sales_invoices_router, prefix="/sales-invoices", tags=["sales"])
app.include_router(credit_notes_router, prefix="/credit-notes", tags=["sales"])
app.include_router(pos_router, prefix="/pos", tags=["pos"])
app.include_router(purchase_orders_router, prefix="/purchase-orders", tags=["purchasing"])
app.include_router(purchase_invoices_router, prefix="/purchase-invoices", tags=["purchasing"])
app.include_router(bank_accounts_router, prefix="/bank-accounts", tags=["payments"])
app.include_router(payments_router, prefix="/payments", tags=["payments"])
app.include_router(receipts_router, prefix="/receipts", tags=["payments"])
app.include_router(ai_proxy_router, prefix="/ai", tags=["ai-platform"])
app.include_router(documents_router, prefix="/documents", tags=["documents"])
app.include_router(webhooks_router, prefix="/webhooks", tags=["integrations"])
app.include_router(platform_admin_router, prefix="/platform-admin", tags=["platform-admin"])

# ── ربط الأحداث بين الوحدات (القسم 6.6) ─────────────────────────────────────
# Task #6-S1: هذا الجزء بالكامل انتقل من "تنفيذ مباشر عند الاستيراد" إلى
# "تعريف دالة wiring تُستدعى مرة واحدة من lifespan (أعلاه)". محتوى كل
# اشتراك (event_name، المعالج، الترتيب) طابَق حرفياً النسخة المرجعية —
# فقط استُبدل `event_bus.subscribe(...)` العالمي بمُعامِل `bus` مُمرَّر.
from modules.audit.application.use_cases.audit_use_cases import RecordAuditLogUseCase
from modules.audit.presentation.routes.audit_router import router as audit_router
from modules.integrations.application.use_cases.integrations_use_cases import (
    DispatchEventToWebhooksUseCase,
)
from modules.integrations.infrastructure.external.httpx_webhook_sender import (
    HttpxWebhookSender,
)
from modules.notifications.application.use_cases.notifications_use_cases import (
    CreateNotificationFromEventUseCase,
)
from modules.notifications.presentation.routes.notifications_router import (
    router as notifications_router,
)
from modules.purchasing.infrastructure.event_handlers import apply_payment_to_invoice
from modules.sales.infrastructure.event_handlers import handle_sales_invoice_created
from modules.workflow.infrastructure.adapters.workflow_port_adapter import WorkflowPortAdapter
from modules.workflow.presentation.routes.workflow_router import router as workflow_router
from platform_core.database import AsyncSessionLocal

app.include_router(workflow_router, prefix="/workflow", tags=["workflow"])
app.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
app.include_router(audit_router, prefix="/audit", tags=["audit"])


async def _on_payment_recorded(payload: dict) -> None:
    async with AsyncSessionLocal() as session:
        await apply_payment_to_invoice(session, payload)


# مهمة #12 (sales↔workflow): فاتورة بيع > 10,000 تحتاج موافقة مدير قبل
# الترحيل. sales/infrastructure/event_handlers.py لا يستورد workflow/infrastructure
# مباشرة (القسم 11.2) — لذا الـ Adapter الفعلي (WorkflowPortAdapter) يُبنى
# هنا فقط، في نقطة التوصيل، بنفس مبدأ حقن IAccountingPort/IInventoryPort في
# invoices_router.py.
async def _on_sales_invoice_created(payload: dict) -> None:
    async with AsyncSessionLocal() as session:
        await handle_sales_invoice_created(WorkflowPortAdapter(session), payload)


# بثّ Webhooks خارجية (العضو 13) — يستمع لنفس الأحداث المُعلَنة في
# docs/architecture/contracts.md §2 دون أي معرفة بالوحدة الناشرة (sales/
# purchasing/payments)، تماماً كما يفرض القسم 11.2. "InvoiceDraftReady" غير
# مُشترَك هنا عمداً — حمولته لا تحتوي company_id بشكل مباشر بعد (راجع الفجوة
# الموثَّقة في contracts.md §4)، وDispatchEventToWebhooksUseCase يتجاهل بصمت
# أي حمولة بلا company_id، لذا الاشتراك به الآن لن يفعل شيئاً مفيداً.
async def _dispatch_webhooks(event_name: str, payload: dict) -> None:
    async with AsyncSessionLocal() as session:
        await DispatchEventToWebhooksUseCase(session, HttpxWebhookSender()).execute(
            event_name, payload
        )


# العضو 12: تسجيل تدقيق شامل + إشعارات — نفس نمط العضو 13 تماماً
async def _record_audit_log(event_name: str, payload: dict) -> None:
    async with AsyncSessionLocal() as session:
        await RecordAuditLogUseCase(session).execute(event_name, payload)


async def _create_notification(event_name: str, payload: dict) -> None:
    async with AsyncSessionLocal() as session:
        await CreateNotificationFromEventUseCase(session).execute(event_name, payload)


def wire_event_subscriptions(bus) -> None:
    """يسجّل كل الاشتراكات الستة على `bus` المُمرَّر (Application-scoped،
    يُنشأ في `lifespan` أعلاه) بدل الكائن العالمي القديم. تُستدعى مرة واحدة
    فقط عند إقلاع التطبيق — **نفس** الاشتراكات، **نفس** الترتيب، **بلا أي**
    تغيير على اسم حدث أو شكل payload، مطابقة تماماً للنسخة المرجعية
    main.py.مرجع_للقراءة_فقط."""
    bus.subscribe("PaymentRecorded", _on_payment_recorded)

    bus.subscribe("SalesInvoiceCreated", _on_sales_invoice_created)

    # ... (نفس النمط لكل module إضافي — القسم 12، بانتظار بقية الأعضاء)

    for _webhook_event_name in ("InvoicePosted", "PaymentRecorded"):
        bus.subscribe(
            _webhook_event_name,
            lambda payload, _name=_webhook_event_name: _dispatch_webhooks(_name, payload),
        )

    # audit: كل الأحداث الستة المُعلَنة في contracts.md §2 — بلا استثناء
    for _audited_event in (
        "InvoicePosted", "PaymentRecorded", "StockLevelLow",
        "AccountSettingsChanged", "InvoiceDraftReady", "FiscalPeriodClosed",
    ):
        bus.subscribe(
            _audited_event,
            lambda payload, _name=_audited_event: _record_audit_log(_name, payload),
        )

    # notifications: فقط الحدثان المُعلَنان صراحة كمستهلِك لهما في contracts.md §2
    for _notified_event in ("InvoicePosted", "StockLevelLow"):
        bus.subscribe(
            _notified_event,
            lambda payload, _name=_notified_event: _create_notification(_name, payload),
        )
