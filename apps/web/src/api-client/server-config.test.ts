import { afterEach, beforeEach, describe, expect, it } from "vitest";

/**
 * بيئة الاختبار node بلا DOM (vitest.config.ts) — بدل إضافة jsdom كتبعية
 * جديدة لملف واحد، نحاكي أصغر جزء من window يحتاجه server-config.ts فعلياً:
 * localStorage + وجود/غياب __TAURI_INTERNALS__. هذا يطابق تماماً ما تفحصه
 * الدالة الحقيقية (`"__TAURI_INTERNALS__" in window`), وليس تبسيطاً مخلاً.
 */
function installFakeWindow(hasTauri: boolean): void {
  const store = new Map<string, string>();
  const fakeWindow: Record<string, unknown> = {
    localStorage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
      removeItem: (key: string) => void store.delete(key),
    },
  };
  if (hasTauri) fakeWindow.__TAURI_INTERNALS__ = {};
  // @ts-expect-error -- تعريف مُتعمَّد لمحاكاة بيئة متصفح/Tauri داخل بيئة node
  globalThis.window = fakeWindow;
}

function uninstallFakeWindow(): void {
  // @ts-expect-error -- تفكيك المحاكاة بعد كل اختبار لعزل الحالات عن بعضها
  delete globalThis.window;
}

describe("server-config (desktop runtime — العضو 10)", () => {
  afterEach(() => {
    uninstallFakeWindow();
  });

  it("لا يعتبر الجلسة تشغيل سطح مكتب في نشر الويب العادي (بلا __TAURI_INTERNALS__)", async () => {
    installFakeWindow(false);
    const { isDesktopRuntime, needsServerConnectionSetup } = await import("./server-config");
    expect(isDesktopRuntime()).toBe(false);
    expect(needsServerConnectionSetup()).toBe(false);
  });

  it("لا يحتاج شاشة الاتصال إن كان عنوان الخادم محفوظاً مسبقاً على سطح المكتب", async () => {
    installFakeWindow(true);
    const { setConfiguredServerUrl, needsServerConnectionSetup } = await import(
      "./server-config"
    );
    setConfiguredServerUrl("https://erp.example.com");
    expect(needsServerConnectionSetup()).toBe(false);
  });

  it("يحتاج شاشة الاتصال على سطح المكتب بلا عنوان محفوظ", async () => {
    installFakeWindow(true);
    const { needsServerConnectionSetup } = await import("./server-config");
    expect(needsServerConnectionSetup()).toBe(true);
  });

  it("يزيل الشرطة المائلة الزائدة من نهاية العنوان المحفوظ", async () => {
    installFakeWindow(true);
    const { setConfiguredServerUrl, getConfiguredServerUrl } = await import("./server-config");
    setConfiguredServerUrl("https://erp.example.com///");
    expect(getConfiguredServerUrl()).toBe("https://erp.example.com");
  });

  it("getApiBaseUrl يستخدم العنوان المحفوظ محلياً إن وُجد، بدل قيمة البناء", async () => {
    installFakeWindow(true);
    const { setConfiguredServerUrl, getApiBaseUrl } = await import("./server-config");
    setConfiguredServerUrl("https://tenant.example.com");
    expect(getApiBaseUrl()).toBe("https://tenant.example.com");
  });

  it("clearConfiguredServerUrl يعيد الحاجة لشاشة الاتصال من جديد", async () => {
    installFakeWindow(true);
    const { setConfiguredServerUrl, clearConfiguredServerUrl, needsServerConnectionSetup } =
      await import("./server-config");
    setConfiguredServerUrl("https://erp.example.com");
    expect(needsServerConnectionSetup()).toBe(false);
    clearConfiguredServerUrl();
    expect(needsServerConnectionSetup()).toBe(true);
  });
});
