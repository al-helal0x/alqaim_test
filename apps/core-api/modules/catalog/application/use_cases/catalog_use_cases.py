from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.application.dto.catalog_dto import (
    CategoryCreateRequest,
    PriceListCreateRequest,
    PriceListItemCreateRequest,
    ProductCreateRequest,
    ProductUpdateRequest,
    UomCreateRequest,
)
from modules.catalog.domain.rules import validate_price
from modules.catalog.infrastructure.models.catalog_models import (
    PriceList,
    PriceListItem,
    Product,
    ProductCategory,
    UnitOfMeasure,
)
from platform_core.auth_middleware import TenantContext
from shared_kernel.pagination import PageParams, paginate


class CreateCategoryUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: CategoryCreateRequest) -> ProductCategory:
        if request.parent_id is not None:
            await _get_owned(self._session, ProductCategory, ctx, request.parent_id, "التصنيف الأب")

        category = ProductCategory(
            company_id=ctx.company_id, name=request.name, parent_id=request.parent_id
        )
        self._session.add(category)
        await self._session.commit()
        await self._session.refresh(category)
        return category


class ListCategoriesUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext) -> list[ProductCategory]:
        stmt = select(ProductCategory).where(
            ProductCategory.company_id == ctx.company_id, ProductCategory.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class CreateUomUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: UomCreateRequest) -> UnitOfMeasure:
        uom = UnitOfMeasure(company_id=ctx.company_id, code=request.code, name=request.name)
        self._session.add(uom)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ValueError("رمز وحدة القياس مستخدم بالفعل في هذه الشركة") from exc
        await self._session.refresh(uom)
        return uom


class ListUomsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext) -> list[UnitOfMeasure]:
        stmt = select(UnitOfMeasure).where(
            UnitOfMeasure.company_id == ctx.company_id, UnitOfMeasure.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class CreateProductUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: ProductCreateRequest) -> Product:
        validate_price(request.sale_price)
        validate_price(request.purchase_price)

        # التحقق من عزل الشركة على المراجع الأجنبية (uom/category) — القسم 6.10
        await _get_owned(self._session, UnitOfMeasure, ctx, request.base_uom_id, "وحدة القياس")
        if request.category_id is not None:
            await _get_owned(self._session, ProductCategory, ctx, request.category_id, "التصنيف")

        product = Product(
            company_id=ctx.company_id,
            sku=request.sku,
            name=request.name,
            product_type=request.product_type.value,
            category_id=request.category_id,
            base_uom_id=request.base_uom_id,
            sale_price=request.sale_price,
            purchase_price=request.purchase_price,
            track_inventory=request.track_inventory,
        )
        self._session.add(product)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ValueError("رمز المنتج (SKU) مستخدم بالفعل في هذه الشركة") from exc
        await self._session.refresh(product)
        return product


class UpdateProductUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, product_id: str, request: ProductUpdateRequest
    ) -> Product:
        product = await _get_owned(self._session, Product, ctx, product_id, "المنتج")

        updates = request.model_dump(exclude_unset=True)
        if "sale_price" in updates:
            validate_price(updates["sale_price"])
        if "purchase_price" in updates:
            validate_price(updates["purchase_price"])
        if updates.get("category_id") is not None:
            await _get_owned(self._session, ProductCategory, ctx, updates["category_id"], "التصنيف")

        for field, value in updates.items():
            setattr(product, field, value)

        await self._session.commit()
        await self._session.refresh(product)
        return product


class GetProductUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, product_id: str) -> Product:
        return await _get_owned(self._session, Product, ctx, product_id, "المنتج")


class ListProductsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, *, search: str | None = None, category_id: str | None = None
    ) -> list[Product]:
        stmt = select(Product).where(
            Product.company_id == ctx.company_id, Product.deleted_at.is_(None)
        )
        if search:
            stmt = stmt.where(Product.name.ilike(f"%{search}%"))
        if category_id:
            stmt = stmt.where(Product.category_id == category_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ListProductsPageUseCase:
    """نسخة مرقّمة (Pagination) من ListProductsUseCase — القسم 9.3.
    مُستقلة عن ListProductsUseCase الحالية لتفادي كسر أي مستهلك داخلي يعتمد
    على شكلها الحالي (قائمة كاملة، بلا صفحات) — مثال: تصدير CSV يحتاج كل الصفوف.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        ctx: TenantContext,
        params: PageParams,
        *,
        search: str | None = None,
        category_id: str | None = None,
    ) -> tuple[list[Product], int]:
        stmt = select(Product).where(
            Product.company_id == ctx.company_id, Product.deleted_at.is_(None)
        )
        if search:
            stmt = stmt.where(Product.name.ilike(f"%{search}%"))
        if category_id:
            stmt = stmt.where(Product.category_id == category_id)
        return await paginate(self._session, stmt, Product, params)


class CreatePriceListUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: PriceListCreateRequest) -> PriceList:
        price_list = PriceList(
            company_id=ctx.company_id,
            name=request.name,
            currency=request.currency,
            is_default=request.is_default,
        )
        self._session.add(price_list)
        await self._session.commit()
        await self._session.refresh(price_list)
        return price_list


class AddPriceListItemUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, price_list_id: str, request: PriceListItemCreateRequest
    ) -> PriceListItem:
        validate_price(request.price)
        await _get_owned(self._session, PriceList, ctx, price_list_id, "قائمة الأسعار")
        await _get_owned(self._session, Product, ctx, request.product_id, "المنتج")

        item = PriceListItem(
            price_list_id=price_list_id, product_id=request.product_id, price=request.price
        )
        self._session.add(item)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ValueError("هذا المنتج موجود بالفعل في قائمة الأسعار") from exc
        await self._session.refresh(item)
        return item


async def _get_owned(session: AsyncSession, model, ctx: TenantContext, entity_id: str, label: str):
    """يفرض عزل الشركة على أي مرجع بين كيانات هذه الوحدة (القسم 6.10)."""
    stmt = select(model).where(model.id == entity_id, model.company_id == ctx.company_id)
    result = await session.execute(stmt)
    entity = result.scalar_one_or_none()
    if entity is None:
        raise ValueError(f"{label} غير موجود أو لا يعود لشركتك")
    return entity
