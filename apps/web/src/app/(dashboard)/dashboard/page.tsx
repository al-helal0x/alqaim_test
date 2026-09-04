import Link from "next/link";
import { Card, PageHeader } from "@/common/ui";
import { BusinessPulseDashboard } from "@/features/reporting/business-pulse-dashboard";

export default function DashboardPage() {
  return (
    <div>
      <PageHeader title="لوحة الإدارة" description="نظرة عامة سريعة على شركتك" />

      {/* TASK-BI-01 — لوحة "نبض الشركة اليومي": 5 مؤشرات حيّة، بلا أي AI */}
      <div className="mb-6">
        <BusinessPulseDashboard />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <ShortcutCard href="/catalog/products" title="المنتجات" description="كتالوج المنتجات والخدمات" />
        <ShortcutCard href="/partners/customers" title="العملاء" description="إدارة قائمة العملاء" />
        <ShortcutCard href="/partners/suppliers" title="الموردون" description="إدارة قائمة الموردين" />
        <ShortcutCard href="/inventory/balances" title="أرصدة المخزون" description="الكميات المتوفرة حالياً" />
        <ShortcutCard href="/sales/orders" title="أوامر البيع" description="دورة المبيعات الكاملة" />
        <ShortcutCard href="/purchasing/orders" title="أوامر الشراء" description="دورة المشتريات الكاملة" />
        <ShortcutCard href="/payments/payments" title="المدفوعات" description="دفعات ومقبوضات" />
        <ShortcutCard href="/accounting/reports" title="التقارير المالية" description="ميزان المراجعة وقوائم الدخل" />
        <ShortcutCard href="/settings/branches" title="الفروع والمستودعات" description="إعدادات الشركة التنظيمية" />
      </div>
    </div>
  );
}

function ShortcutCard({ href, title, description }: { href: string; title: string; description: string }) {
  return (
    <Link href={href}>
      <Card className="h-full transition-colors hover:border-copper-500">
        <p className="font-display text-lg text-ink">{title}</p>
        <p className="mt-1 text-sm text-ink-soft">{description}</p>
      </Card>
    </Link>
  );
}
