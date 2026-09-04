"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button, Field } from "@/common/ui";
import { setConfiguredServerUrl } from "@/api-client/server-config";

/**
 * شاشة تظهر مرة واحدة فقط عند أول تشغيل لنسخة سطح المكتب (Tauri — العضو 10)
 * قبل الوصول لتسجيل الدخول. غير مرئية إطلاقاً في نشر الويب العادي
 * (`needsServerConnectionSetup` في common/desktop-bootstrap.tsx تمنع
 * التحويل إليها إلا داخل غلاف Tauri بلا عنوان محفوظ — القسم 6.3).
 *
 * سبب وجودها: نسخة Self-Hosted لكل شركة على خادمها الخاص، وثنائي سطح
 * المكتب المُصرَّف مرة واحدة يُوزَّع على شركات متعددة — لا يمكن تضمين
 * عنوان واحد وقت البناء (خلافاً لنشر الويب العادي الذي يملك
 * NEXT_PUBLIC_API_URL ثابتاً وقت البناء).
 */
export default function ConnectPage(): JSX.Element {
  const router = useRouter();
  const [serverUrl, setServerUrl] = useState("https://");
  const [status, setStatus] = useState<"idle" | "checking" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setStatus("checking");
    setErrorMessage(null);

    const trimmed = serverUrl.trim().replace(/\/+$/, "");
    try {
      const response = await fetch(`${trimmed}/health`, { method: "GET" });
      if (!response.ok) throw new Error(`الخادم استجاب بخطأ (${response.status})`);
    } catch {
      setStatus("error");
      setErrorMessage(
        "تعذّر الوصول إلى الخادم على هذا العنوان. تأكد من العنوان ومن أن الخادم يعمل، ثم حاول مجدداً."
      );
      return;
    }

    setConfiguredServerUrl(trimmed);
    router.replace("/login");
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-6">
      <div className="w-full max-w-sm">
        <span className="font-display text-2xl text-ink">القائم</span>
        <div className="kufic-rule mt-3 w-16" />
        <h1 className="mt-6 font-display text-xl text-ink">الاتصال بخادم شركتك</h1>
        <p className="mt-1 text-sm text-ink-soft">
          أدخل عنوان الخادم (Self-Hosted أو نسخة سحابية مخصّصة). يُطلَب هذا مرة
          واحدة فقط على هذا الجهاز.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <Field
            label="عنوان الخادم"
            id="server-url"
            type="url"
            required
            dir="ltr"
            placeholder="https://erp.yourcompany.com"
            value={serverUrl}
            onChange={(event) => setServerUrl(event.target.value)}
            error={status === "error" ? errorMessage ?? undefined : undefined}
          />
          <Button type="submit" disabled={status === "checking"} className="w-full">
            {status === "checking" ? "جارِ التحقق من الاتصال…" : "اتصال ومتابعة"}
          </Button>
        </form>
      </div>
    </div>
  );
}
