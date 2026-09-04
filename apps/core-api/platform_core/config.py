"""إعدادات النظام المركزية (Environment-based Settings).

Skeleton أولي — يُستكمل من العضو 1 خلال أول 2-3 أيام (المرحلة 0 / يوم 2-3).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AlQaim Core API"
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://alqaim:alqaim@localhost:5432/alqaim"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = "CHANGE_ME_IN_ENV"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "alqaim-documents"

    # مسار تخزين المرفقات محلياً على القرص (modules/documents، العضو 13).
    # الإعدادان أعلاه (object_storage_endpoint/bucket) كانا مُعرَّفين منذ
    # البداية دون أي مستهلك فعلي — هذا أول استهلاك حقيقي لمساحة "التخزين"،
    # لكن اخترنا القرص المحلي بدل MinIO/S3 الآن (بلا حزمة SDK بعد، ولا
    # اتصال شبكة متاح للتحقق من إضافتها بأمان) خلف نفس واجهة IFileStorage —
    # يمكن استبداله لاحقاً بتنفيذ MinIO حقيقي يستخدم الإعدادين أعلاه دون أي
    # تغيير في طبقة application/. راجع modules/documents/infrastructure/external/local_file_storage.py
    documents_storage_dir: str = "var/documents"

    # بوابة ai-platform (القسم 9.7) — العنوان الداخلي لخدمة ai-platform
    # المنفصلة (القسم 6.12). core-api يتصرّف كـ Proxy موثَّق (Auth/RBAC محلي)
    # بدل كشف منفذ 8100 مباشرة للمتصفح/التطبيقات.
    ai_platform_base_url: str = "http://localhost:8100"

    # مفتاح مصادقة خدمة-لخدمة (self-hosted، بلا OAuth كامل) — يسمح لـ
    # ai-platform بقراءة /internal/partners/known-suppliers و
    # /internal/catalog/known-products عبر ترويسة X-Service-Token، منفصل
    # تماماً عن مصادقة المستخدمين (JWT). راجع platform_core/auth_middleware.py
    # (get_service_context) و README_عضو-1.md §4 للعقد الكامل.
    # القيمة الافتراضية أدناه مقصودة كعلامة "غير مُهيَّأ" — get_service_context
    # يرفض أي طلب طالما لم تُستبدَل بقيمة حقيقية في .env.
    ai_platform_service_token: str = "CHANGE_ME_IN_ENV"

    class Config:
        env_file = ".env"
        env_prefix = "ALQAIM_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
