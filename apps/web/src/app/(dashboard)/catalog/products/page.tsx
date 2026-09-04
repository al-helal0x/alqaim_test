"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Banner, Button, Card, EmptyState, Field, PageHeader, SelectField } from "@/common/ui";
import { formatAmount } from "@/common/format";
import { ApiError } from "@/api-client/http";
import { createProduct, listCategories, listProducts, listUnitsOfMeasure } from "@/features/catalog/api";
import type { CategoryResponse, ProductResponse, ProductType, UomResponse } from "@/api-client/types";

const PRODUCT_TYPE_LABELS: Record<ProductType, string> = {
  product: "منتج",
  service: "خدمة",
};

export default function ProductsPage() {
  const [products, setProducts] = useState<ProductResponse[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [categories, setCategories] = useState<CategoryResponse[]>([]);
  const [units, setUnits] = useState<UomResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  async function refresh() {
    try {
      const [productsPage, categoriesData, unitsData] = await Promise.all([
        listProducts({ search: search || undefined, page }),
        listCategories(),
        listUnitsOfMeasure(),
      ]);
      setProducts(productsPage.items);
      setTotal(productsPage.total);
      setCategories(categoriesData);
      setUnits(unitsData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل المنتجات");
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  async function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    refresh();
  }

  const totalPages = Math.max(1, Math.ceil(total / 50));

  return (
    <div>
      <PageHeader
        title="المنتجات"
        description="كتالوج المنتجات والخدمات"
        action={
          <div className="flex gap-2">
            <Link href="/catalog/categories">
              <Button variant="secondary">الفئات</Button>
            </Link>
            <Link href="/catalog/units-of-measure">
              <Button variant="secondary">وحدات القياس</Button>
            </Link>
            <Button onClick={() => setShowForm((s) => !s)}>{showForm ? "إغلاق" : "منتج جديد"}</Button>
          </div>
        }
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {showForm && (
        <Card className="mb-6">
          {units.length === 0 ? (
            <p className="text-sm text-ink-soft">
              أضف وحدة قياس واحدة على الأقل أولاً من صفحة{" "}
              <Link href="/catalog/units-of-measure" className="text-copper-600 hover:underline">
                وحدات القياس
              </Link>
              .
            </p>
          ) : (
            <CreateProductForm
              categories={categories}
              units={units}
              onCreated={() => {
                setShowForm(false);
                refresh();
              }}
            />
          )}
        </Card>
      )}

      <form onSubmit={handleSearchSubmit} className="mb-4 flex gap-2">
        <div className="w-64">
          <Field
            label=""
            placeholder="بحث بالاسم أو الكود (SKU)"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Button type="submit" variant="secondary">
          بحث
        </Button>
      </form>

      {products === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : products.length === 0 ? (
        <EmptyState title="لا توجد منتجات بعد" description="أنشئ أول منتج من الأعلى" />
      ) : (
        <>
          <Card className="overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-right text-ink-soft">
                  <th className="px-4 py-3 font-normal">SKU</th>
                  <th className="px-4 py-3 font-normal">الاسم</th>
                  <th className="px-4 py-3 font-normal">النوع</th>
                  <th className="px-4 py-3 font-normal">سعر البيع</th>
                  <th className="px-4 py-3 font-normal">سعر الشراء</th>
                  <th className="px-4 py-3 font-normal">تتبّع المخزون</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => (
                  <tr key={p.id} className="border-b border-line last:border-0">
                    <td className="num px-4 py-2">{p.sku}</td>
                    <td className="px-4 py-2">{p.name}</td>
                    <td className="px-4 py-2 text-ink-soft">{PRODUCT_TYPE_LABELS[p.product_type]}</td>
                    <td className="num px-4 py-2 text-ledger-700">{formatAmount(p.sale_price)}</td>
                    <td className="num px-4 py-2 text-ink-soft">{formatAmount(p.purchase_price)}</td>
                    <td className="px-4 py-2 text-ink-soft">{p.track_inventory ? "نعم" : "لا"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <div className="mt-4 flex items-center justify-between text-sm text-ink-soft">
            <span>
              {total} منتج — صفحة {page} من {totalPages}
            </span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                السابق
              </Button>
              <Button variant="secondary" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                التالي
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function CreateProductForm({
  categories,
  units,
  onCreated,
}: {
  categories: CategoryResponse[];
  units: UomResponse[];
  onCreated: () => void;
}) {
  const [sku, setSku] = useState("");
  const [name, setName] = useState("");
  const [productType, setProductType] = useState<ProductType>("product");
  const [categoryId, setCategoryId] = useState("");
  const [baseUomId, setBaseUomId] = useState(units[0]?.id ?? "");
  const [salePrice, setSalePrice] = useState("");
  const [purchasePrice, setPurchasePrice] = useState("");
  const [trackInventory, setTrackInventory] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createProduct({
        sku,
        name,
        product_type: productType,
        category_id: categoryId || null,
        base_uom_id: baseUomId,
        sale_price: salePrice || "0",
        purchase_price: purchasePrice || "0",
        track_inventory: trackInventory,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء المنتج");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {error && <div className="sm:col-span-3"><Banner kind="error">{error}</Banner></div>}
      <Field label="SKU" required value={sku} onChange={(e) => setSku(e.target.value)} />
      <Field label="الاسم" required value={name} onChange={(e) => setName(e.target.value)} />
      <SelectField label="النوع" value={productType} onChange={(e) => setProductType(e.target.value as ProductType)}>
        <option value="product">منتج</option>
        <option value="service">خدمة</option>
      </SelectField>
      <SelectField label="وحدة القياس الأساسية" required value={baseUomId} onChange={(e) => setBaseUomId(e.target.value)}>
        {units.map((u) => (
          <option key={u.id} value={u.id}>
            {u.name}
          </option>
        ))}
      </SelectField>
      <SelectField label="الفئة (اختياري)" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
        <option value="">بلا فئة</option>
        {categories.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </SelectField>
      <Field label="سعر البيع" type="number" step="0.01" value={salePrice} onChange={(e) => setSalePrice(e.target.value)} />
      <Field label="سعر الشراء" type="number" step="0.01" value={purchasePrice} onChange={(e) => setPurchasePrice(e.target.value)} />
      <label className="flex items-center gap-2 self-end pb-2 text-sm text-ink-soft">
        <input type="checkbox" checked={trackInventory} onChange={(e) => setTrackInventory(e.target.checked)} />
        تتبّع المخزون
      </label>
      <div className="sm:col-span-3">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "جارِ الإنشاء…" : "إنشاء المنتج"}
        </Button>
      </div>
    </form>
  );
}
