"""اختبار وحدة لـ core_api_client.py بمعزل تام عن core-api الحقيقي (mock عبر
respx) — البند الثالث من "الاختبارات المطلوبة" في README_عضو-2.md /
القسم 3.3 من الخطة."""
import httpx
import pytest
import respx

from infrastructure.core_api_client import CoreApiClient
from platform_core.config import Settings

pytestmark = pytest.mark.asyncio

_SETTINGS = Settings(
    core_api_base_url="http://core-api.internal:8000",
    ai_platform_service_token="test-service-token",
)
_COMPANY_ID = "11111111-1111-1111-1111-111111111111"


@respx.mock
async def test_fetch_known_suppliers_success():
    route = respx.get(
        "http://core-api.internal:8000/internal/partners/known-suppliers",
        params={"company_id": _COMPANY_ID},
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": "s-1", "name": "Basra Electronics LLC"},
                {"id": "s-2", "name": "Najaf Trading Co"},
            ],
        )
    )

    client = CoreApiClient(settings=_SETTINGS)
    suppliers = await client.fetch_known_suppliers(_COMPANY_ID)

    assert route.called
    # التحقق من الترويسة المتفق عليها في العقد (القسم 3 في README_عضو-2.md)
    sent_request = route.calls.last.request
    assert sent_request.headers["X-Service-Token"] == "test-service-token"

    assert [s.name for s in suppliers] == ["Basra Electronics LLC", "Najaf Trading Co"]
    assert suppliers[0].id == "s-1"


@respx.mock
async def test_fetch_known_products_success():
    respx.get(
        "http://core-api.internal:8000/internal/catalog/known-products",
        params={"company_id": _COMPANY_ID},
    ).mock(return_value=httpx.Response(200, json=[{"id": "p-1", "name": "Cable 3x5"}]))

    client = CoreApiClient(settings=_SETTINGS)
    products = await client.fetch_known_products(_COMPANY_ID)

    assert len(products) == 1
    assert products[0].id == "p-1"
    assert products[0].name == "Cable 3x5"


@respx.mock
async def test_fetch_known_suppliers_raises_on_401():
    respx.get(
        "http://core-api.internal:8000/internal/partners/known-suppliers",
        params={"company_id": _COMPANY_ID},
    ).mock(return_value=httpx.Response(401, json={"detail": "توكن خاطئ"}))

    client = CoreApiClient(settings=_SETTINGS)
    with pytest.raises(httpx.HTTPStatusError):
        await client.fetch_known_suppliers(_COMPANY_ID)


@respx.mock
async def test_fetch_known_products_raises_on_connection_error():
    respx.get(
        "http://core-api.internal:8000/internal/catalog/known-products",
        params={"company_id": _COMPANY_ID},
    ).mock(side_effect=httpx.ConnectError("connection refused"))

    client = CoreApiClient(settings=_SETTINGS)
    with pytest.raises(httpx.ConnectError):
        await client.fetch_known_products(_COMPANY_ID)
