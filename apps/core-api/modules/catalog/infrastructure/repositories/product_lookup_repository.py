"""تنفيذ IProductLookup (contracts.md §1) — نقطة الدخول الوحيدة المسموحة
للوحدات الأخرى للوصول لبيانات catalog. ممنوع استيراد infrastructure هذا
مباشرة من أي module آخر غير catalog نفسها — الاستيراد يكون عبر الـ Port فقط.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.application.dto.catalog_dto import ProductDTO
from modules.catalog.infrastructure.models.catalog_models import Product, UnitOfMeasure


class SqlProductLookup:
    """تنفيذ SQL لـ IProductLookup."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, *, company_id: str, product_id: str) -> ProductDTO | None:
        stmt = select(Product, UnitOfMeasure.code).join(
            UnitOfMeasure, UnitOfMeasure.id == Product.base_uom_id
        ).where(
            Product.id == product_id,
            Product.company_id == company_id,
            Product.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        product, uom_code = row
        return ProductDTO(
            id=str(product.id),
            sku=product.sku,
            name=product.name,
            uom=uom_code,
            is_active=product.is_active,
            company_id=str(product.company_id),
        )
