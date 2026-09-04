"use client";

import { useEffect, useState } from "react";
import { Banner, Button, Card, EmptyState, Field, PageHeader, SelectField } from "@/common/ui";
import { formatAmount } from "@/common/format";
import { ApiError } from "@/api-client/http";
import { createSalesInvoice, listSalesInvoices, postSalesInvoice } from "@/features/sales/api";
import { listPartners } from "@/features/partners/api";
import { listProducts } from "@/features/catalog/api";
import { listWarehouses } from "@/features/tenancy/api";
import type {
  LineItemRequest,
  PartnerResponse,
  ProductResponse,
  SalesInvoiceResponse,
  WarehouseResponse,
} from "@/api-client/types";

const STATUS_LABELS: Record<string, string> = {
  draft: "مسودة",
  posted: "مُرحَّلة",
  paid: "مسدَّدة",
  cancelled: "ملغاة",
};

export default function SalesInvoicesPage() {
  const [invoices, setInvoices] = useState<SalesInvoiceResponse[] | null>(null);
  const [customers, setCustomers] = useState<PartnerResponse[]>([]);
  const [products, setProducts] = useState<ProductResponse[]>([]);
  const [warehouses, setWarehouses] = useState<WarehouseResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [postingId, setPostingId] = useState<string | null>(null);

  async function refresh() {
    try {
      const [invoicesPage, customersPage, productsPage, warehousesData] = await Promise.all([
        listSalesInvoices(),
        listPartners({ partnerType: "customer" }),
        listProducts({ page: 1 }),
        listWarehouses(),
      ]);
      setInvoices(invoicesPage.items);
      setCustomers(customersPage.items);
      setProducts(productsPage.items);
      setWarehouses(warehousesData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل فواتير البيع");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handlePost(id: string) {
    setPostingId(id);
    try {
      await postSalesInvoice(id);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر ترحيل الفاتورة");
    } finally {
      setPostingId(null);
    }
  }

  const partnerName = (id: string) => customers.find((c) => c.id === id)?.name ?? id;

  return (
    <div>
      <PageHeader
        title="فواتير البيع"
        description="ترحيل الفاتورة يخصم المخزون ويُنشئ قيداً محاسبياً تلقائياً"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "إغلاق" : "فاتورة جديدة"}</Button>}
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {showForm && (
        <Card className="mb-6">
          <CreateInvoiceForm
            customers={customers}
            products={products}
            warehouses={warehouses}
            onCreated={() => {
              setShowForm(false);
              refresh();
            }}
          />
        </Card>
      )}

      {invoices === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : invoices.length === 0 ? (
        <EmptyState title="لا توجد فواتير بعد" description="أنشئ أول فاتورة بيع من الأعلى" />
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
              {invoices.map((inv) => (
                <tr key={inv.id} className="border-b border-line last:border-0">
                  <td className="num px-4 py-2">{inv.invoice_number}</td>
                  <td className="px-4 py-2">{partnerName(inv.partner_id)}</td>
                  <td className="px-4 py-2 text-ink-soft">{STATUS_LABELS[inv.status] ?? inv.status}</td>
                  <td className="num px-4 py-2">{formatAmount(inv.total_amount)}</td>
                  <td className="px-4 py-2">
                    {inv.status === "draft" && (
                      <button
                        onClick={() => handlePost(inv.id)}
                        disabled={postingId === inv.id}
                        className="text-xs text-copper-600 hover:underline"
                      >
                        {postingId === inv.id ? "جارِ الترحيل…" : "ترحيل"}
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

function CreateInvoiceForm({
  customers,
  products,
  warehouses,
  onCreated,
}: {
  customers: PartnerResponse[];
  products: ProductResponse[];
  warehouses: WarehouseResponse[];
  onCreated: () => void;
}) {
  const [partnerId, setPartnerId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [discountAmount, setDiscountAmount] = useState("0");
  const [lines, setLines] = useState<LineItemRequest[]>([
    { product_id: "", quantity: "1", unit_price: "0", tax_amount: "0" },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function updateLine(i: number, patch: Partial<LineItemRequest>) {
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  }

  function addLine() {
    setLines((prev) => [...prev, { product_id: "", quantity: "1", unit_price: "0", tax_amount: "0" }]);
  }

  function removeLine(i: number) {
    setLines((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createSalesInvoice({
        partner_id: partnerId,
        warehouse_id: warehouseId,
        discount_amount: discountAmount || "0",
        lines,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء الفاتورة");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (customers.length === 0 || warehouses.length === 0) {
    return (
      <p className="text-sm text-ink-soft">
        تحتاج عميلاً واحداً على الأقل ومستودعاً واحداً على الأقل قبل إنشاء فاتورة.
      </p>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <Banner kind="error">{error}</Banner>}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <SelectField label="العميل" required value={partnerId} onChange={(e) => setPartnerId(e.target.value)}>
          <option value="">اختر عميلاً</option>
          {customers.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </SelectField>
        <SelectField label="المستودع" required value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
          <option value="">اختر مستودعاً</option>
          {warehouses.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </SelectField>
        <Field label="خصم إضافي" type="number" step="0.0001" value={discountAmount} onChange={(e) => setDiscountAmount(e.target.value)} />
      </div>

      <div className="space-y-2">
        {lines.map((line, i) => (
          <div key={i} className="grid grid-cols-12 items-end gap-2">
            <div className="col-span-5">
              <SelectField label="المنتج" value={line.product_id} onChange={(e) => updateLine(i, { product_id: e.target.value })}>
                <option value="">اختر منتجاً</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.sku} — {p.name}
                  </option>
                ))}
              </SelectField>
            </div>
            <div className="col-span-2">
              <Field label="الكمية" type="number" step="0.0001" value={String(line.quantity)} onChange={(e) => updateLine(i, { quantity: e.target.value })} />
            </div>
            <div className="col-span-2">
              <Field label="سعر الوحدة" type="number" step="0.0001" value={String(line.unit_price)} onChange={(e) => updateLine(i, { unit_price: e.target.value })} />
            </div>
            <div className="col-span-2">
              <Field label="الضريبة" type="number" step="0.0001" value={String(line.tax_amount ?? 0)} onChange={(e) => updateLine(i, { tax_amount: e.target.value })} />
            </div>
            <div className="col-span-1">
              <button type="button" onClick={() => removeLine(i)} disabled={lines.length <= 1} className="text-xs text-brick-600 hover:underline disabled:text-line">
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
          {isSubmitting ? "جارِ الإنشاء…" : "إنشاء الفاتورة (مسودة)"}
        </Button>
      </div>
    </form>
  );
}
