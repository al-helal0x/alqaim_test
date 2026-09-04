"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/common/auth-context";
import { needsServerConnectionSetup } from "@/api-client/server-config";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (needsServerConnectionSetup()) return; // DesktopBootstrap يتولّى التحويل
    if (!isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center text-ink-soft">
        جارِ التحقق من الجلسة…
      </div>
    );
  }

  return <>{children}</>;
}
