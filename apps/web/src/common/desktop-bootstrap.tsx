"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { needsServerConnectionSetup } from "@/api-client/server-config";

/**
 * يعمل فقط على سطح المكتب (Tauri — العضو 10). في نشر الويب العادي
 * `needsServerConnectionSetup()` تُرجع false دائماً (عنوان البناء متوفر
 * أصلاً)، فهذا المكوّن لا يفعل شيئاً هناك — آمن للتضمين في كل نشر بلا شرط.
 */
export function DesktopBootstrap(): null {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (pathname === "/connect") return;
    if (needsServerConnectionSetup()) {
      router.replace("/connect");
    }
  }, [pathname, router]);

  return null;
}
