"use client";

import { useEffect, useState } from "react";
import { Banner, Button, Card, EmptyState, Field, PageHeader, SelectField } from "@/common/ui";
import { formatAmount } from "@/common/format";
import { ApiError } from "@/api-client/http";
import { createPayment, listBankAccounts, listPayments } from "@/features/payments/api";
import { listPartners } from "@/features/partners/api";
import type { BankAccountResponse, PartnerResponse, PaymentResponse } from "@/api-client/types";

const STATUS_LABELS: Record<string, string> = { posted: "مُرحَّلة", draft: "مسودة", cancelled: "ملغاة" };

export default function PaymentsPage() {
  const [payments, setPayments] = useState<PaymentResponse[] | null>(null);
  const [suppliers, setSuppliers] = useState<PartnerResponse[]>([]);
  const [bankAccounts, setBankAccounts] = useState<BankAccountResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  async function refresh() {
    try {
      const [paymentsData, suppliersPage, bankAccountsData] = await Promise.all([
        listPayments(),
        listPartners({ partnerType: "supplier" }),
        listBankAccounts(),
      ]);
      setPayments(paymentsData);
      setSuppliers(suppliersPage.items);
      setBankAccounts(bankAccountsData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل الدفعات");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const partnerName = (id: string) => suppliers.find((s) => s.id === id)?.name ?? id;

  return (
    <div>
      <PageHeader
        title="دفعات الموردين"
        description="سند دفع يُنشئ قيداً محاسبياً تلقائياً"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "إغلاق" : "دفعة جديدة"}</Button>}
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {showForm && (
        <Card className="mb-6">
          <CreatePaymentForm
            suppliers={suppliers}
            bankAccounts={bankAccounts}
            onCreated={() => {
              setShowForm(false);
              refresh();
            }}
          />
        </Card>
      )}

      {payments === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : payments.length === 0 ? (
        <EmptyState title="لا توجد دفعات بعد" description="سجّل أول دفعة من الأعلى" />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-right text-ink-soft">
                <th className="px-4 py-3 font-normal">الرقم</th>
                <th className="px-4 py-3 font-normal">المورّد</th>
                <th className="px-4 py-3 font-normal">الطريقة</th>
                <th className="px-4 py-3 font-normal">الحالة</th>
                <th className="px-4 py-3 font-normal">المبلغ</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id} className="border-b border-line last:border-0">
                  <td className="num px-4 py-2">{p.payment_number}</td>
                  <td className="px-4 py-2">{partnerName(p.supplier_id)}</td>
                  <td className="px-4 py-2 text-ink-soft">{p.method}</td>
                  <td className="px-4 py-2 text-ink-soft">{STATUS_LABELS[p.status] ?? p.status}</td>
                  <td className="num px-4 py-2 text-brick-600">{formatAmount(p.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

function CreatePaymentForm({
  suppliers,
  bankAccounts,
  onCreated,
}: {
  suppliers: PartnerResponse[];
  bankAccounts: BankAccountResponse[];
  onCreated: () => void;
}) {
  const [supplierId, setSupplierId] = useState("");
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
      await createPayment({
        supplier_id: supplierId,
        amount,
        method,
        bank_account_id: bankAccountId || undefined,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تسجيل الدفعة");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (suppliers.length === 0) {
    return <p className="text-sm text-ink-soft">أضف مورّداً واحداً على الأقل أولاً.</p>;
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-4">
      {error && <div className="sm:col-span-4"><Banner kind="error">{error}</Banner></div>}
      <SelectField label="المورّد" required value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
        <option value="">اختر مورّداً</option>
        {suppliers.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
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
          {isSubmitting ? "جارِ التسجيل…" : "تسجيل الدفعة"}
        </Button>
      </div>
    </form>
  );
}
