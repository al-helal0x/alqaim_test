"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Banner, Button, Card, EmptyState, Field, PageHeader, SelectField } from "@/common/ui";
import { formatAmount } from "@/common/format";
import { computeJournalTotals } from "@/common/journal-balance";
import { ApiError } from "@/api-client/http";
import { listAccounts, listJournalEntries, postManualJournalEntry } from "@/features/accounting/api";
import type { AccountResponse, JournalEntryResponse } from "@/api-client/types";
import { usePageShortcuts } from "@/common/shortcuts/use-page-shortcuts";
import { handleGridKeyDown } from "@/common/shortcuts/use-grid-shortcuts";

type LineDraft = { accountId: string; debit: string; credit: string; description: string };

const EMPTY_LINE: LineDraft = { accountId: "", debit: "", credit: "", description: "" };

export default function JournalEntriesPage() {
  const [entries, setEntries] = useState<JournalEntryResponse[] | null>(null);
  const [accounts, setAccounts] = useState<AccountResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  async function refresh() {
    try {
      const [entriesData, accountsData] = await Promise.all([listJournalEntries(), listAccounts()]);
      setEntries(entriesData);
      setAccounts(accountsData.filter((a) => a.is_postable));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر تحميل القيود");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  // اختصارات عامة: Ctrl/⌘+N يفتح فورمة "قيد جديد" أينما كان المستخدم في هذه
  // الشاشة، وEsc يغلقها فقط إذا كانت مفتوحة أصلاً (بدل أن يفعل شيئاً غير
  // متوقَّع). راجع common/shortcuts/README.md لشرح النمط الكامل.
  usePageShortcuts({
    onNew: () => setShowForm(true),
    onCancel: showForm ? () => setShowForm(false) : undefined,
  });

  return (
    <div>
      <PageHeader
        title="القيود اليومية"
        description="ترحيل قيود يدوية مباشرة — يجب أن يتساوى مجموع المدين والدائن"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "إغلاق" : "قيد جديد"}</Button>}
      />

      {error && <div className="mb-4"><Banner kind="error">{error}</Banner></div>}

      {showForm && (
        <Card className="mb-6">
          <CreateJournalEntryForm
            accounts={accounts}
            onCreated={() => {
              setShowForm(false);
              refresh();
            }}
          />
        </Card>
      )}

      {entries === null ? (
        <p className="text-sm text-ink-soft">جارِ التحميل…</p>
      ) : entries.length === 0 ? (
        <EmptyState title="لا توجد قيود بعد" description="رحّل أول قيد يدوي من الأعلى" />
      ) : (
        <div className="space-y-3">
          {entries.map((entry) => (
            <Card key={entry.id}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-ink">
                    {entry.entry_number}
                    <span className="ms-2 text-xs text-ink-soft num">{entry.entry_date}</span>
                  </p>
                  {entry.memo && <p className="text-sm text-ink-soft">{entry.memo}</p>}
                  {entry.source_document_type && (
                    <p className="mt-0.5 text-xs text-ink-soft">
                      المصدر: {entry.source_document_type} #{entry.source_document_id}
                    </p>
                  )}
                </div>
              </div>
              <table className="mt-3 w-full text-sm">
                <tbody>
                  {entry.lines.map((line) => (
                    <tr key={line.id} className="border-t border-line">
                      <td className="py-1.5 text-ink-soft">{line.description ?? "—"}</td>
                      <td className="num w-32 py-1.5 text-ledger-700">
                        {Number(line.debit) > 0 ? formatAmount(line.debit) : ""}
                      </td>
                      <td className="num w-32 py-1.5 text-copper-600">
                        {Number(line.credit) > 0 ? formatAmount(line.credit) : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function CreateJournalEntryForm({
  accounts,
  onCreated,
}: {
  accounts: AccountResponse[];
  onCreated: () => void;
}) {
  const [entryDate, setEntryDate] = useState(new Date().toISOString().slice(0, 10));
  const [memo, setMemo] = useState("");
  const [lines, setLines] = useState<LineDraft[]>([{ ...EMPTY_LINE }, { ...EMPTY_LINE }]);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  const totals = useMemo(() => computeJournalTotals(lines), [lines]);

  // Ctrl/⌘+S أثناء فتح هذه الفورمة يحفظ القيد مباشرة، بنفس زر "ترحيل القيد".
  // Alt+9 (توافق الأمين لـ F9) يُعامَل هنا كمرادف صريح للترحيل، لأن حفظ
  // القيد وترحيله فعل واحد في هذه الشاشة (لا مسودة/ترحيل منفصلين بعد).
  // مسجَّل هنا (لا في الصفحة الأم) لأن الحفظ منطقياً ملك الفورمة نفسها، وهو
  // يُلغى تلقائياً عند إغلاقها (usePageShortcuts ينظّف نفسه عند unmount).
  usePageShortcuts({
    onSave: () => formRef.current?.requestSubmit(),
    onPost: () => formRef.current?.requestSubmit(),
  });

  function updateLine(index: number, patch: Partial<LineDraft>) {
    setLines((prev) => prev.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  }

  function addLine() {
    setLines((prev) => [...prev, { ...EMPTY_LINE }]);
  }

  function removeLine(index: number) {
    setLines((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!totals.isBalanced) {
      setError("القيد غير متوازن — مجموع المدين يجب أن يساوي مجموع الدائن");
      return;
    }
    setIsSubmitting(true);
    try {
      await postManualJournalEntry({
        entry_date: entryDate,
        memo: memo || undefined,
        lines: lines
          .filter((l) => l.accountId)
          .map((l) => ({
            account_id: l.accountId,
            debit: l.debit || "0",
            credit: l.credit || "0",
            description: l.description || undefined,
          })),
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر ترحيل القيد");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit} className="space-y-4">
      {error && <Banner kind="error">{error}</Banner>}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="تاريخ القيد" type="date" required value={entryDate} onChange={(e) => setEntryDate(e.target.value)} />
        <Field label="البيان (اختياري)" value={memo} onChange={(e) => setMemo(e.target.value)} />
      </div>

      {/*
        شبكة الأسطر: Insert يضيف سطراً جديداً، Ctrl/⌘+Delete يحذف السطر الذي
        فيه التركيز الحالي، Ctrl/⌘+Enter يرحّل القيد مباشرة — بنفس منطق
        الإدخال الجدولي في الأمين وإكسل، معزول هنا داخل هذه الشبكة فقط حتى لا
        يتصادم Insert/Delete مع أي استخدام آخر لهما في باقي الصفحة.
      */}
      <div
        className="space-y-2"
        onKeyDown={(e) =>
          handleGridKeyDown(e, {
            addRow: addLine,
            removeRow: removeLine,
            submit: () => formRef.current?.requestSubmit(),
            currentRowCount: lines.length,
            minRows: 2,
          })
        }
      >
        {lines.map((line, i) => (
          <div key={i} data-grid-row={i} className="grid grid-cols-12 items-end gap-2">
            <div className="col-span-4">
              <SelectField
                label="الحساب"
                value={line.accountId}
                onChange={(e) => updateLine(i, { accountId: e.target.value })}
              >
                <option value="">اختر حساباً</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} — {a.name}
                  </option>
                ))}
              </SelectField>
            </div>
            <div className="col-span-3">
              <Field
                label="مدين"
                type="number"
                step="0.0001"
                value={line.debit}
                onChange={(e) => updateLine(i, { debit: e.target.value, credit: "" })}
              />
            </div>
            <div className="col-span-3">
              <Field
                label="دائن"
                type="number"
                step="0.0001"
                value={line.credit}
                onChange={(e) => updateLine(i, { credit: e.target.value, debit: "" })}
              />
            </div>
            <div className="col-span-2">
              <button
                type="button"
                onClick={() => removeLine(i)}
                disabled={lines.length <= 2}
                className="text-xs text-brick-600 hover:underline disabled:text-line"
              >
                حذف السطر
              </button>
            </div>
          </div>
        ))}
      </div>

      <button type="button" onClick={addLine} className="text-sm text-copper-600 hover:underline">
        + إضافة سطر
      </button>

      <div className="flex items-center justify-between border-t border-line pt-3">
        <div className="num text-sm">
          <span className={totals.isBalanced ? "text-ledger-700" : "text-brick-600"}>
            مدين {formatAmount(totals.debit)} / دائن {formatAmount(totals.credit)}
          </span>
        </div>
        <Button type="submit" disabled={isSubmitting || !totals.isBalanced}>
          {isSubmitting ? "جارِ الترحيل…" : "ترحيل القيد"}
        </Button>
      </div>
    </form>
  );
}
