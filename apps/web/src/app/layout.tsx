import type { Metadata } from "next";
import { AuthProvider } from "@/common/auth-context";
import { DesktopBootstrap } from "@/common/desktop-bootstrap";
import "./globals.css";

export const metadata: Metadata = {
  title: "القائم — AlQaim ERP",
  description: "لوحة إدارة القائم — نظام تخطيط موارد المؤسسة",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <body>
        <DesktopBootstrap />
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
