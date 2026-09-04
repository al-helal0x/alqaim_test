# RUNBOOK — إغلاق GATE-05 (البنود الثلاثة المتبقية)

**لمن يملك بيئة تنفيذ فعلية: Docker + Postgres/Redis حيّين + k6 + Flutter SDK.**
**المرجع:** `ALQAIM_V2_PHASE5_FINAL_CLOSURE_PLAN.md` §5 + `DELIVERY_CARD_phase5_5members_merge_session.md` (كلاهما في جذر هذه الشجرة).

هذه الشجرة (v21) تحتوي فعلياً على: IDOR مغلق (17/17)، وكود `TASK-AI-04` مدموجاً ومختبَراً بـmocks. **لم يُتحقَّق من 3 بنود بعد لغياب بيئة تنفيذ حقيقية في كل الجلسات السابقة — لا نقص كود.** هذا الملف يغطي الثلاثة دفعة واحدة، بالترتيب الموصى به.

---

## ✅ ملاحظة تحقّق مسبقة (قبل أن تبدأ)

تم التحقق مسبقاً بتشغيل حقيقي في هذه الجلسة (بلا Docker):
```
apps/core-api:    163 passed, 12 skipped, 0 failed   (17/17 IDOR ضمنها)
apps/ai-platform:  26 passed,  1 skipped, 0 failed
```
لا حاجة لإعادة هذا — ركّز مباشرة على الأقسام 1-3 أدناه.

**ملاحظة جانبية (ليست جزءاً من GATE-05، لكن يُستحسَن تنظيفها الآن إن كان لديك وقت):**
`known_failures.txt` الخاص بـ`core-api` متأخر عن الواقع بقليل — يوجد ملفان (`migrations/versions/partners_20260816_0001_walkin_system_managed.py` و`purchasing_20260813_0001_add_purchase_invoice_ai_draft_id.py`) من مسارات عمل أخرى غير هذا الدمج، تحويان مخالفات `ruff` لم تُسجَّل في الـbaseline. غير مرتبطة بعمل الأعضاء الخمسة (تحقَّقتُ: التصريح الأصلي بـ"صفر مخالفات جديدة" كان دقيقاً بالنسبة لنطاق الملفات التي لمسها هذا الدمج تحديداً). لإصلاحها:
```bash
cd apps/core-api
bash ../../scripts/generate_lint_baseline.sh > known_failures.txt.new
# راجع الفرق يدوياً قبل الاستبدال (السكربت نفسه يحذّر من احتمال ضياع تعليقات الترويسة)
```

---

## 1️⃣ E2E حي كامل (`PKG-A3`) → إغلاق `GATE-03`

### الهدف
إثبات أن `ai-platform` يستطيع فعلياً سؤال `core-api` عن الموردين/المنتجات المعروفين عبر شبكة Docker حقيقية (لا mocks)، وأن `matched_supplier_id` يُملأ فعلياً في مسودة فاتورة حقيقية.

### الخطوات

```bash
# 1. تشغيل كل الخدمات
docker-compose up -d --build
docker-compose ps   # تأكد أن postgres/redis/minio/core-api/ai-platform كلها healthy

# 2. تشغيل الـmigrations (إن لم تُشغَّل تلقائياً عند الإقلاع)
docker-compose exec core-api alembic upgrade head
docker-compose exec ai-platform alembic upgrade head

# 3. زرع بيانات شركة تجريبية (شركة + مورد معروف على الأقل)
docker-compose exec core-api python scripts/seed_demo_company.py
# ← لاحظ/احتفظ بـ company_id واسم المورد المزروع من مخرجات هذا السكربت
```

**تحقق يدوي مباشر من المسار الداخلي بين الخدمتين (قبل اختبار المسار الكامل):**
```bash
docker-compose exec core-api curl -s \
  -H "X-Service-Token: dev-only-service-token-change-me" \
  "http://localhost:8000/internal/partners/known-suppliers?company_id=<COMPANY_ID>"
# متوقَّع: 200 + قائمة JSON فيها المورد المزروع

docker-compose exec core-api curl -s \
  -H "X-Service-Token: WRONG_TOKEN" \
  "http://localhost:8000/internal/partners/known-suppliers?company_id=<COMPANY_ID>"
# متوقَّع: 401
```

