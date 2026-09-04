# تسليم TASK-BI-01 — لوحة "نبض الشركة اليومي"

هذه حزمة **التنفيذ الفعلي المُختبَر**، لا وصف نظري. كل ما فيها شُغِّل
فعلياً على شجرة `AlQaim_V2_v21_phase5_FINAL_MERGED__3_` وتحقَّق منه
(pytest / tsc / eslint / vitest / next build) — التفاصيل الكاملة والأدلة
في نهاية `TASK-BI-01.md` المرفقة، قسم "سجل التنفيذ الفعلي".

## كيفية التطبيق

انسخ محتويات `changed_files/` فوق نفس المسارات في نسخة مشروعك الفعلية
(7 ملفات: 6 جديدة + تعديل سطر واحد في ملف ثامن قائم). لا حاجة لأي أمر Git
خاص — المسارات مطابقة تماماً لبنية المستودع.

| الملف | جديد/معدَّل |
|---|---|
| `apps/core-api/modules/reporting/application/dto/business_pulse_dto.py` | جديد |
| `apps/core-api/modules/reporting/application/use_cases/business_pulse_use_case.py` | جديد |
| `apps/core-api/modules/reporting/presentation/routes/reports_router.py` | معدَّل (+endpoint واحد فقط) |
| `apps/core-api/tests/integration/test_business_pulse_dashboard.py` | جديد |
| `apps/web/src/features/reporting/api.ts` | جديد |
| `apps/web/src/features/reporting/business-pulse-dashboard.tsx` | جديد |
| `apps/web/src/app/(dashboard)/dashboard/page.tsx` | معدَّل (تضمين المكوّن فقط) |

## ملخص سريع لما تحقّق

- ✅ Backend: `GET /reports/business-pulse?period_days=7..90` — 5 مؤشرات
  (اتجاه المبيعات، أعلى المنتجات، الصندوق، أدنى مخزوناً، أعمار الذمم)
- ✅ 6 اختبارات جديدة تمر، بما فيها اختبار عزل tenant الإلزامي
- ✅ 172 اختباراً قائماً في المشروع لا يزال يمر (0 كسر)
- ✅ Frontend: مكوّن `BusinessPulseDashboard` مُدمَج في `/dashboard`، `tsc`
  و`eslint` و`vitest` (37 اختباراً) و`next build` كلها ناجحة بلا أخطاء
- ✅ صفر تعديل داخل `sales/accounting/inventory/payments` أو `main.py`
- ✅ صفر تبعية npm جديدة (رسوم SVG يدوية بدل مكتبة رسوم بيانية)

## غير مكتمل (بحاجة إنسان، لا يمكن لتنفيذ آلي تحقيقه)

بند **Product Acceptance** في بطاقة المهمة يتطلب مستخدماً فعلياً (محاسب/مالك
أو من يمثّله) يفتح اللوحة على بيئة حقيقية (Postgres + خادم حي) ويؤكد أن
الأرقام مفهومة بلا شرح إضافي. هذا خارج نطاق ما يمكن إثباته آلياً — الحالة
الحالية **IMPLEMENTED + TESTED، وليست ACCEPTED بعد**.

كذلك: قياس زمن استجابة حقيقي على حجم بيانات إنتاجي (SQLite في الذاكرة
المستخدَم في الاختبارات لا يمثّل ذلك).

## قرارات تنفيذ يجب معرفتها قبل المراجعة

كلها موثَّقة كتعليقات داخل الكود نفسه أيضاً، لا مخفية:

1. **لا مكتبة رسوم بيانية جديدة** — SVG يدوي بدل إضافة تبعية (كان
   `package.json` خالياً من أي مكتبة رسوم بيانية أصلاً)
2. **"الأقل مخزوناً" بدل "تحت حد إعادة الطلب"** — الحقل الثاني يعيش في
   وحدة `catalog`، خارج الوحدات المرجعية المسموح بها في بطاقة المهمة
3. **أعلى المنتجات بلا اسم، فقط `product_id`** — لنفس السبب أعلاه، معروض
   صراحة للمستخدم في الواجهة
4. **أنواع TypeScript يدوية** في `features/reporting/api.ts` بدل التوليد
   التلقائي المعتاد (`npm run generate:api-types` يحتاج خادماً حياً غير
   متاح في بيئة التنفيذ) — يجب استبدالها بالتوليد الحقيقي أول فرصة ممكنة
