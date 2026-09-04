"use client";

/**
 * سلوك "شبكة الإدخال" المستخدَم في شاشات القيود/الفواتير متعددة الأسطر —
 * يُحاكي تجربة الأمين وإكسل داخل جدول واحد بدل اختصارات عامة على مستوى
 * الصفحة كلها:
 *
 *   Insert          → إضافة سطر جديد (بدل الضغط يدوياً على "+ إضافة سطر")
 *   Ctrl/⌘+Delete   → حذف السطر الذي يحوي التركيز الحالي
 *   Ctrl/⌘+Enter    → ترحيل/حفظ الفورمة مباشرة من أي حقل داخل الشبكة
 *
 * يُطبَّق عبر onKeyDown على عنصر الحاوية (fieldset/div) المحيط بالجدول، لا
 * على النافذة كلها — حتى لا يتعارض مع Insert/Delete في شاشات أخرى.
 *
 * مثال:
 *   <div onKeyDown={(e) => handleGridKeyDown(e, { addRow, removeRow, submit, currentRowCount, minRows })}>
 */

import type { KeyboardEvent } from "react";

export type GridActions = {
  addRow: () => void;
  removeRow: (rowIndex: number) => void;
  submit?: () => void;
  /** أقل عدد أسطر مسموح به (لا يُحذف تحته) — افتراضياً 1 */
  minRows?: number;
  currentRowCount: number;
};

/**
 * يحدّد رقم السطر الذي يحوي عنصر التركيز الحالي عبر أقرب `data-grid-row`.
 */
function findRowIndex(target: EventTarget | null): number | null {
  if (!(target instanceof HTMLElement)) return null;
  const rowEl = target.closest<HTMLElement>("[data-grid-row]");
  if (!rowEl) return null;
  const idx = Number(rowEl.dataset.gridRow);
  return Number.isNaN(idx) ? null : idx;
}

export function handleGridKeyDown(e: KeyboardEvent<HTMLElement>, actions: GridActions) {
  const meta = e.ctrlKey || e.metaKey;
  const minRows = actions.minRows ?? 1;

  if (e.key === "Insert" && !meta) {
    e.preventDefault();
    actions.addRow();
    return;
  }

  if (meta && e.key === "Delete") {
    if (actions.currentRowCount <= minRows) return;
    const rowIndex = findRowIndex(e.target);
    if (rowIndex !== null) {
      e.preventDefault();
      actions.removeRow(rowIndex);
    }
    return;
  }

  if (meta && e.key === "Enter" && actions.submit) {
    e.preventDefault();
    actions.submit();
  }
}