**المسار الكامل E2E (عبر البوابة الحقيقية `core-api → ai-platform`):**
```bash
# احصل أولاً على JWT مستخدم صالح لهذه الشركة (login endpoint المعتاد في المشروع)
TOKEN="<JWT من core-api>"

curl -s -X POST "http://localhost:8000/ai/documents/analyze" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/invoice_scan_with_known_supplier_name.jpg" \
  -F "company_currency=IQD"
# يرجع job_id → استخدمه:

curl -s "http://localhost:8000/ai/documents/jobs/<JOB_ID>" -H "Authorization: Bearer $TOKEN"
# انتظر status=done، خذ draft_id منه

curl -s "http://localhost:8000/ai/drafts/<DRAFT_ID>" -H "Authorization: Bearer $TOKEN"
# ✅ النجاح = matched_supplier_id غير null (وليس فارغاً كما كان قبل TASK-AI-04)
```

**اختبار مسار الفشل الآمن (مطلوب أيضاً — موثَّق في الخطة):**
```bash
docker-compose stop core-api
# أعد نفس طلب /ai/documents/analyze مباشرة على ai-platform (منفذ 8100 مباشرة، تجاوز البوابة)
# متوقَّع: يكمل بنجاح بلا مطابقة (matched_supplier_id=null)، ليس 500
docker-compose start core-api
```

### إغلاق GATE-03
لو نجحت الخطوات أعلاه (200/matched_supplier_id غير null + تجاوز أنيق عند تعطّل core-api) → أضف سطراً في `STATUS_20_TASKS.md` يعلن `GATE-03` **مُغلَقاً رسمياً** مع تاريخ ونتائج الأوامر أعلاه.

---

## 2️⃣ اختبار الحمل الفعلي (`PKG-C3` / k6)

الملفات جاهزة في `scripts/load/`. البيئة من نفس `docker-compose up` أعلاه.

```bash
# تأكد من وجود بيانات كافية (شركة + منتجات + مخزون) — أعد seed_demo_company.py إن لزم
k6 run scripts/load/k6_sales_invoice_create.js
k6 run scripts/load/k6_sales_invoice_post.js
k6 run scripts/load/k6_trial_balance_report.js
```

وثّق لكل سكربت: p50/p95/p99، معدل الأخطاء، طلبات/ثانية — **حتى لو كانت النتيجة ضعيفة، هذا مخرج صحيح ومقبول** (الخطة تنص على ذلك صراحة). لا تُصلح كوداً أثناء هذه الخطوة إن ظهر خلل أداء — وثّقه فقط لجلسة لاحقة.

---

## 3️⃣ أول تشغيل حقيقي لـ `pos-app-baseline` (Flutter CI)

ملاحظة من جلسة الدمج: أُضيفت خطوة `dart run build_runner build --delete-conflicting-outputs` إلى `.github/workflows/ci.yml` قبل `dart analyze` (لم تُختبَر فعلياً — لا Flutter SDK كان متاحاً).

```bash
cd apps/pos-app
flutter pub get
dart run build_runner build --delete-conflicting-outputs   # تحقق أن هذه الخطوة الجديدة تعمل فعلاً
dart analyze
flutter test
```

إن نجحت محلياً: ادفع commit/PR فعلياً لتشغيل `pos-app-baseline` على GitHub Actions حقيقي، وراقب النتيجة في تبويب Actions. **التوثيق يجب أن يكون من نتيجة Actions نفسها، وليس التشغيل المحلي فقط** (شرط صريح في الخطة الأصلية).

---

## 🔧 استكشاف الأخطاء — مشكلتان حقيقيتان اكتُشِفتا عند أول تشغيل فعلي (2026-08-16)

### المشكلة 1: `Bind for 0.0.0.0:5432 failed: port is already allocated`

**السبب:** شيء آخر على جهازك (تثبيت Postgres محلي، أو حاوية قديمة من مشروع آخر، أو تشغيل سابق لم يُنظَّف) يستخدم المنفذ 5432 فعلاً على المضيف.

**تشخيص:**
```powershell
netstat -ano | findstr :5432
# لاحظ الـ PID في العمود الأخير
tasklist /FI "PID eq <PID>"
docker ps -a   # تحقق أيضاً هل هي حاوية Docker قديمة (من مشروع آخر أو تشغيل سابق فاشل)
```

