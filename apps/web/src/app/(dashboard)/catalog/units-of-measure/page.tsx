"use client";

import { useEffect, useState } from "react";
import { Banner, Button, Card, EmptyState, Field, PageHeader } from "@/common/ui";
import { ApiError } from "@/api-client/http";
import { createUnitOfMeasure, listUnitsOfMeasure } from "@/features/catalog/api";
import type { UomResponse } from "@/api-client/types";

export default function UnitsOfMeasurePage() {
  const [units, setUnits] = useState<UomResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  async function refresh() {
    try {
      setUnits(await listUnitsOfMeasure());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل وحدات القياس");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div>
      <PageHeader
        title="وحدات القياس"
        description="الوحدات المستخدَمة لقياس المنتجات (قطعة، كغم، لتر...)"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "إغلاق" : "وحدة جديدة"}</Button>}
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {showForm && (
        <Card className="mb-6">
          <CreateUomForm
            onCreated={() => {
              setShowForm(false);
              refresh();
            }}
          />
        </Card>
      )}

      {units === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : units.length === 0 ? (
        <EmptyState title="لا توجد وحدات قياس بعد" description="أضف وحدة (مثل: قطعة) قبل إنشاء أول منتج" />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-right text-ink-soft">
                <th className="px-4 py-3 font-normal">الكود</th>
                <th className="px-4 py-3 font-normal">الاسم</th>
              </tr>
            </thead>
            <tbody>
              {units.map((u) => (
                <tr key={u.id} className="border-b border-line last:border-0">
                  <td className="num px-4 py-2">{u.code}</td>
                  <td className="px-4 py-2">{u.name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

function CreateUomForm({ onCreated }: { onCreated: () => void }) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createUnitOfMeasure({ code, name });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء الوحدة");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {error && <div className="sm:col-span-3"><Banner kind="error">{error}</Banner></div>}
      <Field label="الكود (مثال: PCS)" required value={code} onChange={(e) => setCode(e.target.value)} />
      <Field label="الاسم (مثال: قطعة)" required value={name} onChange={(e) => setName(e.target.value)} />
      <div className="sm:col-span-3">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "جارِ الإنشاء…" : "إنشاء"}
        </Button>
      </div>
    </form>
  );
}
