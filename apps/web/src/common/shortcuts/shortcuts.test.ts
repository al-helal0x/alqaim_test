import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { handleGridKeyDown, type GridActions } from "./use-grid-shortcuts";
import { AL_AMIN_COMPAT_KEYS, GLOBAL_ACTION_KEYS, HOME_SHORTCUT, NAV_SHORTCUTS, VISIBLE_NAV_SHORTCUTS } from "./registry";

/**
 * بيئة الاختبار node بلا DOM (vitest.config.ts، نفس قيد server-config.test.ts)
 * — findRowIndex في use-grid-shortcuts.ts يفحص `target instanceof HTMLElement`،
 * فبلا تعريف HTMLElement عالمياً يرمي ReferenceError مباشرة. نُعرِّف صنفاً
 * وهمياً أصغر ما يكفي (closest + dataset) بدل إضافة jsdom كتبعية جديدة لملف
 * واحد، ونثبّته على `globalThis.HTMLElement` طوال هذا الملف فقط.
 */
class FakeHTMLElement {
  dataset: Record<string, string> = {};
  private parent: FakeHTMLElement | null = null;
  private hasGridRow = false;

  withGridRow(row: number): this {
    this.hasGridRow = true;
    this.dataset.gridRow = String(row);
    return this;
  }

  withParent(parent: FakeHTMLElement): this {
    this.parent = parent;
    return this;
  }

  closest(selector: string): FakeHTMLElement | null {
    if (selector !== "[data-grid-row]") return null;
    return this.findAncestorWithGridRow();
  }

  private findAncestorWithGridRow(): FakeHTMLElement | null {
    if (this.hasGridRow) return this;
    return this.parent ? this.parent.findAncestorWithGridRow() : null;
  }
}

let originalHTMLElement: unknown;

beforeAll(() => {
  originalHTMLElement = (globalThis as Record<string, unknown>).HTMLElement;
  (globalThis as Record<string, unknown>).HTMLElement = FakeHTMLElement;
});

afterAll(() => {
  (globalThis as Record<string, unknown>).HTMLElement = originalHTMLElement;
});

/**
 * KeyboardEvent وهمي بأدنى ما يحتاجه handleGridKeyDown فعلياً.
 */
function fakeGridEvent(
  key: string,
  opts: { ctrlKey?: boolean; targetRow?: number } = {}
): Parameters<typeof handleGridKeyDown>[0] {
  const target = new FakeHTMLElement();
  if (opts.targetRow !== undefined) target.withGridRow(opts.targetRow);
  return {
    key,
    ctrlKey: opts.ctrlKey ?? false,
    metaKey: false,
    target,
    preventDefault: vi.fn(),
  } as unknown as Parameters<typeof handleGridKeyDown>[0];
}

describe("handleGridKeyDown (شبكة القيود/الفواتير)", () => {
  it("Insert بلا Ctrl يضيف سطراً", () => {
    const addRow = vi.fn();
    const actions: GridActions = { addRow, removeRow: vi.fn(), currentRowCount: 2 };
    const e = fakeGridEvent("Insert");
    handleGridKeyDown(e, actions);
    expect(addRow).toHaveBeenCalledOnce();
    expect(e.preventDefault).toHaveBeenCalledOnce();
  });

  it("Ctrl+Delete يحذف السطر الذي فيه التركيز الحالي", () => {
    const removeRow = vi.fn();
    const actions: GridActions = { addRow: vi.fn(), removeRow, currentRowCount: 3 };
    const e = fakeGridEvent("Delete", { ctrlKey: true, targetRow: 1 });
    handleGridKeyDown(e, actions);
    expect(removeRow).toHaveBeenCalledWith(1);
  });

  it("Ctrl+Delete لا يحذف تحت minRows (يحمي القيد من صفر أسطر)", () => {
    const removeRow = vi.fn();
    const actions: GridActions = { addRow: vi.fn(), removeRow, currentRowCount: 2, minRows: 2 };
    const e = fakeGridEvent("Delete", { ctrlKey: true, targetRow: 0 });
    handleGridKeyDown(e, actions);
    expect(removeRow).not.toHaveBeenCalled();
  });

  it("Ctrl+Enter يرحّل/يحفظ عبر submit", () => {
    const submit = vi.fn();
    const actions: GridActions = { addRow: vi.fn(), removeRow: vi.fn(), currentRowCount: 2, submit };
    const e = fakeGridEvent("Enter", { ctrlKey: true });
    handleGridKeyDown(e, actions);
    expect(submit).toHaveBeenCalledOnce();
  });

  it("Delete المفرد (بلا Ctrl) لا يفعل شيئاً — يُترك لحذف نص الحقل نفسه", () => {
    const removeRow = vi.fn();
    const actions: GridActions = { addRow: vi.fn(), removeRow, currentRowCount: 2 };
    const e = fakeGridEvent("Delete", { targetRow: 0 });
    handleGridKeyDown(e, actions);
    expect(removeRow).not.toHaveBeenCalled();
  });
});

