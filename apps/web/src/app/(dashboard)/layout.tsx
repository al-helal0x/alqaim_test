"use client";

import { RequireAuth } from "@/common/require-auth";
import { AppShell } from "@/common/app-shell";

export default function DashboardGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <AppShell>{children}</AppShell>
    </RequireAuth>
  );
}
