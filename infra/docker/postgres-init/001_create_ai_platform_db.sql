-- يُشغَّل تلقائياً من postgres:16 image فقط عند إنشاء الفوليوم لأول مرة
-- (docker-entrypoint-initdb.d لا يعمل على فوليوم موجود مسبقاً فيه بيانات).
-- ينشئ قاعدة بيانات ai-platform المستقلة عن core-api (القسم 8.5 من الخطة).
-- لو كان الفوليوم لديك موجوداً مسبقاً (تشغيل سابق)، شغّل هذا يدوياً بدلاً
-- من ذلك (انظر RUNBOOK_GATE05_CLOSURE.md § استكشاف الأخطاء):
--   docker-compose exec postgres psql -U alqaim -d alqaim -f /docker-entrypoint-initdb.d/001_create_ai_platform_db.sql

CREATE USER alqaim_ai WITH PASSWORD 'alqaim_ai';
CREATE DATABASE alqaim_ai OWNER alqaim_ai;
