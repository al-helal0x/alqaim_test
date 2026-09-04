"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/common/auth-context";
import { needsServerConnectionSetup } from "@/api-client/server-config";

export default function RootPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (isLoading) return;
    // على سطح المكتب بلا خادم مُهيَّأ بعد: DesktopBootstrap (app/layout.tsx)
    // هو المسؤول الوحيد عن التحويل إلى /connect — لا نتسابق معه هنا على
    // نفس عملية router.replace في نفس اللحظة.
    if (needsServerConnectionSetup()) return;
    router.replace(isAuthenticated ? "/dashboard" : "/login");
  }, [isLoading, isAuthenticated, router]);

  return null;
}
