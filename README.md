# AlQaim V2 — ERP Monorepo

> **حالة المشروع الحالية: جولة الإغلاق (Closing Sprint).** المشروع **ليس**
> ناقصًا من الصفر — دورة تجارية كاملة (بيع/شراء → مخزون → محاسبة → تقرير)
> تعمل فعليًا، ومنصة AI تعمل كخط أنابيب مستقل، وتعارض #6×#10×#11×#12
> (Outbox/إقفال الفترة/Idempotency/موافقة المدير) **مُنجَز ومُتحقَّق منه**
> (`STATUS_20_TASKS.md §15`). المتبقي فجوات محددة موثَّقة في
> `ALQAIM_V2_MASTER_EXECUTION_PLAN.md`: Walk-in Customer، حلقة تكامل
> AI↔Purchasing غير مقفلة بعد، CI Baseline، وتنظيف. **راجع تلك الوثيقة أولًا**
> لمعرفة أي جزء من الخطة قيد التنفيذ الآن، ثم `PRODUCT_VISION.md` (لماذا
> نبني ما نبنيه) قبل `AlQaim_V2_Blueprint.md` (الوثيقة المرجعية المعمارية
> الأصلية).
>
> **ملاحظة تاريخية:** كانت هذه الفقرة تحيل إلى `AlQaim_V2_closing_sprint_plan.md`
> — ملف غير موجود فعليًا في أي حزمة مُسلَّمة (فجوة موثَّقة في
> `PROJECT_STATUS_SUMMARY.md §6`). `ALQAIM_V2_MASTER_EXECUTION_PLAN.md`
> يحل محله كمرجع البداية الرسمي (`docs/architecture/ADR-003 §6`).

## قبل أي شيء
1. اقرأ `ALQAIM_V2_MASTER_EXECUTION_PLAN.md` — يحتوي حالة كل مهمة متبقية
   (منجزة / مسلَّمة بانتظار دمج / متعارضة / لم تبدأ)، ترتيب التنفيذ
   الملزم، وGates التحقق (القسم 11).
2. اقرأ `PRODUCT_VISION.md` — المرجع الأعلى لسؤال "هل ما نبنيه يخدم
   المنتج؟"، منفصل عمداً عن التفاصيل التقنية.
3. اقرأ `AlQaim_V2_Blueprint.md` (الوثيقة المعمارية المرجعية الأصلية)،
   ثم `docs/architecture/contracts.md` و`docs/architecture/ADR-003-vertical-slice-strategy.md`.

## البنية
```
alqaim-v2/
├── apps/
│   ├── core-api/          # Backend الرئيسي — Modular Monolith (Python/FastAPI)
│   │   ├── platform_core/     # بنية تحتية مشتركة — العضو 1 حصرياً
│   │   ├── shared_kernel/     # Money/Currency/TenantContext/AuditFields — العضو 1 حصرياً
│   │   ├── modules/           # الوحدات التجارية (كل وحدة: domain/application/infrastructure/presentation)
│   │   ├── migrations/        # Alembic
│   │   └── tests/              # unit/ integration/ e2e/ (تُنشأ عند أول اختبار فعلي في كل نوع)
│   ├── ai-platform/       # خدمة الذكاء الاصطناعي المستقلة — العضو 8 حصرياً
│   ├── web/               # لوحة الإدارة + PWA (Next.js) — العضو 7
│   ├── desktop/            # غلاف Tauri فوق apps/web
│   └── pos-app/              # Flutter (Offline-first) — العضو 9، نظام تصميم Flutter محلي مستقل في lib/design/
├── packages/                 # api-types / ui-kit (React/TSX — للويب فقط) / i18n (مشترك بين الواجهات)
├── infra/                     # Docker / k8s / CI
├── docs/                       # architecture (contracts.md) / api / modules
├── scripts/                     # seed_demo_company.py / run_migrations.sh / backup_db.sh
├── docker-compose.yml            # بيئة تطوير محلية (Postgres/Redis/MinIO)
├── docker-compose.selfhosted.yml
└── .github/workflows/ci.yml
```

