"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/common/auth-context";
import { Banner, Button, Field } from "@/common/ui";
import { ApiError } from "@/api-client/http";
import { registerCompany } from "@/features/identity/api";
import { t } from "@alqaim/i18n";

export default function RegisterPage() {
  const router = useRouter();
  const auth = useAuth();
  const [form, setForm] = useState({
    company_name: "",
    default_currency: "IQD",
    admin_full_name: "",
    admin_email: "",
    admin_password: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function update<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const tokens = await registerCompany(form);
      auth.login(tokens);
      router.push("/onboarding");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر الاتصال بالخادم");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-6 py-12">
      <div className="w-full max-w-md">
        <Link href="/login" className="font-display text-2xl text-ink">
          {t("brand.name")}
        </Link>
        <h1 className="mt-6 font-display text-2xl text-ink">إنشاء شركة جديدة</h1>
        <p className="mt-1 text-sm text-ink-soft">
          خطوة واحدة: بيانات الشركة وحساب المالك (Owner) معاً
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          {error && <Banner kind="error">{error}</Banner>}

          <Field
            label="اسم الشركة"
            required
            value={form.company_name}
            onChange={(e) => update("company_name", e.target.value)}
          />
          <Field
            label="العملة الافتراضية (3 أحرف)"
            required
            maxLength={3}
            value={form.default_currency}
            onChange={(e) => update("default_currency", e.target.value.toUpperCase())}
          />
          <div className="kufic-rule w-12" />
          <Field
            label="الاسم الكامل للمالك"
            required
            value={form.admin_full_name}
            onChange={(e) => update("admin_full_name", e.target.value)}
          />
          <Field
            label="البريد الإلكتروني"
            type="email"
            required
            value={form.admin_email}
            onChange={(e) => update("admin_email", e.target.value)}
          />
          <Field
            label="كلمة المرور (8 أحرف على الأقل)"
            type="password"
            required
            minLength={8}
            value={form.admin_password}
            onChange={(e) => update("admin_password", e.target.value)}
          />

          <Button type="submit" disabled={isSubmitting} className="w-full">
            {isSubmitting ? "جارِ الإنشاء…" : "إنشاء الشركة والمتابعة"}
          </Button>
        </form>

        <p className="mt-6 text-sm text-ink-soft">
          تملك حساباً بالفعل؟{" "}
          <Link href="/login" className="text-copper-600 hover:underline">
            سجّل الدخول
          </Link>
        </p>
      </div>
    </div>
  );
}
