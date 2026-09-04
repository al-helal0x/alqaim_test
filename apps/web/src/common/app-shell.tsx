"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/common/auth-context";
import { t } from "@alqaim/i18n";
import { ShortcutProvider, useShortcutContext } from "@/common/shortcuts/shortcut-context";
import { useGlobalShortcuts } from "@/common/shortcuts/use-global-shortcuts";
import { CommandPalette } from "@/common/shortcuts/command-palette";
import { ShortcutsHelp } from "@/common/shortcuts/shortcuts-help";
import { GLOBAL_ACTION_KEYS } from "@/common/shortcuts/registry";

// تكامل فعلي مع @alqaim/i18n: كل نصوص شريط التنقّل والعلامة التجارية تمرّ عبر
// t() بدل نصوص عربية مكتوبة مباشرة هنا — إثبات استخدام حقيقي للحزمة، وليست
// بنية تحتية خاملة. بقية صفحات التطبيق (27 صفحة) لم تُحوَّل بعد عمداً (نطاق
// كبير جداً لجولة واحدة) — موثَّق في packages/i18n/README.md.
const NAV_SECTIONS: { labelKey: Parameters<typeof t>[0]; items: { href: string; labelKey: Parameters<typeof t>[0] }[] }[] = [
  {
    labelKey: "nav.catalog",
    items: [
      { href: "/catalog/products", labelKey: "nav.catalog.products" },
      { href: "/catalog/categories", labelKey: "nav.catalog.categories" },
      { href: "/catalog/units-of-measure", labelKey: "nav.catalog.units" },
    ],
  },
  {
    labelKey: "nav.partners",
    items: [
      { href: "/partners/customers", labelKey: "nav.partners.customers" },
      { href: "/partners/suppliers", labelKey: "nav.partners.suppliers" },
    ],
  },
  {
    labelKey: "nav.inventory",
    items: [
      { href: "/inventory/balances", labelKey: "nav.inventory.balances" },
      { href: "/inventory/movements", labelKey: "nav.inventory.movements" },
    ],
  },
  {
    labelKey: "nav.sales",
    items: [
      { href: "/sales/quotations", labelKey: "nav.sales.quotations" },
      { href: "/sales/orders", labelKey: "nav.sales.orders" },
      { href: "/sales/invoices", labelKey: "nav.sales.invoices" },
    ],
  },
  {
    labelKey: "nav.purchasing",
    items: [
      { href: "/purchasing/orders", labelKey: "nav.purchasing.orders" },
      { href: "/purchasing/invoices", labelKey: "nav.purchasing.invoices" },
      { href: "/purchasing/invoices/ai-upload", labelKey: "nav.purchasing.aiUpload" },
    ],
  },
  {
    labelKey: "nav.payments",
    items: [
      { href: "/payments/bank-accounts", labelKey: "nav.payments.bankAccounts" },
      { href: "/payments/payments", labelKey: "nav.payments.payments" },
      { href: "/payments/receipts", labelKey: "nav.payments.receipts" },
    ],
  },
  {
    labelKey: "nav.accounting",
    items: [
      { href: "/accounting/accounts", labelKey: "nav.accounting.accounts" },
      { href: "/accounting/journal-entries", labelKey: "nav.accounting.journalEntries" },
      { href: "/accounting/fiscal-years", labelKey: "nav.accounting.fiscalYears" },
      { href: "/accounting/reports", labelKey: "nav.accounting.reports" },
    ],
  },
  {
    labelKey: "nav.taxation",
    items: [{ href: "/taxation/tax-rates", labelKey: "nav.taxation.taxRates" }],
  },
  {
    labelKey: "nav.settings",
    items: [{ href: "/settings/branches", labelKey: "nav.settings.branches" }],
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ShortcutProvider>
      <AppShellInner>{children}</AppShellInner>
    </ShortcutProvider>
  );
}

