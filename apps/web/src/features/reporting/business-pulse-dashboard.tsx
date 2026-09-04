"use client";

import { useEffect, useState } from "react";
import { Banner, Card } from "@/common/ui";
import { formatAmount } from "@/common/format";
import { ApiError } from "@/api-client/http";
import { getBusinessPulse } from "@/features/reporting/api";
import type { BusinessPulseResponse } from "@/features/reporting/api";

/**
 * TASK-BI-01 — لوحة "نبض الشركة اليومي".
 *
 * قرار تصميم صريح: لا مكتبة رسوم بيانية جديدة (recharts/d3/...) في هذه
 * النسخة الأولى — لم تكن أي مكتبة رسوم بيانية مثبَّتة أصلاً في
 * apps/web/package.json وقت تنفيذ هذه المهمة، وإضافة تبعية جديدة قرار
 * تقني يستحق نقاشاً منفصلاً لا أن يُتخَذ ضمنياً داخل أول Slice. الرسمان
 * أدناه (خط المبيعات، أعمدة أعلى المنتجات) SVG يدوي بسيط.
 *
 * هذا المكوّن عرض بيانات خام فقط — لا تفسير، لا توصية، لا أي طبقة AI
 * (حسب "Explicitly NOT in scope" في TASK-BI-01.md).
 */
export function BusinessPulseDashboard() {
  const [data, setData] = useState<BusinessPulseResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBusinessPulse(7)
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "تعذّر تحميل لوحة نبض الشركة"));
  }, []);

  if (error) return <Banner kind="error">{error}</Banner>;
  if (!data) return <p className="text-sm text-ink-soft">جارِ التحميل…</p>;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <SalesTrendCard data={data} />
      <TopProductsCard data={data} />
      <CashPositionCard data={data} />
      <LowStockCard data={data} />
      <ReceivablesAgingCard data={data} />
    </div>
  );
}

function SalesTrendCard({ data }: { data: BusinessPulseResponse }) {
  const points = data.sales_trend.map((p) => Number(p.total_amount));
  const max = Math.max(1, ...points);
  const width = 320;
  const height = 100;
  const stepX = points.length > 1 ? width / (points.length - 1) : width;

  const path = points
    .map((v, i) => {
      const x = i * stepX;
      const y = height - (v / max) * height;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const current = Number(data.sales_total_current_period);
  const previous = Number(data.sales_total_previous_period);
  const changePct = previous > 0 ? ((current - previous) / previous) * 100 : null;

  return (
    <Card className="lg:col-span-2">
      <p className="mb-1 font-display text-lg text-ink">مبيعات آخر {data.period_days} أيام</p>
      <p className="mb-3 text-sm text-ink-soft">
        <span className="num text-ink">{formatAmount(current)}</span>
        {changePct !== null && (
          <span className={changePct >= 0 ? "text-ledger-700" : "text-brick-600"}>
            {" "}
            ({changePct >= 0 ? "+" : ""}
            {changePct.toFixed(1)}٪ مقارنة بالفترة السابقة)
          </span>
        )}
      </p>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-24 w-full" preserveAspectRatio="none">
        <path d={path} fill="none" stroke="currentColor" strokeWidth={2} className="text-copper-500" />
      </svg>
      <div className="mt-2 flex justify-between text-xs text-ink-soft">
        <span>{data.sales_trend[0]?.day}</span>
        <span>{data.sales_trend[data.sales_trend.length - 1]?.day}</span>
      </div>
    </Card>
  );
}

function TopProductsCard({ data }: { data: BusinessPulseResponse }) {
  const max = Math.max(1, ...data.top_products.map((p) => Number(p.total_amount)));

  return (
    <Card>
      <p className="mb-3 font-display text-lg text-ink">أعلى المنتجات مبيعاً</p>
      {data.top_products.length === 0 ? (
        <p className="text-sm text-ink-soft">لا مبيعات ضمن هذه الفترة.</p>
      ) : (
        <div className="space-y-2">
          {data.top_products.map((p) => {
            const pct = (Number(p.total_amount) / max) * 100;
            return (
              <div key={p.product_id}>
                <div className="mb-1 flex justify-between text-xs text-ink-soft">
                  <span className="num">{p.product_id.slice(0, 8)}…</span>
                  <span className="num">{formatAmount(p.total_amount)}</span>
                </div>
                <div className="h-2 rounded bg-line">
                  <div className="h-2 rounded bg-copper-500" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
      <p className="mt-3 text-xs text-ink-soft">
        يُعرَض معرّف المنتج مؤقتاً بدل الاسم (لا يعتمد هذا الـ Slice على وحدة الكتالوج).
      </p>
    </Card>
  );
}

function CashPositionCard({ data }: { data: BusinessPulseResponse }) {
  return (
    <Card>
      <p className="mb-1 font-display text-lg text-ink">الصندوق والحسابات البنكية</p>
      <p className="mb-3 text-2xl text-ledger-700">
        <span className="num">{formatAmount(data.cash_total)}</span>
      </p>
      {data.cash_accounts.length === 0 ? (
        <p className="text-sm text-ink-soft">لا حسابات بنكية مُسجَّلة بعد.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {data.cash_accounts.map((acc) => (
            <li key={acc.bank_account_id} className="flex justify-between text-ink-soft">
              <span>{acc.name}</span>
              <span className="num">
                {formatAmount(acc.balance)} {acc.currency_code}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function LowStockCard({ data }: { data: BusinessPulseResponse }) {
  return (
    <Card>
      <p className="mb-1 font-display text-lg text-ink">الأقل مخزوناً</p>
      <p className="mb-3 text-xs text-ink-soft">
        أدنى 5 عناصر بالكمية الحالية (وليس بالضرورة تحت حد إعادة الطلب).
      </p>
      {data.low_stock_items.length === 0 ? (
        <p className="text-sm text-ink-soft">لا أرصدة مخزون مُسجَّلة بعد.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {data.low_stock_items.map((item, i) => (
            <li key={`${item.product_id}-${item.warehouse_id}-${i}`} className="flex justify-between text-ink-soft">
              <span className="num">{item.product_id.slice(0, 8)}…</span>
              <span className={`num ${Number(item.quantity) === 0 ? "text-brick-600" : ""}`}>
                {formatAmount(item.quantity)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function ReceivablesAgingCard({ data }: { data: BusinessPulseResponse }) {
  const buckets: { label: string; value: string; tone: string }[] = [
    { label: "0–30 يوم", value: data.receivables_aging.bucket_0_30, tone: "text-ledger-700" },
    { label: "31–60 يوم", value: data.receivables_aging.bucket_31_60, tone: "text-copper-600" },
    { label: "أكثر من 60 يوماً", value: data.receivables_aging.bucket_61_plus, tone: "text-brick-600" },
  ];

  return (
    <Card>
      <p className="mb-3 font-display text-lg text-ink">أعمار الذمم المدينة</p>
      <div className="space-y-2">
        {buckets.map((b) => (
          <div key={b.label} className="flex justify-between text-sm">
            <span className="text-ink-soft">{b.label}</span>
            <span className={`num ${b.tone}`}>{formatAmount(b.value)}</span>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-ink-soft">
        الأساس هنا تاريخ إنشاء الفاتورة المرحَّلة (لا يوجد تاريخ استحقاق منفصل حالياً).
      </p>
    </Card>
  );
}
