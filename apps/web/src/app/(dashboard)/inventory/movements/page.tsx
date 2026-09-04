"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Banner, Button, Card, EmptyState, Field, PageHeader, SelectField } from "@/common/ui";
import { formatAmount } from "@/common/format";
import { ApiError } from "@/api-client/http";
import {
  createStockAdjustment,
  createStockTransfer,
  listStockMovements,
  recordMovement,
} from "@/features/inventory/api";
import { listWarehouses } from "@/features/tenancy/api";
import { listProducts } from "@/features/catalog/api";
import type { MovementType, ProductResponse, StockMovementResponse, WarehouseResponse } from "@/api-client/types";

const MOVEMENT_TYPE_LABELS: Record<MovementType, string> = {
  in: "وارد",
  out: "صادر",
  transfer: "تحويل",
  adjustment: "تسوية",
};

type FormMode = null | "movement" | "transfer" | "adjustment";

export default function StockMovementsPage() {
  const [movements, setMovements] = useState<StockMovementResponse[] | null>(null);
  const [warehouses, setWarehouses] = useState<WarehouseResponse[]>([]);
  const [products, setProducts] = useState<ProductResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [formMode, setFormMode] = useState<FormMode>(null);

  async function refresh() {
    try {
      const [movementsPage, warehousesData, productsPage] = await Promise.all([
        listStockMovements({}),
        listWarehouses(),
        listProducts({ page: 1 }),
      ]);
      setMovements(movementsPage.items);
      setWarehouses(warehousesData);
      setProducts(productsPage.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل حركات المخزون");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const productName = (id: string) => products.find((p) => p.id === id)?.name ?? id;
  const warehouseName = (id: string) => warehouses.find((w) => w.id === id)?.name ?? id;

  function handleDone() {
    setFormMode(null);
    refresh();
  }

  return (
    <div>
      <PageHeader
        title="حركات المخزون"
        description="سجل كل حركة على المخزون — استلام، صرف، تحويل، تسوية"
        action={
          <div className="flex gap-2">
            <Link href="/inventory/balances">
              <Button variant="secondary">الأرصدة</Button>
            </Link>
            <Button variant="secondary" onClick={() => setFormMode(formMode === "adjustment" ? null : "adjustment")}>
              تسوية
            </Button>
            <Button variant="secondary" onClick={() => setFormMode(formMode === "transfer" ? null : "transfer")}>
              تحويل بين مستودعات
            </Button>
            <Button onClick={() => setFormMode(formMode === "movement" ? null : "movement")}>حركة يدوية</Button>
          </div>
        }
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {formMode === "movement" && (
        <Card className="mb-6">
          <RecordMovementForm warehouses={warehouses} products={products} onDone={handleDone} />
        </Card>
      )}
      {formMode === "transfer" && (
        <Card className="mb-6">
          <TransferForm warehouses={warehouses} products={products} onDone={handleDone} />
        </Card>
      )}
      {formMode === "adjustment" && (
        <Card className="mb-6">
          <AdjustmentForm warehouses={warehouses} products={products} onDone={handleDone} />
        </Card>
      )}

      {movements === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : movements.length === 0 ? (
        <EmptyState title="لا توجد حركات بعد" description="سجّل أول حركة مخزون من الأعلى" />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-right text-ink-soft">
                <th className="px-4 py-3 font-normal">التاريخ</th>
                <th className="px-4 py-3 font-normal">المنتج</th>
                <th className="px-4 py-3 font-normal">المستودع</th>
                <th className="px-4 py-3 font-normal">النوع</th>
                <th className="px-4 py-3 font-normal">الكمية</th>
                <th className="px-4 py-3 font-normal">المصدر</th>
              </tr>
            </thead>
            <tbody>
              {movements.map((m) => (
                <tr key={m.id} className="border-b border-line last:border-0">
                  <td className="num px-4 py-2 text-ink-soft">{m.movement_date.slice(0, 10)}</td>
                  <td className="px-4 py-2">{productName(m.product_id)}</td>
                  <td className="px-4 py-2 text-ink-soft">{warehouseName(m.warehouse_id)}</td>
                  <td className="px-4 py-2 text-ink-soft">{MOVEMENT_TYPE_LABELS[m.movement_type]}</td>
                  <td className="num px-4 py-2">{formatAmount(m.quantity)}</td>
                  <td className="px-4 py-2 text-xs text-ink-soft">{m.source_type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

function ProductWarehouseSelects({
  warehouses,
  products,
  warehouseId,
  setWarehouseId,
  productId,
  setProductId,
  warehouseLabel = "المستودع",
}: {
  warehouses: WarehouseResponse[];
  products: ProductResponse[];
  warehouseId: string;
  setWarehouseId: (v: string) => void;
  productId: string;
  setProductId: (v: string) => void;
  warehouseLabel?: string;
}) {
  return (
    <>
      <SelectField label={warehouseLabel} required value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
        <option value="">اختر مستودعاً</option>
        {warehouses.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name}
          </option>
        ))}
      </SelectField>
      <SelectField label="المنتج" required value={productId} onChange={(e) => setProductId(e.target.value)}>
        <option value="">اختر منتجاً</option>
        {products.map((p) => (
          <option key={p.id} value={p.id}>
            {p.sku} — {p.name}
          </option>
        ))}
      </SelectField>
    </>
  );
}

function RecordMovementForm({
  warehouses,
  products,
  onDone,
}: {
  warehouses: WarehouseResponse[];
  products: ProductResponse[];
  onDone: () => void;
}) {
  const [warehouseId, setWarehouseId] = useState("");
  const [productId, setProductId] = useState("");
  const [movementType, setMovementType] = useState<MovementType>("in");
  const [quantity, setQuantity] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await recordMovement({
        warehouse_id: warehouseId,
        product_id: productId,
        movement_type: movementType,
        quantity,
        unit_cost: unitCost || undefined,
      });
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تسجيل الحركة");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {error && <div className="sm:col-span-3"><Banner kind="error">{error}</Banner></div>}
      <ProductWarehouseSelects
        warehouses={warehouses}
        products={products}
        warehouseId={warehouseId}
        setWarehouseId={setWarehouseId}
        productId={productId}
        setProductId={setProductId}
      />
      <SelectField label="نوع الحركة" value={movementType} onChange={(e) => setMovementType(e.target.value as MovementType)}>
        {Object.entries(MOVEMENT_TYPE_LABELS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </SelectField>
      <Field label="الكمية" type="number" step="0.0001" required value={quantity} onChange={(e) => setQuantity(e.target.value)} />
      <Field label="تكلفة الوحدة (اختياري)" type="number" step="0.0001" value={unitCost} onChange={(e) => setUnitCost(e.target.value)} />
      <div className="sm:col-span-3">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "جارِ التسجيل…" : "تسجيل الحركة"}
        </Button>
      </div>
    </form>
  );
}

function TransferForm({
  warehouses,
  products,
  onDone,
}: {
  warehouses: WarehouseResponse[];
  products: ProductResponse[];
  onDone: () => void;
}) {
  const [fromWarehouseId, setFromWarehouseId] = useState("");
  const [toWarehouseId, setToWarehouseId] = useState("");
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (fromWarehouseId && fromWarehouseId === toWarehouseId) {
      setError("لا يمكن التحويل من وإلى نفس المستودع");
      return;
    }
    setIsSubmitting(true);
    try {
      await createStockTransfer({
        from_warehouse_id: fromWarehouseId,
        to_warehouse_id: toWarehouseId,
        product_id: productId,
        quantity,
        notes: notes || undefined,
      });
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء التحويل");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {error && <div className="sm:col-span-3"><Banner kind="error">{error}</Banner></div>}
      <ProductWarehouseSelects
        warehouses={warehouses}
        products={products}
        warehouseId={fromWarehouseId}
        setWarehouseId={setFromWarehouseId}
        productId={productId}
        setProductId={setProductId}
        warehouseLabel="من مستودع"
      />
      <SelectField label="إلى مستودع" required value={toWarehouseId} onChange={(e) => setToWarehouseId(e.target.value)}>
        <option value="">اختر مستودعاً</option>
        {warehouses.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name}
          </option>
        ))}
      </SelectField>
      <Field label="الكمية" type="number" step="0.0001" required value={quantity} onChange={(e) => setQuantity(e.target.value)} />
      <Field label="ملاحظات (اختياري)" value={notes} onChange={(e) => setNotes(e.target.value)} />
      <div className="sm:col-span-3">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "جارِ التحويل…" : "تنفيذ التحويل"}
        </Button>
      </div>
    </form>
  );
}

function AdjustmentForm({
  warehouses,
  products,
  onDone,
}: {
  warehouses: WarehouseResponse[];
  products: ProductResponse[];
  onDone: () => void;
}) {
  const [warehouseId, setWarehouseId] = useState("");
  const [productId, setProductId] = useState("");
  const [quantityDelta, setQuantityDelta] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createStockAdjustment({
        warehouse_id: warehouseId,
        product_id: productId,
        quantity_delta: quantityDelta,
        reason,
      });
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء التسوية");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {error && <div className="sm:col-span-3"><Banner kind="error">{error}</Banner></div>}
      <ProductWarehouseSelects
        warehouses={warehouses}
        products={products}
        warehouseId={warehouseId}
        setWarehouseId={setWarehouseId}
        productId={productId}
        setProductId={setProductId}
      />
      <Field
        label="فرق الكمية (موجب = زيادة، سالب = نقص)"
        type="number"
        step="0.0001"
        required
        value={quantityDelta}
        onChange={(e) => setQuantityDelta(e.target.value)}
      />
      <div className="sm:col-span-3">
        <Field label="السبب" required value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>
      <div className="sm:col-span-3">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "جارِ التسوية…" : "تنفيذ التسوية"}
        </Button>
      </div>
    </form>
  );
}
