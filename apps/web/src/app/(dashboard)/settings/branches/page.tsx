"use client";

import { useEffect, useState } from "react";
import { Banner, Button, Card, EmptyState, Field, PageHeader } from "@/common/ui";
import { ApiError } from "@/api-client/http";
import { createBranch, createWarehouse, listBranches, listWarehouses } from "@/features/tenancy/api";
import type { BranchResponse, WarehouseResponse } from "@/api-client/types";

export default function BranchesPage() {
  const [branches, setBranches] = useState<BranchResponse[] | null>(null);
  const [warehouses, setWarehouses] = useState<WarehouseResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showBranchForm, setShowBranchForm] = useState(false);
  const [warehouseFormFor, setWarehouseFormFor] = useState<string | null>(null);

  async function refresh() {
    try {
      // استدعاء واحد لكل المستودعات (بلا branch_id) بدل استدعاء منفصل لكل
      // فرع — تُجمَّع محلياً حسب branch_id أدناه. يحل QA_FINDINGS #4: هذه
      // الصفحة كانت لا تستدعي listWarehouses() إطلاقاً رغم أن الـbackend
      // والدالة كانا جاهزَين ومُستخدَمَين بنجاح من صفحات أخرى.
      const [branchList, warehouseList] = await Promise.all([listBranches(), listWarehouses()]);
      setBranches(branchList);
      setWarehouses(warehouseList);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل الفروع");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div>
      <PageHeader
        title="الفروع والمستودعات"
        description="الهيكل التنظيمي للشركة"
        action={<Button onClick={() => setShowBranchForm((s) => !s)}>{showBranchForm ? "إغلاق" : "فرع جديد"}</Button>}
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {showBranchForm && (
        <Card className="mb-6">
          <CreateBranchForm
            onCreated={() => {
              setShowBranchForm(false);
              refresh();
            }}
          />
        </Card>
      )}

      {branches === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : branches.length === 0 ? (
        <EmptyState title="لا توجد فروع بعد" description="أنشئ الفرع الأول لشركتك" />
      ) : (
        <div className="space-y-4">
          {branches.map((branch) => {
            const branchWarehouses = (warehouses ?? []).filter((w) => w.branch_id === branch.id);
            return (
              <Card key={branch.id}>
                <div className="flex items-center justify-between">
                  <p className="font-display text-lg text-ink">{branch.name}</p>
                  <button
                    onClick={() => setWarehouseFormFor(warehouseFormFor === branch.id ? null : branch.id)}
                    className="text-sm text-copper-600 hover:underline"
                  >
                    {warehouseFormFor === branch.id ? "إغلاق" : "+ مستودع"}
                  </button>
                </div>

                {warehouses !== null && (
                  <div className="mt-3">
                    {branchWarehouses.length === 0 ? (
                      <p className="text-sm text-ink-soft">لا توجد مستودعات في هذا الفرع بعد</p>
                    ) : (
                      <ul className="space-y-1">
                        {branchWarehouses.map((w) => (
                          <li
                            key={w.id}
                            className="flex items-center justify-between rounded border border-line bg-paper px-3 py-1.5 text-sm text-ink"
                          >
                            <span>{w.name}</span>
                            {!w.is_active && <span className="text-xs text-ink-soft">غير نشِط</span>}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                {warehouseFormFor === branch.id && (
                  <div className="mt-4 border-t border-line pt-4">
                    <CreateWarehouseForm
                      branchId={branch.id}
                      onCreated={() => {
                        setWarehouseFormFor(null);
                        refresh();
                      }}
                    />
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function CreateBranchForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createBranch(name);
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء الفرع");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-4">
      {error && <div className="w-full"><Banner kind="error">{error}</Banner></div>}
      <div className="w-64">
        <Field label="اسم الفرع" required value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "جارِ الإنشاء…" : "إنشاء"}
      </Button>
    </form>
  );
}

function CreateWarehouseForm({ branchId, onCreated }: { branchId: string; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createWarehouse(branchId, name);
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء المستودع");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-4">
      {error && <div className="w-full"><Banner kind="error">{error}</Banner></div>}
      <div className="w-64">
        <Field label="اسم المستودع" required value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "جارِ الإنشاء…" : "إنشاء"}
      </Button>
    </form>
  );
}
