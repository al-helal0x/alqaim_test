# packages/ui-kit

مكوّنات تصميم مشتركة (Web/Desktop/PWA) — Buttons, Tables, Forms... مستقلة
تماماً عن أي منطق أعمال (مطابق لمبدأ `common/` في القسم 6.5).

## الحالة (محدَّثة)
✅ منقولة فعلياً من `apps/web/src/common/ui.tsx` — Button, Field, SelectField, Card, PageHeader, Banner, EmptyState. `apps/web` يستهلكها عبر مسار TypeScript `@alqaim/ui-kit` (نفس نمط `@alqaim/api-types`)، وملف `apps/web/src/common/ui.tsx` أصبح إعادة تصدير فقط للحفاظ على توافق كل الصفحات الحالية.
