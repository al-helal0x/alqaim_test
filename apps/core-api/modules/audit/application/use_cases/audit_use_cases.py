"""Use Cases لموديول audit (سجل تدقيق شامل — العضو 12).

`RecordAuditLogUseCase` هو المستهلِك الفعلي لأحداث Event Bus — يُسجَّل في
main.py لكل الأحداث الستة المُعلَنة في docs/architecture/contracts.md §2 بلا
استثناء (عكس notifications الانتقائية). لا يعرف شيئاً عن الوحدة الناشرة، فقط
(event_name, payload) عاماً — نفس نمط الفصل المستخدم في
DispatchEventToWebhooksUseCase (العضو 13).
"""
from sqlalchemy.ext.asyncio import AsyncSession

from modules.audit.infrastructure.models.audit_models import AuditLogEntry
from modules.audit.infrastructure.repositories.audit_repository import AuditLogRepository
from platform_core.auth_middleware import TenantContext
from shared_kernel.db_base import utcnow
from shared_kernel.pagination import PageParams, paginate


class RecordAuditLogUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, event_name: str, payload: dict) -> None:
        company_id = payload.get("company_id")
        if not company_id:
            # نفس منطق integrations: حمولة بلا company_id لا يمكن نطاقها — تُهمَل بصمت.
            return
        self._session.add(
            AuditLogEntry(
                company_id=company_id,
                event_name=event_name,
                payload=payload,
                occurred_at=utcnow(),
            )
        )
        await self._session.commit()


class ListAuditLogsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, event_name: str | None, params: PageParams
    ) -> tuple[list[AuditLogEntry], int]:
        stmt = AuditLogRepository(self._session).query_for_company(
            company_id=ctx.company_id, event_name=event_name
        )
        return await paginate(self._session, stmt, AuditLogEntry, params)
