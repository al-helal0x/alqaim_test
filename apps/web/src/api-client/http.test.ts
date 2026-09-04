import { describe, expect, it } from "vitest";
import { formatValidationErrors } from "./http";

/**
 * تغطية QA_FINDINGS #3 (مدة سداد سالبة → رسالة 422 خام "طلب فاشل: 422").
 * السبب الجذري الفعلي: `detail` في استجابة FastAPI/Pydantic 422 مصفوفة
 * `[{loc, msg, type}]`، وليس نصاً واحداً — كان الكود القديم يتحقق فقط من
 * `typeof data?.detail === "string"` فيتجاهل الشكل الحقيقي تماماً.
 */
describe("formatValidationErrors (QA_FINDINGS #3)", () => {
  it("يستخرج اسم الحقل من نهاية loc متجاهلاً body/query/path", () => {
    const message = formatValidationErrors([
      { loc: ["body", "payment_terms_days"], msg: "ensure this value is greater than or equal to 0" },
    ]);
    expect(message).toContain("payment_terms_days");
    expect(message).toContain("ensure this value is greater than or equal to 0");
    expect(message).not.toBe("طلب فاشل: 422");
  });

  it("يجمع عدة أخطاء حقول بفاصلة عربية", () => {
    const message = formatValidationErrors([
      { loc: ["body", "payment_terms_days"], msg: "خطأ 1" },
      { loc: ["body", "email"], msg: "خطأ 2" },
    ]);
    expect(message).toContain("payment_terms_days: خطأ 1");
    expect(message).toContain("email: خطأ 2");
  });

  it("يرجع رسالة عربية عامة معقولة إن كانت loc غائبة", () => {
    const message = formatValidationErrors([{ msg: "قيمة غير صالحة" }]);
    expect(message).toBe("بيانات غير صالحة — قيمة غير صالحة");
  });

  it("لا ينهار على مصفوفة فارغة", () => {
    expect(formatValidationErrors([])).toBe("بيانات غير صالحة");
  });
});
