"use client";

/**
 * المستمع العام الوحيد للوحة المفاتيح — يُركَّب مرة واحدة في app-shell.tsx.
 *
 * قواعد أساسية (لتفادي كسر تجربة الكتابة العادية):
 * 1) أي اختصار من حرف واحد (مثل "g" أو "?") يُتجاهل كلياً إن كان التركيز
 *    داخل حقل إدخال/نص/select (input/textarea/select/[contenteditable]) —
 *    تماماً كسلوك Gmail وLinear. أما Ctrl/⌘+K وCtrl/⌘+S وCtrl/⌘+N وEsc
 *    فتعمل حتى داخل الحقول لأنها تحمل مُعدِّلاً (modifier) لا يتعارض مع
 *    الكتابة العادية.
 * 2) لا نستخدم أبداً مفاتيح F المحجوزة من المتصفح (F1/F3/F5/F12...).
 * 3) تتابع "G ثم حرف" له نافذة زمنية قصيرة (900ms) ويُصفَّر فوراً بأي مفتاح
 *    آخر — لا يتراكم عبر ثوانٍ طويلة.
 */

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { HOME_SHORTCUT, VISIBLE_NAV_SHORTCUTS } from "./registry";
import { useShortcutContext } from "./shortcut-context";

const GO_SEQUENCE_TIMEOUT_MS = 900;

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}

export function useGlobalShortcuts() {
  const router = useRouter();
  const {
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
  } = useShortcutContext();

  const pendingGoRef = useRef(false);
  const goTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function clearPendingGo() {
      pendingGoRef.current = false;
      if (goTimerRef.current) {
        clearTimeout(goTimerRef.current);
        goTimerRef.current = null;
      }
    }

    function handleKeyDown(e: KeyboardEvent) {
      const meta = e.ctrlKey || e.metaKey;
      const typing = isTypingTarget(e.target);

      // --- Esc: يعمل دائماً، حتى داخل الحقول، ويُغلق أعلى طبقة مفتوحة أولاً
      if (e.key === "Escape") {
        if (isPaletteOpen) {
          setPaletteOpen(false);
          return;
        }
        if (isHelpOpen) {
          setHelpOpen(false);
          return;
        }
        triggerCancel();
        clearPendingGo();
        return;
      }

      // --- Ctrl/⌘+K: لوحة الانتقال السريع — تعمل حتى داخل الحقول
      if (meta && !e.shiftKey && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setPaletteOpen(!isPaletteOpen);
        return;
      }

      // --- Ctrl/⌘+N: سجل جديد في الشاشة الحالية
      if (meta && !e.shiftKey && (e.key === "n" || e.key === "N")) {
        if (triggerNew()) e.preventDefault();
        return;
      }

      // --- Ctrl/⌘+S: حفظ الفورمة المفتوحة (نمنع حفظ صفحة المتصفح دائماً)
      if (meta && !e.shiftKey && (e.key === "s" || e.key === "S")) {
        e.preventDefault();
        triggerSave();
        return;
      }

      // --- Ctrl/⌘+Shift+Q: تسجيل خروج سريع
      if (meta && e.shiftKey && (e.key === "q" || e.key === "Q")) {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent("alqaim:shortcut:logout"));
        return;
      }

      // --- طبقة توافق الأمين: Alt+2/3/5/6/8/9 (بديل آمن لـ F2/F3/F5/F6/F8/F9
      // المحجوزة من المتصفح — راجع الشرح في registry.ts). تعمل حتى داخل
      // الحقول لأن Alt مُعدِّل، لا حرف مفرد يتعارض مع الكتابة العادية.
      if (e.altKey && !meta) {
        if (e.key === "2") {
          if (triggerNew()) e.preventDefault();
          return;
        }
        if (e.key === "3") {
          e.preventDefault();
          setPaletteOpen(!isPaletteOpen);
          return;
        }
        if (e.key === "5") {
          e.preventDefault();
          triggerSave();
          return;
        }
        if (e.key === "6") {
          e.preventDefault();
          triggerPrint();
          return;
        }
        if (e.key === "8") {
          if (triggerDelete()) e.preventDefault();
          return;
        }
        if (e.key === "9") {
          e.preventDefault();
          triggerPost();
          return;
        }
      }

      // بقية الاختصارات أحادية الحرف: تُتجاهل أثناء الكتابة في حقل
      if (typing || meta || e.altKey) {
        clearPendingGo();
        return;
      }

      // --- ? : فتح/إغلاق مساعدة الاختصارات
      if (e.key === "?") {
        e.preventDefault();
        setHelpOpen(!isHelpOpen);
        return;
      }

      // --- تتابع G ثم حرف: انتقال مباشر لأي شاشة
      if (pendingGoRef.current) {
        clearPendingGo();
        const key = e.key.toLowerCase();
        if (key === "h") {
          router.push(HOME_SHORTCUT.href);
          return;
        }
        const target = VISIBLE_NAV_SHORTCUTS.find((s) => s.goToKey === key);
        if (target) {
          e.preventDefault();
          router.push(target.href);
        }
        return;
      }

      if (e.key.toLowerCase() === "g") {
        pendingGoRef.current = true;
        goTimerRef.current = setTimeout(clearPendingGo, GO_SEQUENCE_TIMEOUT_MS);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      clearPendingGo();
    };
  }, [
    router,
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
  ]);
}
