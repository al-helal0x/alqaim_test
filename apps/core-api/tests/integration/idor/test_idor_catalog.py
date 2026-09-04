"""PKG-C1 (partial) — live IDOR test template: `catalog` module
(`GET`/`PATCH /products/{product_id}` and
`POST /price-lists/{price_list_id}/items`).

Sixth worked example.
"""
from __future__ import annotations

import pytest

from .conftest import create_product


async def _create_product(client, headers) -> str:
    return await create_product(client, headers, name="IDOR Test Product", sku="IDOR-CAT-001")


@pytest.mark.asyncio
async def test_product_get_is_isolated(client, company_a_headers, company_b_headers):
    product_id = await _create_product(client, company_a_headers)
    cross_tenant_resp = await client.get(f"/products/{product_id}", headers=company_b_headers)
    assert cross_tenant_resp.status_code == 404, (
        f"IDOR: company B could read company A's product {product_id} "
        f"(got {cross_tenant_resp.status_code}, expected 404)"
    )


@pytest.mark.asyncio
async def test_product_update_is_isolated(client, company_a_headers, company_b_headers):
    """Note the expected status here is 400, not 404 — `UpdateProductUseCase`
    raises a generic `ValueError` which the router maps to 400, unlike
    `GetProductUseCase`'s 404 for the same resource. Same status-code
    inconsistency pattern already flagged for `purchasing` in
    test_idor_purchasing_orders.py — worth folding into the same cleanup
    ticket rather than treating as two separate findings."""
    product_id = await _create_product(client, company_a_headers)
    cross_tenant_resp = await client.patch(
        f"/products/{product_id}",
        json={"name": "Hijacked by company B"},
        headers=company_b_headers,
    )
    assert cross_tenant_resp.status_code == 400, (
        f"IDOR: company B could modify company A's product {product_id} "
        f"(got {cross_tenant_resp.status_code}, expected 400 per this app's current convention)"
    )


@pytest.mark.asyncio
async def test_price_list_add_item_is_isolated(client, company_a_headers, company_b_headers):
    """company B must not be able to add items to company A's price list."""
    create_resp = await client.post(
        "/price-lists",
        json={"name": "IDOR Test Price List", "currency": "USD"},
        headers=company_a_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    price_list_id = create_resp.json()["id"]

    product_id = await _create_product(client, company_a_headers)

    cross_tenant_resp = await client.post(
        f"/price-lists/{price_list_id}/items",
        json={"product_id": product_id, "price": 9.99},
        headers=company_b_headers,
    )
    assert cross_tenant_resp.status_code == 400, (
        f"IDOR: company B could add an item to company A's price list {price_list_id} "
        f"(got {cross_tenant_resp.status_code}, expected 400)"
    )
