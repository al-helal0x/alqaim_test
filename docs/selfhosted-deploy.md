# نشر Self-Hosted على سيرفر/VM نظيف تماماً

مرجع لمهمة #3 (تصليب Self-hosted واختباره على بيئة نظيفة). يفترض هذا الدليل
سيرفر Linux (Ubuntu 22.04/24.04) جديداً تماماً بلا أي تثبيت سابق للمشروع.

## 0. المتطلبات

- Docker Engine + Docker Compose v2 (`docker compose version` يجب أن يعمل).
- منفذان مفتوحان في جدار الحماية: `CORE_API_PORT` (افتراضي 8000) و`WEB_PORT`
  (افتراضي 3000). لا تحتاج فتح أي منفذ آخر — postgres/redis/minio/ai-platform
  داخلية فقط.
- Git.

## 1. سحب المشروع

```bash
git clone <رابط المستودع> alqaim-v2
cd alqaim-v2
```

## 2. إعداد متغيرات البيئة

```bash
cp .env.selfhosted.example .env.selfhosted
# ثم افتح .env.selfhosted وعدّل كل قيمة CHANGE_ME_* بقيمة حقيقية:
openssl rand -base64 24   # لاستخدامه في كلمات مرور postgres/postgres-ai/minio
openssl rand -hex 32      # لاستخدامه في JWT_SECRET_KEY
```

اضبط `PUBLIC_API_URL` على العنوان الذي سيستخدمه متصفح المستخدم فعلياً للوصول
لـ core-api (مثال: `http://<IP السيرفر>:8000`) — هذه القيمة تُخبَز داخل حزمة
الويب وقت البناء، فلا يمكن تغييرها لاحقاً دون إعادة بناء صورة `web`.

## 3. البناء والتشغيل

```bash
docker compose -f docker-compose.selfhosted.yml --env-file .env.selfhosted up -d --build
```

## 4. تشغيل الـ Migrations (خطوة يدوية حتى يُسلَّم `scripts/run_migrations.sh` — مهمة #2)

قواعد البيانات تُنشَأ فارغة؛ لا شيء يُشغِّل Alembic تلقائياً عند الإقلاع بعد.
شغّل الأمرين التاليين مرة واحدة بعد نجاح الخطوة السابقة:

```bash
docker compose -f docker-compose.selfhosted.yml --env-file .env.selfhosted \
  exec core-api alembic upgrade head

docker compose -f docker-compose.selfhosted.yml --env-file .env.selfhosted \
  exec ai-platform alembic upgrade head
```

> بمجرد تسليم مهمة #2، يفترض أن يحل `scripts/run_migrations.sh` محل هذه
> الخطوة اليدوية لكلتا الخدمتين.

## 5. التحقق

```bash
curl http://localhost:${CORE_API_PORT:-8000}/health   # {"status":"ok"}
# ai-platform ليس له منفذ مكشوف عمداً — تحقق منه عبر core-api كبروكسي، أو مؤقتاً:
docker compose -f docker-compose.selfhosted.yml --env-file .env.selfhosted \
  exec core-api curl -s http://ai-platform:8100/health
```

ثم افتح `http://<IP السيرفر>:${WEB_PORT:-3000}` في المتصفح وتحقق من ظهور شاشة
تسجيل الدخول/الإعداد الأولي وأن الطلبات فعلياً تصل core-api (تحقق من تبويب
Network في أدوات المطوّر أنها تذهب لعنوان `PUBLIC_API_URL` لا `localhost`).

## 6. إعادة التشغيل بعد إعادة إقلاع السيرفر

جميع الخدمات معرَّفة بـ `restart: unless-stopped` — يجب أن تُقلَع تلقائياً مع
Docker daemon دون أي تدخل يدوي. للتحقق:

```bash
sudo reboot
# بعد عودة السيرفر:
docker compose -f docker-compose.selfhosted.yml --env-file .env.selfhosted ps
```

## ملاحظات النطاق (مهم لأي عضو يراجع هذه المهمة)

- هذا الدليل مكتوب ليكون قابلاً للتنفيذ الحرفي على سيرفر نظيف، لكن التنفيذ
  الفعلي على VM حقيقي **لم يتم داخل بيئة العمل الحالية** (لا وصول Docker/شبكة
  خارجية متاح فيها لسحب صور postgres/redis/minio/node). التحقق الذي تم فعلياً:
  - صحة صياغة YAML لملف `docker-compose.selfhosted.yml` (لا أخطاء parsing).
  - تتبّع يدوي لكل متغيّر بيئة حتى مصدره في `platform_core/config.py`
    (core-api و ai-platform) للتأكد من تطابق أسماء `ALQAIM_*`/`ALQAIM_AI_*`
    مع `env_prefix` الفعلي في كل خدمة.
  - مطابقة كل مسار COPY في `Dockerfile.web`/`Dockerfile.core-api`/
    `Dockerfile.ai-platform` مع بنية المستودع الفعلية.
- **مطلوب فعلياً قبل إغلاق المهمة**: تنفيذ الخطوات 1-6 أعلاه حرفياً على
  VM/سيرفر جديد تماماً من عضو لديه وصول فعلي لبيئة Docker، وتسجيل النتيجة
  (نجاح/فشل + أي تعديل لزم) هنا أو في بطاقة تسليم الـ PR.
- فجوتان أُصلحتا هنا رغم كونهما خارج مسارات المهمة (§4.2) لأن معيار القبول
  ("تشغيل كامل على بيئة نظيفة") لا يتحقق بدونهما تقنياً: قاعدة بيانات
  `ai-platform` غير الموصولة أصلاً في `docker-compose.yml`، وعدم تمرير
  `NEXT_PUBLIC_API_URL` وقت بناء `web`. كلاهما مُوثَّق أعلى
  `docker-compose.selfhosted.yml` وفي بطاقة التسليم.
