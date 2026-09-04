## بطاقة تسليم المهمة

- رقم المهمة: #5
- المسار: 🔐 Platform
- الفرع: task/05-auth-hardening
- مبني على commit: <hash آخر سحب من main — يُملأ عند فتح PR فعلي>

### الملفات/المجلدات التي تم إنشاؤها (جديدة)
- `apps/core-api/migrations/versions/identity_20260808_0003_auth_hardening_refresh_tokens.py` — هجرة جديدة: جدول `refresh_tokens` (hash فقط) + جدول `login_attempts`
- `apps/core-api/modules/identity/infrastructure/repositories/refresh_token_repository.py` — تخزين/بحث/إبطال refresh tokens عبر hash فقط
- `apps/core-api/modules/identity/infrastructure/repositories/login_attempt_repository.py` — تسجيل محاولات الدخول وحساب الفاشلة الأخيرة (بريد/IP)
- `apps/core-api/tests/integration/test_auth_hardening.py` — 7 اختبارات تكامل جديدة (تفصيل أدناه)

### الملفات/المجلدات التي تم تعديلها
- `apps/core-api/modules/identity/infrastructure/models/identity_models.py` — إضافة نموذجَي `RefreshToken` و`LoginAttempt`
- `apps/core-api/modules/identity/application/dto/identity_dto.py` — إضافة `LogoutRequest`
- `apps/core-api/modules/identity/application/use_cases/auth_use_cases.py` — تخزين refresh token كـ hash عند التسجيل/الدخول، Rotation عند `/auth/refresh`، `LogoutUseCase` جديد، `AccountLockedError` + منطق Rate Limiting/قفل الحساب داخل `LoginUseCase` (إزالة الدَين التقني الثلاثي المُسجَّل سابقاً في تعليق TODO أسفل الملف)
- `apps/core-api/modules/identity/presentation/routes/auth_router.py` — إضافة `POST /auth/logout` (204)، وتمرير IP الطلب لاستخدامه في Rate Limiting بـ `/auth/login`، وترجمة `AccountLockedError` إلى 429
- `apps/core-api/platform_core/security.py` — إضافة `hash_refresh_token()` (SHA-256، بحث مساواة حتمي عبر index)

### Migrations
- `identity_20260808_0003_auth_hardening_refresh_tokens.py` — `down_revision = wfna_20260808_0002` (Head وحيد بعد الدمج، تم التحقق آلياً). ينشئ:
  - `refresh_tokens(id, user_id, token_hash UNIQUE, expires_at, revoked_at, + audit columns)`
  - `login_attempts(id, email, ip_address, success, + audit columns)` مع فهارس على `email`, `ip_address`, `created_at`

### الاختبارات المضافة
- `apps/core-api/tests/integration/test_auth_hardening.py` (7 اختبارات، جميعها ناجحة):
  1. `test_refresh_token_is_stored_as_hash_only` — التحقق أن القيمة المخزَّنة hash فقط وتطابق `hash_refresh_token`
  2. `test_logout_revokes_refresh_token_and_refresh_then_fails` — Logout يُبطل التوكن فعلياً
  3. `test_logout_is_idempotent_for_unknown_token` — Logout لا يفشل على توكن غير موجود
  4. `test_refresh_rotates_token_and_old_one_becomes_unusable` — Rotation: القديم يُبطَل، الجديد صالح
  5. `test_login_locks_account_after_five_failed_attempts` — قفل الحساب بعد 5 محاولات فاشلة (حتى بكلمة مرور صحيحة لاحقاً)
  6. `test_login_rate_limits_by_ip_across_different_emails` — Rate Limiting بمعيار IP مستقل عن معيار البريد
  7. `test_failed_attempts_outside_window_do_not_count` — انزلاق نافذة الـ15 دقيقة يعمل صحيحاً

### التوثيق المحدَّث
- لا يوجد (لا تعديل على `contracts.md` — هذه المهمة لا تُنشئ عقداً بين وحدتين مختلفتين، فقط داخل `core-api`)

### اعتماديات هذه المهمة
- تعتمد على: لا شيء
- تُبنى عليها: مهمة 15 (تفعيل `/auth/refresh` في pos-app — تحتاج شكل `refresh_tokens` النهائي)، مهمة 20 (التدقيق الأمني — يراجع نتائج هذه المهمة)

### التحقق المحلي قبل التسليم
- [x] تشغيل الاختبارات محلياً وناجحة (7/7 جديدة + 13/13 مع bootstrap/rbac القائمة)
- [x] `ruff check` نظيف على كل ملف جديد/مُعدَّل من هذه المهمة تحديداً
- [x] سلسلة هجرات Alembic بها Head وحيد فقط (`identity_20260808_0003`) — تم التحقق آلياً
- [x] لا تعديل خارج المسارات المصرَّح بها في القسم 4.2 (وحدة identity + `platform_core/security.py`)
- [x] كل بند في عمود "المخرج" الخاص بالمهمة محقَّق فعلياً:
  - [x] جدول `refresh_tokens` + إبطال عند logout (hash فقط، لا نص صريح)
  - [x] Rate Limiting وقفل حساب على `/auth/login` (5 محاولات/15 دقيقة)
  - [x] اختبارات تكامل ووحدة

### ملاحظة مهمة لمسؤول الدمج
- CI الكامل (postgres حقيقي) **لم يُشغَّل هنا** — بيئة التطوير الحالية بلا خادم Postgres متصل، فقط SQLite (نفس نمط `tests/README.md`). كل اختبارات `tests/integration/` نجحت (74 ناجح + 4 متخطّى) باستثناء 6 اختبارات في `test_sales_and_pos.py` **غير متعلقة بهذه المهمة إطلاقاً** وتفشل بسبب محاولة اتصال حقيقي بـ `127.0.0.1:5432` غير متوفر في هذه البيئة تحديداً — يُرجى تأكيدها خضراء على CI الفعلي قبل الدمج.
