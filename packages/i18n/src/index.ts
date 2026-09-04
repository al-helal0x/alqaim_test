import ar from "../ar/common.json";
import en from "../en/common.json";

export type Locale = "ar" | "en";

export const DEFAULT_LOCALE: Locale = "ar";

export const LOCALE_DIRECTION: Record<Locale, "rtl" | "ltr"> = {
  ar: "rtl",
  en: "ltr",
};

const DICTIONARIES: Record<Locale, Record<string, string>> = { ar, en };

export type TranslationKey = keyof typeof ar;

/**
 * يعيد النص المترجَم لمفتاح معطى. يسقط تلقائياً إلى العربية إن كان المفتاح
 * غير موجود في قاموس اللغة المطلوبة (لا نص مكسور أبداً)، ثم إلى المفتاح
 * نفسه كملاذ أخير — حتى لا تتوقف الواجهة عن العمل بسبب ترجمة ناقصة.
 */
export function t(key: TranslationKey, locale: Locale = DEFAULT_LOCALE): string {
  return DICTIONARIES[locale]?.[key] ?? DICTIONARIES.ar[key] ?? key;
}

export function getDictionary(locale: Locale = DEFAULT_LOCALE): Record<string, string> {
  return DICTIONARIES[locale] ?? DICTIONARIES.ar;
}
