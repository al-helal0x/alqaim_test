"use client";

import { useEffect, useState } from "react";
import { Banner, Button, Card, EmptyState, Field, PageHeader, SelectField } from "@/common/ui";
import { formatAmount } from "@/common/format";
import { ApiError } from "@/api-client/http";
import {
  cancelPurchaseOrder,
  confirmPurchaseOrder,
  createPurchaseOrder,
  listPurchaseOrders,
  receivePurchaseOrder,
  type PurchaseOrderLineInput,
} from "@/features/purchasing/api";
import { listPartners } from "@/features/partners/api";
import { listProducts } from "@/features/catalog/api";
import { listBranches, listWarehouses } from "@/features/tenancy/api";
import type { BranchResponse, PartnerResponse, ProductResponse, PurchaseOrderResponse, WarehouseResponse } from "@/api-client/types";

const STATUS_LABELS: Record<string, string> = {
  draft: "مسودة",
  confirmed: "مؤكَّد",
  received: "مستلَم",
  cancelled: "ملغى",
};

export default function PurchaseOrdersPage() {
  const [orders, setOrders] = useState<PurchaseOrderResponse[] | null>(null);
  const [suppliers, setSuppliers] = useState<PartnerResponse[]>([]);
  const [products, setProducts] = useState<ProductResponse[]>([]);
  const [branches, setBranches] = useState<BranchResponse[]>([]);
  const [warehouses, setWarehouses] = useState<WarehouseResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [receivingId, setReceivingId] = useState<string | null>(null);
  const [receiveWarehouseId, setReceiveWarehouseId] = useState("");

  async function refresh() {
    try {
      const [ordersData, suppliersPage, productsPage, branchesData, warehousesData] = await Promise.all([
        listPurchaseOrders(),
        listPartners({ partnerType: "supplier" }),
        listProducts({ page: 1 }),
        listBranches(),
        listWarehouses(),
      ]);
      setOrders(ordersData);
      setSuppliers(suppliersPage.items);
      setProducts(productsPage.items);
      setBranches(branchesData);
      setWarehouses(warehousesData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل أوامر الشراء");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleConfirm(id: string) {
    setBusyId(id);
    try {
      await confirmPurchaseOrder(id);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تأكيد الأمر");
    } finally {
      setBusyId(null);
    }
  }

  async function handleCancel(id: string) {
    setBusyId(id);
    try {
      await cancelPurchaseOrder(id);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إلغاء الأمر");
    } finally {
      setBusyId(null);
    }
  }

  async function handleReceive(id: string) {
    if (!receiveWarehouseId) {
      setError("اختر مستودعاً للاستلام أولاً");
      return;
    }
    setBusyId(id);
    try {
      await receivePurchaseOrder(id, receiveWarehouseId);
      setReceivingId(null);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر استلام الأمر");
    } finally {
      setBusyId(null);
    }
  }

  const partnerName = (id: string) => suppliers.find((s) => s.id === id)?.name ?? id;

  return (
    <div>
      <PageHeader
        title="أوامر الشراء"
        description="أوامر شراء من الموردين — الاستلام يزيد المخزون تلقائياً"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "إغلاق" : "أمر شراء جديد"}</Button>}
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {showForm && (
        <Card className="mb-6">
          <CreatePurchaseOrderForm
            suppliers={suppliers}
            products={products}
            branches={branches}
            onCreated={() => {
              setShowForm(false);
              refresh();
            }}
          />
        </Card>
      )}

      {orders === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : orders.length === 0 ? (
        <EmptyState title="لا توجد أوامر شراء بعد" description="أنشئ أول أمر شراء من الأعلى" />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-right text-ink-soft">
                <th className="px-4 py-3 font-normal">الرقم</th>
                <th className="px-4 py-3 font-normal">المورّد</th>
                <th className="px-4 py-3 font-normal">الحالة</th>
                <th className="px-4 py-3 font-normal">الإجمالي</th>
                <th className="px-4 py-3 font-normal"></th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id} className="border-b border-line last:border-0">
                  <td className="num px-4 py-2">{o.order_number}</td>
                  <td className="px-4 py-2">{partnerName(o.supplier_id)}</td>
                  <td className="px-4 py-2 text-ink-soft">{STATUS_LABELS[o.status] ?? o.status}</td>
                  <td className="num px-4 py-2">{formatAmount(o.total_amount)}</td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-3">
                      {o.status === "draft" && (
                        <>
                          <button onClick={() => handleConfirm(o.id)} disabled={busyId === o.id} className="text-xs text-copper-600 hover:underline">
                            تأكيد
                          </button>
                          <button onClick={() => handleCancel(o.id)} disabled={busyId === o.id} className="text-xs text-brick-600 hover:underline">
                            إلغاء
                          </button>
                        </>
                      )}
                      {o.status === "confirmed" && receivingId !== o.id && (
                        <button onClick={() => setReceivingId(o.id)} className="text-xs text-copper-600 hover:underline">
                          استلام
                        </button>
                      )}
                      {o.status === "confirmed" && receivingId === o.id && (
                        <div className="flex items-center gap-2">
                          <select
                            value={receiveWarehouseId}
                            onChange={(e) => setReceiveWarehouseId(e.target.value)}
                            className="rounded border border-line px-2 py-1 text-xs"
                          >
                            <option value="">مستودع الاستلام</option>
                            {warehouses.map((w) => (
                              <option key={w.id} value={w.id}>
                                {w.name}
                              </option>
                            ))}
                          </select>
                          <button onClick={() => handleReceive(o.id)} disabled={busyId === o.id} className="text-xs text-ledger-700 hover:underline">
                            {busyId === o.id ? "جارِ الاستلام…" : "تأكيد الاستلام"}
                          </button>
                        </div>
                      )}
                    </div>
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

function CreatePurchaseOrderForm({
  suppliers,
  products,
  branches,
  onCreated,
}: {
  suppliers: PartnerResponse[];
  products: ProductResponse[];
  branches: BranchResponse[];
  onCreated: () => void;
}) {
  const [supplierId, setSupplierId] = useState("");
  const [branchId, setBranchId] = useState("");
  const [lines, setLines] = useState<PurchaseOrderLineInput[]>([
    { product_id: "", description: "", quantity: "1", unit_price: "0" },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function updateLine(i: number, patch: Partial<PurchaseOrderLineInput>) {
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  }

  function addLine() {
    setLines((prev) => [...prev, { product_id: "", description: "", quantity: "1", unit_price: "0" }]);
  }

  function removeLine(i: number) {
    setLines((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createPurchaseOrder({ branch_id: branchId, supplier_id: supplierId, lines });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء أمر الشراء");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (suppliers.length === 0 || branches.length === 0) {
    return <p className="text-sm text-ink-soft">تحتاج مورّداً واحداً وفرعاً واحداً على الأقل قبل إنشاء أمر شراء.</p>;
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <Banner kind="error">{error}</Banner>}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <SelectField label="المورّد" required value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
          <option value="">اختر مورّداً</option>
          {suppliers.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </SelectField>
        <SelectField label="الفرع" required value={branchId} onChange={(e) => setBranchId(e.target.value)}>
          <option value="">اختر فرعاً</option>
          {branches.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </SelectField>
      </div>

      <div className="space-y-2">
        {lines.map((line, i) => (
          <div key={i} className="grid grid-cols-12 items-end gap-2">
            <div className="col-span-3">
              <SelectField
                label="المنتج"
                value={line.product_id}
                onChange={(e) => {
                  const product = products.find((p) => p.id === e.target.value);
                  updateLine(i, { product_id: e.target.value, description: product?.name ?? line.description });
                }}
              >
                <option value="">اختر منتجاً</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.sku} — {p.name}
                  </option>
                ))}
              </SelectField>
            </div>
            <div className="col-span-3">
              <Field label="الوصف" required value={line.description} onChange={(e) => updateLine(i, { description: e.target.value })} />
            </div>
            <div className="col-span-2">
              <Field label="الكمية" type="number" step="0.0001" value={line.quantity} onChange={(e) => updateLine(i, { quantity: e.target.value })} />
            </div>
            <div className="col-span-3">
              <Field label="سعر الوحدة" type="number" step="0.0001" value={line.unit_price} onChange={(e) => updateLine(i, { unit_price: e.target.value })} />
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
          {isSubmitting ? "جارِ الإنشاء…" : "إنشاء أمر الشراء"}
        </Button>
      </div>
    </form>
  );
}
