from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.audit.infrastructure.models.audit_models import AuditLogEntry


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def query_for_company(self, *, company_id: str, event_name: str | None = None):
        """يُعيد `Select` غير مُنفَّذ بعد — تستهلكه `paginate()` من
        shared_kernel/pagination.py (لا تُعِد تنفيذ pagination يدوياً هنا)."""
        stmt = select(AuditLogEntry).where(AuditLogEntry.company_id == company_id)
        if event_name:
            stmt = stmt.where(AuditLogEntry.event_name == event_name)
        return stmt
