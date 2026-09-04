"use client";

import { useEffect, useState } from "react";
import { Banner, Button, Card, EmptyState, Field, PageHeader, SelectField } from "@/common/ui";
import { formatAmount } from "@/common/format";
import { ApiError } from "@/api-client/http";
import { createQuotation, listQuotations, updateQuotationStatus } from "@/features/sales/api";
import { listPartners } from "@/features/partners/api";
import { listProducts } from "@/features/catalog/api";
import type { LineItemRequest, PartnerResponse, ProductResponse, QuotationResponse } from "@/api-client/types";

const STATUS_LABELS: Record<string, string> = {
  draft: "مسودة",
  sent: "مُرسَلة",
  accepted: "مقبولة",
  rejected: "مرفوضة",
  expired: "منتهية",
};

export default function QuotationsPage() {
  const [quotations, setQuotations] = useState<QuotationResponse[] | null>(null);
  const [customers, setCustomers] = useState<PartnerResponse[]>([]);
  const [products, setProducts] = useState<ProductResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  async function refresh() {
    try {
      const [quotationsPage, customersPage, productsPage] = await Promise.all([
        listQuotations(),
        listPartners({ partnerType: "customer" }),
        listProducts({ page: 1 }),
      ]);
      setQuotations(quotationsPage.items);
      setCustomers(customersPage.items);
      setProducts(productsPage.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل عروض الأسعار");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleSend(id: string) {
    setUpdatingId(id);
    try {
      await updateQuotationStatus(id, "sent");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحديث الحالة");
    } finally {
      setUpdatingId(null);
    }
  }

  const partnerName = (id: string) => customers.find((c) => c.id === id)?.name ?? id;

  return (
    <div>
      <PageHeader
        title="عروض الأسعار"
        description="عروض أسعار للعملاء قبل تحويلها لأمر بيع"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "إغلاق" : "عرض سعر جديد"}</Button>}
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {showForm && (
        <Card className="mb-6">
          <CreateQuotationForm
            customers={customers}
            products={products}
            onCreated={() => {
              setShowForm(false);
              refresh();
            }}
          />
        </Card>
      )}

      {quotations === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : quotations.length === 0 ? (
        <EmptyState title="لا توجد عروض أسعار بعد" description="أنشئ أول عرض سعر من الأعلى" />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-right text-ink-soft">
                <th className="px-4 py-3 font-normal">الرقم</th>
                <th className="px-4 py-3 font-normal">العميل</th>
                <th className="px-4 py-3 font-normal">الحالة</th>
                <th className="px-4 py-3 font-normal">الإجمالي</th>
                <th className="px-4 py-3 font-normal"></th>
              </tr>
            </thead>
            <tbody>
              {quotations.map((q) => (
                <tr key={q.id} className="border-b border-line last:border-0">
                  <td className="num px-4 py-2">{q.quotation_number}</td>
                  <td className="px-4 py-2">{partnerName(q.partner_id)}</td>
                  <td className="px-4 py-2 text-ink-soft">{STATUS_LABELS[q.status] ?? q.status}</td>
                  <td className="num px-4 py-2">{formatAmount(q.total_amount)}</td>
                  <td className="px-4 py-2">
                    {q.status === "draft" && (
                      <button
                        onClick={() => handleSend(q.id)}
                        disabled={updatingId === q.id}
                        className="text-xs text-copper-600 hover:underline"
                      >
                        {updatingId === q.id ? "جارِ الإرسال…" : "إرسال للعميل"}
                      </button>
                    )}
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

function CreateQuotationForm({
  customers,
  products,
  onCreated,
}: {
  customers: PartnerResponse[];
  products: ProductResponse[];
  onCreated: () => void;
}) {
  const [partnerId, setPartnerId] = useState("");
  const [lines, setLines] = useState<LineItemRequest[]>([
    { product_id: "", quantity: "1", unit_price: "0", tax_amount: "0" },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function updateLine(i: number, patch: Partial<LineItemRequest>) {
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  }

  function addLine() {
    setLines((prev) => [
      ...prev,
      { product_id: "", quantity: "1", unit_price: "0", tax_amount: "0" },
    ]);
  }

  function removeLine(i: number) {
    setLines((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createQuotation({ partner_id: partnerId, lines });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء عرض السعر");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <Banner kind="error">{error}</Banner>}
      {customers.length === 0 ? (
        <p className="text-sm text-ink-soft">أضف عميلاً واحداً على الأقل أولاً من صفحة العملاء.</p>
      ) : (
        <>
          <div className="w-72">
            <SelectField label="العميل" required value={partnerId} onChange={(e) => setPartnerId(e.target.value)}>
              <option value="">اختر عميلاً</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </SelectField>
          </div>

          <div className="space-y-2">
            {lines.map((line, i) => (
              <div key={i} className="grid grid-cols-12 items-end gap-2">
                <div className="col-span-5">
                  <SelectField
                    label="المنتج"
                    value={line.product_id}
                    onChange={(e) => updateLine(i, { product_id: e.target.value })}
                  >
                    <option value="">اختر منتجاً</option>
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.sku} — {p.name}
                      </option>
                    ))}
                  </SelectField>
                </div>
                <div className="col-span-2">
                  <Field
                    label="الكمية"
                    type="number"
                    step="0.0001"
                    value={String(line.quantity)}
                    onChange={(e) => updateLine(i, { quantity: e.target.value })}
                  />
                </div>
                <div className="col-span-2">
                  <Field
                    label="سعر الوحدة"
                    type="number"
                    step="0.0001"
                    value={String(line.unit_price)}
                    onChange={(e) => updateLine(i, { unit_price: e.target.value })}
                  />
                </div>
                <div className="col-span-2">
                  <Field
                    label="الضريبة"
                    type="number"
                    step="0.0001"
                    value={String(line.tax_amount ?? 0)}
                    onChange={(e) => updateLine(i, { tax_amount: e.target.value })}
                  />
                </div>
                <div className="col-span-1">
                  <button
                    type="button"
                    onClick={() => removeLine(i)}
                    disabled={lines.length <= 1}
                    className="text-xs text-brick-600 hover:underline disabled:text-line"
                  >
                    حذف
                  </button>
                </div>
              </div>
            ))}
          </div>

          <button type="button" onClick={addLine} className="text-sm text-copper-600 hover:underline">
            + إضافة بند
          </button>

          <div>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "جارِ الإنشاء…" : "إنشاء عرض السعر"}
            </Button>
          </div>
        </>
      )}
    </form>
  );
}
