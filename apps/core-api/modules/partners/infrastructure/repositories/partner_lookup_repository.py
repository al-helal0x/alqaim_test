"""تنفيذ IPartnerLookup (contracts.md §1) — نقطة الدخول الوحيدة المسموحة
للوحدات الأخرى للوصول لبيانات partners. ممنوع استيراد infrastructure هذا
مباشرة من أي module آخر غير partners نفسها — الاستيراد يكون عبر الـ Port فقط.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.partners.application.dto.partner_dto import PartnerDTO
from modules.partners.infrastructure.models.partner_models import Partner


class SqlPartnerLookup:
    """تنفيذ SQL لـ IPartnerLookup."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, *, company_id: str, partner_id: str) -> PartnerDTO | None:
        stmt = select(Partner).where(
            Partner.id == partner_id,
            Partner.company_id == company_id,
            Partner.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        partner = result.scalar_one_or_none()
        if partner is None:
            return None
        return PartnerDTO(
            id=str(partner.id),
            name=partner.name,
            type=partner.partner_type,
            tax_number=partner.tax_number,
            company_id=str(partner.company_id),
        )
