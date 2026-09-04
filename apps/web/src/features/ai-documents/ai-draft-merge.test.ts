import { describe, expect, it } from "vitest";
import {
  applyManualEdit,
  applyManualLineEdit,
  buildCorrections,
  emptyLocalEdits,
  needsManualReview,
  type LocalEdits,
} from "./ai-draft-merge";
import type { AiInvoiceDraft } from "./ai-documents-types";

function makeDraft(overrides: Partial<AiInvoiceDraft> = {}): AiInvoiceDraft {
  return {
    draft_id: "draft-1",
    status: "pending_review",
    supplier_name: { value: "شركة الفرات", confidence: "high" },
    invoice_number: { value: "INV-100", confidence: "high" },
    invoice_date: { value: "2026-08-01", confidence: "high" },
    total_amount: { value: "1500.00", confidence: "high" },
    lines: [
      {
        description: { value: "أسمنت", confidence: "high" },
        quantity: { value: "10", confidence: "high" },
        unit_price: { value: "150.00", confidence: "high" },
      },
    ],
    ...overrides,
  };
}

describe("needsManualReview", () => {
  it("لا تحتاج مراجعة عندما كل الحقول high والفرع/المورّد مُختاران", () => {
    const draft = makeDraft();
    const edits = { ...emptyLocalEdits(), branchId: "b1", supplierId: "s1" };
    expect(needsManualReview(draft, edits)).toBe(false);
  });

  it("تحتاج مراجعة عند وجود حقل رأس واحد بثقة low بلا تعديل يدوي", () => {
    const draft = makeDraft({ invoice_number: { value: "INV-100", confidence: "low" } });
    const edits = { ...emptyLocalEdits(), branchId: "b1", supplierId: "s1" };
    expect(needsManualReview(draft, edits)).toBe(true);
  });

  it("تحتاج مراجعة عند وجود حقل سطر بثقة low بلا تعديل يدوي", () => {
    const draft = makeDraft({
      lines: [
        {
          description: { value: "أسمنت", confidence: "low" },
          quantity: { value: "10", confidence: "high" },
          unit_price: { value: "150.00", confidence: "high" },
        },
      ],
    });
    const edits = { ...emptyLocalEdits(), branchId: "b1", supplierId: "s1" };
    expect(needsManualReview(draft, edits)).toBe(true);
  });

  it("لا تعود بحاجة لمراجعة بعد تعديل يدوي يغطي الحقل الضعيف (رأس)", () => {
    const draft = makeDraft({ invoice_number: { value: "INV-100", confidence: "low" } });
    let edits: LocalEdits = { ...emptyLocalEdits(), branchId: "b1", supplierId: "s1" };
    edits = applyManualEdit(edits, "invoice_number", "INV-100-CORRECTED");
    expect(needsManualReview(draft, edits)).toBe(false);
  });

  it("لا تعود بحاجة لمراجعة بعد تعديل يدوي يغطي الحقل الضعيف (سطر)", () => {
    const draft = makeDraft({
      lines: [
        {
          description: { value: "أسمنت", confidence: "low" },
          quantity: { value: "10", confidence: "high" },
          unit_price: { value: "150.00", confidence: "high" },
        },
      ],
    });
    let edits: LocalEdits = { ...emptyLocalEdits(), branchId: "b1", supplierId: "s1" };
    edits = applyManualLineEdit(edits, 0, "description", "أسمنت (مصحَّح)");
    expect(needsManualReview(draft, edits)).toBe(false);
  });

  it("تحتاج مراجعة دائماً ما دام الفرع أو المورّد غير مُختارين، حتى لو كل الحقول high", () => {
    const draft = makeDraft();
    expect(needsManualReview(draft, emptyLocalEdits())).toBe(true);
    expect(needsManualReview(draft, { ...emptyLocalEdits(), branchId: "b1" })).toBe(true);
  });

  it("تحتاج مراجعة ما دامت حالة المسودة ليست pending_review", () => {
    const draft = makeDraft({ status: "confirmed" });
    const edits = { ...emptyLocalEdits(), branchId: "b1", supplierId: "s1" };
    expect(needsManualReview(draft, edits)).toBe(true);
  });
});

describe("buildCorrections", () => {
  it("يحوّل تعديلات الرأس والفرع/المورّد بمفاتيح مسطّحة صحيحة", () => {
    let edits = emptyLocalEdits();
    edits = applyManualEdit(edits, "invoice_number", "INV-200");
    edits = { ...edits, branchId: "branch-1", supplierId: "supplier-1" };

    const corrections = buildCorrections(edits);
    expect(corrections.invoice_number).toBe("INV-200");
    expect(corrections.branch_id).toBe("branch-1");
    expect(corrections.supplier_id).toBe("supplier-1");
  });

  it("يحوّل تعديلات أسطر متعددة بمفاتيح lines[index].field صحيحة", () => {
    let edits = emptyLocalEdits();
    edits = applyManualLineEdit(edits, 0, "quantity", "5");
    edits = applyManualLineEdit(edits, 1, "unit_price", "99.50");

    const corrections = buildCorrections(edits);
    expect(corrections["lines[0].quantity"]).toBe("5");
    expect(corrections["lines[1].unit_price"]).toBe("99.50");
  });

  it("لا يُدرج مفاتيح لحقول لم تُعدَّل يدوياً إطلاقاً", () => {
    const corrections = buildCorrections(emptyLocalEdits());
    expect(Object.keys(corrections)).toHaveLength(0);
  });
});
