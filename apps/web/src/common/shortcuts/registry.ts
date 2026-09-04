/**
 * سجل اختصارات لوحة المفاتيح — مصدر وحيد للحقيقة.
 *
 * الفلسفة (موثّقة أيضاً في shortcuts/README.md):
 * - برامج المحاسبة العربية الكلاسيكية (الأمين وأمثاله) تعتمد أرقام F مباشرة
 *   (F2/F3/F5/F9/F12...) لأنها تطبيقات Desktop تملك المفاتيح بالكامل.
 *   على الويب هذه المفاتيح محجوزة فعلياً من المتصفح (F1 مساعدة المتصفح,
 *   F3 بحث الصفحة, F5 تحديث, F12 أدوات المطوّر) — استخدامها يكسر تجربة
 *   المستخدم أو يتعارض مع المتصفح، لذلك نستبدلها بمكافئ حديث موثوق:
 *     • تنقّل مباشر لأي شاشة عبر تتابع "G ثم حرف" (أسلوب Gmail/Linear/GitHub)
 *       بدل الاعتماد على أرقام F، وهو ما يوفّره أيضاً محرك البحث الموحّد
 *       (الوحدة #14 في مخطط المنتج).
 *     • لوحة انتقال سريع Ctrl+K (تبحث بالاسم العربي/الإنجليزي) تكافئ فكرة
 *       "البحث الشامل" الذي توفّره برامج المحاسبة الحديثة (QuickBooks/Xero).
 *     • إجراءات عامة تُحاكي القياسي عبر كل برامج المحاسبة: Ctrl+N (سجل
 *       جديد), Ctrl+S (حفظ), Esc (إلغاء) — نفس المنطق الموجود في الأمين
 *       (Insert لسطر جديد، Esc للخروج من الفورمة) لكن بمفاتيح لا تصطدم
 *       بالمتصفح.
 *     • داخل جداول القيود/الفواتير: Insert لإضافة سطر، Ctrl+Delete لحذف
 *       السطر الحالي — نفس تجربة إكسل وشبكات الإدخال في الأمين.
 */

export type NavShortcut = {
  /** المسار الفعلي (يطابق app-shell.tsx تماماً) */
  href: string;
  /** مفتاح الترجمة المستخدم أصلاً في شريط التنقّل */
  labelKey:
    | "nav.catalog.products"
    | "nav.catalog.categories"
    | "nav.catalog.units"
    | "nav.partners.customers"
    | "nav.partners.suppliers"
    | "nav.inventory.balances"
    | "nav.inventory.movements"
    | "nav.sales.quotations"
    | "nav.sales.orders"
    | "nav.sales.invoices"
    | "nav.purchasing.orders"
    | "nav.purchasing.invoices"
    | "nav.purchasing.aiUpload"
    | "nav.payments.bankAccounts"
    | "nav.payments.payments"
    | "nav.payments.receipts"
    | "nav.accounting.accounts"
    | "nav.accounting.journalEntries"
    | "nav.accounting.fiscalYears"
    | "nav.accounting.reports"
    | "nav.taxation.taxRates"
    | "nav.settings.branches";
  /** اسم القسم (للعرض في اللوحة/المساعدة) */
  sectionKey:
    | "nav.catalog"
    | "nav.partners"
    | "nav.inventory"
    | "nav.sales"
    | "nav.purchasing"
    | "nav.payments"
    | "nav.accounting"
    | "nav.taxation"
    | "nav.settings";
  /**
   * تتابع "الانتقال المباشر": يُضغط G ثم هذا الحرف خلال أقل من 900ms.
   * الحروف مأخوذة من أول صوت مميّز في الاسم الإنجليزي لتفادي التصادم،
   * ويجب أن تبقى فريدة عبر كل القائمة (مُتحقَّق منها في use-global-shortcuts).
   */
  goToKey: string;
};

