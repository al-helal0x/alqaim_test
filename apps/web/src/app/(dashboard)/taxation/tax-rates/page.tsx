"use client";

import { useEffect, useState } from "react";
import { Banner, Button, Card, EmptyState, Field, PageHeader } from "@/common/ui";
import { formatAmount } from "@/common/format";
import { ApiError } from "@/api-client/http";
import { calculateTax, createTaxRate, listTaxRates } from "@/features/taxation/api";
import type { TaxCalculationResponse, TaxRateResponse } from "@/api-client/types";

export default function TaxRatesPage() {
  const [rates, setRates] = useState<TaxRateResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  async function refresh() {
    try {
      setRates(await listTaxRates());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل نسب الضريبة");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div>
      <PageHeader
        title="نسب الضريبة"
        description="إدارة نسب الضريبة المستخدَمة في الفواتير"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "إغلاق" : "نسبة جديدة"}</Button>}
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {showForm && (
        <Card className="mb-6">
          <CreateTaxRateForm
            onCreated={() => {
              setShowForm(false);
              refresh();
            }}
          />
        </Card>
      )}

      {rates === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : rates.length === 0 ? (
        <EmptyState title="لا توجد نسب ضريبة بعد" description="أضف أول نسبة ضريبة لاستخدامها في الفواتير" />
      ) : (
        <>
          <Card className="mb-6 overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-right text-ink-soft">
                  <th className="px-4 py-3 font-normal">الكود</th>
                  <th className="px-4 py-3 font-normal">الاسم</th>
                  <th className="px-4 py-3 font-normal">النسبة</th>
                </tr>
              </thead>
              <tbody>
                {rates.map((r) => (
                  <tr key={r.id} className="border-b border-line last:border-0">
                    <td className="num px-4 py-2">{r.code}</td>
                    <td className="px-4 py-2">{r.name}</td>
                    <td className="num px-4 py-2">{formatAmount(r.rate_percent)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <TaxCalculator rates={rates} />
        </>
      )}
    </div>
  );
}

function CreateTaxRateForm({ onCreated }: { onCreated: () => void }) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [ratePercent, setRatePercent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createTaxRate({ code, name, rate_percent: ratePercent });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء نسبة الضريبة");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {error && <div className="sm:col-span-3"><Banner kind="error">{error}</Banner></div>}
      <Field label="الكود" required value={code} onChange={(e) => setCode(e.target.value)} />
      <Field label="الاسم" required value={name} onChange={(e) => setName(e.target.value)} />
      <Field
        label="النسبة (%)"
        type="number"
        step="0.01"
        min="0"
        max="100"
        required
        value={ratePercent}
        onChange={(e) => setRatePercent(e.target.value)}
      />
      <div className="sm:col-span-3">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "جارِ الإنشاء…" : "إنشاء"}
        </Button>
      </div>
    </form>
  );
}

function TaxCalculator({ rates }: { rates: TaxRateResponse[] }) {
  const [baseAmount, setBaseAmount] = useState("");
  const [taxRateId, setTaxRateId] = useState(rates[0]?.id ?? "");
  const [result, setResult] = useState<TaxCalculationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isCalculating, setIsCalculating] = useState(false);

  async function handleCalculate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setIsCalculating(true);
    try {
      setResult(await calculateTax({ base_amount: baseAmount, tax_rate_id: taxRateId }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر حساب الضريبة");
    } finally {
      setIsCalculating(false);
    }
  }

  return (
    <Card>
      <p className="mb-3 font-display text-lg text-ink">حاسبة الضريبة</p>
      <form onSubmit={handleCalculate} className="flex flex-wrap items-end gap-4">
        {error && <div className="w-full"><Banner kind="error">{error}</Banner></div>}
        <div className="w-40">
          <Field
            label="المبلغ الأساسي"
            type="number"
            step="0.01"
            required
            value={baseAmount}
            onChange={(e) => setBaseAmount(e.target.value)}
          />
        </div>
        <div className="w-56">
          <label className="block">
            <span className="mb-1 block text-sm text-ink-soft">نسبة الضريبة</span>
            <select
              value={taxRateId}
              onChange={(e) => setTaxRateId(e.target.value)}
              className="w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-copper-500"
            >
              {rates.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} ({formatAmount(r.rate_percent)}%)
                </option>
              ))}
            </select>
          </label>
        </div>
        <Button type="submit" disabled={isCalculating}>
          {isCalculating ? "جارِ الحساب…" : "احسب"}
        </Button>
      </form>

      {result && (
        <div className="mt-4 flex gap-6 border-t border-line pt-4 text-sm">
          <span>
            الضريبة: <span className="num text-copper-600">{formatAmount(result.tax_amount)}</span>
          </span>
          <span>
            الإجمالي: <span className="num font-medium text-ink">{formatAmount(result.total_amount)}</span>
          </span>
        </div>
      )}
    </Card>
  );
}
