"""PKG-C1 (partial) — live IDOR test template: `pos` module
(`POST /pos/sessions/{session_id}/close`).

Tenth worked example. Closing a POS session reconciles cash/sales totals
for that till — company B force-closing company A's open session mid-shift
would be a real operational problem (cashier's still-open session gets
reconciled and locked out from under them), even though it's not a
security data leak per se.
"""
from __future__ import annotations

import pytest

from .conftest import create_warehouse


@pytest.mark.asyncio
async def test_pos_session_close_is_isolated(client, company_a_headers, company_b_headers):
    """company B must not be able to close company A's open POS session."""
    warehouse_id = await create_warehouse(client, company_a_headers)
    open_resp = await client.post(
        "/pos/sessions",
        json={"warehouse_id": warehouse_id, "opening_cash": 100.0},
        headers=company_a_headers,
    )
    assert open_resp.status_code == 201, open_resp.text
    session_id = open_resp.json()["id"]

    cross_tenant_resp = await client.post(
        f"/pos/sessions/{session_id}/close",
        json={"closing_cash": 100.0},
        headers=company_b_headers,
    )
    assert cross_tenant_resp.status_code == 400, (
        f"IDOR: company B could close company A's POS session {session_id} "
        f"(got {cross_tenant_resp.status_code}, expected 400 per this app's "
        f"current convention for this action — see purchasing/catalog templates "
        f"for the same 400-vs-404 status-code-convention note)"
    )

    # Sanity: the session must still be open and closeable by its real owner.
    owner_resp = await client.post(
        f"/pos/sessions/{session_id}/close",
        json={"closing_cash": 100.0},
        headers=company_a_headers,
    )
    assert owner_resp.status_code == 200, owner_resp.text
