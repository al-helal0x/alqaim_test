// ⚠️ ملاحظة تكييف: PART_A_عميل-AI-والمنطق.md الأصلي يصف توقيعات
// applyManualEdit/needsManualReview/toApprovedPayload مبنية على تدفّق
// "Payload اعتماد كامل يبنيه العميل" — وهو التصميم الذي ألغاه العقد الجديد
// صراحةً (00_CONTRACT_مشترك.md ينص: "لا حاجة لبناء Payload... الفاتورة تُنشأ
// خلف confirm في الخلفية"). الدوال هنا تحافظ على **نية** PART_A (تعديل يدوي
// لحقل واحد، تحديد الحاجة لمراجعة، تجهيز شيء جاهز للإرسال) لكن مُكيَّفة لشكل
// البيانات الفعلي: لا "source" داخل AiDraftField نفسه، فالتمييز يدوي/AI هنا
// محلي بالكامل (LocalEdits) حتى لحظة الإرسال الفعلي عبر submitDraftCorrections.
// toApprovedPayload استُبدلت بـ buildCorrections لأنه لا "Payload اعتماد"
// بعد الآن — فقط خريطة تصحيحات مسطّحة.

import type { AiDraftCorrections, AiInvoiceDraft } from "./ai-documents-types";

export type DraftHeaderField = "supplier_name" | "invoice_number" | "invoice_date" | "total_amount";
export type DraftLineField = "description" | "quantity" | "unit_price";

/**
 * التعديلات اليدوية المحلية للشاشة، منفصلة عن AiInvoiceDraft القادم من
 * الخادم (الذي لا يتغيّر محلياً — التصحيحات تُرسَل لاحقاً كخريطة مستقلة).
 */
export type LocalEdits = {
  header: Partial<Record<DraftHeaderField, string>>;
  lines: Record<number, Partial<Record<DraftLineField, string>>>;
  // غير مستخرَجَين من AI إطلاقاً — تُعبَّر عنهما كتصحيح أيضاً بحسب العقد.
  branchId?: string;
  supplierId?: string;
};

export function emptyLocalEdits(): LocalEdits {
  return { header: {}, lines: {} };
}

const HEADER_FIELDS: DraftHeaderField[] = ["supplier_name", "invoice_number", "invoice_date", "total_amount"];
const LINE_FIELDS: DraftLineField[] = ["description", "quantity", "unit_price"];

/** يُعيد نسخة من التعديلات المحلية بعد تعديل حقل رأس واحد يدوياً. */
export function applyManualEdit(edits: LocalEdits, field: DraftHeaderField, value: string): LocalEdits {
  return { ...edits, header: { ...edits.header, [field]: value } };
}

/** يُعيد نسخة من التعديلات المحلية بعد تعديل حقل داخل سطر واحد يدوياً. */
export function applyManualLineEdit(
  edits: LocalEdits,
  lineIndex: number,
  field: DraftLineField,
  value: string
): LocalEdits {
  return {
    ...edits,
    lines: { ...edits.lines, [lineIndex]: { ...edits.lines[lineIndex], [field]: value } },
  };
}

/** القيمة الفعّالة لعرضها في حقل رأس: التعديل المحلي إن وُجد، وإلا قيمة AI الأصلية (أو فارغة). */
export function effectiveHeaderValue(draft: AiInvoiceDraft, edits: LocalEdits, field: DraftHeaderField): string {
  return edits.header[field] ?? draft[field].value ?? "";
}

/** القيمة الفعّالة لعرضها في حقل سطر. */
export function effectiveLineValue(
  draft: AiInvoiceDraft,
  edits: LocalEdits,
  lineIndex: number,
  field: DraftLineField
): string {
  return edits.lines[lineIndex]?.[field] ?? draft.lines[lineIndex]?.[field]?.value ?? "";
}

/**
 * هل تحتاج المسودة مراجعة يدوية قبل السماح بالاعتماد؟ صحيح إذا: المسودة
 * ليست "pending_review" بعد، أو الفرع/المورّد غير مُختارين بعد (حقلان
 * إلزاميان غير مستخرَجَين من AI أصلاً)، أو أي حقل (رأس أو سطر) لا يزال بثقة
 * "low" **بلا تعديل يدوي محلي مطابق له بعد**.
 */
export function needsManualReview(draft: AiInvoiceDraft, edits: LocalEdits): boolean {
  if (draft.status !== "pending_review") return true;
  if (!edits.branchId || !edits.supplierId) return true;

  const headerNeedsReview = HEADER_FIELDS.some(
    (field) => draft[field].confidence === "low" && edits.header[field] === undefined
  );
  if (headerNeedsReview) return true;

  return draft.lines.some((line, index) =>
    LINE_FIELDS.some((field) => line[field].confidence === "low" && edits.lines[index]?.[field] === undefined)
  );
}

/**
 * يبني خريطة corrections المسطّحة الجاهزة لِـ submitDraftCorrections من كل
 * التعديلات المحلية (رأس + أسطر + فرع/مورّد). الشاشة (الجزء ب) لا تتعامل مع
 * تسمية المفاتيح مباشرة، فقط تستدعي هذه الدالة — أي تعديل على تسمية المفاتيح
 * (نقطة مفتوحة معلَنة في العقد) يقتصر عليها هي وحدها.
 */
export function buildCorrections(edits: LocalEdits): AiDraftCorrections {
  const corrections: AiDraftCorrections = {};

  for (const [field, value] of Object.entries(edits.header)) {
    corrections[field] = value as string;
  }

  for (const [lineIndex, lineEdits] of Object.entries(edits.lines)) {
    for (const [field, value] of Object.entries(lineEdits)) {
      corrections[`lines[${lineIndex}].${field}`] = value as string;
    }
  }

  if (edits.branchId) corrections.branch_id = edits.branchId;
  if (edits.supplierId) corrections.supplier_id = edits.supplierId;

  return corrections;
}
