"""INumberingService — Port مُعلَن للاستهلاك من كل الوحدات الأخرى (contracts.md)."""
from typing import Protocol


class INumberingService(Protocol):
    async def next_number(self, *, company_id: str, document_type: str) -> str: ...
