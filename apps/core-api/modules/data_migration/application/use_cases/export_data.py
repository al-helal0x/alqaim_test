from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.auth_middleware import TenantContext


class ExportDataUseCase:
    """التصدير الاحترافي (§5) — عام لأي كيان AlQaim، وليس خاصاً بالاستيراد.
    يُستدعى مثلاً من زر 'تصدير' في أي شاشة تقارير موجودة فعلياً، لا فقط بعد
    استيراد. TODO (TASK-MIG-06): تحديد مصدر rows فعلياً (repository الكيان
    المطلوب تصديره) ثم تمريرها إلى excel_exporter/pdf_exporter."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, entity_name: str, fmt: str) -> str:
        raise NotImplementedError
