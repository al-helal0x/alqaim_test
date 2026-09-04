"use client";

/**
 * @alqaim/ui-kit — مكوّنات الواجهة المشتركة الفعلية.
 *
 * تُرحَّل هذه الوحدة من `apps/web/src/common/ui.tsx` (العضو 7) لتكون مصدراً
 * وحيداً يستهلكه كل تطبيق (Web الآن، وسطح المكتب/العضو 10 لاحقاً) بدل أن
 * يبني كل تطبيق مكوّناته المحلية الخاصة. لا خطوة بناء هنا: يُستهلَك المصدر
 * مباشرة عبر تعيين المسارات في tsconfig.json لكل تطبيق مستهلِك
 * (`"@alqaim/ui-kit": ["../../packages/ui-kit/src/index.tsx"]`).
 *
 * لا اعتماد هنا على أي حزمة تطبيق (لا `@/api-client`، لا `@alqaim/i18n`) —
 * هذه الحزمة مستقلة تماماً بتصميم، بلا نصوص عربية مكتوبة مباشرة داخل
 * المكوّنات نفسها (النصوص تأتي دائماً من المستدعي عبر props).
 */

import {
  forwardRef,
  useId,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";

/* -------------------------------------------------------------------------
 * أداة دمج أصناف Tailwind — بلا الاعتماد على حزمة خارجية (tailwind-merge).
 * ملاحظة مهمة: ترتيب الأصناف داخل `className` في HTML لا يحدّد مَن يفوز في
 * التعارض — Tailwind يولّد كل صنف كقاعدة CSS منفصلة بترتيب ثابت مبني على
 * مقياس القيم (مثلاً `.p-0` تُولَّد قبل `.p-6` دائماً)، فلو مرّرنا `p-6` ضمن
 * الأصناف الافتراضية و `p-0` ضمن `className` الممرَّر من المستدعي، فإن
 * `.p-6` (المعرَّفة لاحقاً في الجدول) تفوز رغم ترتيب الكتابة — وهو عكس ما
 * يتوقعه أي مستهلك للمكوّن. الحل: عند التعارض على نفس "مجموعة" الخاصية
 * (padding مثلاً)، نُسقِط الصنف الافتراضي المطابق قبل الدمج.
 * -------------------------------------------------------------------------
 */
const CONFLICT_GROUPS: RegExp[] = [
  /^p-/,
  /^px-/,
  /^py-/,
  /^pt-/,
  /^pb-/,
  /^pl-/,
  /^pr-/,
  /^rounded/,
  /^overflow-/,
  /^overflow$/,
  /^border$/,
  /^border-\d/,
];

function cx(base: string, override?: string): string {
  if (!override) return base;
  const overrideTokens = override.split(/\s+/).filter(Boolean);
  let baseTokens = base.split(/\s+/).filter(Boolean);
  for (const token of overrideTokens) {
    const group = CONFLICT_GROUPS.find((re) => re.test(token));
    if (group) {
      baseTokens = baseTokens.filter((existing) => !group.test(existing));
    }
  }
  return [...baseTokens, ...overrideTokens].join(" ");
}

/* -------------------------------------------------------------------------
 * Button
 * -------------------------------------------------------------------------
 */
export type ButtonVariant = "primary" | "secondary" | "danger";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed";

const BUTTON_VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: "bg-ledger-600 text-white hover:bg-ledger-700 disabled:bg-ledger-100 disabled:text-ledger-400",
  // ⚠️ إصلاح (QA_FINDINGS_apps_web_manual_test.md #5): الحد كان
  // `border-line` (#DCD8CC) على خلفية `bg-white`، فوق خلفية صفحة `paper`
  // (#F1F0E9) قريبة جداً بصرياً من الاثنين — الزر كان يكاد يندمج بخلفية
  // الصفحة حتى الـhover. الحد الآن `ink-soft/35` (تباين أعلى بكثير مع
  // paper/white) يجعل حدود الزر مرئية بوضوح في حالته العادية لا فقط عند
  // hover — بلا تغيير الألوان الأساسية للـ variant (لا يزال محايداً، ليس
  // ملوَّناً كـprimary).
  secondary:
    "border border-ink-soft/35 bg-white text-ink hover:bg-paper hover:border-ink-soft/60 disabled:text-ink-soft disabled:border-line disabled:hover:bg-white",
  danger: "bg-brick-500 text-white hover:bg-brick-600 disabled:bg-brick-500/40",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", className = "", type = "button", ...props },
  ref
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cx(`${BUTTON_BASE} ${BUTTON_VARIANT_CLASSES[variant]}`, className)}
      {...props}
    />
  );
});

