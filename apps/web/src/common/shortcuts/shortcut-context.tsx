"use client";

/**
 * سياق React خفيف يتيح لأي صفحة أن "تسجّل" معالِج فعل عام (سجل جديد / حفظ /
 * إلغاء) بدون أن تعرف شيئاً عن مستمع لوحة المفاتيح العام. هذا يطابق فلسفة
 * برامج المحاسبة الكلاسيكية حيث Ctrl+N/Ctrl+S تعمل دائماً بنفس المعنى
 * مهما كانت الشاشة المفتوحة، لكن كل شاشة تملأ التفاصيل الخاصة بها.
 *
 * صفحة لا تسجّل معالِجاً؟ الاختصار المطابق يُتجاهَل بصمت (لا خطأ) — انظر
 * use-global-shortcuts.ts.
 */

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

type Handler = () => void;

type ShortcutContextValue = {
  registerNewHandler: (fn: Handler | null) => void;
  registerSaveHandler: (fn: Handler | null) => void;
  registerCancelHandler: (fn: Handler | null) => void;
  registerDeleteHandler: (fn: Handler | null) => void;
  registerPrintHandler: (fn: Handler | null) => void;
  registerPostHandler: (fn: Handler | null) => void;
  triggerNew: () => boolean;
  triggerSave: () => boolean;
  triggerCancel: () => boolean;
  triggerDelete: () => boolean;
  triggerPrint: () => boolean;
  /** يسقط تلقائياً إلى triggerSave إن لم تسجّل الشاشة معالِج "ترحيل" مستقلاً
   *  عن "حفظ" — في أغلب شاشاتنا الحالية الفعلان متطابقان (زر واحد). */
  triggerPost: () => boolean;
  isPaletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;
  isHelpOpen: boolean;
  setHelpOpen: (open: boolean) => void;
};

const ShortcutContext = createContext<ShortcutContextValue | null>(null);

export function ShortcutProvider({ children }: { children: ReactNode }) {
  const newHandlerRef = useRef<Handler | null>(null);
  const saveHandlerRef = useRef<Handler | null>(null);
  const cancelHandlerRef = useRef<Handler | null>(null);
  const deleteHandlerRef = useRef<Handler | null>(null);
  const printHandlerRef = useRef<Handler | null>(null);
  const postHandlerRef = useRef<Handler | null>(null);
  const [isPaletteOpen, setPaletteOpen] = useState(false);
  const [isHelpOpen, setHelpOpen] = useState(false);

  const registerNewHandler = useCallback((fn: Handler | null) => {
    newHandlerRef.current = fn;
  }, []);
  const registerSaveHandler = useCallback((fn: Handler | null) => {
    saveHandlerRef.current = fn;
  }, []);
  const registerCancelHandler = useCallback((fn: Handler | null) => {
    cancelHandlerRef.current = fn;
  }, []);
  const registerDeleteHandler = useCallback((fn: Handler | null) => {
    deleteHandlerRef.current = fn;
  }, []);
  const registerPrintHandler = useCallback((fn: Handler | null) => {
    printHandlerRef.current = fn;
  }, []);
  const registerPostHandler = useCallback((fn: Handler | null) => {
    postHandlerRef.current = fn;
  }, []);

  const triggerNew = useCallback(() => {
    if (!newHandlerRef.current) return false;
    newHandlerRef.current();
    return true;
  }, []);
  const triggerSave = useCallback(() => {
    if (!saveHandlerRef.current) return false;
    saveHandlerRef.current();
    return true;
  }, []);
  const triggerCancel = useCallback(() => {
    if (!cancelHandlerRef.current) return false;
    cancelHandlerRef.current();
    return true;
  }, []);
  const triggerDelete = useCallback(() => {
    if (!deleteHandlerRef.current) return false;
    deleteHandlerRef.current();
    return true;
  }, []);
  const triggerPrint = useCallback(() => {
    if (printHandlerRef.current) {
      printHandlerRef.current();
      return true;
    }
    // لا معالِج مسجَّل من الصفحة الحالية؟ اطبع نافذة المتصفح كسلوك افتراضي
    // معقول (بدل تجاهل الاختصار بصمت).
    window.print();
    return true;
  }, []);
  const triggerPost = useCallback(() => {
    if (postHandlerRef.current) {
      postHandlerRef.current();
      return true;
    }
    // بلا معالِج "ترحيل" مستقل، الترحيل والحفظ فعل واحد في أغلب شاشاتنا.
    if (!saveHandlerRef.current) return false;
    saveHandlerRef.current();
    return true;
  }, []);

  return (
    <ShortcutContext.Provider
      value={{
        registerNewHandler,
        registerSaveHandler,
        registerCancelHandler,
        registerDeleteHandler,
        registerPrintHandler,
        registerPostHandler,
        triggerNew,
        triggerSave,
        triggerCancel,
        triggerDelete,
        triggerPrint,
        triggerPost,
        isPaletteOpen,
        setPaletteOpen,
        isHelpOpen,
        setHelpOpen,
      }}
    >
      {children}
    </ShortcutContext.Provider>
  );
}

export function useShortcutContext(): ShortcutContextValue {
  const ctx = useContext(ShortcutContext);
  if (!ctx) {
    throw new Error("useShortcutContext must be used within <ShortcutProvider>");
  }
  return ctx;
}
