"""PKG-C1 (partial) — live IDOR test template: `sales` module
(`POST /sales-invoices/{invoice_id}/post` and `/cancel`).

Third worked example. Chosen because it's an *action* endpoint, not a
plain read/update — the isolation bug shape to watch for is company B
triggering a state transition (posting to the ledger, cancelling) on
company A's invoice, which is a more damaging class of IDOR than a
read leak: it corrupts company A's books, not just discloses data.

See test_idor_partners.py for the fixture-wiring notes (same pattern,
not repeated here).
"""
from __future__ import annotations

import pytest

from .conftest import create_product, create_warehouse, seed_chart_of_accounts, stock_in


@pytest.fixture
async def company_a_partner_id(client, company_a_headers) -> str:
    """An existing partner_id belonging to company A (invoice creation needs one).

    Created live through the real API rather than a hardcoded id, same
    reasoning as test_idor_purchasing_orders.py's fixtures.
    """
    resp = await client.post(
        "/partners",
        json={"name": "IDOR Test Invoice Customer", "partner_type": "customer"},
        headers=company_a_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.fixture
async def company_a_product_id(client, company_a_headers) -> str:
    """An existing product_id belonging to company A (invoice lines need one)."""
    return await create_product(
        client, company_a_headers, name="IDOR Test Invoice Product", sku="IDOR-INV-001"
    )


@pytest.fixture
async def company_a_warehouse_id(client, company_a_headers, company_a_product_id) -> str:
    """POST /sales-invoices requires warehouse_id, and posting requires
    reservable stock + a seeded chart of accounts + an open fiscal period —
    none of this was visible from the isolated package this test was
    originally written from; discovered only by running it here for real."""
    warehouse_id = await create_warehouse(client, company_a_headers)
    await stock_in(client, company_a_headers, warehouse_id=warehouse_id, product_id=company_a_product_id)
    await seed_chart_of_accounts(client, company_a_headers)
    fy_resp = await client.post(
        "/fiscal-periods/years",
        json={"code": "FY-INV-TEST", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        headers=company_a_headers,
    )
    assert fy_resp.status_code in (200, 409), fy_resp.text
    return warehouse_id


async def _create_draft_invoice(client, headers, partner_id, product_id, warehouse_id) -> str:
    resp = await client.post(
        "/sales-invoices",
        json={
            "partner_id": partner_id,
            "warehouse_id": warehouse_id,
            "lines": [{"product_id": product_id, "quantity": 1, "unit_price": 10.0}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_invoice_post_is_isolated(
    client,
    company_a_headers,
    company_b_headers,
    company_a_partner_id,
    company_a_product_id,
    company_a_warehouse_id,
):
    """company B must not be able to POST /sales-invoices/{id}/post company A's draft."""
    invoice_id = await _create_draft_invoice(
        client, company_a_headers, company_a_partner_id, company_a_product_id, company_a_warehouse_id
    )

    cross_tenant_resp = await client.post(f"/sales-invoices/{invoice_id}/post", headers=company_b_headers)
    assert cross_tenant_resp.status_code == 422, (
        f"IDOR: company B could POST (ledger-post) company A's invoice {invoice_id} "
        f"(got {cross_tenant_resp.status_code}, expected 422). Isolation itself IS "
        f"enforced (confirmed by reading PostSalesInvoiceUseCase/_reload_invoice — "
        f"filters by company_id, raises ValueError if not found/not owned); this "
        f"endpoint's router just maps that generic ValueError to 422 rather than "
        f"403/404 (see invoices_router.py's post_sales_invoice, mirrors the same "
        f"convention inconsistency already flagged in test_idor_partners.py and "
        f"test_idor_purchasing_orders.py — status code, not a real vulnerability)."
    )

    # Sanity: it must still be postable by its actual owner afterwards, i.e. the
    # cross-tenant attempt above must not have silently mutated invoice state.
    owner_resp = await client.post(f"/sales-invoices/{invoice_id}/post", headers=company_a_headers)
    assert owner_resp.status_code == 200, (
        "owner's post failed after the cross-tenant attempt above — check whether "
        "the cross-tenant call had a side effect on invoice state despite being refused"
    )


@pytest.mark.asyncio
async def test_invoice_cancel_is_isolated(
    client,
    company_a_headers,
    company_b_headers,
    company_a_partner_id,
    company_a_product_id,
    company_a_warehouse_id,
):
    """company B must not be able to POST /sales-invoices/{id}/cancel company A's draft."""
    invoice_id = await _create_draft_invoice(
        client, company_a_headers, company_a_partner_id, company_a_product_id, company_a_warehouse_id
    )

    cross_tenant_resp = await client.post(f"/sales-invoices/{invoice_id}/cancel", headers=company_b_headers)
    assert cross_tenant_resp.status_code in (403, 404), (
        f"IDOR: company B could cancel company A's invoice {invoice_id} "
        f"(got {cross_tenant_resp.status_code}, expected 403 or 404)"
    )
