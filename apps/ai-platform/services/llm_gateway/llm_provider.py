"""ILLMProvider — القسم 7.10/7.12: نقطة وصول موحّدة لأي نموذج لغوي، بتنفيذ
يُختار عبر إعداد الشركة/النشر (Config) دون تغيير الكود المستهلك.

**حدود هذا التنفيذ:** AI Assistant/Recommendations هي أصلاً ميزات المرحلة
3-4 وليست MVP (القسم 7.13) — ولا يوجد مفتاح API فعلي أو نموذج ذاتي محمَّل
في بيئة التطوير هذه. `NullLLMProvider` يوثّق الواجهة النهائية ويفشل بوضوح
بدل الادّعاء بقدرة غير موجودة، تماماً كما يقتضي مبدأ "لا اقتراح بلا أساس
حقيقي" في القسم 17. تفعيل مزوّد فعلي (سحابي عبر مفتاح API، أو ذاتي عبر
نموذج مفتوح الأوزان) يتطلب فقط كتابة صف جديد يطبّق نفس ILLMProvider.
"""
from platform_core.config import get_settings


class LLMNotConfiguredError(Exception):
    pass


class NullLLMProvider:
    """التنفيذ الافتراضي عندما ALQAIM_AI_LLM_PROVIDER=null (القيمة الافتراضية)."""

    async def complete(self, prompt: str, *, context: dict | None = None) -> str:
        raise LLMNotConfiguredError(
            "لا يوجد مزوّد LLM مُفعَّل لهذه البيئة — اضبط ALQAIM_AI_LLM_PROVIDER "
            "إلى 'cloud' أو 'self_hosted' مع بيانات الاعتماد المطلوبة (المرحلة 4 — القسم 7.13)"
        )


def get_llm_provider():
    settings = get_settings()
    if settings.llm_provider == "null":
        return NullLLMProvider()
    raise NotImplementedError(
        f"مزوّد '{settings.llm_provider}' غير مُنفَّذ بعد في هذه النسخة من الحزمة "
        "— يُضاف كصف جديد يطبّق ILLMProvider عند الوصول للمرحلة 4"
    )
