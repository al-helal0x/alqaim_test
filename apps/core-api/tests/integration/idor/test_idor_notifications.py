"""PKG-C1 (partial) — live IDOR test template: `notifications` module
(`POST /notifications/{notification_id}/read`).

Ninth worked example. Lowest-severity of the set if it were ever broken
(worst case is a read-state flip, not data exposure or a ledger write) —
included anyway for completeness rather than skipped, since it's cheap to
test and "low severity" isn't the same as "not worth checking".
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_notification_mark_read_is_isolated(client, company_a_headers, company_b_headers):
    """company B must not be able to mark company A's notification as read.

    No direct "create notification" endpoint is exposed here (notifications
    are presumably system-generated as a side effect of other actions) —
    trigger one indirectly first, e.g. by creating something that's known
    to fire a notification in this project, then list company A's
    notifications to grab a real id, before running the cross-tenant call
    below.
    """
    list_resp = await client.get("/notifications", headers=company_a_headers)
    assert list_resp.status_code == 200, list_resp.text
    items = list_resp.json().get("items", [])
    if not items:
        pytest.skip(
            "No notification exists for company A yet — trigger one (e.g. via "
            "an action known to fire a notification in this project) before running this test."
        )
    notification_id = items[0]["id"]

    cross_tenant_resp = await client.post(
        f"/notifications/{notification_id}/read", headers=company_b_headers
    )
    assert cross_tenant_resp.status_code == 404, (
        f"IDOR: company B could mark company A's notification {notification_id} as read "
        f"(got {cross_tenant_resp.status_code}, expected 404)"
    )
