"""PKG-C1 (partial) — live IDOR test template: `accounting` module
(`GET /journal-entries/{entry_id}` and
`POST /fiscal-periods/{period_id}/close`).

Fifth worked example. Fiscal period close is a good one to cover:
`ClosePeriodUseCase` builds and posts a real closing journal entry — if
company B could ever trigger this on company A's fiscal period, it would
write a bogus closing entry into company A's real books. High-impact if
it existed; the router code (below) already distinguishes not-found from
already-closed with a dedicated `FiscalPeriodNotFoundError`, which is a
good sign, but only a live test proves the query behind it is actually
company-scoped.
"""
from __future__ import annotations

import pytest

from .conftest import create_product, create_warehouse, seed_chart_of_accounts, stock_in


async def _create_and_post_company_a_invoice(client, company_a_headers) -> str:
    """Posts one real sales invoice for company A, which is expected to write
    a journal entry as a side effect (per this module's own docstring: "a
    normal posted sales/purchase invoice" is the intended source of a real
    journal entry id — there's no direct "create raw journal entry" endpoint).
    Mirrors test_idor_sales_invoices.py's draft-then-post flow locally so this
    file doesn't depend on fixtures private to that module.

    Returns the resulting journal_entry_id directly from the posted invoice's
    own response body (SalesInvoiceResponse.journal_entry_id).

    Note: `GET /journal-entries` (list) now exists (added to close
    ALQAIM_V2_ISSUES_LOG.md #1) — this helper still sources the id from the
    invoice response rather than the list, since that's the more direct
    real-world source and keeps this helper independent of list ordering.
    """
    partner_resp = await client.post(
        "/partners",
        json={"name": "IDOR Accounting Test Customer", "partner_type": "customer"},
        headers=company_a_headers,
    )
    assert partner_resp.status_code == 201, partner_resp.text
    partner_id = partner_resp.json()["id"]

    # لازم فترة مالية تغطي تاريخ اليوم قبل أي ترحيل — بدونها يفشل POST
    # /sales-invoices/{id}/post بـ422 ("لا توجد فترة مالية معرَّفة...").
    fy_resp = await client.post(
        "/fiscal-periods/years",
        json={"code": "FY-JE-TEST", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        headers=company_a_headers,
    )
    assert fy_resp.status_code == 200, fy_resp.text

    product_id = await create_product(
        client, company_a_headers, name="IDOR Accounting Test Product", sku="IDOR-ACC-001"
    )

    warehouse_id = await create_warehouse(client, company_a_headers)
    await stock_in(client, company_a_headers, warehouse_id=warehouse_id, product_id=product_id)
    await seed_chart_of_accounts(client, company_a_headers)

    invoice_resp = await client.post(
        "/sales-invoices",
        json={
            "partner_id": partner_id,
            "warehouse_id": warehouse_id,
            "lines": [{"product_id": product_id, "quantity": 1, "unit_price": 10.0}],
        },
        headers=company_a_headers,
    )
    assert invoice_resp.status_code == 201, invoice_resp.text
    invoice_id = invoice_resp.json()["id"]

    post_resp = await client.post(f"/sales-invoices/{invoice_id}/post", headers=company_a_headers)
    assert post_resp.status_code == 200, post_resp.text
    journal_entry_id = post_resp.json().get("journal_entry_id")
    assert journal_entry_id, f"posted invoice had no journal_entry_id: {post_resp.text}"
    return journal_entry_id


@pytest.mark.asyncio
async def test_journal_entry_get_is_isolated(client, company_a_headers, company_b_headers):
    """GET /journal-entries/{entry_id}: company B must not read company A's entry.

    Sources a real company-A journal entry id from the posted invoice's own
    response body (see `_create_and_post_company_a_invoice`).
    """
    company_a_journal_entry_id = await _create_and_post_company_a_invoice(client, company_a_headers)

    cross_tenant_resp = await client.get(
        f"/journal-entries/{company_a_journal_entry_id}", headers=company_b_headers
    )
    assert cross_tenant_resp.status_code == 404, (
        f"IDOR: company B could read company A's journal entry "
        f"{company_a_journal_entry_id} (got {cross_tenant_resp.status_code}, expected 404)"
    )


@pytest.mark.asyncio
async def test_journal_entries_list_is_scoped_and_isolated(client, company_a_headers, company_b_headers):
    """GET /journal-entries (list, no params): closes ALQAIM_V2_ISSUES_LOG.md #1.

    Verifies the two things the issues log's own "الاختبار المطلوب" section
    asked for: (1) company A's list contains the entry it just posted, and
    (2) company B's list — despite hitting the exact same unparameterised
    endpoint — never contains company A's entry (company_id scoping, not
    just per-id 404s like the test above).
    """
    company_a_journal_entry_id = await _create_and_post_company_a_invoice(client, company_a_headers)

    company_a_list_resp = await client.get("/journal-entries", headers=company_a_headers)
    assert company_a_list_resp.status_code == 200, company_a_list_resp.text
    company_a_ids = {e["id"] for e in company_a_list_resp.json()}
    assert company_a_journal_entry_id in company_a_ids

    company_b_list_resp = await client.get("/journal-entries", headers=company_b_headers)
    assert company_b_list_resp.status_code == 200, company_b_list_resp.text
    company_b_ids = {e["id"] for e in company_b_list_resp.json()}
    assert company_a_journal_entry_id not in company_b_ids, (
        f"IDOR: company B's journal-entries list included company A's entry "
        f"{company_a_journal_entry_id}"
    )


@pytest.mark.asyncio
async def test_fiscal_period_close_is_isolated(client, company_a_headers, company_b_headers):
    """POST /fiscal-periods/{period_id}/close: company B must not be
    able to close (and write a closing journal entry into) company A's period.

    HIGH severity if reproduced: this doesn't just read data, it writes a
    real accounting entry into the target company's ledger.
    """
    create_resp = await client.post(
        "/fiscal-periods/years",
        json={"code": "FY2026", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        headers=company_a_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    fiscal_year = create_resp.json()
    # Response-shape assumption left explicit rather than silently guessed:
    # this package doesn't include FiscalYearResponse's actual definition,
    # so both plausible shapes are tried before giving up loudly. If neither
    # matches, that mismatch itself is worth noting in your findings (it
    # means the DTO differs from what every worked example in this file
    # assumed) rather than quietly reshaping the test around whatever the
    # real response turns out to be.
    if fiscal_year.get("periods"):
        period_id = fiscal_year["periods"][0]["id"]
    else:
        periods_resp = await client.get(
            f"/fiscal-periods?fiscal_year_id={fiscal_year.get('id', '')}",
            headers=company_a_headers,
        )
        periods_body = periods_resp.json() if periods_resp.status_code == 200 else []
        periods_list = periods_body.get("items", periods_body) if isinstance(periods_body, dict) else periods_body
        if not periods_list:
            pytest.skip(
                "Neither the fiscal-year creation response nor "
                "GET /fiscal-periods?fiscal_year_id=... yielded a period id — "
                "confirm this project's actual endpoint/response shape before running."
            )
        period_id = periods_list[0]["id"]

    cross_tenant_resp = await client.post(
        f"/fiscal-periods/{period_id}/close", headers=company_b_headers
    )
    assert cross_tenant_resp.status_code == 404, (
        f"IDOR (HIGH severity — writes a real closing journal entry if it succeeds): "
        f"company B could close company A's fiscal period {period_id} "
        f"(got {cross_tenant_resp.status_code}, expected 404)"
    )