> **ملاحظة:** `apps/mobile` أُزيل من الشجرة — كان سقالة فارغة بمستويين
> مكرَّرين بلا أي كود Flutter فعلي ولا اعتماديات عليه من أي مهمة، وتقرر
> حذفه بدل تعيين مالك له (قرار مهمة #16). عند نشوء حاجة منتج فعلية لتطبيق
> موبايل مستقل عن pos-app مستقبلًا، تُفتح مهمة تخطيط جديدة من الصفر بدل
> استئناف هذه السقالة.

## تشغيل بيئة التطوير محلياً
```bash
docker compose up -d          # Postgres + Redis + MinIO + core-api + ai-platform + web
curl http://localhost:8000/health   # core-api
curl http://localhost:8100/health   # ai-platform
```

## خريطة الفريق
| العضو | المسؤولية | المجلد الرئيسي |
|---|---|---|
| 1 — Platform & Foundation Lead | Auth/Tenancy/Platform Core | `apps/core-api/platform_core`, `modules/identity`, `modules/tenancy` |
| 2 — Master Data | العملاء/الموردين/المنتجات | `modules/partners`, `modules/catalog` |
| 3 — Inventory | المخزون | `modules/inventory` |
| 4 — Sales & POS (Backend) | المبيعات ونقاط البيع (API) | `modules/sales`, `modules/pos` |
| 5 — Purchasing & Payments | المشتريات والمدفوعات | `modules/purchasing`, `modules/payments` |
| 6 — Accounting & Taxation | المحاسبة والضرائب والتقارير | `modules/accounting`, `modules/taxation`, `modules/reporting` |
| 7 — Web Frontend Lead | لوحة الإدارة | `apps/web`, `packages/ui-kit`, `packages/i18n` |
| 8 — AI Platform Lead | OCR/فهم الفواتير | `apps/ai-platform` |
| 9 — Mobile/POS Client Lead | تطبيق نقطة البيع (Flutter، Offline-first) | `apps/pos-app` |

`packages/ui-kit` مكتبة **React/TSX للويب فقط** — غير قابلة للاستخدام تقنيًا
من Flutter (لا جسر توليد كود ولا هذا مطروح في الخطة المعمارية). لذلك pos-app
(العضو 9) لا ينتظر أي ترحيل منها؛ لديه نظام تصميم Flutter محلي مستقل في
`apps/pos-app/lib/design/` وهو الاختيار الدائم للتطبيق.

تفاصيل كل عضو (الجداول، الـ APIs، الاختبارات المطلوبة، معيار التسليم) في
القسم 13/14 من `AlQaim_V2_Blueprint.md`. حالة كل مهمة تسليم فعلية حالية في
`ALQAIM_V2_MASTER_EXECUTION_PLAN.md`.

## قواعد إلزامية سريعة (تفصيلها الكامل في الوثيقة المعمارية)
- **API-first دائماً:** لا اتصال مباشر بقاعدة البيانات من أي واجهة (القسم 6.2).
- **4 طبقات إلزامية لكل Module:** `domain → application → infrastructure → presentation` (القسم 6.4).
- **ممنوع `Float` للمبالغ المالية** — `Decimal`/`NUMERIC` فقط (القسم 17).
- **ممنوع `print()`** — Logger مركزي من `platform_core` فقط (القسم 11.4).
- **لا ترحيل تلقائي لمخرجات الذكاء الاصطناعي** بدون موافقة بشرية صريحة (القسم 17).
- حدود الوحدات تُفرض آلياً عبر Import Linter في CI — ليست اتفاقاً شفهياً (القسم 11.2).

## الخطوة التالية
تنفيذ `ALQAIM_V2_MASTER_EXECUTION_PLAN.md` — `EXECUTION ORDER` (آخر قسم
في الوثيقة) هو الترتيب الملزم الحالي: Walk-in Customer وAI→Purchasing
Vertical Slice (القسم 8، Phases 2-3) بالتوازي، وصولًا لتعريف "Working
Product" الكامل (القسم 17 من نفس الوثيقة) والدخول في Production Hardening.
"# alqaim_test" 
