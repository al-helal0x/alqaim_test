"""PKG-C1 (partial) — live IDOR test template: `integrations` module
(`DELETE /webhooks/{subscription_id}` and
`GET /webhooks/{subscription_id}/deliveries`).

Eighth worked example. Webhook delivery history is worth checking
specifically because it can contain **payloads of past events** (order
data, customer data — whatever this company's webhooks broadcast) —
another exfiltration-shaped endpoint like `documents/download`, just less
obviously so from the route name alone.
"""
from __future__ import annotations

import pytest


async def _create_webhook_subscription(client, headers) -> str:
    resp = await client.post(
        "/webhooks",
        json={
            "target_url": "https://example.com/idor-test-hook",
            "event_types": ["InvoicePosted"],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_webhook_deliveries_list_is_isolated(client, company_a_headers, company_b_headers):
    """company B must not be able to read company A's webhook delivery history
    (potential payload/event-data leak, not just metadata)."""
    subscription_id = await _create_webhook_subscription(client, company_a_headers)

    cross_tenant_resp = await client.get(
        f"/webhooks/{subscription_id}/deliveries", headers=company_b_headers
    )
    assert cross_tenant_resp.status_code == 404, (
        f"IDOR: company B could read company A's webhook delivery history for "
        f"subscription {subscription_id} (got {cross_tenant_resp.status_code}, expected 404)"
    )


@pytest.mark.asyncio
async def test_webhook_deactivate_is_isolated(client, company_a_headers, company_b_headers):
    """company B must not be able to deactivate company A's webhook —
    a working webhook silently getting disabled by another tenant would be
    a hard-to-diagnose availability bug for whoever depends on it."""
    subscription_id = await _create_webhook_subscription(client, company_a_headers)

    cross_tenant_resp = await client.delete(
        f"/webhooks/{subscription_id}", headers=company_b_headers
    )
    assert cross_tenant_resp.status_code == 404, (
        f"IDOR: company B could deactivate company A's webhook subscription "
        f"{subscription_id} (got {cross_tenant_resp.status_code}, expected 404)"
    )
