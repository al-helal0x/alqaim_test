"""PKG-C1 (partial) — live IDOR test template: `purchasing` module
(`GET /purchase-orders/{order_id}` and the confirm/cancel/receive actions).

Fourth worked example. Also carries one concrete finding surfaced just by
reading `purchase_order_use_cases.py` while writing this test (not a bug —
noted so whoever runs this doesn't mistake it for a bug):

  `ConfirmPurchaseOrderUseCase`, `CancelPurchaseOrderUseCase` and
  `ReceivePurchaseOrderUseCase` all correctly filter by `ctx.company_id`
  before acting — cross-tenant access IS blocked. But the isolation
  failure is reported as a generic `ValueError` → the router maps that to
  **HTTP 400**, not 403/404 (see `purchase_orders_router.py`:
  `except ValueError as exc: raise HTTPException(status_code=400, ...)`).
  That's DIFFERENT from `get_purchase_order` (plain GET by id), which
  returns a proper **404** for the same "not found or not yours" case.

  So: no data leak, no cross-tenant mutation — but the *status-code
  convention* is inconsistent between read and action endpoints on the
  same resource. Worth a follow-up cleanup ticket (align on 404, or at
  least document 400-for-actions as the deliberate convention); not
  worth a security fix ticket. Flagging explicitly so this isn't silently
  "fixed" here, per PKG-C1's "no implicit fixes" rule.
"""
from __future__ import annotations

import pytest

from .conftest import create_product


@pytest.fixture
async def company_a_vendor_id(client, company_a_headers) -> str:
    """An existing partner_id (vendor) belonging to company A.

    Created live through the real API (same pattern as `_create_product` in
    test_idor_catalog.py / test_idor_partners.py's partner-creation call)
    instead of a hardcoded id — a fixed id would either not exist in whatever
    DB this suite runs against, or (worse) accidentally collide with a real
    row and mask an isolation bug instead of testing for one.
    """
    # partner_type "supplier" — matches the value already used for the same
    # concept in test_idor_partners.py's `test_partner_update_is_isolated`
    # ("vendor" is the field name on the purchase order, but the underlying
    # partner record uses this project's "supplier" partner_type value).
    resp = await client.post(
        "/partners",
        json={"name": "IDOR Test Vendor", "partner_type": "supplier"},
        headers=company_a_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.fixture
async def company_a_product_id(client, company_a_headers) -> str:
    return await create_product(
        client, company_a_headers, name="IDOR Test PO Product", sku="IDOR-PO-001"
    )


async def _create_purchase_order(client, headers, vendor_id, product_id, branch_id) -> str:
    resp = await client.post(
        "/purchase-orders",
        json={
            "branch_id": branch_id,
            "supplier_id": vendor_id,
            "lines": [
                {
                    "product_id": product_id,
                    "description": "IDOR test line",
                    "quantity": 5,
                    "unit_price": 3.0,
                }
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.fixture
async def company_a_branch_id(client, company_a_headers) -> str:
    resp = await client.post("/branches", json={"name": "IDOR PO Branch"}, headers=company_a_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_purchase_order_get_by_id_is_isolated(
    client,
    company_a_headers,
    company_b_headers,
    company_a_vendor_id,
    company_a_product_id,
    company_a_branch_id,
):
    order_id = await _create_purchase_order(
        client, company_a_headers, company_a_vendor_id, company_a_product_id, company_a_branch_id
    )
    cross_tenant_resp = await client.get(f"/purchase-orders/{order_id}", headers=company_b_headers)
    assert cross_tenant_resp.status_code == 404, (
        f"IDOR: company B could read company A's purchase order {order_id} "
        f"(got {cross_tenant_resp.status_code}, expected 404)"
    )


@pytest.mark.asyncio
async def test_purchase_order_confirm_is_isolated(
    client,
    company_a_headers,
    company_b_headers,
    company_a_vendor_id,
    company_a_product_id,
    company_a_branch_id,
):
    """Cross-tenant confirm must be refused. Expected status is 400, NOT 403/404
    — see module docstring above for why that's this app's actual (if
    inconsistent) convention on this particular endpoint family."""
    order_id = await _create_purchase_order(
        client, company_a_headers, company_a_vendor_id, company_a_product_id, company_a_branch_id
    )
    cross_tenant_resp = await client.post(
        f"/purchase-orders/{order_id}/confirm", headers=company_b_headers
    )
    assert cross_tenant_resp.status_code == 400, (
        f"IDOR: company B could confirm company A's purchase order {order_id} "
        f"(got {cross_tenant_resp.status_code}, expected 400 per this app's "
        f"current — if inconsistent — convention for action endpoints)"
    )

    # Sanity: the order must still be confirmable by its real owner, i.e. the
    # blocked cross-tenant call above must not have left it in a broken state.
    owner_resp = await client.post(
        f"/purchase-orders/{order_id}/confirm", headers=company_a_headers
    )
    assert owner_resp.status_code == 200, owner_resp.text
