"use client";

import { useEffect, useState } from "react";
import { Banner, Button, Card, EmptyState, Field, PageHeader, SelectField } from "@/common/ui";
import { formatAmount } from "@/common/format";
import { ApiError } from "@/api-client/http";
import { createReceipt, listBankAccounts, listReceipts } from "@/features/payments/api";
import { listPartners } from "@/features/partners/api";
import type { BankAccountResponse, PartnerResponse, ReceiptResponse } from "@/api-client/types";

const STATUS_LABELS: Record<string, string> = { posted: "مُرحَّلة", draft: "مسودة", cancelled: "ملغاة" };

export default function ReceiptsPage() {
  const [receipts, setReceipts] = useState<ReceiptResponse[] | null>(null);
  const [customers, setCustomers] = useState<PartnerResponse[]>([]);
  const [bankAccounts, setBankAccounts] = useState<BankAccountResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  async function refresh() {
    try {
      const [receiptsData, customersPage, bankAccountsData] = await Promise.all([
        listReceipts(),
        listPartners({ partnerType: "customer" }),
        listBankAccounts(),
      ]);
      setReceipts(receiptsData);
      setCustomers(customersPage.items);
      setBankAccounts(bankAccountsData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل سندات القبض");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const partnerName = (id: string) => customers.find((c) => c.id === id)?.name ?? id;

  return (
    <div>
      <PageHeader
        title="سندات القبض"
        description="سند قبض من عميل يُنشئ قيداً محاسبياً تلقائياً"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "إغلاق" : "سند قبض جديد"}</Button>}
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {showForm && (
        <Card className="mb-6">
          <CreateReceiptForm
            customers={customers}
            bankAccounts={bankAccounts}
            onCreated={() => {
              setShowForm(false);
              refresh();
            }}
          />
        </Card>
      )}

      {receipts === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : receipts.length === 0 ? (
        <EmptyState title="لا توجد سندات قبض بعد" description="سجّل أول سند من الأعلى" />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-right text-ink-soft">
                <th className="px-4 py-3 font-normal">الرقم</th>
                <th className="px-4 py-3 font-normal">العميل</th>
                <th className="px-4 py-3 font-normal">الطريقة</th>
                <th className="px-4 py-3 font-normal">الحالة</th>
                <th className="px-4 py-3 font-normal">المبلغ</th>
              </tr>
            </thead>
            <tbody>
              {receipts.map((r) => (
                <tr key={r.id} className="border-b border-line last:border-0">
                  <td className="num px-4 py-2">{r.receipt_number}</td>
                  <td className="px-4 py-2">{partnerName(r.customer_id)}</td>
                  <td className="px-4 py-2 text-ink-soft">{r.method}</td>
                  <td className="px-4 py-2 text-ink-soft">{STATUS_LABELS[r.status] ?? r.status}</td>
                  <td className="num px-4 py-2 text-ledger-700">{formatAmount(r.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

function CreateReceiptForm({
  customers,
  bankAccounts,
  onCreated,
}: {
  customers: PartnerResponse[];
  bankAccounts: BankAccountResponse[];
  onCreated: () => void;
}) {
  const [customerId, setCustomerId] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("cash");
  const [bankAccountId, setBankAccountId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createReceipt({
        customer_id: customerId,
        amount,
        method,
        bank_account_id: bankAccountId || undefined,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تسجيل السند");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (customers.length === 0) {
    return <p className="text-sm text-ink-soft">أضف عميلاً واحداً على الأقل أولاً.</p>;
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-4">
      {error && <div className="sm:col-span-4"><Banner kind="error">{error}</Banner></div>}
      <SelectField label="العميل" required value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
        <option value="">اختر عميلاً</option>
        {customers.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </SelectField>
      <Field label="المبلغ" type="number" step="0.01" required value={amount} onChange={(e) => setAmount(e.target.value)} />
      <SelectField label="الطريقة" value={method} onChange={(e) => setMethod(e.target.value)}>
        <option value="cash">نقداً</option>
        <option value="bank_transfer">تحويل بنكي</option>
        <option value="cheque">شيك</option>
      </SelectField>
      <SelectField label="الحساب (اختياري)" value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
        <option value="">بلا حساب محدَّد</option>
        {bankAccounts.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </SelectField>
      <div className="sm:col-span-4">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "جارِ التسجيل…" : "تسجيل السند"}
        </Button>
      </div>
    </form>
  );
}
