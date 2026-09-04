from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AlQaim AI Platform"
    environment: str = "development"

    # قاعدة بيانات مستقلة عن core-api (القسم 8.5) — تحمل نفس مبادئ 8.2
    database_url: str = "postgresql+asyncpg://alqaim_ai:alqaim_ai@localhost:5433/alqaim_ai"
    redis_url: str = "redis://localhost:6379/1"  # DB مختلف عن core-api على نفس Redis

    # OCR — القسم 7.12: PaddleOCR/Tesseract ذاتي كافتراضي، سحابي اختياري لاحقاً
    ocr_engine: str = "tesseract"  # tesseract | paddleocr | cloud
    ocr_languages: str = "ara+eng"

    # LLM — القسم 7.10/7.12: هجين حسب بيئة النشر (Config-driven, لا كود مختلف)
    llm_provider: str = "null"  # null | cloud | self_hosted
    llm_api_key: str | None = None

    # عتبات المطابقة (القسم 7.4) — تُضبط لاحقاً عبر Learning Engine (7.6)
    entity_match_auto_link_threshold: float = 0.92
    entity_match_suggest_threshold: float = 0.55

    # اتصال ai-platform → core-api (خدمة-لخدمة، TASK-AI-04 القسم 3.3، الخيار أ)
    # — عنوان داخل شبكة docker (اسم الخدمة core-api)، ليس PUBLIC_API_URL الذي
    # يراه المتصفح. التوكن مفتاح ثابت بسيط (self-hosted، لا OAuth كامل بعد)
    # يتحقق منه core-api على مسارات /internal/* فقط دون المساس بمصادقة
    # المستخدمين الحالية.
    core_api_base_url: str = "http://core-api:8000"
    ai_platform_service_token: str = "CHANGE_ME_IN_ENV"

    class Config:
        env_file = ".env"
        env_prefix = "ALQAIM_AI_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
