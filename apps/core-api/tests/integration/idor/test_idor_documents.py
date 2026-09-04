"""PKG-C1 (partial) — live IDOR test template: `documents` module
(`GET /documents/{document_id}/download` and `DELETE /documents/{document_id}`).

Seventh worked example, and arguably the single highest-value one to run
first among all the templates in this directory: this is the only
endpoint set audited so far where a successful IDOR means straightforward
**file exfiltration** (attached invoices, contracts, scanned IDs —
whatever this company stores) rather than "just" reading structured rows
company B could partially guess anyway. `delete_document` is checked too
because losing another company's document is a real availability/
integrity issue even without reading its contents.
"""
from __future__ import annotations

import pytest


async def _upload_document(client, headers) -> str:
    resp = await client.post(
        "/documents",
        data={"entity_type": "partner", "entity_id": "idor-test-entity"},
        files={"file": ("idor-test.txt", b"idor test content", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_document_download_is_isolated(client, company_a_headers, company_b_headers):
    """The core exfiltration check: company B must never receive company A's
    file bytes, not even a 200 with wrong content — assert on status code,
    and if it's ever 200, that alone is the bug regardless of body."""
    document_id = await _upload_document(client, company_a_headers)

    cross_tenant_resp = await client.get(
        f"/documents/{document_id}/download", headers=company_b_headers
    )
    assert cross_tenant_resp.status_code == 404, (
        f"IDOR (file exfiltration risk): company B could download company A's "
        f"document {document_id} (got {cross_tenant_resp.status_code}, expected 404)"
    )


@pytest.mark.asyncio
async def test_document_delete_is_isolated(client, company_a_headers, company_b_headers):
    document_id = await _upload_document(client, company_a_headers)

    cross_tenant_resp = await client.delete(f"/documents/{document_id}", headers=company_b_headers)
    assert cross_tenant_resp.status_code == 404, (
        f"IDOR: company B could delete company A's document {document_id} "
        f"(got {cross_tenant_resp.status_code}, expected 404)"
    )

    # Sanity: confirm it's still there for its real owner — i.e. the blocked
    # cross-tenant delete attempt above must not have partially succeeded.
    owner_resp = await client.get(f"/documents/{document_id}/download", headers=company_a_headers)
    assert owner_resp.status_code == 200, (
        "owner could not download their own document after the blocked cross-tenant "
        "delete attempt — check whether that attempt had a partial side effect"
    )
