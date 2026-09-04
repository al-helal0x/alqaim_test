"use client";

/**
 * لوحة الانتقال السريع (Ctrl/⌘+K) — تبحث عبر كل شاشات النظام بالعربية
 * والإنجليزية معاً، وتُظهر أيضاً حرف "الذهاب المباشر" (G ثم حرف) بجانب كل
 * نتيجة حتى يتعلّمها المستخدم تدريجياً بدل حفظها فجأة. هذا نفس مبدأ لوحات
 * الأوامر في الأدوات الحديثة (Linear/Notion/VS Code) وهو تطوير لفكرة "البحث
 * الشامل عن أي شاشة" الموجودة في برامج محاسبة عربية حديثة.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { t } from "@alqaim/i18n";
import { VISIBLE_NAV_SHORTCUTS, type NavShortcut } from "./registry";
import { useShortcutContext } from "./shortcut-context";

function normalize(s: string): string {
  return s.trim().toLowerCase();
}

export function CommandPalette() {
  const { isPaletteOpen, setPaletteOpen } = useShortcutContext();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const results = useMemo(() => {
    const q = normalize(query);
    if (!q) return VISIBLE_NAV_SHORTCUTS;
    return VISIBLE_NAV_SHORTCUTS.filter((item) => {
      const label = normalize(t(item.labelKey));
      const labelEn = normalize(t(item.labelKey, "en"));
      const section = normalize(t(item.sectionKey));
      return label.includes(q) || labelEn.includes(q) || section.includes(q) || item.goToKey === q;
    });
  }, [query]);

  useEffect(() => {
    if (isPaletteOpen) {
      setQuery("");
      setActiveIndex(0);
      // تركيز تلقائي بعد رسم اللوحة
      const id = requestAnimationFrame(() => inputRef.current?.focus());
      return () => cancelAnimationFrame(id);
    }
  }, [isPaletteOpen]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  function go(item: NavShortcut) {
    setPaletteOpen(false);
    router.push(item.href);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = results[activeIndex];
      if (item) go(item);
    }
    // Escape يُعالَج مركزياً في use-global-shortcuts (يغلق اللوحة)
  }

  if (!isPaletteOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-ink/40 px-4 pt-24"
      onClick={() => setPaletteOpen(false)}
      role="presentation"
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-md border border-line bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={t("shortcuts.paletteTitle")}
      >
        <div className="border-b border-line px-4 py-3">
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("shortcuts.palettePlaceholder")}
            className="w-full bg-transparent text-sm text-ink placeholder:text-ink-soft/60 focus:outline-none"
            aria-label={t("shortcuts.paletteTitle")}
          />
        </div>

        <ul className="max-h-80 overflow-y-auto py-1" role="listbox">
          {results.length === 0 && (
            <li className="px-4 py-6 text-center text-sm text-ink-soft">{t("shortcuts.paletteEmpty")}</li>
          )}
          {results.map((item, i) => (
            <li key={item.href} role="option" aria-selected={i === activeIndex}>
              <button
                type="button"
                onMouseEnter={() => setActiveIndex(i)}
                onClick={() => go(item)}
                className={`flex w-full items-center justify-between px-4 py-2 text-start text-sm transition-colors ${
                  i === activeIndex ? "bg-paper text-ink" : "text-ink-soft hover:bg-paper"
                }`}
              >
                <span>
                  <span className="text-ink">{t(item.labelKey)}</span>
                  <span className="ms-2 text-xs text-ink-soft">{t(item.sectionKey)}</span>
                </span>
                <kbd className="rounded border border-line bg-paper px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">
                  G {item.goToKey.toUpperCase()}
                </kbd>
              </button>
            </li>
          ))}
        </ul>

        <div className="border-t border-line px-4 py-2 text-xs text-ink-soft">{t("shortcuts.paletteHintGo")}</div>
      </div>
    </div>
  );
}
