"use client";

import { useEffect, useState } from "react";
import { Banner, Button, Card, EmptyState, Field, PageHeader } from "@/common/ui";
import { ApiError } from "@/api-client/http";
import { closeFiscalPeriod, createFiscalYear, listFiscalYears } from "@/features/accounting/api";
import type { FiscalYearResponse } from "@/api-client/types";

export default function FiscalYearsPage() {
  const [years, setYears] = useState<FiscalYearResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [closingId, setClosingId] = useState<string | null>(null);

  async function refresh() {
    try {
      setYears(await listFiscalYears());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل السنوات المالية");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleClose(periodId: string) {
    setError(null);
    setClosingId(periodId);
    try {
      await closeFiscalPeriod(periodId);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إقفال الفترة");
    } finally {
      setClosingId(null);
    }
  }

  return (
    <div>
      <PageHeader
        title="السنوات المالية"
        description="إدارة السنوات والفترات المحاسبية — لا يُقبل أي ترحيل على فترة مقفلة"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "إغلاق" : "سنة مالية جديدة"}</Button>}
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {showForm && (
        <Card className="mb-6">
          <CreateFiscalYearForm
            onCreated={() => {
              setShowForm(false);
              refresh();
            }}
          />
        </Card>
      )}

      {years === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : years.length === 0 ? (
        <EmptyState title="لا توجد سنوات مالية بعد" description="أنشئ سنة مالية لتتمكن من ترحيل القيود" />
      ) : (
        <div className="space-y-4">
          {years.map((year) => (
            <Card key={year.id}>
              <div className="flex items-center justify-between">
                <p className="font-display text-lg text-ink">
                  السنة المالية {year.code}
                  <span className="ms-2 text-xs text-ink-soft">
                    {year.start_date} — {year.end_date}
                  </span>
                </p>
              </div>
              <table className="mt-4 w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-right text-ink-soft">
                    <th className="py-2 font-normal">الفترة</th>
                    <th className="py-2 font-normal">من</th>
                    <th className="py-2 font-normal">إلى</th>
                    <th className="py-2 font-normal">الحالة</th>
                    <th className="py-2 font-normal"></th>
                  </tr>
                </thead>
                <tbody>
                  {year.periods.map((p) => (
                    <tr key={p.id} className="border-b border-line last:border-0">
                      <td className="py-2">{p.period_number}</td>
                      <td className="num py-2">{p.start_date}</td>
                      <td className="num py-2">{p.end_date}</td>
                      <td className="py-2">
                        {p.is_closed ? (
                          <span className="rounded bg-brick-500/10 px-2 py-0.5 text-xs text-brick-600">مقفلة</span>
                        ) : (
                          <span className="rounded bg-ledger-50 px-2 py-0.5 text-xs text-ledger-700">مفتوحة</span>
                        )}
                      </td>
                      <td className="py-2">
                        {!p.is_closed && (
                          <button
                            onClick={() => handleClose(p.id)}
                            disabled={closingId === p.id}
                            className="text-xs text-brick-600 hover:underline"
                          >
                            {closingId === p.id ? "جارِ الإقفال…" : "إقفال"}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function CreateFiscalYearForm({ onCreated }: { onCreated: () => void }) {
  const [code, setCode] = useState(String(new Date().getFullYear()));
  const [startDate, setStartDate] = useState(`${new Date().getFullYear()}-01-01`);
  const [endDate, setEndDate] = useState(`${new Date().getFullYear()}-12-31`);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createFiscalYear({ code, start_date: startDate, end_date: endDate, period_count: 12 });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء السنة المالية");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {error && <div className="sm:col-span-3"><Banner kind="error">{error}</Banner></div>}
      <Field label="الرمز" required value={code} onChange={(e) => setCode(e.target.value)} />
      <Field label="تاريخ البداية" type="date" required value={startDate} onChange={(e) => setStartDate(e.target.value)} />
      <Field label="تاريخ النهاية" type="date" required value={endDate} onChange={(e) => setEndDate(e.target.value)} />
      <div className="sm:col-span-3">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "جارِ الإنشاء…" : "إنشاء (12 فترة شهرية تلقائياً)"}
        </Button>
      </div>
    </form>
  );
}
