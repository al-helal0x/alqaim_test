"""عميل HTTP رقيق لبوابة ai-platform (القسم 9.7) — يُستهلَك حصراً من
presentation/routes/ai_proxy_router.py. لا منطق أعمال هنا، تمرير فقط.
"""
import httpx

from platform_core.config import get_settings


def get_ai_platform_client() -> httpx.AsyncClient:
    """عميل جديد لكل طلب (بدل عميل عام طويل العمر) — أبسط للاختبار
    (يمكن حقن base_url مختلف بسهولة) وكافٍ لحجم الحركة الحالي."""
    settings = get_settings()
    return httpx.AsyncClient(base_url=settings.ai_platform_base_url, timeout=30.0)
