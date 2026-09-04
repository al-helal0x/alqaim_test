"""إعادة تصدير TenantContext من platform_core لتسهيل الاستيراد داخل الوحدات
دون أن تعتمد الوحدات على تفاصيل platform_core الداخلية مباشرة.
"""
from platform_core.auth_middleware import TenantContext  # noqa: F401