**الحل الأسرع (لا يحتاج تعديل ملفات):** أوقف العملية/الحاوية التي تحجز المنفذ، ثم:
```bash
docker-compose down
docker-compose up -d --build
```

**بديل إن كان المنفذ مطلوباً لشيء آخر لديك فعلاً:** غيّر المنفذ المنشور على المضيف فقط (الاتصال الداخلي بين core-api/ai-platform وPostgres يمر عبر اسم الخدمة `postgres:5432` داخل شبكة Docker، وليس عبر منفذ المضيف — تغييره هنا آمن تماماً ولا يكسر شيئاً):
```yaml
# docker-compose.yml → service postgres
ports: ["5433:5432"]   # بدل "5432:5432"
```
(لو احتجت الاتصال من أداة على جهازك مثل psql/DBeaver لاحقاً، استخدم `localhost:5433` بدل `5432`.)

**⚠️ مهم:** بسبب هذا الخطأ، `core-api` و`web` بقيتا بحالة `Created` فقط ولم تُشغَّلا فعلياً — كل أوامر `docker-compose exec core-api ...` بعدها ستفشل بـ`service "core-api" is not running` حتى تُحل هذه المشكلة أولاً ويُعاد `docker-compose up -d`.

---

### المشكلة 2: `ModuleNotFoundError: No module named 'models'` عند `alembic upgrade head`

**هذا خلل حقيقي في `Dockerfile.ai-platform`/`Dockerfile.core-api` — **تم إصلاحه في هذه الحزمة**، لا حاجة لأي إجراء يدوي منك سوى إعادة البناء:

```bash
docker-compose up -d --build
```

**السبب الجذري (للتوثيق):** الترتيب القديم كان:
```dockerfile
COPY apps/ai-platform/pyproject.toml .
RUN pip install -e ".[dev]" || true     # ← يُشغَّل قبل وجود الكود المصدري فعلياً!
COPY apps/ai-platform/ .
```
تثبيت `pip install -e` الحديث (PEP 660) يبني "finder" يربط كل حزمة بمكانها **وقت التثبيت فقط** — بما أن `models/`, `platform_core/`, إلخ لم تكن منسوخة بعد عند هذا السطر، اكتشف الأداة صفر حزم، فبقي أي استيراد عادي خارج تطبيق FastAPI نفسه (مثل `from models import ai_models` في `migrations/env.py`) يفشل. `uvicorn main:app` كان يعمل رغم ذلك فقط لأن uvicorn يُدخِل مجلد العمل الحالي إلى `sys.path` يدوياً عند تحميل app string — حيلة لا تنطبق على `alembic` أو أي console-script آخر (كان `core-api` سيقع في نفس الخلل بالضبط لولا أنه لم يُقلِع أصلاً بسبب المشكلة 1 أعلاه).

**الإصلاح المطبَّق في هذه الحزمة:** إعادة ترتيب الأسطر (نسخ الكود المصدري كاملاً قبل `pip install -e`) + `ENV PYTHONPATH=/app` كطبقة أمان إضافية في كلا الـDockerfile. `|| true` أُزيل أيضاً عمداً — كان يُخفي فشل هذا التثبيت بصمت، وهذا بالضبط سبب عدم اكتشاف الخلل مبكراً.

**لو كنت لا تريد إعادة بناء الصور الآن وتحتاج فقط تجاوزاً فورياً على الحاوية الحالية القديمة:**
```bash
docker-compose exec ai-platform python -m alembic upgrade head
docker-compose exec core-api python -m alembic upgrade head
```
(`python -m` يضيف مجلد العمل الحالي لـ`sys.path` تلقائياً، يلتف حول نفس المشكلة بدون تعديل أي ملف — لكن الأفضل هو `--build` أعلاه لأنه يُصلح المشكلة نهائياً لكل الأوامر القادمة، بما فيها `seed_demo_company.py`.)

---

### المشكلة 3: `ai-platform` alembic → `Connect call failed ('127.0.0.1', 5433)`

