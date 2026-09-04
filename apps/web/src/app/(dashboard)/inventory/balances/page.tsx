"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Banner, Button, Card, EmptyState, PageHeader, SelectField } from "@/common/ui";
import { formatAmount } from "@/common/format";
import { ApiError } from "@/api-client/http";
import { listStockBalances } from "@/features/inventory/api";
import { listWarehouses } from "@/features/tenancy/api";
import { listProducts } from "@/features/catalog/api";
import type { ProductResponse, StockBalanceResponse, WarehouseResponse } from "@/api-client/types";

export default function StockBalancesPage() {
  const [balances, setBalances] = useState<StockBalanceResponse[] | null>(null);
  const [warehouses, setWarehouses] = useState<WarehouseResponse[]>([]);
  const [products, setProducts] = useState<ProductResponse[]>([]);
  const [warehouseId, setWarehouseId] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function refresh(currentWarehouseId: string) {
    try {
      const [balancesPage, warehousesData, productsPage] = await Promise.all([
        listStockBalances({ warehouseId: currentWarehouseId || undefined }),
        listWarehouses(),
        listProducts({ page: 1 }),
      ]);
      setBalances(balancesPage.items);
      setWarehouses(warehousesData);
      setProducts(productsPage.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل أرصدة المخزون");
    }
  }

  useEffect(() => {
    refresh(warehouseId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [warehouseId]);

  const productName = (id: string) => products.find((p) => p.id === id)?.name ?? id;
  const warehouseName = (id: string) => warehouses.find((w) => w.id === id)?.name ?? id;

  return (
    <div>
      <PageHeader
        title="أرصدة المخزون"
        description="الكمية المتوفرة لكل منتج في كل مستودع"
        action={
          <div className="flex gap-2">
            <Link href="/inventory/movements">
              <Button variant="secondary">الحركات والتسويات</Button>
            </Link>
          </div>
        }
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      <div className="mb-4 w-64">
        <SelectField label="تصفية حسب المستودع" value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
          <option value="">كل المستودعات</option>
          {warehouses.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </SelectField>
      </div>

      {balances === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : warehouses.length === 0 ? (
        <EmptyState title="لا توجد مستودعات بعد" description="أنشئ مستودعاً من صفحة الفروع والمستودعات" />
      ) : balances.length === 0 ? (
        <EmptyState title="لا توجد أرصدة بعد" description="سجّل حركة مخزون أو استلم أمر شراء لتظهر الأرصدة هنا" />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-right text-ink-soft">
                <th className="px-4 py-3 font-normal">المنتج</th>
                <th className="px-4 py-3 font-normal">المستودع</th>
                <th className="px-4 py-3 font-normal">الكمية</th>
              </tr>
            </thead>
            <tbody>
              {balances.map((b) => (
                <tr key={`${b.warehouse_id}-${b.product_id}`} className="border-b border-line last:border-0">
                  <td className="px-4 py-2">{productName(b.product_id)}</td>
                  <td className="px-4 py-2 text-ink-soft">{warehouseName(b.warehouse_id)}</td>
                  <td className="num px-4 py-2">{formatAmount(b.quantity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
