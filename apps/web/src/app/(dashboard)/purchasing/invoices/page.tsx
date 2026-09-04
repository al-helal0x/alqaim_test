"use client";

import { useEffect, useState } from "react";
import { Banner, Button, Card, EmptyState, PageHeader, SelectField } from "@/common/ui";
import { formatAmount } from "@/common/format";
import { ApiError } from "@/api-client/http";
import {
  createPurchaseInvoiceFromOrder,
  listPurchaseInvoices,
  listPurchaseOrders,
  postPurchaseInvoice,
} from "@/features/purchasing/api";
import { listPartners } from "@/features/partners/api";
import type { PartnerResponse, PurchaseInvoiceResponse, PurchaseOrderResponse } from "@/api-client/types";

const STATUS_LABELS: Record<string, string> = {
  draft: "مسودة",
  posted: "مُرحَّلة",
  paid: "مسدَّدة",
  partially_paid: "مسدَّدة جزئياً",
  cancelled: "ملغاة",
};

export default function PurchaseInvoicesPage() {
  const [invoices, setInvoices] = useState<PurchaseInvoiceResponse[] | null>(null);
  const [receivedOrders, setReceivedOrders] = useState<PurchaseOrderResponse[]>([]);
  const [suppliers, setSuppliers] = useState<PartnerResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedOrderId, setSelectedOrderId] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  async function refresh() {
    try {
      const [invoicesData, ordersData, suppliersPage] = await Promise.all([
        listPurchaseInvoices(),
        listPurchaseOrders(),
        listPartners({ partnerType: "supplier" }),
      ]);
      setInvoices(invoicesData);
      setReceivedOrders(ordersData.filter((o) => o.status === "received"));
      setSuppliers(suppliersPage.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل فواتير الشراء");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreateFromOrder(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedOrderId) return;
    setError(null);
    setIsCreating(true);
    try {
      await createPurchaseInvoiceFromOrder(selectedOrderId);
      setSelectedOrderId("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء الفاتورة");
    } finally {
      setIsCreating(false);
    }
  }

  async function handlePost(id: string) {
    setBusyId(id);
    try {
      await postPurchaseInvoice(id);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر ترحيل الفاتورة");
    } finally {
      setBusyId(null);
    }
  }

  const partnerName = (id: string) => suppliers.find((s) => s.id === id)?.name ?? id;

  return (
    <div>
      <PageHeader
        title="فواتير الشراء"
        description="ترحيل الفاتورة يُنشئ قيداً محاسبياً تلقائياً عبر IAccountingPort"
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      <Card className="mb-6">
        <p className="mb-3 font-display text-lg text-ink">إنشاء فاتورة من أمر شراء مستلَم</p>
        {receivedOrders.length === 0 ? (
          <p className="text-sm text-ink-soft">لا توجد أوامر شراء بحالة &quot;مستلَم&quot; حالياً.</p>
        ) : (
          <form onSubmit={handleCreateFromOrder} className="flex flex-wrap items-end gap-4">
            <div className="w-72">
              <SelectField label="أمر الشراء" value={selectedOrderId} onChange={(e) => setSelectedOrderId(e.target.value)}>
                <option value="">اختر أمر شراء مستلَماً</option>
                {receivedOrders.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.order_number} — {partnerName(o.supplier_id)}
                  </option>
                ))}
              </SelectField>
            </div>
            <Button type="submit" disabled={isCreating || !selectedOrderId}>
              {isCreating ? "جارِ الإنشاء…" : "إنشاء الفاتورة"}
            </Button>
          </form>
        )}
      </Card>

      {invoices === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : invoices.length === 0 ? (
        <EmptyState title="لا توجد فواتير شراء بعد" description="أنشئ فاتورة من أمر شراء مستلَم أعلاه" />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-right text-ink-soft">
                <th className="px-4 py-3 font-normal">الرقم</th>
                <th className="px-4 py-3 font-normal">المورّد</th>
                <th className="px-4 py-3 font-normal">الحالة</th>
                <th className="px-4 py-3 font-normal">الإجمالي</th>
                <th className="px-4 py-3 font-normal">المسدَّد</th>
                <th className="px-4 py-3 font-normal"></th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id} className="border-b border-line last:border-0">
                  <td className="num px-4 py-2">{inv.invoice_number}</td>
                  <td className="px-4 py-2">{partnerName(inv.supplier_id)}</td>
                  <td className="px-4 py-2 text-ink-soft">{STATUS_LABELS[inv.status] ?? inv.status}</td>
                  <td className="num px-4 py-2">{formatAmount(inv.total_amount)}</td>
                  <td className="num px-4 py-2 text-ink-soft">{formatAmount(inv.paid_amount)}</td>
                  <td className="px-4 py-2">
                    {inv.status === "draft" && (
                      <button onClick={() => handlePost(inv.id)} disabled={busyId === inv.id} className="text-xs text-copper-600 hover:underline">
                        {busyId === inv.id ? "جارِ الترحيل…" : "ترحيل"}
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
