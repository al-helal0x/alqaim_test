"""core_api_client.py — عميل HTTP لـ ai-platform لاستهلاك core-api (النصف
الثاني من `TASK-AI-04`، القسم 3.3 من `ALQAIM_V2_PHASE5_FINAL_CLOSURE_PLAN.md`،
الخيار (أ)). نفس نمط `httpx.AsyncClient` المستخدَم فعلياً في
`purchase_invoices_router.py` (core-api → ai-platform)، بعكس الاتجاه هنا.

العقد المتفق عليه مسبقاً مع عضو core-api — **لا يُغيَّر من طرف واحد**، أي
تعديل عليه يجب تنسيقه أولاً:

    GET {CORE_API_BASE_URL}/internal/partners/known-suppliers?company_id={company_id}
    GET {CORE_API_BASE_URL}/internal/catalog/known-products?company_id={company_id}
    Headers: X-Service-Token: {AI_PLATFORM_SERVICE_TOKEN}
    200 OK -> [{"id": "uuid", "name": "string"}, ...]
    401    -> الترويسة خاطئة/مفقودة

**معالجة الفشل متروكة عمداً لطبقة الاستدعاء** (`documents_router.py`):
هذا العميل لا يبتلع أي خطأ — يرفع استثناءات `httpx.HTTPError` (اتصال/مهلة/
401) كما هي، حتى تقرر طبقة الاستدعاء بنفسها الاستمرار بلا مطابقة بدل إسقاط
الطلب بالكامل (خطوة 5 في القسم 3.3، بنفس روح ADR-001 — استقلالية النشر).
"""
from __future__ import annotations

import httpx

from application.use_cases.process_document_pipeline import ProductCandidate, SupplierCandidate
from platform_core.config import Settings, get_settings

# مهلة قصيرة عمداً: هذا استدعاء داخلي بين خدمتين على نفس الشبكة، وليس عبوراً
# للإنترنت العام — تجنّب إبطاء /analyze بشكل غير مبرَّر عند تعطّل core-api.
_DEFAULT_TIMEOUT = httpx.Timeout(5.0, connect=3.0)


class CoreApiClient:
    """عميل خفيف بلا حالة (stateless) — يُنشئ اتصال HTTP جديد لكل استدعاء
    (لا يحمل جلسة مفتوحة بين الطلبات، تبسيطاً؛ يمكن تحويله لـ connection
    pooling مشترك لاحقاً دون تغيير الواجهة العامة لو دعت الحاجة الأداء)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def fetch_known_suppliers(self, company_id: str) -> list[SupplierCandidate]:
        items = await self._get("/internal/partners/known-suppliers", company_id)
        return [SupplierCandidate(id=str(item["id"]), name=item["name"]) for item in items]

    async def fetch_known_products(self, company_id: str) -> list[ProductCandidate]:
        items = await self._get("/internal/catalog/known-products", company_id)
        return [ProductCandidate(id=str(item["id"]), name=item["name"]) for item in items]

    async def _get(self, path: str, company_id: str) -> list[dict]:
        url = f"{self._settings.core_api_base_url.rstrip('/')}{path}"
        headers = {"X-Service-Token": self._settings.ai_platform_service_token}
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            response = await client.get(url, params={"company_id": company_id}, headers=headers)
            response.raise_for_status()  # يرفع HTTPStatusError على 401/4xx/5xx
            return response.json()
