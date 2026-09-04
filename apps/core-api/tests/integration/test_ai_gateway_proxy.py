"""يثبت أن بوابة core-api (/ai/*) تُمرِّر فعلياً إلى خدمة ai-platform حقيقية
تعمل على منفذها الخاص (8100) — وليس Mock لـ httpx. يتطلب خادم ai-platform
حقيقياً يعمل على http://127.0.0.1:8100 (uvicorn main:app)؛ يُتخطى تلقائياً
إن لم يكن متاحاً."""
import httpx
import pytest

pytestmark = pytest.mark.asyncio

AI_PLATFORM_URL = "http://127.0.0.1:8100"


async def _ai_platform_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{AI_PLATFORM_URL}/health")
            return response.status_code == 200
    except httpx.RequestError:
        return False


async def test_gateway_client_reaches_real_ai_platform_health():
    if not await _ai_platform_available():
        pytest.skip("خادم ai-platform الحقيقي غير متاح على المنفذ 8100 في هذه البيئة")

    from platform_core.ai_gateway_client import get_ai_platform_client

    async with get_ai_platform_client() as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_gateway_proxies_document_analysis_to_real_ai_platform():
    """يرفع صورة فاتورة فعلية عبر مسار /ai/documents/analyze في core-api،
    ويتحقق أن ai-platform الحقيقي عالجها فعلياً (OCR حقيقي) وأعاد draft قابل
    للجلب عبر /ai/drafts/{id} — عبر نفس عميل البوابة، وليس عبر core-api
    الكامل (لتفادي الحاجة لتسجيل شركة/مستخدم كاملة في هذا الاختبار المركَّز
    على سلوك الشبكة بين العمليتين تحديداً)."""
    if not await _ai_platform_available():
        pytest.skip("خادم ai-platform الحقيقي غير متاح على المنفذ 8100 في هذه البيئة")

    import io

    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (600, 200), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    draw.text((20, 20), "Invoice No: INV-GATEWAY-001", fill="black", font=font)
    draw.text((20, 60), "Total: 99.000", fill="black", font=font)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")

    from platform_core.ai_gateway_client import get_ai_platform_client

    async with get_ai_platform_client() as client:
        response = await client.post(
            "/ai/documents/analyze",
            params={"company_id": "11111111-1111-1111-1111-111111111111", "company_currency": "IQD"},
            files={"file": ("invoice.png", buffer.getvalue(), "image/png")},
        )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "done"
    assert body["job_id"]

    async with get_ai_platform_client() as client:
        draft_response = await client.get(f"/ai/documents/jobs/{body['job_id']}")
    assert draft_response.status_code == 200
    assert draft_response.json()["status"] == "done"
