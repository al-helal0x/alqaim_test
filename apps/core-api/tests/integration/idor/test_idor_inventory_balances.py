"""PKG-C1 (partial) — live IDOR test template: `inventory` module
(`GET /inventory/balances/{product_id}`).

Second worked example (see test_idor_partners.py for the full pattern
explanation). This endpoint is interesting because the "resource" being
looked up is a *product*, but the data leaked would be *stock quantities
per warehouse* — the isolation bug to watch for here is subtly different
from a plain "wrong company owns this row" case: even if `product_id`
itself belongs to company B (i.e. it's a real, guessable id), company A
must not be able to read company B's stock levels for it.
"""
from __future__ import annotations

import pytest

from .conftest import create_product, create_warehouse


@pytest.mark.asyncio
async def test_stock_balance_by_product_is_isolated(client, company_a_headers, company_b_headers):
    """GET /inventory/balances/{product_id}: company A must not see company B's stock levels."""
    product_id = await create_product(
        client, company_b_headers, name="IDOR Test Product", sku="IDOR-SKU-001"
    )
    warehouse_id = await create_warehouse(client, company_b_headers)

    adjustment_resp = await client.post(
        "/inventory/adjustments",
        json={
            "warehouse_id": warehouse_id,
            "product_id": product_id,
            "quantity_delta": 100,
            "reason": "IDOR test seed stock",
        },
        headers=company_b_headers,
    )
    assert adjustment_resp.status_code == 201, adjustment_resp.text

    cross_tenant_resp = await client.get(f"/inventory/balances/{product_id}", headers=company_a_headers)
    assert cross_tenant_resp.status_code in (403, 404, 200), "unexpected status code, inspect manually"
    if cross_tenant_resp.status_code == 200:
        # Some APIs choose to return 200 + empty list instead of 403/404 for
        # a product id that "doesn't exist" in the requester's tenant. That
        # is an ACCEPTABLE isolation strategy IF AND ONLY IF the list is
        # empty. A non-empty list here is the actual bug.
        assert cross_tenant_resp.json() == [], (
            f"IDOR: company A could see company B's stock balances for "
            f"product {product_id}: {cross_tenant_resp.json()}"
        )
