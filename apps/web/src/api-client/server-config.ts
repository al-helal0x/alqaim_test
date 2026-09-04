/**
 * حل عنوان خادم core-api — القسم 6.3/16 (Self-Hosted + Cloud تعيشان جنباً
 * إلى جنب). `NEXT_PUBLIC_API_URL` وحده كافٍ لنشر الويب العادي (Cloud،
 * قيمة واحدة ثابتة وقت البناء لكل عملاء تلك النسخة)، **لكنه غير كافٍ
 * لتوزيع سطح المكتب (العضو 10)**: ثنائي Tauri مُصرَّف مرة واحدة يُوزَّع على
 * آلاف الشركات، وكل شركة Self-Hosted لها عنوان خادمها الخاص — لا يمكن أن
 * يكون العنوان مطبوخاً داخل الثنائي وقت البناء.
 *
 * الحل: عنوان قابل للتهيئة وقت التشغيل (Runtime)، يُخزَّن محلياً (نفس آلية
 * `auth-storage.ts`)، مع تراجع (Fallback) لقيمة البناء العادية — بحيث لا
 * يتغيّر أي سلوك لنشر الويب الحالي إطلاقاً إن لم يُضبَط شيء صراحة.
 */
const SERVER_URL_KEY = "alqaim_api_base_url";
const BUILD_TIME_DEFAULT = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** يُستدعى فقط من مكوّنات "use client" — يُرجع null أثناء SSR/التصدير الساكن. */
export function getConfiguredServerUrl(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(SERVER_URL_KEY);
}

export function getApiBaseUrl(): string {
  return getConfiguredServerUrl() ?? BUILD_TIME_DEFAULT;
}

export function setConfiguredServerUrl(url: string): void {
  if (typeof window === "undefined") return;
  const trimmed = url.trim().replace(/\/+$/, ""); // بلا شرطة مائلة زائدة في النهاية
  window.localStorage.setItem(SERVER_URL_KEY, trimmed);
}

export function clearConfiguredServerUrl(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(SERVER_URL_KEY);
}

/** يكشف تشغيل التطبيق داخل غلاف Tauri لسطح المكتب (وليس متصفحاً عادياً أو PWA).
 * Tauri v2 يحقن `window.__TAURI_INTERNALS__` في كل صفحة يعرضها. */
export function isDesktopRuntime(): boolean {
  if (typeof window === "undefined") return false;
  return "__TAURI_INTERNALS__" in window;
}

/** هل التطبيق (سطح مكتب) يحتاج شاشة "الاتصال بالخادم" أولاً؟ مطلوب فقط
 * حين يكون التشغيل داخل Tauri ولا يوجد عنوان محفوظ مسبقاً — نشر الويب
 * العادي (Cloud) لديه دائماً `NEXT_PUBLIC_API_URL` من البناء فلا يحتاج هذه
 * الشاشة إطلاقاً حتى لو استُدعيت الدالة بالخطأ. */
export function needsServerConnectionSetup(): boolean {
  return isDesktopRuntime() && getConfiguredServerUrl() === null;
}
