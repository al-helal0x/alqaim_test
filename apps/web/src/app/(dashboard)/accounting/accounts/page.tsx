"use client";

import { useEffect, useState } from "react";
import { Banner, Button, Card, EmptyState, Field, PageHeader, SelectField } from "@/common/ui";
import { ApiError } from "@/api-client/http";
import { createAccount, listAccounts, seedDefaultChartOfAccounts } from "@/features/accounting/api";
import type { AccountNormalBalance, AccountResponse, AccountType } from "@/api-client/types";

const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = {
  asset: "أصول",
  liability: "التزامات",
  equity: "حقوق ملكية",
  revenue: "إيرادات",
  expense: "مصروفات",
};

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<AccountResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSeeding, setIsSeeding] = useState(false);
  const [showForm, setShowForm] = useState(false);

  async function refresh() {
    try {
      setAccounts(await listAccounts());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل شجرة الحسابات");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleSeed() {
    setError(null);
    setIsSeeding(true);
    try {
      await seedDefaultChartOfAccounts();
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر زرع شجرة الحسابات");
    } finally {
      setIsSeeding(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="شجرة الحسابات"
        description="الحسابات المحاسبية المتاحة للترحيل عليها"
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={handleSeed} disabled={isSeeding}>
              {isSeeding ? "جارِ الزرع…" : "زرع شجرة افتراضية"}
            </Button>
            <Button onClick={() => setShowForm((s) => !s)}>
              {showForm ? "إغلاق" : "حساب جديد"}
            </Button>
          </div>
        }
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {showForm && (
        <Card className="mb-6">
          <CreateAccountForm
            onCreated={() => {
              setShowForm(false);
              refresh();
            }}
          />
        </Card>
      )}

      {accounts === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : accounts.length === 0 ? (
        <EmptyState
          title="لا توجد حسابات بعد"
          description="ابدأ بزرع شجرة حسابات افتراضية أو أنشئ حساباً يدوياً"
          action={
            <Button onClick={handleSeed} disabled={isSeeding}>
              زرع شجرة افتراضية
            </Button>
          }
        />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-right text-ink-soft">
                <th className="px-4 py-3 font-normal">الكود</th>
                <th className="px-4 py-3 font-normal">الاسم</th>
                <th className="px-4 py-3 font-normal">النوع</th>
                <th className="px-4 py-3 font-normal">الطبيعة</th>
                <th className="px-4 py-3 font-normal">قابل للترحيل</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id} className="border-b border-line last:border-0">
                  <td className="num px-4 py-2">{a.code}</td>
                  <td className={`px-4 py-2 ${a.is_postable ? "" : "font-medium text-ink"}`}>{a.name}</td>
                  <td className="px-4 py-2 text-ink-soft">{ACCOUNT_TYPE_LABELS[a.account_type]}</td>
                  <td className="px-4 py-2 text-ink-soft">{a.normal_balance === "debit" ? "مدين" : "دائن"}</td>
                  <td className="px-4 py-2 text-ink-soft">{a.is_postable ? "نعم" : "تجميعي"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

function CreateAccountForm({ onCreated }: { onCreated: () => void }) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [accountType, setAccountType] = useState<AccountType>("asset");
  const [normalBalance, setNormalBalance] = useState<AccountNormalBalance>("debit");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createAccount({ code, name, account_type: accountType, normal_balance: normalBalance });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء الحساب");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {error && <div className="sm:col-span-2"><Banner kind="error">{error}</Banner></div>}
      <Field label="الكود" required value={code} onChange={(e) => setCode(e.target.value)} />
      <Field label="الاسم" required value={name} onChange={(e) => setName(e.target.value)} />
      <SelectField
        label="النوع"
        value={accountType}
        onChange={(e) => setAccountType(e.target.value as AccountType)}
      >
        {Object.entries(ACCOUNT_TYPE_LABELS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </SelectField>
      <SelectField
        label="الطبيعة"
        value={normalBalance}
        onChange={(e) => setNormalBalance(e.target.value as AccountNormalBalance)}
      >
        <option value="debit">مدين</option>
        <option value="credit">دائن</option>
      </SelectField>
      <div className="sm:col-span-2">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "جارِ الإنشاء…" : "إنشاء الحساب"}
        </Button>
      </div>
    </form>
  );
}
