"""IProductLookup — Port مُعلَن للاستهلاك من inventory/sales/purchasing/ai-platform
(contracts.md §1).

قاعدة صارمة: الوحدات المستهلكة تستدعي هذا الـ Port فقط، ولا تستورد
`modules.catalog.infrastructure` مباشرة أبداً (القسم 11.2).
"""
from typing import Protocol

from modules.catalog.application.dto.catalog_dto import ProductDTO


class IProductLookup(Protocol):
    async def get(self, *, company_id: str, product_id: str) -> ProductDTO | None: ...
