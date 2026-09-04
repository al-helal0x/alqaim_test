"use client";

/**
 * يُستدعى من داخل أي صفحة تريد الاستجابة لاختصارات الفعل العامة
 * (Ctrl+N / Ctrl+S / Esc). التسجيل يُزال تلقائياً عند مغادرة الصفحة حتى لا
 * يبقى معالِج شاشة سابقة فعّالاً بالخطأ.
 *
 * مثال استخدام (انظر journal-entries/page.tsx للتطبيق الفعلي):
 *
 *   usePageShortcuts({
 *     onNew: () => setShowForm(true),
 *     onCancel: showForm ? () => setShowForm(false) : undefined,
 *   });
 */

import { useEffect } from "react";
import { useShortcutContext } from "./shortcut-context";

export type PageShortcutHandlers = {
  onNew?: () => void;
  onSave?: () => void;
  onCancel?: () => void;
  /** Alt+8 (توافق مع F8 في الأمين) */
  onDelete?: () => void;
  /** Alt+6 (توافق مع F6 في الأمين). بلا تسجيل، Alt+6 يستدعي window.print(). */
  onPrint?: () => void;
  /** Alt+9 (توافق مع F9 في الأمين — "ترحيل" منفصل عن "حفظ"). إن لم يُسجَّل،
   *  Alt+9 يسقط تلقائياً إلى onSave. */
  onPost?: () => void;
};

export function usePageShortcuts({ onNew, onSave, onCancel, onDelete, onPrint, onPost }: PageShortcutHandlers) {
  const {
    registerNewHandler,
    registerSaveHandler,
    registerCancelHandler,
    registerDeleteHandler,
    registerPrintHandler,
    registerPostHandler,
  } = useShortcutContext();

  useEffect(() => {
    registerNewHandler(onNew ?? null);
    return () => registerNewHandler(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onNew]);

  useEffect(() => {
    registerSaveHandler(onSave ?? null);
    return () => registerSaveHandler(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onSave]);

  useEffect(() => {
    registerCancelHandler(onCancel ?? null);
    return () => registerCancelHandler(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onCancel]);

  useEffect(() => {
    registerDeleteHandler(onDelete ?? null);
    return () => registerDeleteHandler(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onDelete]);

  useEffect(() => {
    registerPrintHandler(onPrint ?? null);
    return () => registerPrintHandler(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onPrint]);

  useEffect(() => {
    registerPostHandler(onPost ?? null);
    return () => registerPostHandler(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onPost]);
}
