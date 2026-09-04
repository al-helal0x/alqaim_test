"use client";

import { useEffect, useState } from "react";
import { Banner, Button, Card, EmptyState, Field, PageHeader } from "@/common/ui";
import { formatAmount } from "@/common/format";
import { ApiError } from "@/api-client/http";
import { createPartner, listPartners } from "@/features/partners/api";
import type { PartnerResponse, PartnerType } from "@/api-client/types";

export function PartnersListPage({
  partnerType,
  title,
  description,
  createLabel,
}: {
  partnerType: Extract<PartnerType, "customer" | "supplier">;
  title: string;
  description: string;
  createLabel: string;
}) {
  const [partners, setPartners] = useState<PartnerResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  async function refresh() {
    try {
      const result = await listPartners({ partnerType });
      setPartners(result.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل القائمة");
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [partnerType]);

  return (
    <div>
      <PageHeader
        title={title}
        description={description}
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "إغلاق" : createLabel}</Button>}
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {showForm && (
        <Card className="mb-6">
          <CreatePartnerForm
            partnerType={partnerType}
            onCreated={() => {
              setShowForm(false);
              refresh();
            }}
          />
        </Card>
      )}

      {partners === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : partners.length === 0 ? (
        <EmptyState title="لا توجد سجلات بعد" description={`أضف أول ${createLabel.replace("جديد", "").trim()}`} />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-right text-ink-soft">
                <th className="px-4 py-3 font-normal">الاسم</th>
                <th className="px-4 py-3 font-normal">الهاتف</th>
                <th className="px-4 py-3 font-normal">البريد</th>
                <th className="px-4 py-3 font-normal">الرقم الضريبي</th>
                <th className="px-4 py-3 font-normal">سقف الائتمان</th>
              </tr>
            </thead>
            <tbody>
              {partners.map((p) => (
                <tr key={p.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-2">{p.name}</td>
                  <td className="num px-4 py-2 text-ink-soft">{p.phone ?? "—"}</td>
                  <td className="px-4 py-2 text-ink-soft">{p.email ?? "—"}</td>
                  <td className="num px-4 py-2 text-ink-soft">{p.tax_number ?? "—"}</td>
                  <td className="num px-4 py-2 text-ink-soft">
                    {p.credit_limit != null ? formatAmount(p.credit_limit) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

function CreatePartnerForm({
  partnerType,
  onCreated,
}: {
  partnerType: Extract<PartnerType, "customer" | "supplier">;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [taxNumber, setTaxNumber] = useState("");
  const [creditLimit, setCreditLimit] = useState("");
  const [paymentTermsDays, setPaymentTermsDays] = useState("0");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createPartner({
        name,
        partner_type: partnerType,
        phone: phone || undefined,
        email: email || undefined,
        tax_number: taxNumber || undefined,
        credit_limit: creditLimit || undefined,
        payment_terms_days: Number(paymentTermsDays) || 0,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر الإنشاء");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {error && <div className="sm:col-span-3"><Banner kind="error">{error}</Banner></div>}
      <Field label="الاسم" required value={name} onChange={(e) => setName(e.target.value)} />
      <Field label="الهاتف" value={phone} onChange={(e) => setPhone(e.target.value)} />
      <Field label="البريد الإلكتروني" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <Field label="الرقم الضريبي" value={taxNumber} onChange={(e) => setTaxNumber(e.target.value)} />
      <Field label="سقف الائتمان" type="number" step="0.01" value={creditLimit} onChange={(e) => setCreditLimit(e.target.value)} />
      <Field
        label="مدة السداد (أيام)"
        type="number"
        min={0}
        value={paymentTermsDays}
        onChange={(e) => setPaymentTermsDays(e.target.value)}
      />
      <div className="sm:col-span-3">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "جارِ الإنشاء…" : "إنشاء"}
        </Button>
      </div>
    </form>
  );
}