export const NAV_SHORTCUTS: NavShortcut[] = [
  { href: "/dashboard", labelKey: "nav.accounting.reports", sectionKey: "nav.accounting", goToKey: "h" }, // لوحة التحكم = "home"، تُستثنى من القائمة الظاهرة أدناه (انظر ملاحظة أسفل الملف)
  { href: "/catalog/products", labelKey: "nav.catalog.products", sectionKey: "nav.catalog", goToKey: "p" },
  { href: "/catalog/categories", labelKey: "nav.catalog.categories", sectionKey: "nav.catalog", goToKey: "c" },
  { href: "/catalog/units-of-measure", labelKey: "nav.catalog.units", sectionKey: "nav.catalog", goToKey: "u" },
  { href: "/partners/customers", labelKey: "nav.partners.customers", sectionKey: "nav.partners", goToKey: "m" }, // Mushtari
  { href: "/partners/suppliers", labelKey: "nav.partners.suppliers", sectionKey: "nav.partners", goToKey: "o" }, // mOrred / supplier
  { href: "/inventory/balances", labelKey: "nav.inventory.balances", sectionKey: "nav.inventory", goToKey: "b" },
  { href: "/inventory/movements", labelKey: "nav.inventory.movements", sectionKey: "nav.inventory", goToKey: "v" }, // moVements
  { href: "/sales/quotations", labelKey: "nav.sales.quotations", sectionKey: "nav.sales", goToKey: "q" },
  { href: "/sales/orders", labelKey: "nav.sales.orders", sectionKey: "nav.sales", goToKey: "s" }, // Sales orders
  { href: "/sales/invoices", labelKey: "nav.sales.invoices", sectionKey: "nav.sales", goToKey: "i" }, // Invoices (sales)
  { href: "/purchasing/orders", labelKey: "nav.purchasing.orders", sectionKey: "nav.purchasing", goToKey: "r" }, // puRchasing orders
  { href: "/purchasing/invoices", labelKey: "nav.purchasing.invoices", sectionKey: "nav.purchasing", goToKey: "f" }, // Faturas shraa
  { href: "/purchasing/invoices/ai-upload", labelKey: "nav.purchasing.aiUpload", sectionKey: "nav.purchasing", goToKey: "a" }, // AI
  { href: "/payments/bank-accounts", labelKey: "nav.payments.bankAccounts", sectionKey: "nav.payments", goToKey: "k" }, // banK
  { href: "/payments/payments", labelKey: "nav.payments.payments", sectionKey: "nav.payments", goToKey: "y" }, // paYments
  { href: "/payments/receipts", labelKey: "nav.payments.receipts", sectionKey: "nav.payments", goToKey: "d" }, // receipt voucher / sanaD
  { href: "/accounting/accounts", labelKey: "nav.accounting.accounts", sectionKey: "nav.accounting", goToKey: "t" }, // chart of accounTs / shajarat al-hisabat
  { href: "/accounting/journal-entries", labelKey: "nav.accounting.journalEntries", sectionKey: "nav.accounting", goToKey: "j" },
  { href: "/accounting/fiscal-years", labelKey: "nav.accounting.fiscalYears", sectionKey: "nav.accounting", goToKey: "l" }, // fiscaL years / sana maliya
  { href: "/accounting/reports", labelKey: "nav.accounting.reports", sectionKey: "nav.accounting", goToKey: "e" }, // rEports / taqarir
  { href: "/taxation/tax-rates", labelKey: "nav.taxation.taxRates", sectionKey: "nav.taxation", goToKey: "x" }, // taX
  { href: "/settings/branches", labelKey: "nav.settings.branches", sectionKey: "nav.settings", goToKey: "n" }, // brancHes conflicts h(home) so use N (fruoN)
];

// لوحة التحكم الرئيسية ليست ضمن NAV_SECTIONS في app-shell (لا رابط ظاهر لها
// حالياً في القائمة الجانبية)، لذا نستثنيها من القائمة القابلة للعرض/البحث
// ونُبقيها فقط كاختصار "الذهاب للرئيسية" (G ثم H) لأنها الشاشة الافتراضية
// بعد تسجيل الدخول. الفهرس أعلاه مقصود بأن يبقى مطابقاً 1:1 لبنية
// NAV_SECTIONS في app-shell.tsx — أي تعديل هناك يجب أن يُقابله تعديل هنا.
export const HOME_SHORTCUT: NavShortcut = NAV_SHORTCUTS[0];
export const VISIBLE_NAV_SHORTCUTS: NavShortcut[] = NAV_SHORTCUTS.slice(1);

export type GlobalActionId = "new" | "save" | "cancel" | "help" | "palette" | "logout" | "delete" | "print" | "post";

export const GLOBAL_ACTION_KEYS: Record<GlobalActionId, string> = {
  palette: "Ctrl/⌘ + K",
  new: "Ctrl/⌘ + N",
  save: "Ctrl/⌘ + S",
  cancel: "Esc",
  help: "?",
  logout: "Ctrl/⌘ + Shift + Q",
  delete: "Alt + 8",
  print: "Alt + 6",
  post: "Alt + 9",
};

/**
 * طبقة "توافق الأمين" — مقصودة لنقل الذاكرة العضلية لمستخدمي الأمين وبرامج
 * المحاسبة العربية المشابهة (كلها تتبع نفس تقليد Delphi/Windows Desktop):
 * F2 سجل جديد، F3 بحث، F5 حفظ، F6 طباعة، F8 حذف، F9 ترحيل، Insert سطر جديد،
 * Esc إلغاء. لم نجد جدول اختصارات رسمياً منشوراً من الأمين نفسها يوثّق هذه
 * الأرقام حرفياً؛ هذا هو النمط الشائع الموثَّق عبر هذا الجيل من البرامج
 * (وهو ما استند إليه هذا التصميم)، لا اقتباساً من مصدر رسمي واحد.
 *
 * بما أن F2/F3/F5/F6/F8/F9 محجوزة أو تتصادم مع المتصفح (راجع الجدول في
 * README.md)، نُبقي **نفس الرقم** لكن خلف Alt بدل الاعتماد على المفتاح
 * وحده — أقرب استبدال آمن ممكن على الويب مع محافظة على الرقم المألوف:
 *
 *   F2 (سجل جديد)  → Alt+2   F3 (بحث)   → Alt+3   F5 (حفظ)  → Alt+5
 *   F6 (طباعة)     → Alt+6   F8 (حذف)   → Alt+8   F9 (ترحيل) → Alt+9
 *   Insert وEsc تبقيان كما هي حرفياً — لا تصادم مع المتصفح أصلاً.
 */
export const AL_AMIN_COMPAT_KEYS: Record<"new" | "search" | "save" | "print" | "delete" | "post", string> = {
  new: "Alt+2",
  search: "Alt+3",
  save: "Alt+5",
  print: "Alt+6",
  delete: "Alt+8",
  post: "Alt+9",
};

export const GRID_ACTION_KEYS = {
  addRow: "Insert",
  removeRow: "Ctrl/⌘ + Delete",
  nextField: "Tab",
  prevField: "Shift + Tab",
  submit: "Ctrl/⌘ + Enter",
};
