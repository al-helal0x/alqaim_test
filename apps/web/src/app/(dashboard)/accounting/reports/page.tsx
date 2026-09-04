"use client";

import { useEffect, useState } from "react";
import { Banner, Card, PageHeader, SelectField } from "@/common/ui";
import { formatAmount } from "@/common/format";
import { ApiError } from "@/api-client/http";
import {
  getBalanceSheet,
  getIncomeStatement,
  getTrialBalance,
  listFiscalYears,
} from "@/features/accounting/api";
import type {
  BalanceSheetResponse,
  FiscalYearResponse,
  IncomeStatementResponse,
  TrialBalanceResponse,
} from "@/api-client/types";

type Tab = "trial-balance" | "income-statement" | "balance-sheet";

export default function ReportsPage() {
  const [years, setYears] = useState<FiscalYearResponse[]>([]);
  const [yearId, setYearId] = useState("");
  const [periodId, setPeriodId] = useState("");
  const [tab, setTab] = useState<Tab>("trial-balance");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listFiscalYears()
      .then((data) => {
        setYears(data);
        if (data[0]) {
          setYearId(data[0].id);
          setPeriodId(data[0].periods[0]?.id ?? "");
        }
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "تعذّر تحميل السنوات المالية"));
  }, []);

  const selectedYear = years.find((y) => y.id === yearId);

  return (
    <div>
      <PageHeader title="التقارير المالية" description="ميزان المراجعة، قائمة الدخل، والميزانية العمومية" />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {years.length === 0 ? (
        <p className="text-sm text-ink-soft">أنشئ سنة مالية أولاً من صفحة السنوات المالية.</p>
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-end gap-4">
            <div className="w-56">
              <SelectField
                label="السنة المالية"
                value={yearId}
                onChange={(e) => {
                  setYearId(e.target.value);
                  const y = years.find((x) => x.id === e.target.value);
                  setPeriodId(y?.periods[0]?.id ?? "");
                }}
              >
                {years.map((y) => (
                  <option key={y.id} value={y.id}>
                    {y.code}
                  </option>
                ))}
              </SelectField>
            </div>
            {tab === "trial-balance" && selectedYear && (
              <div className="w-56">
                <SelectField label="الفترة" value={periodId} onChange={(e) => setPeriodId(e.target.value)}>
                  {selectedYear.periods.map((p) => (
                    <option key={p.id} value={p.id}>
                      فترة {p.period_number} ({p.start_date} — {p.end_date})
                    </option>
                  ))}
                </SelectField>
              </div>
            )}
          </div>

          <div className="mb-4 flex gap-2 border-b border-line">
            <TabButton active={tab === "trial-balance"} onClick={() => setTab("trial-balance")}>
              ميزان المراجعة
            </TabButton>
            <TabButton active={tab === "income-statement"} onClick={() => setTab("income-statement")}>
              قائمة الدخل
            </TabButton>
            <TabButton active={tab === "balance-sheet"} onClick={() => setTab("balance-sheet")}>
              الميزانية العمومية
            </TabButton>
          </div>

          {tab === "trial-balance" && periodId && <TrialBalanceView periodId={periodId} />}
          {tab === "income-statement" && yearId && <IncomeStatementView yearId={yearId} />}
          {tab === "balance-sheet" && yearId && <BalanceSheetView yearId={yearId} />}
        </>
      )}
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`border-b-2 px-1 pb-2 text-sm transition-colors ${
        active ? "border-copper-500 text-ink" : "border-transparent text-ink-soft hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

function TrialBalanceView({ periodId }: { periodId: string }) {
  const [data, setData] = useState<TrialBalanceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    getTrialBalance(periodId)
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "تعذّر تحميل ميزان المراجعة"));
  }, [periodId]);

  if (error) return <Banner kind="error">{error}</Banner>;
  if (!data) return <p className="text-sm text-ink-soft">جارِ التحميل…</p>;

  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-right text-ink-soft">
            <th className="px-4 py-3 font-normal">الكود</th>
            <th className="px-4 py-3 font-normal">الحساب</th>
            <th className="px-4 py-3 font-normal">مدين</th>
            <th className="px-4 py-3 font-normal">دائن</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.account_id} className="border-b border-line last:border-0">
              <td className="num px-4 py-2">{r.account_code}</td>
              <td className="px-4 py-2">{r.account_name}</td>
              <td className="num px-4 py-2 text-ledger-700">{formatAmount(r.total_debit)}</td>
              <td className="num px-4 py-2 text-copper-600">{formatAmount(r.total_credit)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center justify-between border-t border-line px-4 py-3">
        <span className="text-sm text-ink-soft">
          {data.is_balanced ? "الميزان متوازن ✓" : "تنبيه: الميزان غير متوازن"}
        </span>
      </div>
    </Card>
  );
}

function IncomeStatementView({ yearId }: { yearId: string }) {
  const [data, setData] = useState<IncomeStatementResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    getIncomeStatement(yearId)
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "تعذّر تحميل قائمة الدخل"));
  }, [yearId]);

  if (error) return <Banner kind="error">{error}</Banner>;
  if (!data) return <p className="text-sm text-ink-soft">جارِ التحميل…</p>;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <StatementCard title="الإيرادات" rows={data.revenue_rows} total={data.total_revenue} tone="ledger" />
      <StatementCard title="المصروفات" rows={data.expense_rows} total={data.total_expense} tone="brick" />
      <Card className="lg:col-span-2">
        <p className="font-display text-lg text-ink">
          صافي {Number(data.net_income) >= 0 ? "الربح" : "الخسارة"}:{" "}
          <span className="num">{formatAmount(data.net_income)}</span>
        </p>
      </Card>
    </div>
  );
}

function BalanceSheetView({ yearId }: { yearId: string }) {
  const [data, setData] = useState<BalanceSheetResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    getBalanceSheet(yearId)
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "تعذّر تحميل الميزانية العمومية"));
  }, [yearId]);

  if (error) return <Banner kind="error">{error}</Banner>;
  if (!data) return <p className="text-sm text-ink-soft">جارِ التحميل…</p>;

  return (
    <div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <StatementCard title="الأصول" rows={data.asset_rows} total={data.total_assets} tone="ledger" />
        <div className="space-y-4">
          <StatementCard title="الالتزامات" rows={data.liability_rows} total={data.total_liabilities} tone="brick" />
          <StatementCard
            title="حقوق الملكية"
            rows={data.equity_rows}
            total={data.total_equity}
            tone="copper"
            extraRow={{ label: "صافي ربح الفترة الحالية", amount: data.current_period_net_income }}
          />
        </div>
      </div>
      <p className="mt-4 text-sm text-ink-soft">
        {data.is_balanced ? "الميزانية متوازنة: الأصول = الالتزامات + حقوق الملكية ✓" : "تنبيه: الميزانية غير متوازنة"}
      </p>
    </div>
  );
}

function StatementCard({
  title,
  rows,
  total,
  tone,
  extraRow,
}: {
  title: string;
  rows: { account_id: string; account_code: string; account_name: string; amount: string }[];
  total: string;
  tone: "ledger" | "brick" | "copper";
  extraRow?: { label: string; amount: string };
}) {
  const toneClass = { ledger: "text-ledger-700", brick: "text-brick-600", copper: "text-copper-600" }[tone];
  return (
    <Card>
      <p className="mb-3 font-display text-lg text-ink">{title}</p>
      <table className="w-full text-sm">
        <tbody>
          {rows.map((r) => (
            <tr key={r.account_id} className="border-b border-line">
              <td className="py-1.5 text-ink-soft">
                <span className="num me-2">{r.account_code}</span>
                {r.account_name}
              </td>
              <td className={`num py-1.5 text-left ${toneClass}`}>{formatAmount(r.amount)}</td>
            </tr>
          ))}
          {extraRow && (
            <tr className="border-b border-line">
              <td className="py-1.5 text-ink-soft">{extraRow.label}</td>
              <td className={`num py-1.5 text-left ${toneClass}`}>{formatAmount(extraRow.amount)}</td>
            </tr>
          )}
        </tbody>
      </table>
      <div className="mt-2 flex justify-between border-t border-line pt-2 text-sm font-medium">
        <span>الإجمالي</span>
        <span className={`num ${toneClass}`}>{formatAmount(total)}</span>
      </div>
    </Card>
  );
}
