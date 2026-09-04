"""يغطي معيار تسليم العضو 13 (integrations): إنشاء اشتراك Webhook، ثم بثّ حدث
حقيقي الشكل (نفس حمولة InvoicePosted الفعلية من sales_use_cases.py) والتأكد
أن المُرسِل استُدعي بالبيانات الصحيحة وأن سجل التسليم (WebhookDelivery) كُتب،
مع التحقق من عزل الشركات وتصفية event_types. لا اتصال شبكة حقيقياً هنا —
IWebhookSender مُموَّه (Fake) بديلاً عن HttpxWebhookSender الحقيقي، بما أن
اختبار طلب HTTP خارجي فعلي خارج نطاق اختبار وحدة/تكامل داخلي."""
import pytest

from modules.identity.application.dto.identity_dto import RegisterCompanyRequest
from modules.identity.application.use_cases.auth_use_cases import RegisterCompanyUseCase
from modules.identity.infrastructure.models.identity_models import Permission
from modules.integrations.application.dto.integrations_dto import (
    WebhookSubscriptionCreateRequest,
)
from modules.integrations.application.use_cases.integrations_use_cases import (
    CreateWebhookSubscriptionUseCase,
    DeactivateWebhookSubscriptionUseCase,
    DispatchEventToWebhooksUseCase,
    ListWebhookDeliveriesUseCase,
    ListWebhookSubscriptionsUseCase,
)
from platform_core.auth_middleware import TenantContext
from platform_core.security import decode_token

pytestmark = pytest.mark.asyncio

PERMISSION_CODE = "integrations.webhook.manage"


class FakeWebhookSender:
    def __init__(self, *, should_succeed: bool = True) -> None:
        self.calls: list[dict] = []
        self._should_succeed = should_succeed

    async def send(self, *, url, payload, secret):
        self.calls.append({"url": url, "payload": payload, "secret": secret})
        if self._should_succeed:
            return True, 200, None
        return False, 500, "internal error"


async def _register(db_session, email: str) -> TenantContext:
    existing = await db_session.execute(
        Permission.__table__.select().where(Permission.code == PERMISSION_CODE)
    )
    if existing.first() is None:
        db_session.add(Permission(code=PERMISSION_CODE, description="x"))
        await db_session.commit()

    tokens = await RegisterCompanyUseCase(db_session).execute(
        RegisterCompanyRequest(
            company_name=f"Company for {email}", admin_full_name="Admin",
            admin_email=email, admin_password="StrongPass123",
        )
    )
    payload = decode_token(tokens.access_token, expected_type="access")
    return TenantContext(company_id=payload["company_id"], user_id=payload["sub"])


async def test_dispatch_sends_only_to_matching_active_subscriptions(db_session):
    ctx = await _register(db_session, "hook-a@alqaim-demo.com")

    matching = await CreateWebhookSubscriptionUseCase(db_session).execute(
        ctx,
        WebhookSubscriptionCreateRequest(
            target_url="https://example.com/hooks/alqaim", event_types=["InvoicePosted"]
        ),
    )
    await CreateWebhookSubscriptionUseCase(db_session).execute(
        ctx,
        WebhookSubscriptionCreateRequest(
            target_url="https://example.com/hooks/other", event_types=["PaymentRecorded"]
        ),
    )

    sender = FakeWebhookSender()
    payload = {
        "invoice_id": "inv-1", "invoice_type": "sale", "total": "150.0000",
        "currency": "IQD", "partner_id": "partner-1", "company_id": ctx.company_id,
    }
    await DispatchEventToWebhooksUseCase(db_session, sender).execute("InvoicePosted", payload)

    # فقط الاشتراك المطابق لنوع الحدث استُدعي — وليس الاشتراك الآخر لنوع مختلف
    assert len(sender.calls) == 1
    assert sender.calls[0]["url"] == "https://example.com/hooks/alqaim"
    assert sender.calls[0]["payload"] == payload
    assert sender.calls[0]["secret"] == matching.secret

    deliveries = await ListWebhookDeliveriesUseCase(db_session).execute(ctx, str(matching.id))
    assert len(deliveries) == 1
    assert deliveries[0].success is True
    assert deliveries[0].status_code == 200


async def test_dispatch_records_failed_delivery_without_raising(db_session):
    ctx = await _register(db_session, "hook-b@alqaim-demo.com")
    subscription = await CreateWebhookSubscriptionUseCase(db_session).execute(
        ctx,
        WebhookSubscriptionCreateRequest(
            target_url="https://example.com/down", event_types=["PaymentRecorded"]
        ),
    )

    sender = FakeWebhookSender(should_succeed=False)
    await DispatchEventToWebhooksUseCase(db_session, sender).execute(
        "PaymentRecorded",
        {"payment_id": "p1", "invoice_id": "i1", "amount": "10", "currency": "IQD",
         "company_id": ctx.company_id},
    )

    deliveries = await ListWebhookDeliveriesUseCase(db_session).execute(ctx, str(subscription.id))
    assert deliveries[0].success is False
    assert deliveries[0].status_code == 500
    assert deliveries[0].error_message == "internal error"


async def test_dispatch_ignores_other_companies_and_deactivated_subscriptions(db_session):
    ctx_a = await _register(db_session, "hook-c@alqaim-demo.com")
    ctx_b = await _register(db_session, "hook-d@alqaim-demo.com")

    sub_a = await CreateWebhookSubscriptionUseCase(db_session).execute(
        ctx_a,
        WebhookSubscriptionCreateRequest(
            target_url="https://example.com/a", event_types=["InvoicePosted"]
        ),
    )
    await CreateWebhookSubscriptionUseCase(db_session).execute(
        ctx_b,
        WebhookSubscriptionCreateRequest(
            target_url="https://example.com/b", event_types=["InvoicePosted"]
        ),
    )

    sender = FakeWebhookSender()
    await DispatchEventToWebhooksUseCase(db_session, sender).execute(
        "InvoicePosted",
        {"invoice_id": "x", "company_id": ctx_a.company_id},
    )
    # فقط اشتراك الشركة A استُدعي رغم أن الشركة B لديها اشتراك لنفس نوع الحدث
    assert len(sender.calls) == 1
    assert sender.calls[0]["url"] == "https://example.com/a"

    # بعد إلغاء التفعيل، لا يُستدعى الاشتراك حتى لو طابق الحدث والشركة
    await DeactivateWebhookSubscriptionUseCase(db_session).execute(ctx_a, str(sub_a.id))
    sender.calls.clear()
    await DispatchEventToWebhooksUseCase(db_session, sender).execute(
        "InvoicePosted", {"invoice_id": "y", "company_id": ctx_a.company_id}
    )
    assert sender.calls == []

    active_subscriptions = await ListWebhookSubscriptionsUseCase(db_session).execute(ctx_a)
    assert all(not s.is_active for s in active_subscriptions)


async def test_dispatch_ignores_payload_without_company_id(db_session):
    """حمولة بلا company_id (مثل InvoiceDraftReady حالياً — راجع التعليق في
    main.py) يجب ألا تُسقِط الدالة، فقط تُهمَل بصمت."""
    sender = FakeWebhookSender()
    await DispatchEventToWebhooksUseCase(db_session, sender).execute(
        "InvoiceDraftReady", {"draft_id": "d1"}
    )
    assert sender.calls == []
