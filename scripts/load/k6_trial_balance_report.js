// PKG-C3 (partial) — k6 load test, path 3 of 3: GET /reporting/trial-balance
// (financial report — the task package's "ميزان مراجعة" option).
//
// See k6_sales_invoice_create.js for full scope notes. This completes the
// 3-path set 00_TASK_PACKAGE.md asks for; all three remain "simple part"
// scripts (short smoke profile, single script per path) rather than the
// full orchestrated multi-path load run + combined report the task's
// Definition of Done ultimately wants.
//
// This path is read-only (no state mutation, no idempotency concerns) but
// is likely the most DB-heavy of the three — trial balance aggregates
// every journal line in the fiscal period — so it's the one most likely
// to expose a missing index or an N+1 query under concurrent load.
//
// Usage:
//   k6 run -e BASE_URL=http://localhost:8000 -e AUTH_TOKEN=... \
//          -e FISCAL_PERIOD_ID=... \
//          scripts/load/k6_trial_balance_report.js

import http from 'k6/http';
import { check } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';
const FISCAL_PERIOD_ID = __ENV.FISCAL_PERIOD_ID || '';

export const errorRate = new Rate('errors');
export const reportDuration = new Trend('trial_balance_duration', true);

export const options = {
  scenarios: {
    trial_balance_report: {
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
    // Reports over a full fiscal period are the likeliest of the three
    // paths to blow past a "feels fast" assumption — no aggressive
    // threshold set here on purpose; capture the real p95/p99 first,
    // then decide what's acceptable.
    errors: ['rate<0.05'],
  },
};

export default function () {
  if (!AUTH_TOKEN || !FISCAL_PERIOD_ID) {
    throw new Error('Set AUTH_TOKEN and FISCAL_PERIOD_ID before running.');
  }

  const params = {
    headers: { Authorization: `Bearer ${AUTH_TOKEN}` },
  };

  const res = http.get(
    `${BASE_URL}/reports/trial-balance?fiscal_period_id=${FISCAL_PERIOD_ID}`,
      params
  );
  reportDuration.add(res.timings.duration);

  const ok = check(res, { 'status is 200': (r) => r.status === 200 });
  errorRate.add(!ok);
}
