export type LineAmounts = { debit: string; credit: string };

export type JournalTotals = {
  debit: number;
  credit: number;
  isBalanced: boolean;
};

/** يحسب مجموع المدين/الدائن لأسطر قيد في الواجهة، ويحدد إن كان متوازناً.
 * هذا فحص تجربة مستخدم فوري فقط (Fail Fast قبل الإرسال) — التحقق الملزم
 * الفعلي يبقى على الخادم دائماً (assert_balanced في core-api). */
export function computeJournalTotals(lines: LineAmounts[]): JournalTotals {
  const debit = lines.reduce((sum, l) => sum + (Number(l.debit) || 0), 0);
  const credit = lines.reduce((sum, l) => sum + (Number(l.credit) || 0), 0);
  return { debit, credit, isBalanced: debit === credit && debit > 0 };
}
