# packages/api-types

أنواع TypeScript مولَّدة تلقائياً من OpenAPI الخاص بـ core-api (لا تُكتب يدوياً).
تُولَّد عبر: `npm run generate:api-types` (من apps/web) بعد أن يكون core-api
يعمل محلياً ويصدّر `/openapi.json`.

## الحالة (محدَّثة)
✅ مولَّدة فعلياً (آخر تحديث: هذه الجولة) من OpenAPI حيّ لِـ core-api — 61 مساراً، تشمل identity/tenancy/accounting/taxation/catalog/partners/inventory/sales/pos/purchasing/payments. أُعيد توليدها بتشغيل core-api محلياً ثم `npm run generate:api-types` من `apps/web`.