**سبب حقيقي (خلل فعلي، ليس بيئة المستخدم):** `docker-compose.yml` لم يكن يضبط `ALQAIM_AI_DATABASE_URL` لخدمة `ai-platform` إطلاقاً — فسقط على القيمة الافتراضية المكتوبة داخل `apps/ai-platform/platform_core/config.py`:
```python
database_url: str = "postgresql+asyncpg://alqaim_ai:alqaim_ai@localhost:5433/alqaim_ai"
```
`localhost` هنا تعني **الحاوية نفسها**، لا خدمة `postgres` — فيفشل الاتصال دائماً. أيضاً: قاعدة بيانات `ai-platform` مستقلة عمداً عن قاعدة `core-api` (تصميم مقصود، القسم 8.5) — أي أنه حتى لو صُحِّح العنوان، القاعدة `alqaim_ai` والمستخدم `alqaim_ai` غير موجودين أصلاً في حاوية Postgres الحالية (التي تحتوي فقط `alqaim`/`alqaim` الخاصة بـ`core-api`).

**تم إصلاحه في هذه الحزمة:** أُضيف `ALQAIM_AI_DATABASE_URL` في `docker-compose.yml` + سكربت `infra/docker/postgres-init/001_create_ai_platform_db.sql` ينشئ القاعدة تلقائياً على أي فوليوم Postgres **جديد**.

**⚠️ لكن فوليومك الحالي (`pgdata`) ليس جديداً** (core-api شغّل هجراته عليه بالفعل) — سكربتات `docker-entrypoint-initdb.d` لا تُنفَّذ إلا على فوليوم فارغ عند إنشائه لأول مرة. لذا نفّذ هذا يدوياً **مرة واحدة** على الفوليوم الحالي:
```bash
docker-compose exec postgres psql -U alqaim -d alqaim -c "CREATE USER alqaim_ai WITH PASSWORD 'alqaim_ai';"
docker-compose exec postgres psql -U alqaim -d alqaim -c "CREATE DATABASE alqaim_ai OWNER alqaim_ai;"
```
ثم إن كنت لم تُعِد بناء صورة `ai-platform` بعد بهذه الحزمة الجديدة (لتفعيل متغير البيئة الجديد)، مرّره يدوياً لمرة واحدة:
```bash
docker-compose exec -e ALQAIM_AI_DATABASE_URL=postgresql+asyncpg://alqaim_ai:alqaim_ai@postgres:5432/alqaim_ai ai-platform alembic upgrade head
```
أو ببساطة أعد التشغيل بالحزمة الجديدة (`docker-compose up -d`) ثم نفّذ الأمر العادي بلا `-e`.

---

### المشكلة 4: `core-api python scripts/seed_demo_company.py` → `No such file or directory`

**سبب حقيقي:** `scripts/` يعيش في جذر المستودع، خارج `apps/core-api/` — و`Dockerfile.core-api` كان ينسخ `apps/core-api/` فقط، فلم يُنسَخ `scripts/` إلى الحاوية إطلاقاً.

**تم إصلاحه في هذه الحزمة:** `COPY scripts/ ./scripts/` أُضيف إلى `Dockerfile.core-api`.

**تجاوز فوري بلا إعادة بناء (على الحاوية الحالية):**
```bash
docker-compose exec core-api mkdir -p /app/scripts
docker cp scripts/seed_demo_company.py alqaim_v2_v21_phase5_merged-core-api-1:/app/scripts/seed_demo_company.py
docker-compose exec core-api python scripts/seed_demo_company.py
```
(اسم الحاوية `alqaim_v2_v21_phase5_merged-core-api-1` كما ظهر في `docker ps -a` لديك — عدّله لو اختلف الاسم عندك.)

---

## ✅ عند اكتمال الثلاثة

حدِّث جدول `GATE-05` في `ALQAIM_V2_PHASE5_FINAL_CLOSURE_PLAN.md` (أو أضف قسماً جديداً في `STATUS_20_TASKS.md` بنفس منهجية القسم 22 الحالي) بالنتائج الفعلية. عند نجاح الأربعة بنود مجتمعة → `GATE-05` **PASS** → ابدأ `TASK-CI-05` (رفع Enforcement، إزالة `continue-on-error`) — مهمة تسلسلية بعضو واحد، آخر خطوة في المشروع كله.
