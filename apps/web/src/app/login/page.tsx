"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/common/auth-context";
import { t } from "@alqaim/i18n";
import { Banner, Button, Field } from "@/common/ui";
import { ApiError } from "@/api-client/http";
import { login } from "@/features/identity/api";

export default function LoginPage() {
  const router = useRouter();
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [showCompanyField, setShowCompanyField] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const tokens = await login({
        email,
        password,
        company_id: companyId.trim() || undefined,
      });
      auth.login(tokens);
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("تعذّر الاتصال بالخادم");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen">
      <div className="hidden w-1/2 flex-col justify-between bg-ledger-900 p-12 text-white lg:flex">
        <div>
          <span className="font-display text-3xl">{t("brand.name")}</span>
          <div className="kufic-rule mt-3 w-20" />
        </div>

        <div>
          <p className="max-w-sm font-display text-2xl leading-relaxed text-white/90">
            كل قيد متوازن. كل فترة موثّقة. ميزان مراجعتك يتّزن دائماً — تلقائياً.
          </p>
          <LedgerIllustration />
        </div>

        <p className="text-xs text-white/40">نظام تخطيط موارد المؤسسات — AlQaim ERP</p>
      </div>

      <div className="flex w-full items-center justify-center px-6 lg:w-1/2">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <span className="font-display text-2xl text-ink">{t("brand.name")}</span>
          </div>
          <h1 className="font-display text-2xl text-ink">تسجيل الدخول</h1>
          <p className="mt-1 text-sm text-ink-soft">أدخل بياناتك للوصول إلى لوحة الإدارة</p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            {error && <Banner kind="error">{error}</Banner>}
            <Field
              label="البريد الإلكتروني"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
            <Field
              label="كلمة المرور"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />

            {showCompanyField ? (
              <Field
                label="معرّف الشركة"
                value={companyId}
                onChange={(e) => setCompanyId(e.target.value)}
                placeholder="مطلوب فقط إن كنت عضواً في أكثر من شركة"
              />
            ) : (
              <button
                type="button"
                onClick={() => setShowCompanyField(true)}
                className="text-xs text-copper-600 hover:underline"
              >
                عضو في أكثر من شركة؟
              </button>
            )}

            <Button type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting ? "جارِ الدخول…" : "دخول"}
            </Button>
          </form>

          <p className="mt-6 text-sm text-ink-soft">
            لا تملك حساباً؟{" "}
            <Link href="/register" className="text-copper-600 hover:underline">
              أنشئ شركتك الآن
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

/** رسم توضيحي بسيط لعمودَي مدين/دائن — العنصر البصري المميّز للواجهة، مستوحى
 * من صفحة دفتر الأستاذ التقليدية. */
function LedgerIllustration() {
  const rows = [40, 65, 30, 80, 50];
  return (
    <svg viewBox="0 0 320 140" className="mt-8 w-full max-w-sm opacity-90" aria-hidden="true">
      <line x1="160" y1="0" x2="160" y2="140" stroke="white" strokeOpacity="0.15" />
      {rows.map((w, i) => (
        <g key={i}>
          <rect x={160 - w} y={i * 26 + 6} width={w} height="10" fill="#3E8563" />
          <rect x={162} y={i * 26 + 6} width={rows[(i + 2) % rows.length]} height="10" fill="#B9752B" />
        </g>
      ))}
    </svg>
  );
}
