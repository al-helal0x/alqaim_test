"""فجوة تكامل صغيرة تم سدّها هنا: `RecordDocumentPostingUseCase.execute()`
(العضو 6) هو التنفيذ الفعلي لمنطق IAccountingPort، لكن اسم الطريقة لا يطابق
حرفياً توقيع الـ Protocol المُعلَن في contracts.md (`record_document_posting`)
— فلا يمرّ فحص Structural Typing إن مرّرته مباشرة لأي متغيّر من نوع
IAccountingPort. هذا Adapter رقيق (Ports & Adapters قياسي) يلتف حوله فقط،
بلا تغيير أي منطق في journal_use_cases.py (ملك العضو 6 — لا يُعدَّل مباشرة).
"""
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.application.ports.accounting_port import (
    DocumentPostingRequest,
    JournalEntryRef,
)
from modules.accounting.application.use_cases.journal_use_cases import (
    RecordDocumentPostingUseCase,
)
from modules.tenancy.application.ports.numbering_port import INumberingService


class SqlAccountingPort:
    """تنفيذ IAccountingPort الفعلي المُحقَن في أي Module تشغيلي (sales/pos/...)."""

    def __init__(self, session: AsyncSession, numbering_service: INumberingService) -> None:
        self._use_case = RecordDocumentPostingUseCase(session, numbering_service)

    async def record_document_posting(
        self, document_dto: DocumentPostingRequest
    ) -> JournalEntryRef:
        return await self._use_case.execute(document_dto)
