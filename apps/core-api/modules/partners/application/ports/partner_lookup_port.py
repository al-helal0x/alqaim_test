"""IPartnerLookup — Port مُعلَن للاستهلاك من sales/purchasing/payments (contracts.md §1).

قاعدة صارمة: الوحدات المستهلكة تستدعي هذا الـ Port فقط، ولا تستورد
`modules.partners.infrastructure` مباشرة أبداً (القسم 11.2).
"""
from typing import Protocol

from modules.partners.application.dto.partner_dto import PartnerDTO


class IPartnerLookup(Protocol):
    async def get(self, *, company_id: str, partner_id: str) -> PartnerDTO | None: ...