// مفصولة عن AppShell لأن useGlobalShortcuts/useShortcutContext يجب أن تُستدعى
// من *داخل* <ShortcutProvider>، بينما AppShell نفسها هي من يقوم بتركيبه.
function AppShellInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { logout } = useAuth();
  const { setPaletteOpen, setHelpOpen } = useShortcutContext();

  useGlobalShortcuts();

  // Ctrl/⌘+Shift+Q (مُطلَق من use-global-shortcuts) → تسجيل خروج فوري
  useEffect(() => {
    function onLogoutShortcut() {
      logout();
    }
    window.addEventListener("alqaim:shortcut:logout", onLogoutShortcut);
    return () => window.removeEventListener("alqaim:shortcut:logout", onLogoutShortcut);
  }, [logout]);

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 shrink-0 flex-col border-l border-line bg-ledger-900 text-white">
        <div className="border-b border-white/10 px-5 py-5">
          {/* ⚠️ إصلاح: كان <span> عادي بلا أي تفاعل — لا يوجد أي رابط آخر في
              القائمة الجانبية كلها يوصّل لصفحة /dashboard الرئيسية رغم أنها
              مبنية بالكامل (لوحة "نبض الشركة اليومي" + 9 اختصارات). اكتُشف
              عبر فحص يدوي: "المستخدم مايقدر يرجع للصفحة الرئيسية" (19 أغسطس
              2026). تحويله لرابط هو أبسط حل يطابق توقّع أي مستخدم ويب معتاد
              (الضغط على الشعار = رجوع للرئيسية). */}
          <Link href="/dashboard" className="block">
            <span className="font-display text-xl">{t("brand.name")}</span>
          </Link>
          <div className="kufic-rule mt-2 w-12 opacity-80" />
          <p className="mt-1 text-xs text-white/60">{t("brand.tagline")}</p>
        </div>

        <div className="px-3 pt-3">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="flex w-full items-center justify-between rounded border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs text-white/70 transition-colors hover:bg-white/10 hover:text-white"
            aria-label={t("shortcuts.openPalette")}
          >
            <span>{t("action.search")}</span>
            <kbd className="rounded border border-white/20 bg-white/10 px-1.5 py-0.5 font-mono text-[10px]">
              {GLOBAL_ACTION_KEYS.palette}
            </kbd>
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {/* رابط "الرئيسية" ثابت — خارج NAV_SECTIONS عمداً لأنه صفحة واحدة
              لا قسم، ولأنه يجب أن يظهر أول عنصر دائماً بصرف النظر عن ترتيب
              الأقسام. راجع نفس ملاحظة إصلاح شعار البراند أعلاه. */}
          <Link
            href="/dashboard"
            className={`mb-4 block rounded px-2 py-1.5 text-sm font-medium transition-colors ${
              pathname === "/dashboard" ? "bg-white/10 text-white" : "text-white/70 hover:bg-white/5 hover:text-white"
            }`}
          >
            {t("nav.dashboard")}
          </Link>
          {NAV_SECTIONS.map((section) => (
            <div key={section.labelKey} className="mb-5">
              <p className="mb-1 px-2 text-xs text-white/40">{t(section.labelKey)}</p>
              {section.items.map((item) => {
                const active = pathname?.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`block rounded px-2 py-1.5 text-sm transition-colors ${
                      active ? "bg-white/10 text-white" : "text-white/70 hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    {t(item.labelKey)}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="border-t border-white/10 px-5 py-4">
          <button
            type="button"
            onClick={() => setHelpOpen(true)}
            className="mb-2 block w-full text-start text-xs text-white/50 hover:text-white"
          >
            {t("shortcuts.footer.hint").replace("{key}", GLOBAL_ACTION_KEYS.help)}
          </button>
          <button onClick={logout} className="text-sm text-white/60 hover:text-white">
            {t("action.logout")}
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto px-8 py-8">{children}</main>
      <CommandPalette />
      <ShortcutsHelp />
    </div>
  );
}