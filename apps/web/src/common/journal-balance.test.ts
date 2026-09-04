import { describe, expect, it } from "vitest";
import { computeJournalTotals } from "./journal-balance";

describe("computeJournalTotals", () => {
  it("marks a balanced entry as balanced", () => {
    const totals = computeJournalTotals([
      { debit: "1000", credit: "0" },
      { debit: "0", credit: "1000" },
    ]);
    expect(totals.debit).toBe(1000);
    expect(totals.credit).toBe(1000);
    expect(totals.isBalanced).toBe(true);
  });

  it("marks an unbalanced entry as not balanced", () => {
    const totals = computeJournalTotals([
      { debit: "1000", credit: "0" },
      { debit: "0", credit: "999" },
    ]);
    expect(totals.isBalanced).toBe(false);
  });

  it("treats an all-zero entry as not balanced (nothing to post)", () => {
    const totals = computeJournalTotals([
      { debit: "0", credit: "0" },
      { debit: "", credit: "" },
    ]);
    expect(totals.isBalanced).toBe(false);
  });

  it("ignores non-numeric input safely instead of throwing", () => {
    const totals = computeJournalTotals([
      { debit: "abc", credit: "0" },
      { debit: "0", credit: "0" },
    ]);
    expect(totals.debit).toBe(0);
    expect(totals.isBalanced).toBe(false);
  });

  it("sums multiple lines on each side correctly", () => {
    const totals = computeJournalTotals([
      { debit: "600", credit: "0" },
      { debit: "400", credit: "0" },
      { debit: "0", credit: "1000" },
    ]);
    expect(totals.debit).toBe(1000);
    expect(totals.credit).toBe(1000);
    expect(totals.isBalanced).toBe(true);
  });
});
