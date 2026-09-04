"""PKG-C1 (partial) — live IDOR test template: `partners` module.

This is a WORKED EXAMPLE for one of the 18 modules the full PKG-C1 audit
must cover, not the full suite. It shows the exact pattern every other
module's IDOR test should follow:

    1. Create a resource as Company A.
    2. Re-issue the *same* request (same resource id) authenticated as
       Company B.
    3. Assert Company B is refused (404 is preferred over 403 here: a 403
       would confirm to Company B that the id exists at all, which is
       itself a minor information leak — but 403 is acceptable too if
       that's the app's established convention. Whichever the app uses,
       assert on it consistently. Never 200.)

Wiring notes (fill in for your actual test environment — these are left
as `pytest.fixture` stubs on purpose so this file can be copy-pasted per
module without guessing at this project's actual client/auth-header
setup, which lives outside OWNED/ and wasn't touched here):

  - `client`: an `httpx.AsyncClient` (or `TestClient`) pointed at the
    running app.
  - `company_a_token` / `company_b_token`: two valid auth tokens/headers
    for two DIFFERENT companies that already exist in the test DB.

Run:  pytest OWNED/tests/idor/test_idor_partners.py -v
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_partner_get_by_id_is_isolated(client, company_a_headers, company_b_headers):
    """GET /partners/{partner_id}: company B must never see company A's partner."""
    create_resp = await client.post(
        "/partners",
        json={"name": "IDOR Test Partner", "partner_type": "customer"},
        headers=company_a_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    partner_id = create_resp.json()["id"]

    cross_tenant_resp = await client.get(f"/partners/{partner_id}", headers=company_b_headers)
    assert cross_tenant_resp.status_code in (403, 404), (
        f"IDOR: company B could read company A's partner {partner_id} "
        f"(got {cross_tenant_resp.status_code}, expected 403 or 404)"
    )

    same_tenant_resp = await client.get(f"/partners/{partner_id}", headers=company_a_headers)
    assert same_tenant_resp.status_code == 200, "sanity check: owner should still be able to read it"


@pytest.mark.asyncio
async def test_partner_update_is_isolated(client, company_a_headers, company_b_headers):
    """PATCH /partners/{partner_id}: company B must not be able to modify company A's partner."""
    create_resp = await client.post(
        "/partners",
        json={"name": "IDOR Update Target", "partner_type": "supplier"},
        headers=company_a_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    partner_id = create_resp.json()["id"]

    cross_tenant_resp = await client.patch(
        f"/partners/{partner_id}",
        json={"name": "Hijacked by company B"},
        headers=company_b_headers,
    )
    assert cross_tenant_resp.status_code in (403, 404), (
        f"IDOR: company B could modify company A's partner {partner_id} "
        f"(got {cross_tenant_resp.status_code}, expected 403 or 404)"
    )
