"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/common/require-auth";
import { Banner, Button, Field } from "@/common/ui";
import { ApiError } from "@/api-client/http";
import { createBranch, createWarehouse } from "@/features/tenancy/api";
import { seedDefaultChartOfAccounts } from "@/features/accounting/api";
import { t } from "@alqaim/i18n";

type Step = "branch" | "warehouse" | "accounts" | "done";

export default function OnboardingPage() {
  return (
    <RequireAuth>
      <OnboardingWizard />
    </RequireAuth>
  );
}

function OnboardingWizard() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("branch");
  const [branchId, setBranchId] = useState<string | null>(null);
  const [branchName, setBranchName] = useState("الفرع الرئيسي");
  const [warehouseName, setWarehouseName] = useState("المستودع الرئيسي");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const steps: { key: Step; label: string }[] = [
    { key: "branch", label: "الفرع" },
    { key: "warehouse", label: "المستودع" },
    { key: "accounts", label: "شجرة الحسابات" },
  ];

  async function handleCreateBranch() {
    setError(null);
    setIsSubmitting(true);
    try {
      const branch = await createBranch(branchName);
      setBranchId(branch.id);
      setStep("warehouse");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء الفرع");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateWarehouse() {
    if (!branchId) return;
    setError(null);
    setIsSubmitting(true);
    try {
      await createWarehouse(branchId, warehouseName);
      setStep("accounts");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر إنشاء المستودع");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSeedAccounts() {
    setError(null);
    setIsSubmitting(true);
    try {
      await seedDefaultChartOfAccounts();
      setStep("done");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر زرع شجرة الحسابات");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-12">
      <span className="font-display text-2xl text-ink">{t("brand.name")}</span>
      <h1 className="mt-2 font-display text-xl text-ink">إعداد الشركة الأولي</h1>

      <ol className="mt-6 flex gap-2 text-xs text-ink-soft">
        {steps.map((s, i) => (
          <li
            key={s.key}
            className={`flex-1 border-t-2 pt-2 ${
              step === s.key || steps.findIndex((x) => x.key === step) > i
                ? "border-copper-500 text-ink"
                : "border-line"
            }`}
          >
            {i + 1}. {s.label}
          </li>
        ))}
      </ol>

      <div className="mt-8 space-y-4">
        {error && <Banner kind="error">{error}</Banner>}

        {step === "branch" && (
          <>
            <Field label="اسم الفرع" value={branchName} onChange={(e) => setBranchName(e.target.value)} />
            <Button disabled={isSubmitting} onClick={handleCreateBranch}>
              {isSubmitting ? "جارِ الإنشاء…" : "متابعة"}
            </Button>
          </>
        )}

        {step === "warehouse" && (
          <>
            <Field
              label="اسم المستودع"
              value={warehouseName}
              onChange={(e) => setWarehouseName(e.target.value)}
            />
            <Button disabled={isSubmitting} onClick={handleCreateWarehouse}>
              {isSubmitting ? "جارِ الإنشاء…" : "متابعة"}
            </Button>
          </>
        )}

        {step === "accounts" && (
          <>
            <p className="text-sm text-ink-soft">
              سنزرع شجرة حسابات افتراضية (~25 حساباً) يمكنك تعديلها لاحقاً من صفحة شجرة الحسابات.
            </p>
            <Button disabled={isSubmitting} onClick={handleSeedAccounts}>
              {isSubmitting ? "جارِ الزرع…" : "زرع شجرة الحسابات"}
            </Button>
          </>
        )}

        {step === "done" && (
          <>
            <Banner kind="success">تم الإعداد الأولي بنجاح.</Banner>
            <Button onClick={() => router.push("/dashboard")}>الانتقال إلى لوحة الإدارة</Button>
          </>
        )}
      </div>
    </div>
  );
}
