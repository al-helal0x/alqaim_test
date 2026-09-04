// PKG-C3 (partial) — k6 load test, path 2 of 3: POST /sales/invoices/{id}/post
// (invoice posting / ledger commit).
//
// Companion to k6_sales_invoice_create.js. See that file's header for full
// scope notes — same limits apply here (short smoke profile by default,
// extend `stages` to 5-10 min for the real PKG-C3 Definition of Done run).
//
// This path is more expensive per-request than plain creation (it writes
// journal entries, may trigger the manager-approval workflow gate for
// invoices > 10,000 per the sales module's business rule) — so it is a
// more meaningful stress target than create alone, and is worth its own
// numbers rather than being folded into the create-invoice run.
//
// Setup dependency: this script needs EXISTING DRAFT invoice ids to post.
// It does not create them itself (mixing create+post load in one VU loop
// would conflate the two paths' numbers, which defeats the point of
// measuring them separately per the task package). Pre-seed N draft
// invoices and pass their ids via a JSON file — see `INVOICE_IDS_FILE`.
//
// Usage:
//   k6 run -e BASE_URL=http://localhost:8000 -e AUTH_TOKEN=... \
//          -e INVOICE_IDS_FILE=./draft_invoice_ids.json \
//          scripts/load/k6_sales_invoice_post.js
//
//   draft_invoice_ids.json format: ["id1", "id2", "id3", ...]
//   Needs at least as many ids as (peak rps * duration) — each id can only
//   be posted once, so a short 1-minute smoke at 50rps needs ~3000 ids.

import http from 'k6/http';
import { check } from 'k6';
import { SharedArray } from 'k6/data';
import { Rate, Trend, Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';
const INVOICE_IDS_FILE = __ENV.INVOICE_IDS_FILE || './draft_invoice_ids.json';

export const errorRate = new Rate('errors');
export const approvalPendingCount = new Counter('approval_pending_409'); // expected, not an error
export const postDuration = new Trend('invoice_post_duration', true);

const invoiceIds = new SharedArray('draft invoice ids', function () {
  return JSON.parse(open(INVOICE_IDS_FILE));
});

export const options = {
  scenarios: {
    sales_invoice_post: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 60,
      maxVUs: 150,
      stages: [
        { target: 50, duration: '30s' },
        { target: 50, duration: '60s' }, // extend to '5m'/'10m' for the real DoD run
        { target: 0, duration: '15s' },
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<3000'], // placeholder — posting writes journal entries, expect slower than create
    errors: ['rate<0.05'],
  },
};

export default function () {
  if (!AUTH_TOKEN) {
    throw new Error('Set AUTH_TOKEN before running.');
  }
  if (invoiceIds.length === 0) {
    throw new Error(`No invoice ids loaded from ${INVOICE_IDS_FILE} — pre-seed draft invoices first.`);
  }

  // __VU/__ITER give each iteration a distinct id so invoices aren't double-posted
  // within one run (double-posting a real invoice would fail with 422 anyway,
  // which would pollute the error rate with a non-server-performance signal).
  const idx = (__VU * 100000 + __ITER) % invoiceIds.length;
  const invoiceId = invoiceIds[idx];

  const params = {
    headers: { Authorization: `Bearer ${AUTH_TOKEN}` },
  };

  // ⚠️ إصلاح: المسار الصحيح "/sales-invoices/{id}/post" (hyphen، مطابق
  // لـ`app.include_router(sales_invoices_router, prefix="/sales-invoices")`
  // في main.py) — لا "/sales/invoices/{id}/post". نفس فئة الخلل التي كانت
  // في k6_sales_invoice_create.js سابقاً (مسار قديم قبل إعادة تسمية
  // الراوتر). اكتُشِف عبر أول تشغيل فعلي: 100% فشل بزمن استجابة ~2ms
  // (رفض فوري 404 قبل الوصول لأي منطق فعلي)، 19 أغسطس 2026.
  const res = http.post(`${BASE_URL}/sales-invoices/${invoiceId}/post`, null, params);
  postDuration.add(res.timings.duration);

  if (res.status === 409) {
    // Manager-approval-pending is expected business behavior for invoices
    // over the approval threshold, not a server error — track separately
    // so it doesn't inflate the error rate the report cares about.
    approvalPendingCount.add(1);
    return;
  }

  const ok = check(res, { 'status is 200': (r) => r.status === 200 });
  errorRate.add(!ok);
}