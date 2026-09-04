"""PKG-C1 (partial) — live IDOR test template: `workflow` module
(`POST /workflow/instances/{instance_id}/transition`).

Eleventh and last worked example in this partial pass — this closes out
all 11 NEEDS-MANUAL-VERIFICATION modules flagged by the static scan
(see audit/PKG-C1_tenancy_audit_partial.md §1 for the full list and
scan methodology).

Worth noting: workflow instances back things like the manager-approval
gate on sales invoices > 10,000 (see `sales/presentation/routes/
invoices_router.py`'s comment on `WorkflowPortAdapter`). If company B
could transition company A's workflow instance, in the worst case that
could mean approving/rejecting another company's pending invoice — this
is effectively a second angle on the same approval-gate risk surface
`test_idor_sales_invoices.py` covers from the sales side.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_workflow_instance_transition_is_isolated(client, company_a_headers, company_b_headers):
    """company B must not be able to transition company A's workflow instance.

    Needs a real instance_id belonging to company A — the most realistic
    source is whatever the sales-invoice manager-approval gate creates
    when an invoice over the approval threshold is posted (see
    test_idor_sales_invoices.py's `test_invoice_post_is_isolated` for how
    to trigger that), rather than trying to create a bare workflow
    instance directly here.
    """
    list_resp = await client.get("/workflow/instances", headers=company_a_headers)
    assert list_resp.status_code == 200, list_resp.text
    instances = list_resp.json()
    if not instances:
        pytest.skip(
            "No workflow instance exists for company A yet — trigger one (e.g. "
            "post a sales invoice over the manager-approval threshold) before running this test."
        )
    instance_id = instances[0]["id"]

    cross_tenant_resp = await client.post(
        f"/workflow/instances/{instance_id}/transition",
        json={"transition_name": "approve"},
        headers=company_b_headers,
    )
    assert cross_tenant_resp.status_code == 400, (
        f"IDOR (potentially HIGH severity if this instance gates something like "
        f"invoice approval): company B could transition company A's workflow "
        f"instance {instance_id} (got {cross_tenant_resp.status_code}, expected 400 "
        f"per this app's current convention for this action)"
    )
