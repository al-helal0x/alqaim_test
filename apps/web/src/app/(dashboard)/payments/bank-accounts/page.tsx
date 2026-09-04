"use client";

import { useEffect, useState } from "react";
import { Banner, Button, Card, EmptyState, Field, PageHeader } from "@/common/ui";
import { formatAmount } from "@/common/format";
import { ApiError } from "@/api-client/http";
import { createBankAccount, listBankAccounts } from "@/features/payments/api";
import type { BankAccountResponse } from "@/api-client/types";

export default function BankAccountsPage() {
  const [accounts, setAccounts] = useState<BankAccountResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  async function refresh() {
    try {
      setAccounts(await listBankAccounts());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل الحسابات البنكية");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div>
      <PageHeader
        title="الحسابات البنكية والصناديق"
        description="حسابات يمكن ربط الدفعات والمقبوضات بها"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "إغلاق" : "حساب جديد"}</Button>}
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {showForm && (
        <Card className="mb-6">
          <CreateBankAccountForm
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
        <EmptyState title="لا توجد حسابات بعد" description="أضف صندوقاً نقدياً أو حساباً بنكياً" />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-right text-ink-soft">
                <th className="px-4 py-3 font-normal">الاسم</th>
                <th className="px-4 py-3 font-normal">البنك</th>
                <th className="px-4 py-3 font-normal">العملة</th>
                <th className="px-4 py-3 font-normal">الرصيد الافتتاحي</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-2">{a.name}</td>
                  <td className="px-4 py-2 text-ink-soft">{a.bank_name ?? "صندوق نقدي"}</td>
                  <td className="px-4 py-2 text-ink-soft">{a.currency_code}</td>
                  <td className="num px-4 py-2">{formatAmount(a.opening_balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

function CreateBankAccountForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [bankName, setBankName] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [openingBalance, setOpeningBalance] = useState("0");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createBankAccount({
        name,
        bank_name: bankName || undefined,
        account_number: accountNumber || undefined,
        opening_balance: openingBalance || "0",
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء الحساب");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-4">
      {error && <div className="sm:col-span-4"><Banner kind="error">{error}</Banner></div>}
      <Field label="الاسم (مثال: الصندوق الرئيسي)" required value={name} onChange={(e) => setName(e.target.value)} />
      <Field label="اسم البنك (اختياري)" value={bankName} onChange={(e) => setBankName(e.target.value)} />
      <Field label="رقم الحساب (اختياري)" value={accountNumber} onChange={(e) => setAccountNumber(e.target.value)} />
      <Field label="الرصيد الافتتاحي" type="number" step="0.01" value={openingBalance} onChange={(e) => setOpeningBalance(e.target.value)} />
      <div className="sm:col-span-4">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "جارِ الإنشاء…" : "إنشاء"}
        </Button>
      </div>
    </form>
  );
}
