"use client";

/**
 * طبقة مساعدة شاملة (تُفتح بـ "?") تسرد كل الاختصارات مجمّعة، بما فيها
 * اختصارات شبكة القيود. أي مستخدم قادم من الأمين أو إكسل يفهمها فوراً.
 */

import { t } from "@alqaim/i18n";
import { AL_AMIN_COMPAT_KEYS, GLOBAL_ACTION_KEYS, GRID_ACTION_KEYS, VISIBLE_NAV_SHORTCUTS } from "./registry";
import { useShortcutContext } from "./shortcut-context";

function Row({ label, keys }: { label: string; keys: string }) {
  return (
    <div className="flex items-center justify-between border-b border-line/60 py-1.5 text-sm last:border-0">
      <span className="text-ink-soft">{label}</span>
      <kbd className="rounded border border-line bg-paper px-1.5 py-0.5 font-mono text-[11px] text-ink">{keys}</kbd>
    </div>
  );
}

export function ShortcutsHelp() {
  const { isHelpOpen, setHelpOpen } = useShortcutContext();
  if (!isHelpOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 px-4"
      onClick={() => setHelpOpen(false)}
      role="presentation"
    >
      <div
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-md border border-line bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={t("shortcuts.helpTitle")}
      >
        <div className="mb-4 flex items-start justify-between gap-4 border-b border-line pb-3">
          <div>
            <h2 className="font-display text-lg text-ink">{t("shortcuts.helpTitle")}</h2>
            <p className="mt-1 text-xs text-ink-soft">{t("shortcuts.helpSubtitle")}</p>
          </div>
          <button
            type="button"
            onClick={() => setHelpOpen(false)}
            className="text-sm text-ink-soft hover:text-ink"
            aria-label={t("action.close")}
          >
            ✕
          </button>
        </div>

        <section className="mb-5">
          <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-soft">
            {t("shortcuts.group.global")}
          </h3>
          <Row label={t("shortcuts.nav.palette")} keys={GLOBAL_ACTION_KEYS.palette} />
          <Row label={t("shortcuts.global.new")} keys={GLOBAL_ACTION_KEYS.new} />
          <Row label={t("shortcuts.global.save")} keys={GLOBAL_ACTION_KEYS.save} />
          <Row label={t("shortcuts.global.cancel")} keys={GLOBAL_ACTION_KEYS.cancel} />
          <Row label={t("shortcuts.global.help")} keys={GLOBAL_ACTION_KEYS.help} />
          <Row label={t("shortcuts.global.logout")} keys={GLOBAL_ACTION_KEYS.logout} />
        </section>

        <section className="mb-5">
          <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-soft">
            {t("shortcuts.group.alamin")}
          </h3>
          <Row label={t("shortcuts.alamin.new")} keys={AL_AMIN_COMPAT_KEYS.new} />
          <Row label={t("shortcuts.alamin.search")} keys={AL_AMIN_COMPAT_KEYS.search} />
          <Row label={t("shortcuts.alamin.save")} keys={AL_AMIN_COMPAT_KEYS.save} />
          <Row label={t("shortcuts.alamin.print")} keys={AL_AMIN_COMPAT_KEYS.print} />
          <Row label={t("shortcuts.alamin.delete")} keys={AL_AMIN_COMPAT_KEYS.delete} />
          <Row label={t("shortcuts.alamin.post")} keys={AL_AMIN_COMPAT_KEYS.post} />
        </section>

        <section className="mb-5">
          <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-soft">
            {t("shortcuts.group.grid")}
          </h3>
          <Row label={t("shortcuts.grid.addRow")} keys={GRID_ACTION_KEYS.addRow} />
          <Row label={t("shortcuts.grid.removeRow")} keys={GRID_ACTION_KEYS.removeRow} />
          <Row label={t("shortcuts.grid.nextField")} keys={GRID_ACTION_KEYS.nextField} />
          <Row label={t("shortcuts.grid.prevField")} keys={GRID_ACTION_KEYS.prevField} />
          <Row label={t("shortcuts.grid.submit")} keys={GRID_ACTION_KEYS.submit} />
        </section>

        <section>
          <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-soft">
            {t("shortcuts.group.navigation")}
          </h3>
          <p className="mb-2 text-xs text-ink-soft">{t("shortcuts.nav.sequence")}</p>
          <div className="grid grid-cols-2 gap-x-6 sm:grid-cols-3">
            {VISIBLE_NAV_SHORTCUTS.map((item) => (
              <Row key={item.href} label={t(item.labelKey)} keys={`G ${item.goToKey.toUpperCase()}`} />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