/**
 * README.md لهذه الميزة ينص صراحة: "NAV_SHORTCUTS في registry.ts مقصود أن
 * يبقى مطابقاً 1:1 لبنية NAV_SECTIONS في app-shell.tsx... وإلا ستفقد الشاشة
 * الجديدة اختصار الانتقال السريع إليها". هذا الاختبار يفرض ذلك آلياً بدل
 * الاعتماد على تعليق نصي يُنسى — أي شاشة تُضاف/تُحذف من القائمة الجانبية
 * بلا تحديث registry.ts تُسقِط هذا الاختبار فوراً في CI.
 *
 * app-shell.tsx مكوّن "use client" يستورد سلسلة طويلة من وحدات مُعرَّفة
 * بـ`@/` (auth-context، إلخ) لا يحلّها vitest حالياً (لا jsdom ولا alias
 * resolution مُهيَّأين في vitest.config.ts — نفس القيد الذي يجعل كل اختبار
 * آخر في المشروع منطقاً صِرفاً بلا مكوّنات React). بدل إضافة بنية اختبار
 * مكوّنات جديدة للمشروع من أجل هذا الاختبار وحده، نقرأ NAV_SECTIONS نصياً
 * من ملف app-shell.tsx مباشرة (نفس أسلوب فحص التزامن اليدوي الذي أُجري قبل
 * الدمج، لكن بصورة آلية دائمة الآن).
 */
describe("مزامنة registry.ts مع app-shell.tsx (قاعدة الصيانة الموثَّقة في README)", () => {
  const appShellPath = join(dirname(fileURLToPath(import.meta.url)), "..", "app-shell.tsx");
  const appShellSource = readFileSync(appShellPath, "utf-8");
  const shellHrefs = Array.from(appShellSource.matchAll(/href:\s*"([^"]+)"/g)).map((m) => m[1]);

  it("app-shell.tsx يحتوي فعلاً روابط قابلة للقراءة (الاختبار نفسه ليس معطَّلاً بصمت)", () => {
    expect(shellHrefs.length).toBeGreaterThan(0);
  });

  it("كل رابط في القائمة الجانبية له اختصار G+حرف مقابل في registry.ts", () => {
    const registryHrefs = new Set(VISIBLE_NAV_SHORTCUTS.map((s) => s.href));
    for (const href of shellHrefs) {
      expect(registryHrefs.has(href)).toBe(true);
    }
  });

  it("registry.ts لا يحتوي روابط زائدة غير موجودة في القائمة الجانبية", () => {
    const shellSet = new Set(shellHrefs);
    for (const shortcut of VISIBLE_NAV_SHORTCUTS) {
      expect(shellSet.has(shortcut.href)).toBe(true);
    }
  });

  it("كل حروف goToKey فريدة عبر القائمة الكاملة (بلا HOME_SHORTCUT مكرَّراً)", () => {
    const keys = NAV_SHORTCUTS.map((s) => s.goToKey);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("HOME_SHORTCUT (G ثم H) لا يتصادم مع أي حرف انتقال آخر", () => {
    expect(VISIBLE_NAV_SHORTCUTS.some((s) => s.goToKey === HOME_SHORTCUT.goToKey)).toBe(false);
  });
});

/**
 * طبقة "توافق الأمين" (Alt+2/3/5/6/8/9) الجديدة — README.md وregistry.ts
 * يوثّقان صراحة تعيين كل رقم لنفس مفتاح F الذي يقابله في الأمين. هذا
 * الاختبار يتحقق أن الأرقام الموثَّقة في AL_AMIN_COMPAT_KEYS تطابق فعلاً
 * الأرقام المستخدَمة في GLOBAL_ACTION_KEYS للفعل المكافئ (new/save/print/
 * delete/post) — بدل الاعتماد على تطابق يدوي بين ملفين قد ينحرف بصمت.
 */
describe("طبقة توافق الأمين (Alt+2/3/5/6/8/9)", () => {
  it("كل رقم Al-Ameen يطابق رقماً واحداً فقط، بلا تكرار", () => {
    const digits = Object.values(AL_AMIN_COMPAT_KEYS).map((v) => v.replace("Alt+", ""));
    expect(new Set(digits).size).toBe(digits.length);
  });

  it("delete/print/post في GLOBAL_ACTION_KEYS (المعروضة كـ Alt+رقم) تطابق نفس رقم AL_AMIN_COMPAT_KEYS المقابل", () => {
    // new/save في GLOBAL_ACTION_KEYS تُعرَض بمرادفها Ctrl+N/Ctrl+S عمداً (له
    // مكافئ عالمي)، لا برقم الأمين — فقط delete/print/post ليس لها مرادف
    // Ctrl عالمي فتُعرَض مباشرة كـ"Alt + رقم"، لذا تقتصر المقارنة عليها.
    const pairs: [keyof typeof GLOBAL_ACTION_KEYS, keyof typeof AL_AMIN_COMPAT_KEYS][] = [
      ["print", "print"],
      ["delete", "delete"],
      ["post", "post"],
    ];
    for (const [globalKey, alaminKey] of pairs) {
      const globalDigit = GLOBAL_ACTION_KEYS[globalKey].match(/\d/)?.[0];
      const alaminDigit = AL_AMIN_COMPAT_KEYS[alaminKey].match(/\d/)?.[0];
      expect(globalDigit).toBeDefined();
      expect(globalDigit).toBe(alaminDigit);
    }
  });
});
