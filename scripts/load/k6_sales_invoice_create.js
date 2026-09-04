// PKG-C3 (partial) — k6 load test for ONE critical path only:
// POST /sales-invoices (invoice creation).
//
// SCOPE: 00_TASK_PACKAGE.md asks PKG-C3 to cover THREE paths (invoice
// create, invoice post, financial report). This script is deliberately
// scoped to just the first, as the "simple part" of that track — it's a
// template the other two paths can be copied from, not the full suite.
//
// ⚠️ إصلاح (2026-08-17، أول تشغيل حقيقي على core-api حي): النسخة السابقة
// كانت تبعث لـ /sales/invoices (سلاش) — المسار الحقيقي المسجَّل فعلياً في
// main.py هو /sales-invoices (شرطة، app.include_router(sales_invoices_router,
// prefix="/sales-invoices")) — كل طلب كان يرجع 404 فوراً (~1.5ms لكل طلب،
// خطأ 100%). كما أن SalesInvoiceCreateRequest تتطلب warehouse_id إلزامياً
// ولم يكن يُرسَل إطلاقاً — أُضيف كمتغيّر بيئة ثالث مطلوب.
//
// Usage:
//   k6 run -e BASE_URL=http://localhost:8000 -e AUTH_TOKEN=... \
//          -e PARTNER_ID=... -e PRODUCT_ID=... -e WAREHOUSE_ID=... \
//          scripts/load/k6_sales_invoice_create.js
//
// Target from 00_TASK_PACKAGE.md: 50 req/s sustained for 5-10 minutes.
// This script defaults to a short smoke profile (1 min, ramping to
// ~50 rps) — bump `duration`/stages for the full 5-10 minute run.

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';
const PARTNER_ID = __ENV.PARTNER_ID || '';
const PRODUCT_ID = __ENV.PRODUCT_ID || '';
const WAREHOUSE_ID = __ENV.WAREHOUSE_ID || '';

export const errorRate = new Rate('errors');
export const invoiceCreateDuration = new Trend('invoice_create_duration', true);

export const options = {
  scenarios: {
    sales_invoice_create: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 60,
      maxVUs: 150,
      stages: [
        { target: 50, duration: '30s' }, // ramp up
        { target: 50, duration: '60s' }, // hold — extend to '5m'/'10m' for the real DoD run
        { target: 0, duration: '15s' },  // ramp down
      ],
    },
  },
  thresholds: {
    // These are placeholders — 00_TASK_PACKAGE.md's Definition of Done is
    // "real numbers reported", not "must be under X". Set real SLO
    // thresholds once you have a baseline; failing thresholds here just
    // marks the k6 run itself as failed, it doesn't invalidate the data.
    http_req_duration: ['p(95)<2000'],
    errors: ['rate<0.05'],
  },
};

export default function () {
  if (!AUTH_TOKEN || !PARTNER_ID || !PRODUCT_ID || !WAREHOUSE_ID) {
    throw new Error(
      'Set AUTH_TOKEN, PARTNER_ID, PRODUCT_ID and WAREHOUSE_ID env vars before running ' +
      '(see file header for the -e flags k6 needs).'
    );
  }

  const payload = JSON.stringify({
    partner_id: PARTNER_ID,
    warehouse_id: WAREHOUSE_ID,
    lines: [
      { product_id: PRODUCT_ID, quantity: 1, unit_price: 10.0 },
    ],
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${AUTH_TOKEN}`,
      // A load test that reuses one idempotency key would only exercise
      // the "duplicate" branch after the first request — deliberately
      // omitted so every request creates a distinct invoice, matching
      // the "create invoice" path under test.
    },
  };

  const res = http.post(`${BASE_URL}/sales-invoices`, payload, params);

  invoiceCreateDuration.add(res.timings.duration);
  const ok = check(res, {
    'status is 201': (r) => r.status === 201,
  });
  errorRate.add(!ok);

  sleep(0.1);
}

// After the run, k6's own summary gives p50/p95/p99 and error rate for
// this path — pipe `k6 run --summary-export=results.json ...` to keep a
// machine-readable copy for the PKG-C3 report the task package asks for.
