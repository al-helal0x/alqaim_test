"use client";

import { useEffect, useState } from "react";
import { Banner, Button, Card, EmptyState, Field, PageHeader, SelectField } from "@/common/ui";
import { ApiError } from "@/api-client/http";
import { createCategory, listCategories } from "@/features/catalog/api";
import type { CategoryResponse } from "@/api-client/types";

export default function CategoriesPage() {
  const [categories, setCategories] = useState<CategoryResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  async function refresh() {
    try {
      setCategories(await listCategories());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل الفئات");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div>
      <PageHeader
        title="فئات المنتجات"
        description="تصنيف هرمي للمنتجات"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "إغلاق" : "فئة جديدة"}</Button>}
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {showForm && categories && (
        <Card className="mb-6">
          <CreateCategoryForm
            categories={categories}
            onCreated={() => {
              setShowForm(false);
              refresh();
            }}
          />
        </Card>
      )}

      {categories === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : categories.length === 0 ? (
        <EmptyState title="لا توجد فئات بعد" description="أنشئ أول فئة لتنظيم منتجاتك" />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-right text-ink-soft">
                <th className="px-4 py-3 font-normal">الاسم</th>
                <th className="px-4 py-3 font-normal">الفئة الأب</th>
              </tr>
            </thead>
            <tbody>
              {categories.map((c) => (
                <tr key={c.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-2">{c.name}</td>
                  <td className="px-4 py-2 text-ink-soft">
                    {categories.find((p) => p.id === c.parent_id)?.name ?? "—"}
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

function CreateCategoryForm({
  categories,
  onCreated,
}: {
  categories: CategoryResponse[];
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [parentId, setParentId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createCategory({ name, parent_id: parentId || undefined });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء الفئة");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {error && <div className="sm:col-span-3"><Banner kind="error">{error}</Banner></div>}
      <Field label="الاسم" required value={name} onChange={(e) => setName(e.target.value)} />
      <SelectField label="الفئة الأب (اختياري)" value={parentId} onChange={(e) => setParentId(e.target.value)}>
        <option value="">بلا فئة أب</option>
        {categories.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </SelectField>
      <div className="sm:col-span-3">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "جارِ الإنشاء…" : "إنشاء"}
        </Button>
      </div>
    </form>
  );
}