/* -------------------------------------------------------------------------
 * Field (نص/رقم/بريد/كلمة مرور... — أي <input> قياسي)
 * -------------------------------------------------------------------------
 */
export type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  error?: string;
};

export const Field = forwardRef<HTMLInputElement, FieldProps>(function Field(
  { label, hint, error, required, id, className = "", ...props },
  ref
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={inputId} className="text-sm text-ink-soft">
        {label}
        {required && <span className="text-brick-500"> *</span>}
      </label>
      <input
        ref={ref}
        id={inputId}
        required={required}
        aria-invalid={!!error}
        aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
        className={cx(
          `w-full rounded border bg-white px-3 py-2 text-sm text-ink placeholder:text-ink-soft/60 focus:outline-none disabled:bg-paper disabled:text-ink-soft ${
            error ? "border-brick-500" : "border-line"
          }`,
          className
        )}
        {...props}
      />
      {error ? (
        <p id={`${inputId}-error`} className="text-xs text-brick-600">
          {error}
        </p>
      ) : hint ? (
        <p id={`${inputId}-hint`} className="text-xs text-ink-soft">
          {hint}
        </p>
      ) : null}
    </div>
  );
});

/* -------------------------------------------------------------------------
 * SelectField
 * -------------------------------------------------------------------------
 */
export type SelectFieldProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  hint?: string;
  error?: string;
};

export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(function SelectField(
  { label, hint, error, required, id, className = "", children, ...props },
  ref
) {
  const generatedId = useId();
  const selectId = id ?? generatedId;

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={selectId} className="text-sm text-ink-soft">
        {label}
        {required && <span className="text-brick-500"> *</span>}
      </label>
      <select
        ref={ref}
        id={selectId}
        required={required}
        aria-invalid={!!error}
        aria-describedby={error ? `${selectId}-error` : hint ? `${selectId}-hint` : undefined}
        className={cx(
          `w-full rounded border bg-white px-3 py-2 text-sm text-ink focus:outline-none disabled:bg-paper disabled:text-ink-soft ${
            error ? "border-brick-500" : "border-line"
          }`,
          className
        )}
        {...props}
      >
        {children}
      </select>
      {error ? (
        <p id={`${selectId}-error`} className="text-xs text-brick-600">
          {error}
        </p>
      ) : hint ? (
        <p id={`${selectId}-hint`} className="text-xs text-ink-soft">
          {hint}
        </p>
      ) : null}
    </div>
  );
});

/* -------------------------------------------------------------------------
 * Card
 * -------------------------------------------------------------------------
 */
export type CardProps = {
  children: ReactNode;
  className?: string;
};

export function Card({ children, className = "" }: CardProps) {
  return <div className={cx("rounded-md border border-line bg-white p-6", className)}>{children}</div>;
}

/* -------------------------------------------------------------------------
 * PageHeader
 * -------------------------------------------------------------------------
 */
export type PageHeaderProps = {
  title: string;
  description?: string;
  action?: ReactNode;
};

export function PageHeader({ title, description, action }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4 border-b border-line pb-4">
      <div>
        <h1 className="font-display text-2xl text-ink">{title}</h1>
        {description && <p className="mt-1 text-sm text-ink-soft">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Banner
 * -------------------------------------------------------------------------
 */
export type BannerKind = "info" | "success" | "warning" | "error";

export type BannerProps = {
  kind?: BannerKind;
  children: ReactNode;
  className?: string;
};

const BANNER_CLASSES: Record<BannerKind, string> = {
  info: "border-line bg-ink/5 text-ink-soft",
  success: "border-ledger-100 bg-ledger-50 text-ledger-700",
  warning: "border-copper-400/40 bg-copper-400/10 text-copper-600",
  error: "border-brick-500/30 bg-brick-500/10 text-brick-600",
};

export function Banner({ kind = "info", children, className = "" }: BannerProps) {
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={cx(`rounded border px-4 py-3 text-sm ${BANNER_CLASSES[kind]}`, className)}
    >
      {children}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * EmptyState
 * -------------------------------------------------------------------------
 */
export type EmptyStateProps = {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
};

export function EmptyState({ title, description, action, className = "" }: EmptyStateProps) {
  return (
    <div
      className={cx(
        "flex flex-col items-center justify-center rounded-md border border-dashed border-line px-6 py-12 text-center",
        className
      )}
    >
      <p className="font-display text-lg text-ink">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-ink-soft">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
